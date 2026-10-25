#!/bin/bash
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
rm -f /home/ubuntu/cam.png /home/ubuntu/cam_side.png
pkill -f "[p]arameter_bridge"
sleep 1
setsid nohup ros2 run ros_gz_bridge parameter_bridge '/overhead_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image' '/side_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image' > /tmp/bridge.log 2>&1 &
sleep 4
python3 /home/ubuntu/tools/grab.py
