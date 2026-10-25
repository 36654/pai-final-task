#!/bin/bash
# usage: eval_act.sh NAME [eval_act.py の引数: --n 10 --seed 2000 ...]   Gazebo起動後(アームがhome)に実行。
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
mkdir -p /home/ubuntu/outbox
NAME=$1; shift
pkill -f "[p]arameter_bridge"
sleep 1
BR=('/overhead_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image')
if [[ " $* " != *" --no-side "* ]]; then BR+=('/side_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image'); fi
setsid nohup ros2 run ros_gz_bridge parameter_bridge "${BR[@]}" > /tmp/bridge.log 2>&1 &
sleep 3
cd /home/ubuntu/pai_training
{
echo "=== start $(date) ==="
timeout 7200 /home/ubuntu/.pixi/bin/pixi run python /home/ubuntu/tools/eval_act.py --model-path /home/ubuntu/checkpoints/train/$NAME --name eval_${NAME//\//_} "$@"
echo "=== done $(date) ==="
} 2>&1 | tee /home/ubuntu/outbox/eval_act.txt
