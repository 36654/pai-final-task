"""Gazebo なしの確認: 学習デモの画像と関節角(正解の観測)を、評価と同じ読み込み・同じ時間アンサンブル(毎コマ予測)で ACT に入れ、
出てきた指令を専門家の指令と比べる。ここで大きくずれるなら、方策か読み込み側(ライブラリ)の問題。ずれないなら、評価中の入力(画像・関節角)が学習時と違う。"""
import glob, json, os, shutil, sys, tempfile, time
import numpy as np, torch
NPZ = '/home/ubuntu/dataset/expert_npz/s1_region'
name = sys.argv[1] if len(sys.argv) > 1 else 's1_region'
eps = [int(x) for x in (sys.argv[2:] or ['0', '1', '2'])]
mp = '/home/ubuntu/checkpoints/train/' + name
tmp = os.path.join(tempfile.gettempdir(), 'act_off_' + name)
shutil.rmtree(tmp, ignore_errors=True); shutil.copytree(mp, tmp)
cp = os.path.join(tmp, 'config.json'); cfg = json.load(open(cp))
cfg['type'] = 'act'; cfg['device'] = 'cpu'; cfg['temporal_ensemble_coeff'] = 0.01; cfg['n_action_steps'] = 1
json.dump(cfg, open(cp, 'w'), indent=2)
import lerobot
from lerobot.common.policies.act.modeling_act import ACTPolicy
print('torch', torch.__version__, '/ lerobot', getattr(lerobot, '__version__', '?'), '/ checkpoint', name)
pol = ACTPolicy.from_pretrained(tmp); pol.eval(); pol.to('cpu')
feats = getattr(pol.config, 'image_features', None) or {}
key = next(iter(feats.keys()), 'observation.images.overhead'); print('image key:', key, ' chunk', pol.config.chunk_size)
T = [0, 10, 20, 40, 60, 80, 100, 140, 180, 240, 300]
for e in eps:
    z = np.load(os.path.join(NPZ, 'ep_%04d.npz' % e)); img = z['img']; st = z['state'].astype(np.float32); act = z['action'].astype(np.float64)
    pol.reset(); pred = []; t0 = time.time()
    for k in range(len(img)):
        obs = {'observation.state': torch.from_numpy(st[k]).unsqueeze(0),
               key: torch.from_numpy(img[k]).permute(2, 0, 1).float().div(255.0).unsqueeze(0)}
        with torch.no_grad(): pred.append(pol.select_action(obs).cpu().numpy().flatten().astype(np.float64))
    pred = np.array(pred); err = np.degrees(np.abs(pred - act))
    print('\n--- 学習デモ ep_%04d (%d コマ, %.0f 秒)  指令の誤差(度) 平均 j1..j4,手: %s  最大: %s' % (e, len(img), time.time() - t0, np.round(err.mean(axis=0), 1), np.round(err.max(axis=0), 1)))
    for k in [t for t in T if t < len(img)]:
        print('   %3d: 方策 %s | 専門家 %s' % (k, np.round(np.degrees(pred[k]), 0).astype(int), np.round(np.degrees(act[k]), 0).astype(int)))
