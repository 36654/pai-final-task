#!/bin/bash
# usage: smolvla_all.sh URL TOKEN [fresh]   Gazebo起動後(アームがhome)、Colab の推論サーバー(smolvla_infer.ipynb)を立てたうえで実行する。約2時間、途中の操作は不要。
#  1) SmolVLA を ACT と同じ20配置(seed 2000)で  2) SmolVLA を 格子15配置(θ×yaw)で  3) 専門家を 1) と同じ20配置で(上限)  4) 表・握りの座標
# 途中で止まっても、同じコマンドでもう一度実行すれば、終わった段階(outbox に smolvla_*.txt と [要約] がある)は飛ばす。やり直すときは fresh を付ける。
URL=$1; TOKEN=$2
mkdir -p /home/ubuntu/outbox
O=/home/ubuntu/outbox
D=/home/ubuntu/tools
[ "$3" = "fresh" ] && rm -f $O/smolvla_*.txt
done_stage() { grep -qs "\[要約\]" "$1"; }
stage() {
  local f=$1 title=$2 src=$3; shift 3
  if done_stage $O/$f; then echo "######## $title: 終わっているので飛ばします"; else
    echo "######## $title ($(date)) ########"
    "$@"
    cp $O/$src $O/$f
  fi
}
. $D/names.conf || { echo 'names.conf がありません'; exit 1; }
M=$SMOLVLA
stage smolvla_1_main20.txt "1/4 SmolVLA(ACTと同じ20配置)" eval_act.txt bash $D/eval_act.sh $M --smolvla --server-url "$URL" --token "$TOKEN" --n 20 --tag m1
stage smolvla_2_grid.txt "2/4 SmolVLA(格子15配置)" eval_act.txt bash $D/eval_act.sh $M --smolvla --server-url "$URL" --token "$TOKEN" --n 15 --grid --tag g1
stage smolvla_3_expert20.txt "3/4 専門家(1)と同じ20配置)" expert_episode.txt bash $D/expert_episode.sh 20 --probe --seed 2000 --no-side --keep-failures --name probe_ref_m1_$(date +%H%M)
echo "######## 4/4 集計 ($(date)) ########"
python3 $D/grid_report.py | tee $O/smolvla_4_grid_report.txt
bash $D/trace_stats.sh eval_s1_region_smolvla_final_e50_m1 eval_s1_region_smolvla_final_e50_g1
cp $O/trace_stats.txt $O/smolvla_5_trace_stats.txt
echo "######## 完了 ($(date)) ########"
