# Aqara Studio for Home Assistant

将 **Aqara Studio** 中的设备通过 WebSocket 数据转出 API 同步到 Home Assistant，实现实时状态同步与设备控制。

## 功能特点

- ✅ **自动发现设备** — 启动时自动获取 Aqara Studio 中所有设备
- ✅ **实时状态同步** — 通过 WebSocket 订阅设备状态变化，无需轮询
- ✅ **双向控制** — 在 HA 中操作设备，指令实时下发到 Aqara Studio
- ✅ **自动重连** — WebSocket 断开后自动重连
- ✅ **设备增删事件** — Aqara Studio 中添加/移除设备，HA 自动同步
- ✅ **Token 刷新支持** — Access Token 有效期 7 天，支持手动刷新

## 支持的设备类型

| 设备类型 | HA 平台 | 支持的功能 |
|---------|---------|-----------|
| 灯 (Light) | `light` | 开关、亮度、色温、彩光 |
| 开关 (Switch) | `switch` | 开关 |
| 插座 (Outlet) | `switch` | 开关、功率、电压、电量 |
| 门锁 (DoorLock) | `lock` | 开关锁 |
| 窗帘/推窗器 (Pusher) | `cover` | 开/关/停/设定位置 |
| 空调/温控器 (AirConditioner/Thermostat) | `climate` | 开关、温度设定、模式、风速 |
| 风扇 (Fan) | `fan` | 开关、风速 |
| 音箱 (Speaker) | `media_player` | 开关、音量、静音 |
| 温湿度传感器 | `sensor` | 温度、湿度 |
| 光照传感器 | `sensor` | 光照度 |
| 气压传感器 | `sensor` | 气压 |
| CO₂传感器 | `sensor` | CO₂浓度 |
| PM2.5/PM10 传感器 | `sensor` | 颗粒物浓度 |
| 电气参数传感器 | `sensor` | 功率、电压、电流、累计电量 |
| 人体传感器 | `binary_sensor` | 移动侦测 |
| 人体存在传感器 | `binary_sensor` | 存在状态 |
| 门窗传感器 | `binary_sensor` | 门/窗开关 |
| 水浸传感器 | `binary_sensor` | 漏水侦测 |
| 烟雾报警器 | `binary_sensor` | 烟雾检测 |
| 电池传感器 | `sensor` | 电量百分比 |

## 安装方式

### 通过 HACS 安装（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. HACS → 集成 → 右上角菜单 → 自定义存储库
3. 填入 `https://github.com/9072208332qq.com/aqara-studio-ha`，类别选择"集成"
4. 搜索并安装 "Aqara Studio"
5. 重启 Home Assistant

### 手动安装

1. 下载最新 [Release](https://github.com/9072208332qq.com/aqara-studio-ha/releases)
2. 解压后将 `custom_components/aqara_studio` 文件夹复制到 HA 配置目录下的 `custom_components/`
3. 重启 Home Assistant

## 配置

### 前置条件

1. 登录 **Aqara Studio**（确保与 HA 在同一局域网或可互通网络）
2. 左侧侧边栏 → **开发者**
3. 找到 **数据转出 API** 区域
4. 记录 **本机 IP 地址**
5. 启用数据转出 API，点击复制 **Access Token**
6. （可选）开启 [远程访问](https://docs.aqara.com/zh/docs/aqara-studio/remote-access) 功能以支持外网访问

### 添加集成

1. HA → 设置 → 设备与服务 → 添加集成
2. 搜索 "Aqara Studio"
3. 填写：
   - **主机地址**: Aqara Studio 的 IP（或远程访问域名）
   - **端口**: 默认 443（HTTP 则为 80）
   - **Access Token**: 从 Studio 复制的 Token
4. 点击提交，等待连接测试完成

## Token 刷新

Access Token 有效期为 **7 天**，到期后需要刷新：

**方法一**：通过 Aqara Studio 界面手动刷新
- Studio → 开发者 → 数据转出 API → 点击"刷新 Token"
- 重新进入 HA 的集成配置更新 Token

**方法二**：通过 API 自动刷新（需要集成 Refresh Token）
- 使用 API `/open/api/v1/auth/refresh-token` 自动获取新 Token
- 更新 ConfigEntry 中的 Token

## 技术架构

```
┌──────────────────────┐      WebSocket       ┌──────────────────────┐
│   Aqara Studio       │ ◄──────────────────►  │  Home Assistant      │
│                      │   (JSON messages)     │                      │
│  ┌────────────────┐  │                       │  custom_components/  │
│  │ Zigbee/Matter  │  │                       │   aqara_studio/     │
│  │ 设备           │  │                       │                      │
│  └────────────────┘  │                       │  ├─ websocket_client │
│                      │                       │  ├─ coordinator      │
│                      │                       │  ├─ device_mapper   │
│                      │                       │  ├─ light/switch/.. │
│                      │                       │  └─ entity          │
└──────────────────────┘                       └──────────────────────┘
```

## API 协议

本集成基于 [Aqara Studio 数据转出 API v1](https://docs.aqara.com/zh/docs/aqara-studio/api-references/data-export-api-v1)，通过 WebSocket 与 Aqara Studio 通信。

核心接口：
- `GetAllDeviceInfoRequest` — 获取设备列表
- `GetDevicesRequest` — 获取设备 spec 配置
- `GetTraitValueRequest` — 读取 trait 值
- `ExecuteTraitRequest` — 控制设备
- `SubscribeAllRequest` — 订阅所有设备变化
- `TraitValueUpdate`（推送）— 设备值变化实时通知
- `objectEvent`（推送）— 设备添加/移除/上下线通知

## 开发

```bash
# 克隆
git clone https://github.com/9072208332qq.com/aqara-studio-ha.git

# 推荐使用 devcontainer 或直接将 custom_components/ 链接到 HA
ln -s $(pwd)/custom_components/aqara_studio /path/to/ha/config/custom_components/aqara_studio
```

## License

Apache-2.0
