# SmolVLA の推論サーバー(別の仮想環境 venvs/smolvla で動かす。lerobot 0.3.3)。
# eval_act.py(--smolvla)が、画像・状態・言語指示を送り、行動の塊(50コマ×5関節、正規化を戻した値)を受け取る。
# usage: smolvla_server.py --model-path DIR [--port 6010] [--device auto] [--flow-steps N]
import argparse, json, os, shutil, sys, tempfile, time, traceback
import numpy as np
import torch
from multiprocessing.connection import Listener


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-path', required=True)
    ap.add_argument('--port', type=int, default=6010)
    ap.add_argument('--device', default='auto')
    ap.add_argument('--flow-steps', type=int, default=0, help='0=学習時の設定(10)のまま。減らすと速いが精度が変わる')
    a = ap.parse_args()
    dev = ('cuda' if torch.cuda.is_available() else 'cpu') if a.device == 'auto' else a.device
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    # 学習側の config.json は device が cuda のことがあるので、書き換えた一時コピーから読む
    tmp = os.path.join(tempfile.gettempdir(), 'smolvla_ckpt_' + os.path.basename(os.path.normpath(a.model_path)))
    shutil.rmtree(tmp, ignore_errors=True); shutil.copytree(a.model_path, tmp)
    cp = os.path.join(tmp, 'config.json'); cfg = json.load(open(cp)); cfg['device'] = dev
    json.dump(cfg, open(cp, 'w'), indent=2)
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    t0 = time.time()
    pol = SmolVLAPolicy.from_pretrained(tmp).to(dev).eval()
    if a.flow_steps > 0:
        pol.config.num_steps = a.flow_steps
        try: pol.model.config.num_steps = a.flow_steps
        except Exception: pass
    c = pol.config
    img_key = next(iter(c.image_features.keys()))
    print('読み込み %.1f 秒 / device=%s / 画像キー=%s / 入力=%s / 出力=%s / chunk=%d / 流れのステップ数=%s' % (
        time.time() - t0, dev, list(c.image_features.keys()), {k: tuple(v.shape) for k, v in c.input_features.items()},
        {k: tuple(v.shape) for k, v in c.output_features.items()}, c.chunk_size, c.num_steps), flush=True)
    # 正規化の統計が入っているか(平均0・標準偏差1のままなら、学習時の統計が読めていない)
    for n_, b in pol.named_buffers():
        if n_.endswith('mean') or n_.endswith('std'):
            print('  正規化 %s: %s' % (n_, np.round(b.detach().cpu().numpy().flatten()[:6], 3).tolist()), flush=True)

    def infer(img_bytes, h, w, state, task, seed=None):
        img = torch.from_numpy(np.frombuffer(img_bytes, np.uint8).reshape(h, w, 3).copy()).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
        batch = {img_key: img.to(dev), 'observation.state': torch.tensor([state], dtype=torch.float32).to(dev), 'task': [task]}
        if seed is not None:                                  # 流れの出発点の雑音を決まったものにする(再試で同じ入力なら同じ出力)
            torch.manual_seed(int(seed))
            if torch.cuda.is_available(): torch.cuda.manual_seed_all(int(seed))
        with torch.inference_mode():
            return pol.predict_action_chunk(batch).detach().cpu().numpy()[0].astype(np.float32)

    infer(np.zeros((240, 320, 3), np.uint8).tobytes(), 240, 320, [0.0] * c.input_features['observation.state'].shape[0], 'put the red block in the box')    # ならし運転
    t1 = time.time(); ch = infer(np.zeros((240, 320, 3), np.uint8).tobytes(), 240, 320, [0.0] * c.input_features['observation.state'].shape[0], 'put the red block in the box')
    print('ならし運転: 1回の推論 %.2f 秒 / 出力 %s' % (time.time() - t1, ch.shape), flush=True)
    lst = Listener(('127.0.0.1', a.port), authkey=b'pai')
    print('READY', flush=True)
    first = True
    while True:
        conn = lst.accept()
        try:
            while True:
                try: req = conn.recv()
                except EOFError: break
                try:
                    t = time.time()
                    ch = infer(req['img'], req['h'], req['w'], req['state'], req['task'], req.get('seed'))
                    if first:
                        print('最初の要求: 状態=%s 出力の先頭=%s 末尾=%s (%.2f 秒)' % (np.round(req['state'], 3).tolist(), np.round(ch[0], 3).tolist(), np.round(ch[-1], 3).tolist(), time.time() - t), flush=True); first = False
                    conn.send(dict(actions=ch.tobytes(), n=int(ch.shape[0]), dim=int(ch.shape[1]), sec=time.time() - t))
                except Exception:
                    traceback.print_exc(); conn.send(dict(err=traceback.format_exc()[-400:]))
        finally:
            conn.close()


if __name__ == '__main__':
    main()
