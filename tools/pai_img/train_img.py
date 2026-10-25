#!/usr/bin/env python3
"""Train ACT on a LeRobot dataset made by rosbag2lerobot_img.py (state + overhead image)."""
import argparse
import json
import time
from pathlib import Path

import torch
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset, LeRobotDatasetMetadata
from lerobot.common.datasets.utils import dataset_to_policy_features
from lerobot.common.policies.act.configuration_act import ACTConfig
from lerobot.common.policies.act.modeling_act import ACTPolicy
from lerobot.configs.types import FeatureType


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset-root', required=True)
    ap.add_argument('--repo-id', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--steps', type=int, default=300)
    ap.add_argument('--batch-size', type=int, default=4)
    ap.add_argument('--chunk-size', type=int, default=20)
    ap.add_argument('--n-action-steps', type=int, default=10)
    ap.add_argument('--lr', type=float, default=1e-5)
    ap.add_argument('--num-workers', type=int, default=2)
    ap.add_argument('--save-every', type=int, default=1000)
    ap.add_argument('--exclude-episodes', default='', help='comma separated episode indexes kept out of training')
    ap.add_argument('--wandb', action='store_true')
    a = ap.parse_args()
    assert a.n_action_steps <= a.chunk_size

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('device:', device)
    root = Path(a.dataset_root)
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)

    meta = LeRobotDatasetMetadata(a.repo_id, root=root)
    fps = meta.fps
    feats = {k: v for k, v in meta.features.items() if k == 'action' or k.startswith('observation')}
    pf = dataset_to_policy_features(feats)
    out_f = {k: v for k, v in pf.items() if v.type is FeatureType.ACTION}
    in_f = {k: v for k, v in pf.items() if k not in out_f}
    print('inputs :', list(in_f.keys()))
    print('outputs:', list(out_f.keys()))

    cfg = ACTConfig(input_features=in_f, output_features=out_f,
                    chunk_size=a.chunk_size, n_action_steps=a.n_action_steps)
    policy = ACTPolicy(cfg, dataset_stats=meta.stats)
    policy.train()
    policy.to(device)

    exclude = {int(x) for x in a.exclude_episodes.split(',') if x.strip()}
    eps = [i for i in range(meta.total_episodes) if i not in exclude]
    print(f'training episodes: {len(eps)} (excluded: {sorted(exclude)})')
    dataset = LeRobotDataset(a.repo_id, root=root, episodes=eps,
                             delta_timestamps={'action': [i / fps for i in range(a.chunk_size)]})
    dl = torch.utils.data.DataLoader(dataset, batch_size=a.batch_size, shuffle=True,
                                     num_workers=a.num_workers, drop_last=True,
                                     pin_memory=device.type == 'cuda')
    try:
        params = policy.get_optim_params()
    except AttributeError:
        params = policy.parameters()
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=1e-4)

    if a.wandb:
        import wandb
        wandb.init(project='pai_crane_gazebo', config=vars(a))

    (out / 'train_args.json').write_text(json.dumps(vars(a), indent=2))
    step = 0
    t0 = time.time()
    while step < a.steps:
        for batch in dl:
            batch = {k: (v.to(device) if isinstance(v, torch.Tensor) else v) for k, v in batch.items()}
            loss, _ = policy.forward(batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 10.0)
            opt.step()
            opt.zero_grad()
            step += 1
            if step == 1 or step % 10 == 0:
                el = time.time() - t0
                print(f'step {step}/{a.steps} loss {loss.item():.3f}  {el / step:.2f}s/step', flush=True)
                if a.wandb:
                    wandb.log({'loss': loss.item(), 'step': step})
            if step % a.save_every == 0:
                policy.save_pretrained(out)
            if step >= a.steps:
                break
    policy.save_pretrained(out)
    print('saved ->', out)


if __name__ == '__main__':
    main()
