#!/usr/bin/env python3
"""expert_episode.py が作った ep_*.npz を LeRobotDataset v2.1 に変換する(成功した試行だけ)。"""
import argparse, json, shutil
from pathlib import Path
import numpy as np

IMG_KEY = 'observation.images.overhead'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz-dir', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--repo-id', required=True)
    ap.add_argument('--task', default='put the red block in the box')
    ap.add_argument('--fps', type=int, default=20)
    ap.add_argument('--overwrite', action='store_true')
    a = ap.parse_args()
    import torch
    from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
    src = Path(a.npz_dir); out = Path(a.output_dir)
    eps = sorted(src.glob('ep_*.npz'))
    if not eps:
        raise SystemExit('npz がありません: ' + str(src))
    if out.exists():
        if not a.overwrite:
            raise SystemExit(str(out) + ' が既にあります(--overwrite)')
        shutil.rmtree(out)
    ds = None; saved = 0
    for ep in eps:
        meta = json.load(open(ep.with_suffix('.json')))
        if not meta.get('success'):
            print('skip (失敗):', ep.name); continue
        task = meta.get('task') or a.task                      # ステージ2: エピソードごとの言語指示(json の task)。無ければ --task(ステージ1はこちら)
        d = np.load(ep)
        img, state, action = d['img'], d['state'], d['action']
        if ds is None:
            h, w, _ = img[0].shape
            names = ['joint1', 'joint2', 'joint3', 'joint4', 'gripper']
            feats = {'observation.state': {'dtype': 'float32', 'shape': (5,), 'names': names},
                     IMG_KEY: {'dtype': 'video', 'shape': (h, w, 3), 'names': ['height', 'width', 'channel']},
                     'action': {'dtype': 'float32', 'shape': (5,), 'names': names}}
            ds = LeRobotDataset.create(repo_id=a.repo_id, fps=a.fps, root=out, robot_type='crane_plus', features=feats, use_videos=True)
        for i in range(len(img)):
            ds.add_frame({'observation.state': torch.from_numpy(state[i].astype(np.float32)), IMG_KEY: img[i],
                          'action': torch.from_numpy(action[i].astype(np.float32)), 'task': task})
        ds.save_episode(); saved += 1
        print('saved', ep.name, len(img), 'frames', '|', task, flush=True)
    print('done: %d エピソード -> %s' % (saved, out))


if __name__ == '__main__':
    main()
