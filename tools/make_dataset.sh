#!/bin/bash
# usage: make_dataset.sh NAME ["task text"]   expert_episode が作った npz を LeRobot 形式に変換する
NAME=$1
TASK=${2:-put the red block in the box}
cd /home/ubuntu/pai_training
/home/ubuntu/.pixi/bin/pixi run python /home/ubuntu/tools/pai_img/npz2lerobot.py \
  --npz-dir /home/ubuntu/dataset/expert_npz/$NAME \
  --output-dir /home/ubuntu/dataset/lerobot_dataset/$NAME \
  --repo-id $NAME --task "$TASK" --overwrite 2>&1 | tee /home/ubuntu/outbox/make_dataset.txt
