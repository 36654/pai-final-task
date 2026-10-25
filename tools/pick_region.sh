#!/bin/bash
# usage: pick_region.sh SRC DST [オプション]
cd /home/ubuntu/tools
python3 pick_region.py "$@" 2>&1 | tee /home/ubuntu/outbox/pick_region.txt
