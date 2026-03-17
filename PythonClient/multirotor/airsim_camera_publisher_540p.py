#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
960x540 源，JPEG 压缩，上采样到 1920x1080 后发布 ROS2 CompressedImage。
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


class AirSimCamera540pPublisher(Node):
    def __init__(self, vehicle_name="PX4_1", camera_name="WideAngleCamera", topic="/camera/color/image_raw/compressed",
                 jpeg_quality=85, rate=30.0):
        super().__init__("airsim_camera_540p_publisher")
        self.vehicle_name = vehicle_name
        self.camera_name = camera_name
        self.jpeg_quality = jpeg_quality
        self.pub = self.create_publisher(CompressedImage, topic, 10)
        self.req = airsim.ImageRequest(
            camera_name, airsim.ImageType.Scene, False, False, jpeg_quality
        )
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        self.timer = self.create_timer(1.0 / rate, self.tick)
        self.count = 0
        self.t0 = time.perf_counter()
        self.target_size = (1920, 1080)

    def tick(self):
        try:
            responses = self.client.simGetImages([self.req], vehicle_name=self.vehicle_name)
        except Exception:
            return
        if not responses or not responses[0].image_data_uint8:
            return
        raw = responses[0].image_data_uint8
        data = np.asarray(raw, dtype=np.uint8)
        if data.size == 0:
            return
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return
        img = cv2.resize(img, self.target_size, interpolation=cv2.INTER_LINEAR)
        _, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        msg = CompressedImage()
        msg.header = Header(stamp=self.get_clock().now().to_msg(), frame_id="camera_optical_frame")
        msg.format = "jpeg"
        msg.data = list(jpeg.tobytes())
        self.pub.publish(msg)
        self.count += 1
        t = time.perf_counter()
        if t - self.t0 >= 5.0:
            self.get_logger().info("FPS: %.1f, size: %d KB" % (self.count / (t - self.t0), len(msg.data) // 1024))
            self.count = 0
            self.t0 = t


def main(args=None):
    rclpy.init(args=args)
    node = AirSimCamera540pPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
