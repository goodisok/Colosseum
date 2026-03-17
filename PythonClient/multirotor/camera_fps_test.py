#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相机图像帧率测试（支持 JPEG / PNG / 未压缩）。

用法:
  python camera_fps_test.py --duration 15
  python camera_fps_test.py --no-compress --duration 15
  python camera_fps_test.py --jpeg 85 --duration 15
  python camera_fps_test.py --camera WideAngleCamera --vehicle PX4_1
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
    parser = argparse.ArgumentParser(description="AirSim 相机帧率测试")
    parser.add_argument("--vehicle", type=str, default="PX4_1", help="机体名称")
    parser.add_argument("--camera", type=str, default="WideAngleCamera", help="相机名称")
    parser.add_argument("--duration", type=float, default=10.0, help="测试时长(秒)")
    parser.add_argument("--no-compress", action="store_true", help="不压缩(原始像素)，否则 PNG")
    parser.add_argument("--jpeg", type=int, default=0, metavar="QUALITY",
                        help="JPEG 质量 1-100，0 表示不用 JPEG")
    parser.add_argument("--show", action="store_true", help="显示画面")
    args = parser.parse_args()

    client = airsim.MultirotorClient()
    client.confirmConnection()

    compress = not args.no_compress and args.jpeg <= 0
    compress_quality = args.jpeg if args.jpeg > 0 else (-1 if compress else 0)

    req = airsim.ImageRequest(
        args.camera,
        airsim.ImageType.Scene,
        False,
        compress,
        compress_quality,
    )
    mode = "JPEG(q=%d)" % args.jpeg if args.jpeg > 0 else ("PNG" if compress else "raw")

    print("Vehicle: %s, Camera: %s, Mode: %s, Duration: %.1fs" % (
        args.vehicle, args.camera, mode, args.duration))
    start = time.time()
    n = 0
    while time.time() - start < args.duration:
        responses = client.simGetImages([req], vehicle_name=args.vehicle)
        if not responses or not responses[0].image_data_uint8:
            continue
        n += 1
        raw = responses[0].image_data_uint8
        buf = np.asarray(raw, dtype=np.uint8) if args.jpeg > 0 else airsim.string_to_uint8_array(raw)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is not None and args.show:
            cv2.imshow("Camera", img)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
    elapsed = time.time() - start
    fps = n / elapsed if elapsed > 0 else 0
    print("Frames: %d, Time: %.2fs, FPS: %.2f" % (n, elapsed, fps))
    if args.show:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
