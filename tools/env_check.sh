#!/bin/bash
# usage: env_check.sh [チェックポイントのパス]   環境の確認だけ(何も変更しない)。評価・デモ生成の開始時に自動で行う確認(tools/env_gate.py)と同じもの。結果は outbox/env_check.txt
mkdir -p /home/ubuntu/outbox
python3 /home/ubuntu/tools/env_gate.py --no-fix "$@" 2>&1 | tee /home/ubuntu/outbox/env_check.txt
