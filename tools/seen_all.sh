#!/bin/bash
# usage: seen_all.sh [URL TOKEN] [fresh]   Gazebo起動後(アームがhome)に実行。学習に使った最初の10配置の再現(seen)を、ACT 30,000版・80,000版、(URL TOKEN があれば)SmolVLA で測る。
# 途中で止まっても、もう一度実行すれば、終わった段階(outbox に seen_*.txt と [要約] がある)は飛ばす。やり直すときは fresh を付ける。
mkdir -p /home/ubuntu/outbox
O=/home/ubuntu/outbox
D=/home/ubuntu/tools
. $D/names.conf || { echo 'names.conf がありません'; exit 1; }
ARGS=("$@"); FRESH=0
for x in "${ARGS[@]}"; do [ "$x" = "fresh" ] && FRESH=1; done
[ $FRESH = 1 ] && rm -f $O/seen_*.txt
URL=""; TOKEN=""
[ -n "$1" ] && [ "$1" != "fresh" ] && URL=$1
[ -n "$2" ] && [ "$2" != "fresh" ] && TOKEN=$2
done_stage() { grep -qs "\[要約\]" "$1"; }
stage() {
  local f=$1 title=$2 src=$3; shift 3
  if done_stage $O/$f; then echo "######## $title: 終わっているので飛ばします"; else
    echo "######## $title ($(date)) ########"
    "$@"
    cp $O/$src $O/$f
  fi
}
stage seen_1_act30k.txt "1/3 ACT 30,000ステップ版(学習配置の再現)" eval_act.txt bash $D/eval_act.sh $ACT30K --n 10 --replay $DATA --te --tag r1
stage seen_2_act80k.txt "2/3 ACT 80,000ステップ版(学習配置の再現)" eval_act.txt bash $D/eval_act.sh $ACT80K --n 10 --replay $DATA --te --tag r1
if [ -n "$URL" ] && [ -n "$TOKEN" ]; then
  stage seen_3_smolvla.txt "3/3 SmolVLA(学習配置の再現)" eval_act.txt bash $D/eval_act.sh $SMOLVLA --smolvla --server-url "$URL" --token "$TOKEN" --n 10 --replay $DATA --tag r1
else
  echo "######## 3/3 SmolVLA: URL と TOKEN が無いので飛ばします ########"
fi
echo "######## 完了 ($(date)) ########"
