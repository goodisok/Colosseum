#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
不同采集分辨率下的帧率测试，可选上采样到 1920x1080。

用法:
  python camera_fps_test_resolutions.py --duration 15
  python camera_fps_test_resolutions.py --width 960 --height 540 --upsample --duration 15
"""
import argparse
import sys
import time

import setup_path
import airsim
import numpy as np

try:
    import cv2
except ImportError:
    print("pip install opencv-python")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="AirSim 多分辨率帧率测试")
    parser.add_argument("--vehicle", type=str, default="PX4_1")
    parser.add_argument("--camera", type=str, default="WideAngleCamera")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--jpeg", type=int, default=85, help="JPEG 质量 1-100")
    parser.add_argument("--upsample", action="store_true", help="上采样到 1080p")
    parser.add_argument("--duration", type=float, default=10.0)
    args = parser.parse_args()

    client = airsim.MultirotorClient()
    client.confirmConnection()

    req = airsim.ImageRequest(
        args.camera,
        airsim.ImageType.Scene,
        False,
        False,
        args.jpeg,
    )
    target_size = (1920, 1080) if args.upsample else None
    print("Resolution: %dx%d, JPEG: %d, Upsample: %s, Duration: %.1fs" % (
        args.width, args.height, args.jpeg, bool(args.upsample), args.duration))

    start = time.time()
    n = 0
    while time.time() - start < args.duration:
        responses = client.simGetImages([req], vehicle_name=args.vehicle)
        if not responses or not responses[0].image_data_uint8:
            continue
        n += 1
        raw = responses[0].image_data_uint8
        img = cv2.imdecode(
            np.frombuffer(raw, dtype=np.uint8) if hasattr(raw, "__len__") and not isinstance(raw, str)
            else np.asarray(list(raw), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img is not None and target_size:
            img = cv2.resize(img, target_size, interpolation=cv2.INTER_LINEAR)
    elapsed = time.time() - start
    fps = n / elapsed if elapsed > 0 else 0
    print("Frames: %d, Time: %.2fs, FPS: %.2f" % (n, elapsed, fps))


if __name__ == "__main__":
    main()
