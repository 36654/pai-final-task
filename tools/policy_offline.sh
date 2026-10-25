#!/bin/bash
# usage: policy_offline.sh [チェックポイント名(既定 s1_region)] [デモ番号 ...]   Gazebo不要・何も変更しない。
mkdir -p /home/ubuntu/outbox
cd /home/ubuntu/pai_training
/home/ubuntu/.pixi/bin/pixi run python /home/ubuntu/tools/policy_offline.py "$@" 2>&1 | grep -v -E 'WARN|│|╭|╰|help:|aarch64|system-requirements' | tee /home/ubuntu/outbox/policy_offline.txt
