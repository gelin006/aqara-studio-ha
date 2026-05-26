## Aqara Studio for Home Assistant

将 Aqara Studio 中的设备通过 WebSocket 数据转出 API 同步到 Home Assistant，实现实时状态同步与设备控制。

### ✨ v0.2.0 更新内容

- 🐛 **修复状态回弹问题** — 新增 pending state 机制，控制指令后立即乐观更新状态，忽略旧状态推送，不再出现"关闭后重新打开"的闪烁
- 🎨 **新增图标支持** — 集成 Logo、各类型设备（灯、开关、传感器、窗帘、门锁、空调、风扇、音箱等）均有专属图标，并根据状态动态切换（如灯开关、门开闭）
- 🔄 **支持 HACS 升级** — 已安装的用户可直接在 HACS 中检查更新

### 支持的设备类型

| 设备 | 图标 |
|------|------|
| 💡 灯 | `lightbulb-on` / `lightbulb-off-outline` |
| 🔌 开关/插座 | `power-socket-us` / `power-socket-off` |
| 🔒 门锁 | `lock` / `lock-open-variant` |
| 🪟 窗帘 | `curtains` / `curtains-closed` |
| 🌡️ 空调/温控 | `snowflake` / `fire` / `thermostat-off` |
| 🌀 风扇 | `fan` / `fan-off` |
| 🔈 音箱 | `speaker-play` / `speaker-pause` / `speaker-off` |
| 🌡️ 温度传感器 | `thermometer` |
| 💧 湿度传感器 | `water-percent` |
| ☀️ 光照传感器 | `brightness-5` |
| 🧪 CO₂传感器 | `molecule-co2` |
| 🏃 人体传感器 | `motion-sensor` |
| 🚪 门窗传感器 | `door-open` / `door-closed` |
| 💦 水浸传感器 | `water-alert` |
| 🔥 烟雾报警器 | `smoke-detector-alert` |
| 📊 电气参数 | `flash-outline` / `sine-wave` |

### 安装

HACS → 自定义存储库 → 添加 `https://github.com/gelin006/aqara-studio-ha`
