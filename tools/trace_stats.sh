#!/bin/bash
# usage: trace_stats.sh [NAME]   eval_act が記録した指令を、専門家のデモと比べる(Gazebo不要)
mkdir -p /home/ubuntu/outbox
cd /home/ubuntu/pai_training
/home/ubuntu/.pixi/bin/pixi run python /home/ubuntu/tools/trace_stats.py "$@" 2>&1 | grep -v "WARN\|system-requirements\|╭\|│\|╰\|help:\|\"my-linux" | tee /home/ubuntu/outbox/trace_stats.txt
