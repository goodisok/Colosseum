#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞行 + 相机帧率联合验证（SimpleFlight / 1080p）。

在各飞行阶段采样 JPEG 与 NVENC 帧率，并执行基础飞行检查。

Exit codes:
  0 - 全部通过
  1 - 连接失败
  2 - 飞行失败
  3 - 帧率未达阈值
"""
import argparse
import math
import sys
import time

import setup_path
import airsim
from airsim.encoded_image_client import EncodedImageClient


def log(msg):
    print("[flight_fps] %s" % msg, flush=True)


def wait_for_simulator(timeout_sec, port):
    deadline = time.time() + timeout_sec
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            c = airsim.MultirotorClient(port=port, timeout_value=5)
            c.ping()
            log("Connected after %d attempt(s)" % attempt)
            return airsim.MultirotorClient(port=port, timeout_value=600)
        except Exception:
            time.sleep(2)
    return None


def measure_fps(client, transport, duration, vehicle, camera, nvenc_cq=23):
    """transport: 'jpeg' | 'nvenc' | 'nvenc_seg'"""
    enc = EncodedImageClient(client) if transport.startswith("nvenc") else None
    if transport == "jpeg":
        req_jpeg = airsim.ImageRequest(
            camera, airsim.ImageType.Scene, False, True, 85)
    elif transport == "nvenc":
        reqs = [enc.make_scene_request(camera, cq=nvenc_cq)]
    else:
        reqs = [
            enc.make_scene_request(camera, cq=nvenc_cq),
            enc.make_seg_request(camera, strict_iou=True),
        ]

    start = time.time()
    frames = 0
    total_kb = 0.0
    errors = 0
    width = height = 0
    last_msg = ""

    while time.time() - start < duration:
        if transport == "jpeg":
            resp = client.simGetImages([req_jpeg], vehicle_name=vehicle)
            if not resp or not resp[0].image_data_uint8:
                errors += 1
                continue
            frames += 1
            total_kb += len(resp[0].image_data_uint8) / 1024.0
            width, height = resp[0].width, resp[0].height
        else:
            resp = client.simGetImagesEncoded(reqs, vehicle_name=vehicle)
            if not resp or not resp[0].bitstream or len(resp[0].bitstream) == 0:
                errors += 1
                last_msg = resp[0].message if resp else "no response"
                continue
            frames += 1
            for r in resp:
                if r.bitstream is not None:
                    total_kb += len(r.bitstream) / 1024.0
            width, height = resp[0].width, resp[0].height

    elapsed = time.time() - start
    fps = frames / elapsed if elapsed > 0 else 0.0
    return {
        "transport": transport,
        "frames": frames,
        "elapsed": elapsed,
        "fps": fps,
        "avg_kb": total_kb / frames if frames else 0.0,
        "width": width,
        "height": height,
        "errors": errors,
        "last_msg": last_msg,
    }


def run_flight_and_fps(client, args):
    vehicle = args.vehicle
    camera = args.camera
    results = []

    log("Enabling API control")
    client.enableApiControl(True, vehicle)
    time.sleep(0.5)
    client.armDisarm(True, vehicle)
    time.sleep(0.5)

    state = client.getMultirotorState(vehicle)
    if state.landed_state == airsim.LandedState.Landed:
        log("Takeoff to %.1f m" % args.takeoff_z)
        client.takeoffAsync(timeout_sec=60, vehicle_name=vehicle).join()
    client.moveToZAsync(-args.takeoff_z, 3, vehicle_name=vehicle).join()
    client.hoverAsync(vehicle_name=vehicle).join()
    time.sleep(2)

    z = client.getMultirotorState(vehicle).kinematics_estimated.position.z_val
    if abs(z + args.takeoff_z) > 1.5:
        raise AssertionError("takeoff altitude out of range: z=%.2f" % z)

    log("Phase HOVER: FPS sampling (%.1fs each)" % args.fps_duration)
    client.hoverAsync(vehicle_name=vehicle)
    for mode in args.transports:
        log("  HOVER + %s ..." % mode)
        r = measure_fps(client, mode, args.fps_duration, vehicle, camera, args.nvenc_cq)
        r["phase"] = "hover"
        results.append(r)
        log("    -> %.2f FPS, %d frames, %.1f KB/frm, errors=%d" % (
            r["fps"], r["frames"], r["avg_kb"], r["errors"]))
        if args.transport_gap > 0:
            time.sleep(args.transport_gap)

    log("Phase MOVE: flying + FPS sampling")
    pos = client.getMultirotorState(vehicle).kinematics_estimated.position
    target_x = pos.x_val + args.move_x
    target_y = pos.y_val + args.move_y
    move_task = client.moveToPositionAsync(
        target_x, target_y, pos.z_val, 3, vehicle_name=vehicle)
    time.sleep(0.5)
    for mode in args.transports:
        log("  MOVE + %s ..." % mode)
        r = measure_fps(client, mode, args.fps_duration, vehicle, camera, args.nvenc_cq)
        r["phase"] = "move"
        results.append(r)
        log("    -> %.2f FPS, %d frames, %.1f KB/frm, errors=%d" % (
            r["fps"], r["frames"], r["avg_kb"], r["errors"]))
        if args.transport_gap > 0:
            time.sleep(args.transport_gap)
    move_task.join()
    client.hoverAsync(vehicle_name=vehicle).join()
    time.sleep(1)

    end = client.getMultirotorState(vehicle).kinematics_estimated.position
    moved = math.hypot(end.x_val - pos.x_val, end.y_val - pos.y_val)
    if moved < 1.0:
        raise AssertionError("move distance %.2f m < 1.0 m" % moved)
    log("Move OK (%.2f m)" % moved)

    log("Landing")
    client.landAsync(vehicle_name=vehicle).join()
    client.armDisarm(False, vehicle)
    client.enableApiControl(False, vehicle)

    return results, moved


def check_thresholds(results, args):
    fails = []
    limits = {
        ("hover", "jpeg"): args.min_fps_hover_jpeg,
        ("hover", "nvenc"): args.min_fps_hover_nvenc,
        ("hover", "nvenc_seg"): args.min_fps_hover_nvenc_seg,
        ("move", "jpeg"): args.min_fps_move_jpeg,
        ("move", "nvenc"): args.min_fps_move_nvenc,
        ("move", "nvenc_seg"): args.min_fps_move_nvenc_seg,
    }
    for r in results:
        key = (r["phase"], r["transport"])
        min_fps = limits.get(key, 0)
        if r["frames"] == 0:
            fails.append("%s/%s: no frames (%s)" % (r["phase"], r["transport"], r["last_msg"]))
        elif r["fps"] < min_fps:
            fails.append("%s/%s: FPS %.2f < %.2f" % (
                r["phase"], r["transport"], r["fps"], min_fps))
        elif r["errors"] > r["frames"] * 0.1:
            fails.append("%s/%s: too many errors (%d)" % (
                r["phase"], r["transport"], r["errors"]))
    return fails


def print_summary(results, moved):
    print("\n" + "=" * 72)
    print("FLIGHT + FPS SUMMARY")
    print("=" * 72)
    print("Move distance: %.2f m" % moved)
    print("%-8s %-10s %6s %8s %10s %6s" % (
        "Phase", "Transport", "Frames", "FPS", "KB/frame", "Errors"))
    print("-" * 72)
    for r in results:
        print("%-8s %-10s %6d %8.2f %10.1f %6d" % (
            r["phase"], r["transport"], r["frames"], r["fps"],
            r["avg_kb"], r["errors"]))
    if results:
        print("Resolution: %dx%d" % (results[0]["width"], results[0]["height"]))
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Flight + camera FPS joint verification")
    parser.add_argument("--vehicle", default="SimpleFlight")
    parser.add_argument("--camera", default="0")
    parser.add_argument("--port", type=int, default=41451)
    parser.add_argument("--connect-timeout", type=float, default=300)
    parser.add_argument("--takeoff-z", type=float, default=5.0)
    parser.add_argument("--move-x", type=float, default=5.0)
    parser.add_argument("--move-y", type=float, default=0.0)
    parser.add_argument("--fps-duration", type=float, default=10.0,
                        help="Each transport sampled this long per phase")
    parser.add_argument("--transport-gap", type=float, default=1.0,
                        help="Seconds to wait between transport switches (GPU settle)")
    parser.add_argument("--nvenc-cq", type=int, default=23)
    parser.add_argument("--transports", nargs="+",
                        default=["jpeg", "nvenc"],
                        choices=["jpeg", "nvenc", "nvenc_seg"])
    parser.add_argument("--min-fps-hover-jpeg", type=float, default=20.0)
    parser.add_argument("--min-fps-hover-nvenc", type=float, default=30.0)
    parser.add_argument("--min-fps-hover-nvenc-seg", type=float, default=18.0)
    parser.add_argument("--min-fps-move-jpeg", type=float, default=18.0)
    parser.add_argument("--min-fps-move-nvenc", type=float, default=25.0)
    parser.add_argument("--min-fps-move-nvenc-seg", type=float, default=15.0)
    args = parser.parse_args()

    client = wait_for_simulator(args.connect_timeout, args.port)
    if client is None:
        log("ERROR: simulator not reachable")
        sys.exit(1)

    try:
        client.confirmConnection()
        results, moved = run_flight_and_fps(client, args)
        print_summary(results, moved)
        fails = check_thresholds(results, args)
        if fails:
            for f in fails:
                log("FAIL: %s" % f)
            sys.exit(3)
        log("PASS: flight + FPS checks completed")
        sys.exit(0)
    except AssertionError as exc:
        log("FAIL: %s" % exc)
        sys.exit(2)
    except Exception as exc:
        log("ERROR: %s" % exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
