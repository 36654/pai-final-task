#!/bin/bash
# usage: traj_dump.sh [NAME ...]  eval_act が記録した指令と関節角の時系列を出す(Gazebo不要・何も変更しない)。学習配置の再現(r1)があれば、専門家のデモと並べる。
mkdir -p /home/ubuntu/outbox
cd /home/ubuntu/pai_training
/home/ubuntu/.pixi/bin/pixi run python /home/ubuntu/tools/traj_dump.py "$@" 2>&1 | grep -v -E 'WARN|│|╭|╰|help:|aarch64|system-requirements' | tee /home/ubuntu/outbox/traj_dump.txt
