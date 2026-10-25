#!/bin/bash
# usage: expert_video.sh NAME [件数=4] [倍速=2] [--failures]   記録済みのデモから確認用の動画を作る(シミュレーションは不要)
mkdir -p /home/ubuntu/outbox
cd /home/ubuntu/tools
python3 /home/ubuntu/tools/expert_video.py "$@" 2>&1 | tee /home/ubuntu/outbox/expert_video.txt
