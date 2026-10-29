#!/bin/bash
# usage: stage2_eval.sh act            ... 段階2のACT(names.conf の S2_ACT30K。積み木2個のデモで学習)で、条件 C → A → B を測る(約30回、約40分)。結果は s2_act2_*.txt(旧ACT=ACT30K の結果 s2_act_*.txt は記録として残す)
#        stage2_eval.sh seen URL TOKEN ... 条件S(SmolVLA。学習に使った配置の再現を、学習と同じ指示と対象を入れ替えた指示で。12回、約40分)。画面の暗記か指示の理解かを分ける
#        stage2_eval.sh vla URL TOKEN  ... ステージ2のSmolVLA(names.conf の S2_SMOLVLA)で、条件 C → A → B を測る(40回)。URL/TOKEN は smolvla_infer.ipynb のセル5の出力
# Gazebo起動後(アームがhome)に実行。途中で止まっても同じコマンドを実行し直せば、終わった条件(outbox に s2_*.txt と [要約] がある)は飛ばす。やり直すときは末尾に fresh を付ける。
# 条件 A=赤+青(指示だけ替える) B=黄色(未学習の色)が対象・赤が妨害物 C=青1個。配置は ACT と SmolVLA で同じ(seed 2000)。
mkdir -p /home/ubuntu/outbox
O=/home/ubuntu/outbox
D=/home/ubuntu/tools
. $D/names.conf || { echo 'names.conf がありません'; exit 1; }
KIND=$1; shift
FK=$KIND; [ "$KIND" = act ] && FK=act2        # ACT の結果ファイルは s2_act2_*.txt(旧ACTの s2_act_*.txt を上書きしない)
FRESH=0; ARGS=()
for x in "$@"; do if [ "$x" = "fresh" ]; then FRESH=1; else ARGS+=("$x"); fi; done
if [ "$KIND" = "act" ]; then
  M=$S2_ACT30K; EXTRA=(--te)
elif [ "$KIND" = "vla" ] || [ "$KIND" = "seen" ]; then
  URL=${ARGS[0]}; TOKEN=${ARGS[1]}
  [ -n "$URL" ] && [ -n "$TOKEN" ] || { echo 'usage: stage2_eval.sh vla|seen URL TOKEN'; exit 1; }
  M=$S2_SMOLVLA; EXTRA=(--smolvla --server-url "$URL" --token "$TOKEN")
else
  echo 'usage: stage2_eval.sh act | stage2_eval.sh vla|seen URL TOKEN'; exit 1
fi
[ $FRESH = 1 ] && rm -f $O/s2_${FK}_*.txt
done_stage() { grep -qs "\[要約\]" "$1"; }
SCN=(C A B); [ "$KIND" = seen ] && SCN=(S)
for S in "${SCN[@]}"; do
  f=$O/s2_${FK}_${S}.txt
  if done_stage $f; then echo "######## 条件$S: 終わっているので飛ばします"; continue; fi
  echo "######## 条件$S ($KIND, $M) $(date) ########"
  bash $D/eval_act.sh $M "${EXTRA[@]}" --scenario $S --tag s2
  rc=$?
  cp $O/eval_act.txt $f
  if ! done_stage $f; then echo "######## 条件$S が最後まで終わりませんでした(追従確認の失敗など)。上の表示を確かめてから、同じコマンドをもう一度実行してください ########"; exit 2; fi
done
echo "######## 完了 ($(date)) ########"
for S in "${SCN[@]}"; do grep -h "\[要約\]\|内訳" $O/s2_${FK}_$S.txt; done
