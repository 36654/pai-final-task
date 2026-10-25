#!/bin/bash
# usage: vla_diag.sh URL TOKEN [データ名]   SmolVLA の診断(Gazebo不要・何も変更しない。約5分)。結果は outbox/vla_diag.txt
mkdir -p /home/ubuntu/outbox
python3 /home/ubuntu/tools/vla_diag.py "$@" 2>&1 | tee /home/ubuntu/outbox/vla_diag.txt
