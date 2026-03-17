#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
960x540 源，JPEG 拉流后解码，上采样到 1920x1080，发布 ROS2 sensor_msgs/Image（原始像素）。
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
from sensor_msgs.msg import Image
from std_msgs.msg import Header

try:
    import cv2
except ImportError:
    print("pip install opencv-python")
    sys.exit(1)


class AirSimCamera540pRawPublisher(Node):
    def __init__(self, vehicle_name="PX4_1", camera_name="WideAngleCamera", topic="/camera/color/image_raw",
                 jpeg_quality=85, rate=30.0):
        super().__init__("airsim_camera_540p_raw_publisher")
        self.vehicle_name = vehicle_name
        self.req = airsim.ImageRequest(
            camera_name, airsim.ImageType.Scene, False, False, jpeg_quality
        )
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        self.pub = self.create_publisher(Image, topic, 10)
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
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return
        img = cv2.resize(img, self.target_size, interpolation=cv2.INTER_LINEAR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        msg = Image()
        msg.header = Header(stamp=self.get_clock().now().to_msg(), frame_id="camera_optical_frame")
        msg.height, msg.width = img.shape[:2]
        msg.encoding = "rgb8"
        msg.is_bigendian = 0
        msg.step = msg.width * 3
        msg.data = list(img.tobytes())
        self.pub.publish(msg)
        self.count += 1
        t = time.perf_counter()
        if t - self.t0 >= 5.0:
            self.get_logger().info("FPS: %.1f" % (self.count / (t - self.t0)))
            self.count = 0
            self.t0 = t


def main(args=None):
    rclpy.init(args=args)
    node = AirSimCamera540pRawPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
