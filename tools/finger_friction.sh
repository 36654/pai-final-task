#!/bin/bash
# usage: finger_friction.sh [MU=1.5] [--restore]   ロボットの摩擦係数を書き換える(起動し直しで反映)
mkdir -p /home/ubuntu/outbox
python3 /home/ubuntu/tools/finger_friction.py "$@" 2>&1 | tee /home/ubuntu/outbox/finger_friction.txt
