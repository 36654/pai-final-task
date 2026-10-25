#!/bin/bash
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
python3 /home/ubuntu/tools/add_camera.py "$@"
