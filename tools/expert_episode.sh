#!/bin/bash
# Gazebo起動後(アームがhome)に実行。専門家のデモを生成して記録する。例: expert_episode.sh 3 --name test
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
mkdir -p /home/ubuntu/outbox
pkill -f "[p]arameter_bridge"
sleep 1
BR=('/overhead_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image')
# 正面カメラ(動画用)は、橋渡しをしなければ購読者がなく、描画されない可能性が高い(--no-side のとき橋渡しをやめて、描画の負荷を避ける)
if [[ " $* " != *" --no-side "* ]]; then BR+=('/side_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image'); fi
setsid nohup ros2 run ros_gz_bridge parameter_bridge "${BR[@]}" > /tmp/bridge.log 2>&1 &
sleep 3
cd /home/ubuntu/tools
{
echo "=== start $(date) ==="
timeout 14400 python3 /home/ubuntu/tools/expert_episode.py "$@"
echo "=== done $(date) ==="
} 2>&1 | tee /home/ubuntu/outbox/expert_episode.txt
