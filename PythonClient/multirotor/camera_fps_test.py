#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相机图像帧率测试（支持 JPEG / PNG / 未压缩）。

用法:
  python camera_fps_test.py --duration 15
  python camera_fps_test.py --no-compress --duration 15
  python camera_fps_test.py --jpeg 85 --duration 15
  python camera_fps_test.py --nvenc --duration 15
  python camera_fps_test.py --nvenc --seg --duration 15
  python camera_fps_test.py --camera WideAngleCamera --vehicle PX4_1
"""
import argparse
import sys
import time

import setup_path
import airsim
from airsim.encoded_image_client import EncodedImageClient, decode_bitstream_to_bgr
import numpy as np

try:
    import cv2
except ImportError:
    print("pip install opencv-python")
    sys.exit(1)


def to_uint8_buffer(raw):
    if isinstance(raw, (bytes, bytearray)):
        return np.frombuffer(raw, dtype=np.uint8)
    if isinstance(raw, str):
        return np.frombuffer(raw.encode("latin-1", errors="ignore"), dtype=np.uint8)
    return np.asarray(raw, dtype=np.uint8)


def main():
    parser = argparse.ArgumentParser(description="AirSim 相机帧率测试")
    parser.add_argument("--vehicle", type=str, default="PX4_1", help="机体名称")
    parser.add_argument("--camera", type=str, default="WideAngleCamera", help="相机名称")
    parser.add_argument("--duration", type=float, default=10.0, help="测试时长(秒)")
    parser.add_argument("--no-compress", action="store_true", help="不压缩(原始像素)，否则 PNG")
    parser.add_argument("--jpeg", type=int, default=0, metavar="QUALITY",
                        help="JPEG 质量 1-100，0 表示不用 JPEG")
    parser.add_argument("--nvenc", action="store_true", help="使用 NVENC H.264/HEVC 编码管线")
    parser.add_argument("--seg", action="store_true", help="配合 --nvenc 测试 Segmentation 通道")
    parser.add_argument("--nvenc-cq", type=int, default=23, help="NVENC Scene ConstQP (默认 23)")
    parser.add_argument("--show", action="store_true", help="显示画面")
    args = parser.parse_args()

    client = airsim.MultirotorClient()
    client.confirmConnection()

    if args.nvenc:
        enc = EncodedImageClient(client)
        reqs = [enc.make_scene_request(args.camera, cq=args.nvenc_cq)]
        if args.seg:
            reqs.append(enc.make_seg_request(args.camera, strict_iou=True))
        mode = "NVENC H.264" + (" + HEVC Seg" if args.seg else "")
    else:
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
    responses = None
    total_kb = 0.0
    while time.time() - start < args.duration:
        if args.nvenc:
            responses = client.simGetImagesEncoded(reqs, vehicle_name=args.vehicle)
            if not responses:
                continue
            bs = responses[0].bitstream
            if bs is None or (hasattr(bs, "__len__") and len(bs) == 0):
                if responses[0].message:
                    print("Error:", responses[0].message)
                continue
            n += 1
            for resp in responses:
                bs = resp.bitstream
                total_kb += (len(bs) if hasattr(bs, "__len__") else 0) / 1024.0
            if args.show:
                img = decode_bitstream_to_bgr(responses[0])
                cv2.imshow("Camera", img)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
        else:
            responses = client.simGetImages([req], vehicle_name=args.vehicle)
            if not responses or not responses[0].image_data_uint8:
                continue
            n += 1
            raw = responses[0].image_data_uint8
            if args.jpeg > 0 or responses[0].compress:
                buf = to_uint8_buffer(raw)
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            else:
                img = None
                if responses[0].width and responses[0].height:
                    expected = responses[0].width * responses[0].height * 3
                    if hasattr(raw, "__len__") and len(raw) >= expected:
                        img = np.ones((1, 1, 3), dtype=np.uint8)
            if img is not None and args.show:
                cv2.imshow("Camera", img)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
    elapsed = time.time() - start
    fps = n / elapsed if elapsed > 0 else 0
    if n > 0 and responses:
        if args.nvenc and responses[0].width:
            print("Resolution: %dx%d" % (responses[0].width, responses[0].height))
            if total_kb > 0:
                print("Avg KB/frame: %.1f" % (total_kb / n))
        elif not args.nvenc and responses[0].width:
            print("Resolution: %dx%d" % (responses[0].width, responses[0].height))
    print("Frames: %d, Time: %.2fs, FPS: %.2f" % (n, elapsed, fps))
    if args.show:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
