#!/bin/bash
# usage: act_close.sh [モデル名に含まれる文字列]   ACT の段階2A/2B で、手を閉じた位置が対象・もう一方・中間のどれかを調べる(Gazebo不要・何も変更しない・数秒)。結果は outbox/act_close.txt
mkdir -p /home/ubuntu/outbox
python3 /home/ubuntu/tools/act_close.py "$@" 2>&1 | tee /home/ubuntu/outbox/act_close.txt
