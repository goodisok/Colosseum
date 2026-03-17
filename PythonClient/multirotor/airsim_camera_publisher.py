#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应分辨率：根据首帧宽高决定是否上采样到 1920x1080，发布 ROS2 CompressedImage。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup_path
import airsim
import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Header

try:
    import cv2
except ImportError:
    print("pip install opencv-python")
    sys.exit(1)

TARGET_W, TARGET_H = 1920, 1080


class AirSimCameraPublisher(Node):
    def __init__(self, vehicle_name="PX4_1", camera_name="WideAngleCamera", topic="/camera/color/image_raw/compressed",
                 jpeg_quality=85, rate=30.0):
        super().__init__("airsim_camera_publisher")
        self.vehicle_name = vehicle_name
        self.camera_name = camera_name
        self.jpeg_quality = jpeg_quality
        self.pub = self.create_publisher(CompressedImage, topic, 10)
        self.req = airsim.ImageRequest(
            camera_name, airsim.ImageType.Scene, False, False, jpeg_quality
        )
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        self.need_upsample = None
        self.timer = self.create_timer(1.0 / rate, self.tick)
        self.count = 0
        self.t0 = time.perf_counter()

    def tick(self):
        try:
            responses = self.client.simGetImages([self.req], vehicle_name=self.vehicle_name)
        except Exception:
            return
        if not responses or not responses[0].image_data_uint8:
            return
        r = responses[0]
        raw = r.image_data_uint8
        data = np.asarray(raw, dtype=np.uint8)
        if data.size == 0:
            return
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return
        h, w = img.shape[:2]
        if self.need_upsample is None:
            self.need_upsample = (w != TARGET_W or h != TARGET_H)
            self.get_logger().info("Source %dx%d, upsample: %s" % (w, h, self.need_upsample))
        if self.need_upsample:
            img = cv2.resize(img, (TARGET_W, TARGET_H), interpolation=cv2.INTER_LINEAR)
            _, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            payload = list(jpeg.tobytes())
        else:
            payload = data.tolist() if hasattr(data, "tolist") else list(data)
        msg = CompressedImage()
        msg.header = Header(stamp=self.get_clock().now().to_msg(), frame_id="camera_optical_frame")
        msg.format = "jpeg"
        msg.data = payload
        self.pub.publish(msg)
        self.count += 1
        t = time.perf_counter()
        if t - self.t0 >= 5.0:
            self.get_logger().info("FPS: %.1f, size: %d KB" % (self.count / (t - self.t0), len(msg.data) // 1024))
            self.count = 0
            self.t0 = t


def main(args=None):
    rclpy.init(args=args)
    node = AirSimCameraPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
