# 配置方法

## 服务端

第一层容器：

```bash
mm-link --downlink-queue=droptail --downlink-queue-args=bytes=120000 ./run/traces/1.0.trace ./run/traces/1.0.trace
```

然后在容器内配置转发：

```bash
sudo iptables -t nat -A PREROUTING -j DNAT --to-destination 100.64.0.4
```

第二层容器：

```bash
mm-delay 20
```

继续嵌套依此类推

