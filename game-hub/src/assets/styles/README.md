# 前端样式与公共呈现组件

`src/assets/app.css` 是唯一 CSS 入口。它先载入公共基础与游戏域基础，再按统一断点加载布局：

| 层 | 职责 | 生效范围 |
| --- | --- | --- |
| `assets/styles/base/` | 设计变量、字体、控件、导航、弹层、公共房间 | 全部设备 |
| `assets/styles/web/` | Web 布局 | 601px 及以上 |
| `assets/styles/web/compact.css` | 窄 Web 布局 | 601–1040px |
| `assets/styles/mobile/` | 手机导航菜单、底部弹层、触控布局与安全区 | 600px 及以下 |
| `game-templates/*/styles/` | 单人/回合制多人域的同名四层聚合 | 由中央入口调度 |

页面与组件不再自行导入 CSS 或维护独立媒体断点。游戏专属颜色、棋盘和牌面样式放在相应游戏目录，由域聚合层引用。新增样式须使用组件根命名空间；不使用 `.avatar`、`.controls`、`.panel` 等泛类跨域覆盖。

公共组件：

- `components/ui/AppIcon.vue` 使用本地 Phosphor 图标，许可保留在 `assets/icons/LICENSE.txt`。
- `AppPageHeader.vue` 统一紧凑标题、状态和操作插槽。
- `AppMenu.vue` 接收 `items` 并发出 `select(id)`；桌面为定位菜单，手机为底部菜单。菜单挂载到 body，支持方向键、Esc、焦点恢复和外点关闭。
- `AppModal.vue` 保留原有 visible/closable/maskClosable API；统一手机底部弹层、滚动、焦点圈定和强制回应语义。
- 公共 `GameSelectControl`、`GameNumberInput`、radio/switch 与动作按钮保留原事件数据形状。
- `components/game-hub/room/` 为三款在线游戏共用。房间列表按真实筛选数组做客户端分页，页大小来自 CSS 变量；全量刷新仍使用原服务。等待页权限仍由原 room/currentPlayerId/rule 计算。
- 多人对局复用 `TurnPlayerPanel`、`TurnCountdown`、`TurnActionBar` 和 `SelectableItemHand`。鼠标保持松手 XOR 多选，触控轻触选择、原生横滑；输入层不计算游戏规则。

权威数据边界不变：HTTP、WebSocket、stores、reducers、房间/游戏服务与规则 composables 仍提供状态和可用动作。页面只展示这些数据并调用原动作。原型中的模拟对手、计时器、结算或场景控制不进入产品。
