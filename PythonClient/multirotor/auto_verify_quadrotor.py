#!/usr/bin/env python3
"""
Non-interactive quadrotor smoke test for Colosseum (SimpleFlight).

Exit codes:
  0 - all checks passed
  1 - connection / API failure
  2 - flight / motion failure
  3 - sensor failure
"""
import argparse
import math
import sys
import time

import setup_path
import airsim


def log(msg):
    print("[auto_verify] %s" % msg, flush=True)


def wait_for_simulator(timeout_sec, port):
    deadline = time.time() + timeout_sec
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        client = airsim.MultirotorClient(port=port, timeout_value=5)
        try:
            client.ping()
            log("Connected after %d attempt(s)" % attempt)
            return airsim.MultirotorClient(port=port, timeout_value=600)
        except Exception as exc:
            log("Waiting for simulator on port %d (%s)" % (port, type(exc).__name__))
            time.sleep(2)
    return None


def assert_near(actual, expected, tolerance, label):
    if abs(actual - expected) > tolerance:
        raise AssertionError("%s: expected %.2f +/- %.2f, got %.2f" % (
            label, expected, tolerance, actual))


def run_tests(client, vehicle_name, takeoff_z, move_xy, hover_sec):
    log("Enabling API control")
    client.enableApiControl(True, vehicle_name)
    time.sleep(1)
    client.armDisarm(True, vehicle_name)
    time.sleep(1)

    state = client.getMultirotorState(vehicle_name)
    if state.landed_state == airsim.LandedState.Landed:
        log("Taking off to %.1f m altitude" % takeoff_z)
        client.takeoffAsync(timeout_sec=60, vehicle_name=vehicle_name).join()
    else:
        log("Vehicle already airborne")

    client.moveToZAsync(-takeoff_z, 3, vehicle_name=vehicle_name).join()
    client.hoverAsync(vehicle_name=vehicle_name).join()
    time.sleep(2)

    state = client.getMultirotorState(vehicle_name)
    z = state.kinematics_estimated.position.z_val
    assert_near(z, -takeoff_z, 1.5, "takeoff altitude")

    log("Hover stability check (%.1fs)" % hover_sec)
    samples = []
    start = time.time()
    while time.time() - start < hover_sec:
        s = client.getMultirotorState(vehicle_name)
        p = s.kinematics_estimated.position
        samples.append((p.x_val, p.y_val, p.z_val))
        time.sleep(0.5)

    for axis, idx in (("x", 0), ("y", 1), ("z", 2)):
        values = [s[idx] for s in samples]
        drift = max(values) - min(values)
        if drift > 0.8:
            raise AssertionError("hover %s drift %.2f m exceeds 0.8 m" % (axis, drift))
    log("Hover drift OK")

    log("Moving by (%.1f, %.1f) m" % (move_xy[0], move_xy[1]))
    state = client.getMultirotorState(vehicle_name)
    start_pos = state.kinematics_estimated.position
    target_x = start_pos.x_val + move_xy[0]
    target_y = start_pos.y_val + move_xy[1]
    target_z = start_pos.z_val

    client.moveToPositionAsync(
        target_x, target_y, target_z, 3, vehicle_name=vehicle_name
    ).join()
    client.hoverAsync(vehicle_name=vehicle_name).join()
    time.sleep(1)

    state = client.getMultirotorState(vehicle_name)
    end_pos = state.kinematics_estimated.position
    moved = math.sqrt(
        (end_pos.x_val - start_pos.x_val) ** 2 +
        (end_pos.y_val - start_pos.y_val) ** 2
    )
    if moved < 1.0:
        raise AssertionError("move distance %.2f m is less than 1.0 m" % moved)
    log("Move distance OK (%.2f m)" % moved)

    log("Checking sensors")
    imu = client.getImuData(vehicle_name=vehicle_name)
    gps = client.getGpsData(vehicle_name=vehicle_name)
    mag = client.getMagnetometerData(vehicle_name=vehicle_name)
    baro = client.getBarometerData(vehicle_name=vehicle_name)

    if imu.time_stamp == 0:
        raise AssertionError("IMU timestamp is zero")
    if gps.gnss.time_utc == 0 and gps.gnss.fix_type == 0:
        log("Warning: GPS fix not available (may be OK in some scenes)")
    mag_norm = math.sqrt(
        mag.magnetic_field_body.x_val ** 2 +
        mag.magnetic_field_body.y_val ** 2 +
        mag.magnetic_field_body.z_val ** 2
    )
    if mag_norm < 1e-6:
        raise AssertionError("magnetometer field magnitude is zero")
    if baro.altitude == 0.0 and baro.pressure == 0.0:
        raise AssertionError("barometer readings are zero")
    log("Sensors OK")

    log("Landing")
    client.landAsync(vehicle_name=vehicle_name).join()
    client.armDisarm(False, vehicle_name)
    client.enableApiControl(False, vehicle_name)


def main():
    parser = argparse.ArgumentParser(description="Colosseum quadrotor automated verification")
    parser.add_argument("--vehicle", default="SimpleFlight", help="Vehicle name (default: SimpleFlight)")
    parser.add_argument("--port", type=int, default=41451)
    parser.add_argument("--connect-timeout", type=float, default=300.0)
    parser.add_argument("--takeoff-z", type=float, default=5.0, help="Target altitude in meters")
    parser.add_argument("--move-x", type=float, default=5.0)
    parser.add_argument("--move-y", type=float, default=0.0)
    parser.add_argument("--hover-sec", type=float, default=3.0)
    args = parser.parse_args()

    client = wait_for_simulator(args.connect_timeout, args.port)
    if client is None:
        log("ERROR: simulator not reachable within %.0fs" % args.connect_timeout)
        sys.exit(1)

    try:
        client.confirmConnection()
        run_tests(
            client,
            args.vehicle,
            args.takeoff_z,
            (args.move_x, args.move_y),
            args.hover_sec,
        )
    except AssertionError as exc:
        log("FAIL: %s" % exc)
        sys.exit(2)
    except Exception as exc:
        log("ERROR: %s" % exc)
        sys.exit(1)

    log("PASS: all quadrotor checks completed")
    sys.exit(0)


if __name__ == "__main__":
    main()
