#!/usr/bin/env python3
# 使い方: pick_region.py SRC DST [--block-th -90 -30] [--box-th 30 80] [--skip 103 ...]
# [--append] [--max N]: DST が既にあるとき、その続きの番号から追加する(最大 N 件)。
# SRC(expert_npz の下のデータ名)から、成功していて、積み木と箱の角度が範囲内の件だけを、DST に連番でコピーする(元は変えない)。
# DST が既にあるときは中止する。そのあと expert_episode.bat N --name DST --seed 別の値 で続きを足すと、既存の件数の続きから作る。
import argparse, glob, json, os, shutil, sys
BASE = '/home/ubuntu/dataset/expert_npz'
ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--block-th', type=float, nargs=2, default=[-90, -30])
ap.add_argument('--box-th', type=float, nargs=2, default=[30, 80])
ap.add_argument('--append', action='store_true', help='DST が既にあるとき、続きの番号から追加する')
ap.add_argument('--max', type=int, default=None, help='コピーする最大件数')
ap.add_argument('--skip', type=int, nargs='*', default=[], help='範囲内でも除く、元の通し番号(追従誤差が極端だった件など)')
a = ap.parse_args()
src, dst = os.path.join(BASE, a.src), os.path.join(BASE, a.dst)
exist = len([f for f in os.listdir(dst) if f.endswith('.npz')]) if os.path.exists(dst) else 0
if exist and not a.append:
    sys.exit('中止: %s は既にあります(%d 件)。続きに足すなら --append を付ける。別の名前にするか、先に消してもよい' % (dst, exist))
os.makedirs(dst, exist_ok=True)
n = exist; tot = 0
for jf in sorted(glob.glob(os.path.join(src, 'ep_*.json'))):
    k = int(os.path.basename(jf)[3:7]); m = json.load(open(jf)); tot += 1
    if not m.get('success', True) or k in a.skip:
        continue
    if not (a.block_th[0] <= m['block_th'] <= a.block_th[1] and a.box_th[0] <= m['box_th'] <= a.box_th[1]):
        continue
    if a.max is not None and n - exist >= a.max:
        break
    for ext in ('.npz', '.json', '_side.mp4'):
        f = os.path.join(src, 'ep_%04d%s' % (k, ext))
        if os.path.exists(f):
            shutil.copy2(f, os.path.join(dst, 'ep_%04d%s' % (n, ext)))
    n += 1
print('%s の %d 件を調べ、範囲内の %d 件を %s にコピーしました(追加後の合計。積み木 %s° / 箱 %s°、除外した通し番号 %s)' % (a.src, tot, n, a.dst, a.block_th, a.box_th, a.skip))
