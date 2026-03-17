# AirSim JPEG 压缩功能修改说明

## 1. 概述

为支持相机图像 **JPEG 压缩** 输出，在 AirSim 中增加 `compress_quality` 参数，用于减小 RPC 传输体积、提高帧率（尤其 WSL/远程场景）。

**语义**：`compress_quality`：0=raw，-1=PNG，1–100=JPEG 质量。

## 2. 修改文件列表

| 文件 | 修改要点 |
|------|----------|
| AirLib/include/common/ImageCaptureBase.hpp | ImageRequest 增加 compress_quality |
| AirLib/include/api/RpcLibAdaptorsBase.hpp | 适配器增加 compress_quality，MSGPACK 末尾追加 |
| Unreal/.../RenderRequest.h | RenderParams 增加 compress_quality；BufferPool 模板类 |
| Unreal/.../RenderRequest.cpp | 缓冲池、stride 修正、JPEG/PNG/raw 三路分支 |
| Unreal/.../AirBlueprintLib.h | 声明 CompressImageArrayJPEG |
| Unreal/.../AirBlueprintLib.cpp | 实现 CompressImageArrayJPEG（GetCompressed(quality)） |
| Unreal/.../UnrealImageCapture.cpp | 传入 requests[i].compress_quality |
| PythonClient/airsim/types.py | ImageRequest 增加 compress_quality |

## 3. Python 调用示例

```python
# JPEG 质量 85
req = airsim.ImageRequest("WideAngleCamera", airsim.ImageType.Scene, False, False, 85)
responses = client.simGetImages([req], vehicle_name="PX4_1")
# 解码：cv2.imdecode(np.frombuffer(responses[0].image_data_uint8, np.uint8), cv2.IMREAD_COLOR)
```

## 4. UE 5.7 注意

`IImageWrapper` 使用 `GetCompressed(quality)` 传质量，不要使用 `SetQuality`。
