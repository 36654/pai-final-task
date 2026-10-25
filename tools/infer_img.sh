#!/bin/bash
# usage: infer_img.sh NAME      (Gazebo must be running; Ctrl+C to stop)
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
NAME=$1
pkill -f "[p]arameter_bridge"
sleep 1
setsid nohup ros2 run ros_gz_bridge parameter_bridge '/overhead_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image' > /tmp/bridge.log 2>&1 &
sleep 3
cd /home/ubuntu/pai_training
/home/ubuntu/.pixi/bin/pixi run python /home/ubuntu/tools/pai_img/infer_img.py --model-path /home/ubuntu/checkpoints/train/$NAME
