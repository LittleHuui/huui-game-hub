# WebSocket 与认证接入

HTTP 使用 Access Token，WebSocket 使用由该 Token 签发的 Redis 单次 Realtime Ticket。平台只提供 `/ws/game-hub/realtime` 一条实时通道。

## 连接流程

1. 调用 `POST /auth/login`，取得 `accessToken`。
2. 为所有受保护 HTTP 请求设置 `Authorization: Bearer <accessToken>`。
3. 使用该 HTTP 认证调用 `POST /auth/realtime-ticket`，取得短时有效的 `ticket` 和 `expiresAt`。
4. 建立 `ws(s)://{host}/ws/game-hub/realtime?ticket=<ticket>`。
5. 每次首次连接、重连和重试都申请新 Ticket；Ticket 被消费后不能再次使用，也不能缓存连接 URL。

Ticket 的 Redis 记录由原子读取并删除操作消费。缺失、无效或已消费 Ticket 以 close code `1008` 拒绝连接；握手时认证上下文已过期以 `4003` 关闭连接。当前尚未保留原 Access Token 到期边界，也未在连接期间主动关闭或重认证，握手检查不保证连接持续符合 Access Token 的有效期。

浏览器 WebSocket 握手不携带 `Authorization` Header。Access Token 只用于 HTTP 认证和申请 Ticket；`ticket` 是 WebSocket 握手的唯一认证参数。客户端不得提交用户身份查询参数或自定义身份 Header。

## 多进程连接协调

Redis 以带有效期的单连接记录保存 `serviceId` 到当前节点和连接 ID 的原子登记，浏览器 `online.ping` 刷新其有效期。新的连接会替换该登记，并通过 Redis 频道通知持有原连接的节点关闭连接。定向消息按登记路由到持有目标连接的节点；广播由每个节点向其本地有效连接投递。进程内连接表只保存本节点 WebSocket 对象，不作为跨进程连接事实。

## 消息 Envelope

```json
{
  "type": "online.ping",
  "requestId": "uuid",
  "payload": {},
  "timestamp": 1710000000000
}
```

## 边界

- `app/core/websocket` 仅处理传输、连接生命周期、消息 envelope 和分发。
- `app/realtime` 与模块服务处理 Room、Presence、邀请和 GameView 推送。
- 实时业务使用握手认证得到的 `AuthenticatedUser`，不信任消息 payload 中的用户身份字段。
- 收到 `gameViewUpdated` 后按 `version` 顺序应用；存在版本缺口时取消动画队列并通过 `GET /rooms/{roomId}/view` 取得权威快照。
