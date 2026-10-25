#!/usr/bin/env python3
"""Run a trained ACT policy (state + overhead image) on the CRANE+ in Gazebo."""
import argparse
import sys

import numpy as np
import rclpy
import torch
from rclpy.node import Node
from sensor_msgs.msg import Image, JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from lerobot.common.policies.act.modeling_act import ACTPolicy

ARM = ['crane_plus_joint1', 'crane_plus_joint2', 'crane_plus_joint3', 'crane_plus_joint4']
HAND = 'crane_plus_joint_hand'
ORDER = ARM + [HAND]


class Infer(Node):
    def __init__(self, a):
        super().__init__('crane_plus_act_infer_img')
        sys.path.insert(0, '/home/ubuntu/tools')
        from eval_act import load_policy
        self.policy = load_policy(a.model_path)
        self.policy.eval()
        self.policy.to('cpu')
        self.policy.reset()
        feats = getattr(self.policy.config, 'image_features', None) or {}
        self.img_key = next(iter(feats.keys()), 'observation.images.overhead')
        self.get_logger().info(f'image key: {self.img_key}')
        self.state = None
        self.img = None
        self.create_subscription(JointState, '/joint_states', self.on_js, 10)
        self.create_subscription(Image, '/overhead_camera/image', self.on_img, 1)
        self.arm_pub = self.create_publisher(JointTrajectory, '/crane_plus_arm_controller/joint_trajectory', 10)
        self.grp_pub = self.create_publisher(JointTrajectory, '/crane_plus_gripper_controller/joint_trajectory', 10)
        self.dt = 1.0 / a.hz
        self.create_timer(self.dt, self.tick)

    def on_js(self, msg):
        d = dict(zip(msg.name, msg.position))
        if all(n in d for n in ORDER):
            self.state = np.array([d[n] for n in ORDER], dtype=np.float32)

    def on_img(self, msg):
        self.img = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(msg.height, msg.width, 3).copy()

    def send(self, pub, names, positions):
        jt = JointTrajectory()
        jt.joint_names = names
        pt = JointTrajectoryPoint()
        pt.positions = [float(x) for x in positions]
        pt.time_from_start.sec = 0
        pt.time_from_start.nanosec = int(0.1 * 1e9)
        jt.points.append(pt)
        pub.publish(jt)

    def tick(self):
        if self.state is None or self.img is None:
            return
        obs = {
            'observation.state': torch.from_numpy(self.state).unsqueeze(0),
            self.img_key: torch.from_numpy(self.img).permute(2, 0, 1).float().div(255.0).unsqueeze(0),
        }
        with torch.no_grad():
            act = self.policy.select_action(obs).cpu().numpy().flatten()
        self.send(self.arm_pub, ARM, act[:4])
        self.send(self.grp_pub, [HAND], [act[4]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-path', required=True)
    ap.add_argument('--hz', type=float, default=20.0)
    a = ap.parse_args()
    rclpy.init()
    node = Infer(a)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
