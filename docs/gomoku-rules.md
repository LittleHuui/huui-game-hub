# 五子棋规则与动作边界

动作包括 PLACE_STONE、REQUEST_UNDO、ACCEPT_UNDO、REJECT_UNDO、RESIGN。Resolver 输出归一 payload；Executor 直接校验回合、坐标、目标 move/request 和当前状态，不重新枚举棋盘，也不使用 actionId 替代领域验证。

棋盘固定为 15×15，先连成五子者获胜，胜负由 GomokuWinRule 判断。回合时间与悔棋请求有效时间均由服务端规则配置，默认 30 秒，允许范围为 10–120 秒；前端使用服务端配置，不另设悔棋等待时间默认值。
