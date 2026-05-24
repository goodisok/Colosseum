# Colosseum — 机器人自主系统仿真平台

[AirSim](https://github.com/microsoft/AirSim) 的社区延续版本

[![Ubuntu Build](https://github.com/CodexLabsLLC/Colosseum/actions/workflows/test_ubuntu.yml/badge.svg)](https://github.com/CodexLabsLLC/Colosseum/actions/workflows/test_ubuntu.yml)
[![MacOS Build](https://github.com/CodexLabsLLC/Colosseum/actions/workflows/test_macos.yml/badge.svg)](https://github.com/CodexLabsLLC/Colosseum/actions/workflows/test_macos.yml)
[![Windows Build](https://github.com/CodexLabsLLC/Colosseum/actions/workflows/test_windows.yml/badge.svg)](https://github.com/CodexLabsLLC/Colosseum/actions/workflows/test_windows.yml)

[![](https://dcbadge.vercel.app/api/server/y9ZJKKKn8J)](https://discord.gg/y9ZJKKKn8J)

## 项目简介

**Colosseum** 是一个面向机器人与自主系统的**高保真仿真平台**，基于 [Unreal Engine](https://www.unrealengine.com/) 构建（另有实验性的 [Unity](https://unity3d.com/) 支持）。它是微软 [AirSim](https://github.com/microsoft/AirSim) 在 2022 年 7 月停止维护后的社区延续版本，由 [CodexLabsLLC](https://github.com/CodexLabsLLC/Colosseum) 维护，目标是构建更完善的仿真平台。

Colosseum 以 Unreal 插件形式开发，可直接嵌入任意 Unreal 环境；同时也提供实验性的 Unity 插件。项目开源、跨平台，支持软件在环（SITL）与硬件在环（HIL）仿真，可与 PX4、ArduPilot 等主流飞控联调。

### 核心能力

| 能力 | 说明 |
|------|------|
| **软件在环 (SITL)** | 与 PX4、ArduPilot 等飞控固件联调 |
| **硬件在环 (HIL)** | 与 PX4 进行物理级联调 |
| **多平台** | Windows / Linux / macOS（macOS 为实验性） |
| **多引擎** | Unreal 插件为主，Unity 为实验分支 |
| **开放 API** | Python、C++ 等语言可编程控制 |

典型应用场景包括：无人机算法验证、计算机视觉、强化学习、多机协同、传感器仿真等。

## 技术架构

整体采用**引擎无关核心 + 引擎插件**的分层设计：

```
┌─────────────────────────────────────────────────────────┐
│  客户端 / 上层应用                                        │
│  PythonClient · ROS / ROS2 · HelloDrone / DroneShell    │
└──────────────────────────┬──────────────────────────────┘
                           │ RPC API
┌──────────────────────────▼──────────────────────────────┐
│  AirLib 核心库（C++，引擎无关）                           │
│  物理引擎 · 传感器模型 · 车辆模型 · API 层                │
└──────────────────────────┬──────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  Unreal Plugin      Unity Plugin       MavLinkCom
  （渲染/场景）        （实验性）          （飞控通信）
        │                                     │
        └────────────── PX4 / ArduPilot / SimpleFlight
```

### 主要模块

| 目录 | 作用 |
|------|------|
| **`AirLib/`** | 核心 C++ 库：物理引擎、传感器（IMU/GPS/气压计/磁力计/激光雷达/距离传感器）、车辆模型、RPC API |
| **`Unreal/Plugins/AirSim/`** | Unreal 插件（目录名保留 AirSim 历史命名），负责渲染、场景、相机、Lidar 等 |
| **`Unity/`** | Unity 版实验性集成 |
| **`MavLinkCom/`** | MAVLink 通信库，用于与 PX4 等飞控交互 |
| **`PythonClient/`** | Python API 与示例（`pip install airsim`） |
| **`ros/`、`ros2/`** | ROS / ROS2 集成包 |
| **`HelloDrone/`、`HelloCar/`、`DroneShell/`** | C++ 入门示例 |
| **`GazeboDrone/`** | Gazebo 相关集成 |
| **`LogViewer/`** | 日志查看工具 |
| **`docs/`** | 完整文档（MkDocs） |
| **`ExternalRepositories/`** | 外部依赖（如 Eigen 数学库） |

## 支持的仿真对象

- **Multirotor（多旋翼）**：四旋翼、六旋翼等，支持 SimpleFlight / PX4 / ArduPilot
- **Car（地面车辆）**：带相机、GPS 等
- **ComputerVision 模式**：无物理车辆，仅用于视觉/感知算法

### 传感器

相机、Barometer、IMU、GPS、Magnetometer、Distance Sensor、Lidar 等，通过 `settings.json` 配置。详见 [传感器文档](docs/sensors.md)。

## 快速开始

### Python 示例

```python
import airsim

client = airsim.CarClient()
client.confirmConnection()
client.enableApiControl(True)
```

更多示例见 `PythonClient/` 目录，完整 API 说明见 [docs/apis.md](docs/apis.md)。

### 典型使用流程

1. 编译 Unreal 插件并启动仿真环境（如 Blocks 示例场景）
2. 通过 `settings.json` 配置仿真模式、车辆、传感器
3. 用 Python / C++ / ROS 连接仿真器并调用 API

## 环境要求

### 重要说明

主分支现已使用 **Unreal Engine 5.03 及以上**版本。如需使用 UE 4.27，请切换到 `ue4.27` 分支。

### Unreal Engine 版本

本仓库 **main 分支仅支持 Unreal Engine 5.6**。其他版本请查看对应分支。

### 支持的操作系统

#### Windows

- Windows 10（最新版）

#### Linux

- Ubuntu 20.04（使用 `ubuntu-20.04` 分支）
- Ubuntu 22.04
- Ubuntu 24.04

> **注意**：由于 Vulkan 支持问题，Ubuntu 22.04 目前尚未完全支持。如需在 22.04 上使用 Colosseum，强烈建议使用 Docker。

#### macOS（实验性）

- macOS Ventura (14)
- macOS Monterey (13)

> **注意**：macOS 支持仍处于高度实验阶段，未来版本可能移除。Apple 持续变更构建工具链，对第三方开发者支持有限。

## 与 AirSim 的关系

Colosseum 在 AirSim 基础上继续演进，代码结构与 API 大体兼容，但进行了品牌与维护层面的迁移（如 `ColosseumSettings.hpp`、文档中的 Colosseum 命名）。部分历史目录/包名仍保留 `AirSim`（如 Unreal 插件路径、`airsim` Python 包名），属于渐进式重命名过程中的遗留。

## 文档

完整文档请访问：[https://codexlabsllc.github.io/Colosseum/](https://codexlabsllc.github.io/Colosseum/)

本地文档目录见 [`docs/`](docs/)，包含编译指南、PX4 联调、API 参考等。

## 加入社区

欢迎加入 Discord 社区参与讨论：[Colosseum Robotics Discord](https://discord.gg/y9ZJKKKn8J)

## 许可证

本项目采用 [MIT License](LICENSE) 发布。
