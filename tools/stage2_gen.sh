#!/bin/bash
# usage: stage2_gen.sh [N | convert | pair | pairconvert]   Gazebo起動後(アームがhome)に実行。
#   (なし/N)    ステージ2のデモ(積み木2個・言語指示つき)を生成し、LeRobot形式に変換する。N=試行数(既定155)。色は赤・青・緑から毎回異なる2色。データ名は names.conf の S2DATA
#   convert     生成は済んでいて、変換だけやり直す(S2DATA)
#   pair        既存のデモ(S2DATA)と同じ配置・同じ色で、対象だけ入れ替えたデモ(もう一方の積み木を箱に入れる)を作り、元のデモと合わせた新しいデータ(S2PAIR)にして変換する(約2.4時間)
#   pairconvert pair の変換だけやり直す(S2PAIR)
#   mix         S2PAIR のデモ + ステージ1の単一ブロックのデモ(DATA)を、リンクで取り込んで新しいデータ(S2MIX)にして変換する(Gazebo不要。約10分)
#   mixconvert  mix の変換だけやり直す(S2MIX)
# どれも、同名のデータが既にあれば上書きせずに止まる。生成は、最初の10件の成功率が70%未満なら自動停止。
D=/home/ubuntu/tools
O=/home/ubuntu/outbox
. $D/names.conf || { echo 'names.conf がありません'; exit 1; }
MODE=gen; N=155
case "$1" in
  convert) MODE=convert;;
  pair) MODE=pair;;
  pairconvert) MODE=pairconvert;;
  mix) MODE=mix;;
  mixconvert) MODE=mixconvert;;
  '') ;;
  *) N=$1;;
esac
SRC=$S2DATA; NAME=$S2DATA
if [ "$MODE" = pair ] || [ "$MODE" = pairconvert ]; then NAME=$S2PAIR; fi
if [ "$MODE" = mix ] || [ "$MODE" = mixconvert ]; then NAME=$S2MIX; fi
NPZ=/home/ubuntu/dataset/expert_npz/$NAME
LR=/home/ubuntu/dataset/lerobot_dataset/$NAME
SNPZ=/home/ubuntu/dataset/expert_npz/$SRC
mkdir -p $O
if [ "$MODE" = convert ] || [ "$MODE" = pairconvert ] || [ "$MODE" = mixconvert ]; then
  # 生成は済んでいて、変換だけやり直す(デモは作り直さない)。LeRobot側が既にあれば止まる
  if [ -d "$LR" ]; then echo "STOP: $LR が既にあります(上書きしません)" | tee $O/stage2_gen.txt; exit 1; fi
  if ! ls $NPZ/ep_*.npz >/dev/null 2>&1; then echo "STOP: $NPZ にデモがありません" | tee $O/stage2_gen.txt; exit 1; fi
  echo "=== 変換のみ(デモは再利用): $NAME ($(date)) ==="
else
  if ls $NPZ/ep_*.npz >/dev/null 2>&1 || [ -d "$LR" ]; then
    echo "STOP: $NAME は既にあります(上書きしません)。生成は済んでいて変換だけ必要なら: stage2_gen_WRITE.bat convert(pair の場合は pairconvert)" | tee $O/stage2_gen.txt; exit 1
  fi
  if [ "$MODE" = mix ]; then
    PNPZ=/home/ubuntu/dataset/expert_npz/$S2PAIR; ONPZ=/home/ubuntu/dataset/expert_npz/$DATA
    if ! ls $PNPZ/ep_*.npz >/dev/null 2>&1; then echo "STOP: $PNPZ がありません" | tee $O/stage2_gen.txt; exit 1; fi
    if ! ls $ONPZ/ep_*.npz >/dev/null 2>&1; then echo "STOP: ステージ1のデモ $ONPZ がありません(コンテナ内に無い)" | tee $O/stage2_gen.txt; exit 1; fi
    mkdir -p $NPZ
    for f in $PNPZ/ep_*; do ln -s "$f" "$NPZ/$(basename $f)"; done                      # 元のデモは複製せず、リンクで取り込む(元のデータは変更しない)
    for f in $ONPZ/ep_*; do b=$(basename $f); ln -s "$f" "$NPZ/ep_s1r_${b#ep_}"; done   # ステージ1のデモは名前に s1r を付けて衝突を避ける
    echo "=== ステージ2c 混合データ: $NAME ($S2PAIR $(ls $PNPZ/ep_*.npz | wc -l) 件 + $DATA $(ls $ONPZ/ep_*.npz | wc -l) 件、リンクで取り込み) ($(date)) ==="
  elif [ "$MODE" = pair ]; then
    if ! ls $SNPZ/ep_*.npz >/dev/null 2>&1; then echo "STOP: 元のデモ $SNPZ がありません" | tee $O/stage2_gen.txt; exit 1; fi
    mkdir -p $NPZ
    for f in $SNPZ/ep_*; do ln -s "$f" "$NPZ/$(basename $f)"; done        # 元のデモは複製せず、リンクで取り込む(元のデータは変更しない)
    NSRC=$(ls $NPZ/ep_*.npz | wc -l)
    echo "=== ステージ2 入れ替えデモ: $NAME(元 $SRC の $NSRC 件をリンクで取り込み、対象を入れ替えた $NSRC 件を追加) ($(date)) ==="
    bash $D/expert_episode.sh $NSRC --swap-of $SRC --name $NAME --seed 0 --no-side --abort-after 10 --abort-below 0.7
  else
    echo "=== ステージ2 生成: $NAME 試行 $N 件 ($(date)) ==="
    bash $D/expert_episode.sh $N --colors red,blue,green --name $NAME --seed 0 --no-side --abort-after 10 --abort-below 0.7
  fi
  if [ "$MODE" != mix ]; then
  cp $O/expert_episode.txt $O/stage2_gen_expert.txt
  if grep -q "自動停止" $O/stage2_gen_expert.txt; then
    echo "STOP: 最初の10件の成功率が基準未満で止まりました。$O/stage2_gen_expert.txt を確かめてください" | tee $O/stage2_gen.txt; exit 3
  fi
  if ! grep -q "要約" $O/stage2_gen_expert.txt; then
    echo "STOP: 生成が最後まで終わっていません。同じ名前のデモが途中まで $NPZ に残っています(上書きしません)" | tee $O/stage2_gen.txt; exit 4
  fi
  fi
fi
NEP=$(ls $NPZ/ep_*.npz 2>/dev/null | wc -l)
if [ "$NEP" -lt 100 ]; then echo "STOP: 成功したデモが $NEP 件しかありません(100件未満)" | tee $O/stage2_gen.txt; exit 5; fi
echo "=== LeRobot形式に変換: $NEP 件 ($(date)) ==="
bash $D/make_dataset.sh $NAME
cp $O/make_dataset.txt $O/stage2_gen_convert.txt
python3 - <<PY | tee $O/stage2_gen.txt
import json, glob, collections
n = "$NAME"
c = collections.Counter(); w = 0; tot = 0
for f in sorted(glob.glob("$NPZ/ep_*.json")):
    j = json.load(open(f)); tot += 1
    c[(j.get('target_color'), j.get('distractor_color'))] += 1
    w += 1 if j.get('wrong_block') else 0
print('デモ:', tot, '件 / 対象・妨害物の組み合わせ別:', dict(c))
sc = collections.defaultdict(set)
for f in sorted(glob.glob("$NPZ/ep_*.json")):
    j = json.load(open(f)); d = j.get('distractor')
    if d:
        k = frozenset([(j['target_color'], round(j['block_th'], 2), round(j['block_r'], 4)), (j['distractor_color'], round(d['th'], 2), round(d['r'], 4))])
        sc[k].add(j['target_color'])
print('同じ画面で対象が2通りあるデモの組(画面の数 %d 中)・対になった画面: %d' % (len(sc), sum(1 for v in sc.values() if len(v) == 2)))
t = [json.loads(l) for l in open("/home/ubuntu/dataset/lerobot_dataset/%s/meta/tasks.jsonl" % n)]
info = json.load(open("/home/ubuntu/dataset/lerobot_dataset/%s/meta/info.json" % n))
print('LeRobot: episodes', info.get('total_episodes'), 'frames', info.get('total_frames'))
print('指示文:', [x['task'] for x in t])
ok = info.get('total_episodes') == tot and len(t) == 3
print('RESULT=OK' if ok else 'RESULT=CHECK(エピソード数または指示文の数が合いません)')
PY
