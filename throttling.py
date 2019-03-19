import time

import redis


class ImproperlyConfigured(Exception):
    pass


# cache
class Cache(object):
    _conn = None

    @classmethod
    def get_connection_pool(cls):
        if cls._conn is None:
            cls._conn = redis.ConnectionPool(host="127.0.0.1", port=6379, db=1)

    def get_redis_db(self):
        conn = redis.Redis(connection_pool=self.get_connection_pool())
        return conn


default_cache = Cache().get_redis_db()


# base throttle
class BaseThrottle(object):
    def allow_request(self, request, view):
        raise NotImplementedError('.allow_request() must be overridden')

    def get_ident(self, request):
        """
        Identify the machine making the request by parsing HTTP_X_FORWARDED_FOR
        if present and number of proxies is > 0. If not use all of
        HTTP_X_FORWARDED_FOR if it is available, if not use REMOTE_ADDR.
        """
        # xff = request.META.get('HTTP_X_FORWARDED_FOR')
        xff = 'HTTP_X_FORWARDED_FOR'
        # remote_addr = request.META.get('REMOTE_ADDR')
        remote_addr = 'REMOTE_ADDR'
        num_proxies = 1
        if num_proxies is not None:
            if num_proxies == 0 or xff is None:
                return remote_addr
            addrs = xff.split(',')
            client_addr = addrs[-min(num_proxies, len(addrs))]
            return client_addr.strip()

        return ''.join(xff.split()) if xff else remote_addr

    def wait(self):
        return None


default_rates = {}


# request/seconds
class SimpleRateThrottle(BaseThrottle):
    cache = default_cache
    timer = time.time
    cache_format = 'throttle_%(scope)s_%(ident)s'
    scope = None
    THROTTLE_RATES = default_rates

    def __init__(self):
        if not getattr(self, 'rate', None):
            self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

    def get_cache_key(self, request, view):
        raise NotImplementedError('.get_cache_key() must be overridden')

    def get_rate(self):
        if not getattr(self, 'scope', None):
            msg = f"you must set either `.scope` or `.rate` for {self.__class__.__name__} throttle"
            raise ImproperlyConfigured(msg)

        try:
            return self.THROTTLE_RATES[self.scope]
        except KeyError:
            msg = f"No default throttle rate set for {self.__class__.__name__} scope"
            raise ImproperlyConfigured(msg)

    @staticmethod
    def parse_rate(rate):
        if rate is None:
            return None, None
        num, period = rate.split('/')
        num_requests = int(num)
        duration = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[period[0]]
        return num_requests, duration

    def allow_request(self, request, view):
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.history = self.cache.get(self.key)
        if not self.history:
            self.history = []
        self.now = self.timer()

        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        return self.throttle_success()

    def throttle_success(self):
        self.history.insert(0, self.now)
        self.cache.set(self.key, self.history, self.duration)
        return True

    # in base class,use @staticmethod Implemented may cause warning, if your overridden.
    def throttle_failure(self):
        return False

    def wait(self):
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
        else:
            remaining_duration = self.duration
        available_requests = self.num_requests - len(self.history) + 1
        if available_requests <= 0:
            return None
        return remaining_duration / float(available_requests)


class UserRateThrottle(SimpleRateThrottle):
    scope = 'user'
    THROTTLE_RATES = {}

    def get_cache_key(self, request, view):
        if request.user.id_authenticated:
            # ident = request.user.pk
            ident = request.uid
        else:
            ident = self.get_ident(request)

        return self.cache_format % {'scope': self.scope, 'ident': ident}


class BuyRequest(object):
    def __init__(self, uid, gid, oid, res=0):  # 0 wait; 1 success; -1 error;
        self.uid = uid
        self.gid = gid
        self.oid = oid
        self.res = res


class BaseView(object):
    def __init__(self, request):
        self.request = request

    throttling_classes = []


# fake view
class BuyView(object):
    cache = 'default_cache'

    def buy(self, request):
        pass
