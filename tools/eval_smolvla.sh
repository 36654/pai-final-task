#!/bin/bash
# usage: eval_smolvla.sh NAME [eval_act.py の引数]   例: eval_smolvla.sh s1_region_smolvla/final --n 10 --exec-steps 50
# Gazebo起動後(アームがhome)に実行。SmolVLA の推論サーバー(別の仮想環境)を起動し、eval_act.py(ACT と同じ配置・同じ判定)で評価する。
V=/home/ubuntu/venvs/smolvla
if [[ " $* " == *" --server-url "* ]]; then       # Colab の GPU 推論サーバーを使う(ローカルの環境づくり・モデルは不要)
  mkdir -p /home/ubuntu/outbox
  bash /home/ubuntu/tools/eval_act.sh "$1" --smolvla "${@:2}"
  exit 0
fi
mkdir -p /home/ubuntu/outbox /home/ubuntu/venvs
NAME=$1
MP=/home/ubuntu/checkpoints/train/$NAME
if [ ! -f $MP/config.json ]; then echo "モデルがありません: $MP (xfer_WRITE.bat in ckpt 名前 を実行しましたか)"; exit 1; fi
if [ ! -f $V/.install_ok ]; then
  echo "=== SmolVLA用の環境を作ります (初回のみ 10〜20分) ==="
  [ -x $V/bin/python ] || /usr/bin/python3 -m venv $V || { /usr/bin/python3 -m pip install --user virtualenv; /usr/bin/python3 -m virtualenv $V; }
  $V/bin/pip install -U pip
  $V/bin/pip install torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cpu \
   && $V/bin/pip install "lerobot[smolvla]==0.3.3" && touch $V/.install_ok
fi
if [ ! -f $V/.install_ok ]; then echo "環境の作成に失敗しました。上のエラーを貼ってください"; exit 1; fi
pkill -f "[s]molvla_server.py"; sleep 1
LOG=/tmp/smolvla_server.log
setsid nohup $V/bin/python /home/ubuntu/tools/smolvla_server.py --model-path $MP --port 6010 > $LOG 2>&1 &
SP=$!
echo "推論サーバーを起動しています(モデルの読み込みに数分かかります)"
for i in $(seq 1 120); do
  grep -q "^READY" $LOG && break
  if ! kill -0 $SP 2>/dev/null; then echo "推論サーバーが落ちました:"; tail -30 $LOG; cp $LOG /home/ubuntu/outbox/smolvla_server.txt; exit 1; fi
  sleep 5
done
grep -q "^READY" $LOG || { echo "推論サーバーが10分たっても準備できません:"; tail -30 $LOG; cp $LOG /home/ubuntu/outbox/smolvla_server.txt; pkill -f "[s]molvla_server.py"; exit 1; }
cat $LOG | grep -v "^READY" | tail -20
bash /home/ubuntu/tools/eval_act.sh $NAME --smolvla --port 6010 "${@:2}"
cp $LOG /home/ubuntu/outbox/smolvla_server.txt
pkill -f "[s]molvla_server.py"
