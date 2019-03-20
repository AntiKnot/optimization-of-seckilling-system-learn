# optimization-of-seckilling-system-learn

设计一个 throttle，尝试把登录状态心跳环搞进去。

基础的结构尝试用的Django REST framework 的throttle。    
throttle 可以实现单个scope user可以访问的频率，和不限user scope访问的频率。    
但是这种计算型的解决方案可能对服务器开销比较大，使用缓存环去解决性能上应该更好一些。    

用户的频率限制住了，下个feature要考虑"批量放行"的实现方法。和数据库如何回调出发继续放行的策略。
