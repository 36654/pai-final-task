#!/bin/bash
# SmolVLA用の別仮想環境を作り、読み込み・推論時間(CPU)・データ形式を確認する。pai_training には触らない。
mkdir -p /home/ubuntu/outbox /home/ubuntu/venvs
OUT=/home/ubuntu/outbox/smolvla_env.txt
V=/home/ubuntu/venvs/smolvla
{
echo "=== system python ==="
/usr/bin/python3 --version
if [ ! -x $V/bin/python ]; then
  echo "=== create venv ==="
  /usr/bin/python3 -m venv $V || {
    echo "venv失敗 -> virtualenv で代替"
    /usr/bin/python3 -m pip install --user virtualenv
    /usr/bin/python3 -m virtualenv $V
  }
fi
if [ ! -f $V/.install_ok ]; then
  echo "=== install (初回のみ・数分〜十数分) ==="
  $V/bin/pip install -U pip
  $V/bin/pip install torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cpu \
   && $V/bin/pip install "lerobot[smolvla]==0.3.3" \
   && touch $V/.install_ok
fi
if [ ! -f $V/.install_ok ]; then
  echo "RESULT: インストール失敗。上のエラーを貼ってください"
  exit 0
fi
echo "=== probe ==="
$V/bin/python /home/ubuntu/tools/smolvla_probe.py
} 2>&1 | tee $OUT
