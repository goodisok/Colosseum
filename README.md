# Colosseum — 机器人自主系统仿真平台

[AirSim](https://github.com/microsoft/AirSim) 的社区延续版本

[![](https://dcbadge.vercel.app/api/server/y9ZJKKKn8J)](https://discord.gg/y9ZJKKKn8J)

## 项目简介

**Colosseum** 是一个面向机器人与自主系统的**高保真仿真平台**，基于 [Unreal Engine](https://www.unrealengine.com/) 构建。它是微软 [AirSim](https://github.com/microsoft/AirSim) 在 2022 年 7 月停止维护后的社区延续版本，由 [CodexLabsLLC](https://github.com/CodexLabsLLC/Colosseum) 维护。

本分支（`feature/jpeg-geomag-px4`）以 Unreal 插件形式集成于示例工程 **`Unreal/Environments/BlocksV2`**，提供 Python / C++ RPC 客户端控制仿真器。

### 本分支已验证环境

以下内容为**本分支实际跑通并测试通过**的配置，README 仅记录已验证项：

| 项目 | 已验证配置 |
|------|------------|
| **操作系统** | **Windows 11** x64 |
| **Unreal Engine** | **UE 5.7.x**（UE 5.7.4） |
| **示例工程** | `BlocksV2` |
| **仿真模式** | SimpleFlight 多旋翼 |
| **相机** | 1080p Scene / Segmentation |
| **图像接口** | `simGetImages`（JPEG）、`simGetImagesEncoded`（NVENC H.264/HEVC） |
| **GPU** | NVIDIA（支持 NVENC，如 RTX 4090） |
| **客户端** | Python、`HelloDrone` 同类 C++ RPC |

> 本分支**尚未**在 macOS、Ubuntu / 其他 Linux 发行版上完成验证；请勿将下文能力外推到未列出的平台。

### 核心能力（本分支已验证）

| 能力 | 说明 |
|------|------|
| **SimpleFlight 多旋翼** | 起飞 / 悬停 / 移动 / 降落 / 传感器读取 |
| **相机 JPEG 抓帧** | `simGetImages`，1080p 约 26–30 FPS |
| **相机 NVENC 编码** | `simGetImagesEncoded`，1080p Scene 约 37–44 FPS |
| **开放 API** | Python、C++ RPC（同一套 `simGetImagesEncoded` 接口） |

典型应用场景：无人机视觉算法验证、高帧率与低带宽的相机管线测试。

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│  客户端                                                   │
│  PythonClient · HelloDrone（C++ RPC）                    │
└──────────────────────────┬──────────────────────────────┘
                           │ RPC API
┌──────────────────────────▼──────────────────────────────┐
│  AirLib 核心库（C++）                                      │
│  车辆模型 · 传感器 · RPC 客户端/服务端                      │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Unreal Plugin（BlocksV2/Plugins/AirSim）                │
│  渲染 · SceneCapture · NVENC 编码 · SimpleFlight         │
└─────────────────────────────────────────────────────────┘
```

### 主要模块（本分支相关）

| 目录 | 作用 |
|------|------|
| **`AirLib/`** | 核心 C++ 库与 RPC API（含 `EncodedImageCaptureBase`） |
| **`Unreal/Environments/BlocksV2/`** | 本分支使用的 UE 5.7 示例工程 |
| **`Unreal/Plugins/AirSim/`** | Unreal 插件源码（BlocksV2 内为实际编译副本） |
| **`PythonClient/`** | Python API 与验证脚本 |
| **`HelloDrone/`** | C++ RPC 入门示例 |
| **`scripts/settings/`** | 测试用 `settings.json`（如 `multirotor_1080p_fps.json`） |

## 快速开始

### Python 示例

```python
import airsim

client = airsim.MultirotorClient()
client.confirmConnection()
client.enableApiControl(True, "SimpleFlight")
```

更多示例见 `PythonClient/multirotor/`，RPC 说明见 [docs/apis.md](docs/apis.md)。

### GPU 编码相机 API（NVENC）

在原有 `simGetImages`（JPEG/PNG/原始像素）之外，本分支新增 **`simGetImagesEncoded`** RPC，在 **Windows + NVIDIA GPU** 上将 SceneCapture 帧编码为 H.264 / HEVC NAL 码流。原有 `simGetImages` 保持不变。

**平台要求**：Windows 11 x64、支持 NVENC 的 NVIDIA 显卡；编码在独立 D3D11 设备上运行，与 UE 渲染 RHI 隔离。

#### RPC 接口

C++ 与 Python 调用同一 RPC，方法名均为 `simGetImagesEncoded`：

| 语言 | 客户端类 | 方法签名 |
|------|----------|----------|
| **C++** | `RpcLibClientBase` / `MultirotorRpcLibClient` | `vector<EncodedImageCaptureBase::EncodedImageResponse> simGetImagesEncoded(vector<EncodedImageCaptureBase::EncodedImageRequest> request, const string& vehicle_name = "", bool external = false)` |
| **Python** | `VehicleClient` / `MultirotorClient` | `simGetImagesEncoded(requests, vehicle_name='', external=False)` |

类型定义：

- C++：`AirLib/include/common/EncodedImageCaptureBase.hpp`
- C++ RPC 客户端：`AirLib/include/api/RpcLibClientBase.hpp`
- Python：`PythonClient/airsim/types.py`

#### 请求 / 响应字段

**`EncodedImageRequest`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `camera_name` | string | 相机名称（如 `"0"`） |
| `image_type` | int | `ImageType.Scene` / `Segmentation` 等 |
| `encode_mode` | int | 见 `EncodeMode` |
| `lossless` | bool | 是否无损（Seg 严格 IoU 时为 `true`） |
| `cq_or_qp` | int | ConstQP 质量（Scene 推荐 23） |
| `gop_size` | int | GOP 长度（默认 1，每帧 IDR） |
| `pix_fmt` | int | 见 `EncodedPixFmt` |

**`EncodedImageResponse`**

| 字段 | 说明 |
|------|------|
| `bitstream` | H.264 / HEVC NAL 字节流 |
| `width` / `height` | 编码分辨率（偶数对齐） |
| `encoded_size` | 码流字节数 |
| `camera_position` / `camera_orientation` | 捕获时刻相机位姿 |
| `message` | 非空表示失败原因 |

**枚举**（C++ 命名空间 `msr::airlib::EncodedImageCaptureBase`）

| C++ | Python | 值 | 用途 |
|-----|--------|----|------|
| `EncodeMode::NvencH264` | `EncodeMode.NvencH264` | 1 | Scene 等常规 RGB 画面 |
| `EncodeMode::NvencHevc` | `EncodeMode.NvencHevc` | 2 | Segmentation 等需 444 / 无损通道 |
| `EncodedPixFmt::Yuv420` | `EncodedPixFmt.Yuv420` | 0 | 默认 YUV420 |
| `EncodedPixFmt::Yuv444` | `EncodedPixFmt.Yuv444` | 1 | YUV444 |
| `EncodedPixFmt::Gbrp` | `EncodedPixFmt.Gbrp` | 2 | Seg 严格 IoU（RGB 平面） |

**推荐组合**

| 通道 | encode_mode | pix_fmt | lossless | 说明 |
|------|-------------|---------|----------|------|
| Scene | `NvencH264` | `Yuv420` | false | ConstQP，默认 cq=23 |
| Segmentation | `NvencHevc` | `Gbrp` | true | bit-exact 分割；C++ 需 FFmpeg 等自行解码 |

#### C++ 用法

`MultirotorRpcLibClient` 继承自 `RpcLibClientBase`，可直接调用 `simGetImagesEncoded`。参考 `HelloDrone/` 的 RPC 连接方式。

```cpp
#include "vehicles/multirotor/api/MultirotorRpcLibClient.hpp"
#include "common/EncodedImageCaptureBase.hpp"
#include <iostream>
#include <fstream>

int main()
{
    using namespace msr::airlib;

    MultirotorRpcLibClient client;  // 默认 localhost:41451
    client.confirmConnection();

    typedef EncodedImageCaptureBase::EncodedImageRequest EncReq;
    typedef EncodedImageCaptureBase::EncodedImageResponse EncResp;
    typedef ImageCaptureBase::ImageType ImageType;

    // Scene：H.264 ConstQP
    std::vector<EncReq> requests;
    requests.emplace_back(
        "0",                                    // camera_name
        ImageType::Scene,
        EncodedImageCaptureBase::EncodeMode::NvencH264,
        false,                                  // lossless
        23,                                     // cq_or_qp
        1,                                      // gop_size
        EncodedImageCaptureBase::EncodedPixFmt::Yuv420);

    // Segmentation：HEVC 无损 GBRP（可与 Scene 同批请求）
    requests.emplace_back(
        "0",
        ImageType::Segmentation,
        EncodedImageCaptureBase::EncodeMode::NvencHevc,
        true,                                   // lossless
        0,
        1,
        EncodedImageCaptureBase::EncodedPixFmt::Gbrp);

    const std::vector<EncResp>& responses =
        client.simGetImagesEncoded(requests, "SimpleFlight");

    for (const EncResp& resp : responses) {
        if (!resp.message.empty()) {
            std::cout << "error: " << resp.message << std::endl;
            continue;
        }
        std::cout << resp.width << "x" << resp.height
                  << " bitstream bytes: " << resp.bitstream.size() << std::endl;
    }
    return 0;
}
```

C++ 侧说明：

- 头文件：`MultirotorRpcLibClient.hpp`、`EncodedImageCaptureBase.hpp`
- RPC 实现：`AirLib/src/api/RpcLibClientBase.cpp`（`simGetImagesEncoded`）
- 返回的 `bitstream` 为原始 H.264 / HEVC NAL，**不含** Python 中 `encoded_image_client.py` 的 PyAV 解码与 Seg 调色板辅助
- 编译示例工程时链接 AirLib（与 `HelloDrone` 相同依赖）

#### Python 用法

```python
import airsim
from airsim.encoded_image_client import EncodedImageClient, decode_bitstream_to_bgr

client = airsim.MultirotorClient()
client.confirmConnection()

enc = EncodedImageClient(client)
reqs = [
    enc.make_scene_request("0", cq=23),
    enc.make_seg_request("0", strict_iou=True),
]
responses = client.simGetImagesEncoded(reqs, vehicle_name="SimpleFlight")

for resp in responses:
    if resp.message:
        print("error:", resp.message)
        continue
    # 解码需 PyAV: pip install av
    bgr = decode_bitstream_to_bgr(resp)
```

Python 类型与客户端：

- `PythonClient/airsim/types.py` — `EncodeMode`、`EncodedPixFmt`、`EncodedImageRequest`、`EncodedImageResponse`
- `PythonClient/airsim/client.py` — `VehicleClient.simGetImagesEncoded()`
- `PythonClient/airsim/encoded_image_client.py` — 请求构造、PyAV 解码、Seg 调色板

#### 验证脚本

1080p 测试配置：`scripts/settings/multirotor_1080p_fps.json`

```powershell
# 编译插件（VS 2022 + UE 5.7）
scripts\build_with_vs2022.bat

# 启动 UE
UnrealEditor.exe BlocksV2.uproject -game -settings="scripts/settings/multirotor_1080p_fps.json"

cd PythonClient\multirotor

# 静态帧率：JPEG / NVENC / NVENC+Seg
python camera_fps_test.py --vehicle SimpleFlight --camera 0 --jpeg 85 --duration 15
python camera_fps_test.py --vehicle SimpleFlight --camera 0 --nvenc --duration 15
python camera_fps_test.py --vehicle SimpleFlight --camera 0 --nvenc --seg --duration 15

# 基础飞行
python auto_verify_quadrotor.py --connect-timeout 30

# 飞行 + 帧率联合验证
python flight_fps_verify.py --vehicle SimpleFlight --camera 0 --fps-duration 10 --transports jpeg nvenc nvenc_seg
```

| 脚本 | 作用 |
|------|------|
| `camera_fps_test.py` | 静态相机帧率（`--jpeg` / `--nvenc` / `--nvenc --seg`） |
| `auto_verify_quadrotor.py` | 起飞 / 悬停 / 移动 / 传感器 / 降落 |
| `flight_fps_verify.py` | 飞行各阶段采样 JPEG 与 NVENC 帧率 |

### 典型使用流程

1. 在 Windows 11 上编译 BlocksV2 插件（UE 5.7.4）
2. 使用 `scripts/settings/multirotor_1080p_fps.json` 等配置启动仿真
3. 用 Python 或 C++ RPC 客户端连接并调用 API

## 环境要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 11 x64 |
| **Unreal Engine** | UE 5.7.x（已在 UE 5.7.4 验证） |
| **GPU** | NVIDIA，支持 NVENC（相机编码功能） |
| **编译工具** | Visual Studio 2022 |
| **Python** | 3.x（运行 `PythonClient` 验证脚本） |

示例工程路径：`Unreal/Environments/BlocksV2/BlocksV2.uproject`（`EngineAssociation` 为 `5.7`）。

> 若 Epic Launcher 中 UE 安装目录为 `UE_5.7`，请确保该版本已设为 **Current**，再打开 `.uproject` 生成/刷新 `.sln`。

## 与 AirSim 的关系

Colosseum 在 AirSim 基础上继续演进，代码结构与 RPC API 大体兼容。部分历史目录/包名仍保留 `AirSim`（如 Unreal 插件路径、`airsim` Python 包名），属于渐进式重命名过程中的遗留。

## 文档

上游完整文档：[https://codexlabsllc.github.io/Colosseum/](https://codexlabsllc.github.io/Colosseum/)

本地文档目录见 [`docs/`](docs/)。**其中部分平台/编译说明来自上游，未必适用于本分支；请以本文「已验证环境」为准。**

## 加入社区

欢迎加入 Discord 社区参与讨论：[Colosseum Robotics Discord](https://discord.gg/y9ZJKKKn8J)

## 许可证

本项目采用 [MIT License](LICENSE) 发布。
