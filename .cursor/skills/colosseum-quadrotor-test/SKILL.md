---
name: colosseum-quadrotor-test
description: >-
  Automatically build, launch Colosseum UE5.7 Multirotor simulation, and run
  quadrotor verification tests. Use when the user asks to test quadrotor,
  multirotor, drone simulation, SimpleFlight, or automated Colosseum validation.
---

# Colosseum 四旋翼自动测试

## 推荐方案

使用 **SimpleFlight**（零额外依赖，默认飞控），通过 **PowerShell 编排 + Python RPC 断言** 实现全自动验证。Cursor Agent 只需执行一条命令，无需手动点 UE Play。

## 一键执行

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_quadrotor_test.ps1
```

### 常用参数

| 参数 | 用途 |
|------|------|
| `-SkipBuild` | 跳过 `build.cmd`（插件已编译时） |
| `-SkipLaunch` | 不启动 UE（用户已手动运行仿真时） |
| `-Headless` | 添加 `-RenderOffScreen` 减少窗口干扰 |
| `-UeEditorPath "C:\...\UnrealEditor.exe"` | 指定 UE 5.7.4 路径 |

### 仅跑 Python 测试（UE 已在运行）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_quadrotor_test.ps1 -SkipBuild -SkipLaunch
```

或直接：

```powershell
cd PythonClient/multirotor
python auto_verify_quadrotor.py
```

## 测试内容

`PythonClient/multirotor/auto_verify_quadrotor.py` 会自动验证：

1. RPC 连接（端口 41451）
2. API 控制 + 解锁
3. 起飞至 5 m 并检查高度
4. 悬停稳定性（漂移 < 0.8 m）
5. 水平移动 ≥ 1 m
6. IMU / 磁力计 / 气压计读数
7. 降落并释放控制

退出码：`0`=通过，`1`=连接错误，`2`=飞行/运动失败。

## 配置文件

- 仿真设置：`scripts/settings/multirotor_simpleflight.json`
- SimMode：`Multirotor`
- 飞控：`SimpleFlight`（无需 PX4 SITL）

## 前置条件

1. **UE 5.7.x** 已安装（本分支 `BlocksV2.uproject` 关联 5.7）
2. **Visual Studio 2022** + C++ 桌面开发（首次需编译插件）
3. **Python 3** + `pip install msgpack-rpc-python numpy`
4. 首次编译请在 **x64 Native Tools Command Prompt for VS 2022** 中运行，或确保 `build.cmd` 可用

## Agent 执行流程

当用户要求测试四旋翼时，按顺序：

1. 确认 `scripts/settings/multirotor_simpleflight.json` 存在
2. 若插件有 C++ 改动 → 运行 `build.cmd`（否则 `-SkipBuild`）
3. 运行 `scripts/run_quadrotor_test.ps1`
4. 检查退出码与 `scripts/logs/ue_*.log`
5. 失败时读取 UE 日志和 Python 输出，定位问题

## 与 PX4 测试的区别

| 方案 | 适用 | 自动化难度 |
|------|------|------------|
| **SimpleFlight**（本 Skill） | 仿真器功能、传感器、飞行动作 | 低，推荐 |
| **PX4 SITL** | 飞控联调、真实 PX4 参数 | 高，需单独启动 PX4 |

PX4 测试不在本 Skill 范围内；需要时使用 `docs/px4_sitl.md` 手动配置。

## 故障排查

| 现象 | 处理 |
|------|------|
| 端口 41451 超时 | 检查 UE 是否崩溃，查看 `scripts/logs/ue_*.log` |
| `build.cmd` 失败 | 需在 VS2022 开发者命令提示符中运行 |
| 找不到 UnrealEditor | 设置 `$env:UE_EDITOR` 或 `-UeEditorPath` |
| 起飞后高度不对 | 检查 BlocksV2 地图 PlayerStart 是否悬空或穿地 |
| Python import 失败 | `pip install msgpack-rpc-python numpy` |

## 扩展测试

在 `auto_verify_quadrotor.py` 通过后，可按需追加：

- `camera_fps_test.py --jpeg 85` — JPEG 相机帧率（本分支特性）
- `stability_test.py` — 长时间稳定性（约 20 分钟，非 CI 用）
