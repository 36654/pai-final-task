#!/usr/bin/env python3
"""学習済みACTを、Gazebo上で毎回ちがう配置にして N 回走らせ、成功率を測る(専門家と同じ成功判定)。
使い方: eval_act.py --model-path DIR [--n 10] [--seed 2000] [--block-th -90 -30] [--box-th 30 80] [--name NAME]
配置の乱数は専門家の学習データ(seed 0 系)と別の seed(既定 2000)で作る。専門家が届かない配置は除かれる。"""
import argparse, base64, json, math, os, random, sys, time
import numpy as np
import rclpy
import torch
from sensor_msgs.msg import Image, JointState
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from expert_lib import *
from expert_lib import _call
from expert_episode import sample, grid_cells, load_replay, ROOT as NPZ_ROOT, COLORS, BLK, BOX, DIS, SIZE, INNER, RIM, CARRY_Z
from expert_episode import sample_distractor, task_text, in_box, STAGE2_BLOCK_TH, STAGE2_BLOCK_R, STAGE2_SEP

FPS = 20
ORDER = ARM + HAND
OUTBOX = '/home/ubuntu/outbox'
LIM_J1 = 2.6
GRIP = (-0.6, 0.6)
MAX_STEP = 0.15       # 1コマ(0.05秒)で動かしてよい最大の角度(rad)。専門家の最大は約0.03 rad/コマ。暴走防止の安全弁


def load_policy(model_path, te=False, te_coeff=0.01, exec_n=0):
    """保存済みACTを読む。config.json に "type" が無い(学習側の保存形式)ので、補った一時コピーから読む。device は cpu に固定"""
    import shutil, tempfile
    tmp = os.path.join(tempfile.gettempdir(), 'act_ckpt_' + os.path.basename(os.path.normpath(model_path)))
    shutil.rmtree(tmp, ignore_errors=True); shutil.copytree(model_path, tmp)
    cp = os.path.join(tmp, 'config.json')
    cfg = json.load(open(cp)); cfg['type'] = 'act'; cfg['device'] = 'cpu'
    if te:                                   # 時間方向のアンサンブル: 毎コマ予測して重ね合わせる(再学習は不要)
        cfg['temporal_ensemble_coeff'] = te_coeff; cfg['n_action_steps'] = 1
    elif exec_n:
        cfg['n_action_steps'] = exec_n                       # 時間アンサンブルなし: 1回の予測のうち、先頭から何コマ実行するか
    json.dump(cfg, open(cp, 'w'), indent=2)
    from lerobot.common.policies.act.modeling_act import ACTPolicy
    return ACTPolicy.from_pretrained(tmp)


class Runner(Arm):
    def __init__(self, model_path, side, te=False, vla=None, te_coeff=0.01, exec_n=0):
        super().__init__('eval_act')
        self.vla = vla                                   # None=ACT / dict(port, exec_steps, task)=SmolVLA(別プロセスの推論サーバーに問い合わせる)
        self.q = []; self.vla_skip = []; self.vla_sec = []; self.img_stamp = 0.0; self.ep_i = 0; self.call_i = 0
        if vla:
            if vla.get('url'):
                self.conn = None                                  # Colab の推論サーバーへ HTTP(トークン付き)で問い合わせる
                self._http_check()
            else:
                from multiprocessing.connection import Client
                self.conn = Client(('127.0.0.1', vla['port']), authkey=b'pai')
            self.policy = None
            self.img_key = 'observation.images.overhead'
        else:
            self.policy = load_policy(model_path, te, te_coeff, exec_n); self.policy.eval(); self.policy.to('cpu'); self.policy.reset()
            feats = getattr(self.policy.config, 'image_features', None) or {}
            self.img_key = next(iter(feats.keys()), 'observation.images.overhead')
        self.img = None; self.n_img = 0; self.js = None; self.side = None
        self.cmd = np.array(HOME + [OPEN], dtype=np.float64)
        self.create_subscription(Image, '/overhead_camera/image', self._on_img, 10)
        if side:
            self.create_subscription(Image, '/side_camera/image', self._on_side, 10)
        self.create_subscription(JointState, '/joint_states', self._on_js, 10)
        self.t_inf = []

    def _on_img(self, m):
        if m.encoding == 'rgb8':
            self.img = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3).copy(); self.n_img += 1
            self.img_stamp = m.header.stamp.sec + 1e-9 * m.header.stamp.nanosec        # シミュレーション時間

    def _on_side(self, m):
        if m.encoding == 'rgb8':
            self.side = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3).copy()

    def _on_js(self, m):
        d = dict(zip(m.name, m.position))
        if all(k in d for k in ORDER):
            self.js = np.array([d[k] for k in ORDER], dtype=np.float32)

    def go_home(self, max_sim_sec=15.0):
        """ホームへ戻し、関節が十分に近づくまで待つ。戻れたら True。
        待ち時間は、実時間ではなくシミュレーション時間(俯瞰カメラの画像20枚=1秒)で数える。実時間では、シミュレーションが遅いとき(約0.3倍速)に軌道の途中で打ち切っていた"""
        H4 = np.array(HOME)
        self.cmd = np.array(HOME + [OPEN], dtype=np.float64)
        self.send(self.pa, ARM, HOME, 4.0); self.send(self.pg, HAND, [OPEN], 2.0)
        n0 = self.n_img; t0 = time.time()
        while (self.n_img - n0) < max_sim_sec * FPS and time.time() - t0 < 300:
            rclpy.spin_once(self, timeout_sec=0.05)
            if (self.n_img - n0) > 6 * FPS and self.js is not None and float(np.max(np.abs(self.js[:4].astype(np.float64) - H4))) < 0.1:
                return True
        if self.js is not None:
            print('  ホームからのずれ(度) j1..j4: %s 手: %.0f' % (np.round(np.degrees(self.js[:4].astype(np.float64) - H4), 1), math.degrees(float(self.js[4]))), flush=True)
        return False

    def verify_tracking(self, max_try=8, max_sim_sec=15.0, delta=0.4):
        """開始前の追従確認: ホームから関節1を delta rad だけ動かす指令を出し、実測が追従するか確かめる(確認後はホームへ戻す)。
        go_home はホームにいれば何もせず通ってしまい、腕が指令に追従しない状態を見抜けない。追従するまで最大 max_try 回待つ。追従したら True"""
        H4 = np.array(HOME, dtype=np.float64)
        test = H4.copy(); test[0] += delta
        for k in range(max_try):
            self.send(self.pa, ARM, list(test), 3.0)
            n0 = self.n_img; t0 = time.time(); reached = False
            while (self.n_img - n0) < max_sim_sec * FPS and time.time() - t0 < 300:
                rclpy.spin_once(self, timeout_sec=0.05)
                if (self.n_img - n0) > 3 * FPS and self.js is not None and float(np.max(np.abs(self.js[:4].astype(np.float64) - test))) < 0.1:
                    reached = True; break
            if reached:
                print('  追従確認 OK(関節1を%.0f度動かす指令に実測が追従。試行 %d/%d)' % (math.degrees(delta), k + 1, max_try), flush=True)
                return self.go_home()
            print('  追従確認: 腕が指令に追従しません。待って再送します(%d/%d)' % (k + 1, max_try), flush=True)
        return False

    def reset_policy(self):
        if self.vla: self.q = []; self.call_i = 0
        else: self.policy.reset()

    def _http_req(self, path, payload=None):
        import urllib.request, urllib.error
        url = self.vla['url'].rstrip('/') + path
        for k in range(4):
            try:
                req = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(),
                                             headers={'Content-Type': 'application/json', 'X-Token': self.vla['token'], 'User-Agent': 'pai-eval'})
                with urllib.request.urlopen(req, timeout=180) as r: return json.loads(r.read())
            except urllib.error.HTTPError as ex:
                if ex.code in (403, 404): raise RuntimeError('推論サーバーが拒否しました(%d)。URL とトークンを確認してください' % ex.code)
                err = ex
            except Exception as ex:
                err = ex
            print('  [警告] 推論サーバーとの通信に失敗(%d/4): %s' % (k + 1, err), flush=True); time.sleep(3)
        raise RuntimeError('推論サーバーに接続できません: ' + url)

    def _http_check(self):
        r = self._http_req('/')
        print('推論サーバー(HTTP)につながりました: device=%s chunk=%s' % (r.get('device'), r.get('chunk')), flush=True)

    def _world_pause(self, pause):
        """推論の間だけシミュレーションを止める/再開する(Gazebo の WorldControl)。時間切れがあるので、最大5回やり直す。それでも駄目なら止めて知らせる"""
        out = ''
        for k in range(5):
            out = _call(['ign', 'service', '-s', '/world/default/control', '--reqtype', 'ignition.msgs.WorldControl',
                         '--reptype', 'ignition.msgs.Boolean', '--timeout', '15000', '--req', 'pause: %s' % ('true' if pause else 'false')])
            if 'true' in out: return
            print('  [警告] 一時停止/再開の呼び出しが失敗(%d/5): %s' % (k + 1, out[:80]), flush=True); time.sleep(2)
        raise RuntimeError('シミュレーションの一時停止/再開に失敗: ' + out[:80])

    def _vla_action(self):
        """SmolVLA: 行動の塊(chunk)を推論サーバーに作らせ、exec_steps 個ずつ実行する。
        推論の間もシミュレーションは進むので、経過したコマ数(画像の時刻の差)だけ、塊の先頭を捨てる(古い指令を遅れて実行しない)"""
        if not self.q:
            t_obs, n_obs = self.img_stamp, self.n_img
            img, st = self.img.copy(), self.js.astype(np.float32)
            t1 = time.time()
            if self.vla.get('pause'): self._world_pause(True)          # 推論中はシミュレーションを止める(推論の時間が条件に混ざらないように)
            seed = self.vla['seed'] + 1000 * self.ep_i + self.call_i; self.call_i += 1          # 予測ごとに決まった種(雑音が毎回同じになり、再試で同じ入力なら同じ出力)
            try:
                if self.conn is None:
                    r = self._http_req('/predict', dict(img=base64.b64encode(img.tobytes()).decode(), h=int(img.shape[0]), w=int(img.shape[1]), state=st.tolist(), task=self.vla['task'], seed=seed))
                    if 'err' not in r: r['actions'] = base64.b64decode(r['actions'])
                else:
                    self.conn.send(dict(img=img.tobytes(), h=int(img.shape[0]), w=int(img.shape[1]), state=st.tolist(), task=self.vla['task'], seed=seed))
                    r = self.conn.recv()
                if 'err' in r: raise RuntimeError('推論サーバーのエラー: ' + r['err'])
            except Exception:
                if self.vla.get('pause'):
                    try: self._world_pause(False)                     # 失敗しても止めたままにしない
                    except Exception: pass
                raise
            sec = time.time() - t1
            if self.vla.get('pause'): self._world_pause(False)
            chunk = np.frombuffer(r['actions'], np.float32).reshape(r['n'], r['dim']).astype(np.float64)
            for _ in range(60): rclpy.spin_once(self, timeout_sec=0.0)          # 推論中にたまった画像を取り込む(時刻を進める)
            e = int(round((self.img_stamp - t_obs) * FPS)) if t_obs > 0 else min(self.n_img - n_obs, 10)
            if self.vla.get('pause'): e = 0                              # 止めていたので、進んだコマはない
            e = max(0, min(e, len(chunk) - 1))
            if e >= len(chunk) - 1 and not self.vla.get('pause'): print('  [警告] 推論中に進んだコマ数(%d)が1回の予測(%d)以上: 指令がほぼ全部古い。--pause-infer を使うこと' % (e, len(chunk)), flush=True)
            self.q = [chunk[i] for i in range(e, min(len(chunk), e + self.vla['exec_steps']))]
            self.vla_skip.append(e); self.vla_sec.append(sec); self.t_inf.append(sec)
        return self.q.pop(0)

    def act_once(self):
        """新しい画像を待ち、方策で次の指令を決めて送る。(俯瞰画像, 正面画像)を返す"""
        n0 = self.n_img; t0 = time.time()
        while self.n_img == n0 or self.js is None:
            rclpy.spin_once(self, timeout_sec=0.05)
            if time.time() - t0 > 10:
                raise RuntimeError('画像が届きません')
        if self.vla:
            a = self._vla_action()
        else:
            obs = {'observation.state': torch.from_numpy(self.js).unsqueeze(0),
                   self.img_key: torch.from_numpy(self.img).permute(2, 0, 1).float().div(255.0).unsqueeze(0)}
            t1 = time.time()
            with torch.no_grad():
                a = self.policy.select_action(obs).cpu().numpy().flatten().astype(np.float64)
            self.t_inf.append(time.time() - t1)
        a[0] = np.clip(a[0], -LIM_J1, LIM_J1)
        for j in (2, 3, 4):
            a[j - 1] = np.clip(a[j - 1], *LIM[j])
        a[4] = np.clip(a[4], *GRIP)
        a = self.cmd + np.clip(a - self.cmd, -MAX_STEP, MAX_STEP)
        self.cmd = a
        self.send(self.pa, ARM, a[:4], 2.0 / FPS); self.send(self.pg, HAND, [a[4]], 2.0 / FPS)
        if getattr(self, 'loop_delay', 0.0) > 0: time.sleep(self.loop_delay)       # 診断用: 制御ループを遅くする(CPU推論が遅い端末の条件を再現する)
        return self.img, self.side


class BlockRec:
    """評価中の積み木の位置姿勢を、ignの姿勢トピック(約60Hz)から連続で記録する。失敗しても評価は続ける。
    rows の各行 = 1メッセージ分の [x,y,z,qx,qy,qz,qw](そのメッセージに積み木が無ければ NaN)"""
    def __init__(self, target):
        import subprocess, threading
        self.target = target; self.rows = []; self.proc = None
        try:
            self.proc = subprocess.Popen(['ign', 'topic', '-e', '-t', '/world/default/dynamic_pose/info'],
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            threading.Thread(target=self._read, daemon=True).start()
        except Exception as e:
            print('  積み木の連続記録を始められません:', e, flush=True)

    @property
    def n(self):
        return len(self.rows)

    def _read(self):
        cur = None; sec = None; seen = set(); blk = None
        nan = [float('nan')] * 7

        def finish():
            nonlocal seen, blk
            if seen:
                self.rows.append(blk if blk is not None else nan)
            seen = set(); blk = None
        try:
            for line in self.proc.stdout:
                s = line.strip()
                if s == '' or s.startswith('header {'):
                    finish(); continue
                if s == 'pose {':
                    cur = {'name': None, 'p': [0.0, 0.0, 0.0], 'q': None}; sec = None; continue
                if cur is None:
                    continue
                if sec is None and s.startswith('name:') and cur['name'] is None:
                    cur['name'] = s.split('"')[1] if '"' in s else ''
                    if cur['name'] in seen:
                        finish()
                    seen.add(cur['name'])
                elif s == 'position {':
                    sec = 'p'
                elif s == 'orientation {':
                    sec = 'o'; cur['q'] = [0.0, 0.0, 0.0, 0.0]
                elif s == '}':
                    if sec:
                        sec = None
                    else:
                        if cur['name'] == self.target:
                            blk = cur['p'] + (cur['q'] if cur['q'] is not None else [0.0, 0.0, 0.0, 1.0])
                        cur = None
                elif sec and ':' in s:
                    k, v = s.split(':', 1); k = k.strip()
                    if k in 'xyzw' and len(k) == 1:
                        try:
                            val = float(v)
                            if sec == 'p': cur['p']['xyz'.index(k)] = val
                            else: cur['q']['xyzw'.index(k)] = val
                        except ValueError:
                            pass
        except Exception:
            pass

    def stop(self):
        try:
            if self.proc: self.proc.terminate()
        except Exception:
            pass
        return np.array(self.rows, dtype=np.float64).reshape(-1, 7)


def wilson(k, n, z=1.96):
    """Wilson 95% 信頼区間(%)"""
    if n == 0: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def build_scenario(scn, rng, a, vla):
    """ステージ2の評価シナリオ。同じ配置(seed 固定)で ACT と SmolVLA を比べる。
    A: 赤(位置T)+青(位置D)。SmolVLA は指示「赤」「青」の2通り、ACT は指示を受け取れないので配置ごとに1回(両方の対象で採点)
    B: 黄色(未学習の色)が対象(T)、赤が妨害物(D)。指示「黄色」
    C: 青1個だけ(T)。指示「青」
    戻り値: エピソードの dict のリスト。各 dict: lay=(th,r,yaw,thb,rb), dis=(dth,dr,dyaw)|None, T=色, D=色|None, target=色|None, task=指示|None"""
    if scn == 'S':                                   # 学習に使った配置の再現(seen)。各組み合わせの最初のデモ1件につき、学習と同じ指示と、対象を入れ替えた指示の2回
        d0 = os.path.join(NPZ_ROOT, a.seen_data); first = {}
        for f in sorted(os.listdir(d0)):
            if not f.endswith('.json'): continue
            j = json.load(open(os.path.join(d0, f)))
            if j.get('success', True) and j.get('distractor') and (j['target_color'], j['distractor_color']) not in first: first[(j['target_color'], j['distractor_color'])] = j
        eps = []
        for k, (key, j) in enumerate(sorted(first.items())):
            lay = (math.radians(j['block_th']), j['block_r'], math.radians(j['block_yaw_rel']), math.radians(j['box_th']), j['box_r'])
            dj = j['distractor']; dis = (math.radians(dj['th']), dj['r'], math.radians(dj['yaw']))
            T, D = key
            eps.append(dict(k=k, lay=lay, dis=dis, T=T, D=D, target=T, task=task_text(T), kind='学習と同じ指示'))
            eps.append(dict(k=k, lay=lay, dis=dis, T=T, D=D, target=D, task=task_text(D), kind='対象を入れ替えた指示'))
        if not eps: raise SystemExit('学習デモの json がありません: ' + d0)
        return eps
    lays = []
    for _ in range(a.n_layouts):
        for _try in range(500):
            lay = sample(rng, a)
            d = sample_distractor(rng, a, lay[0], lay[1], lay[3], lay[4], a.min_sep)      # C でも同じ乱数を使う(A/B と同じ対象の配置にそろえる)
            if d: break
        else:
            raise SystemExit('評価の配置が作れません')
        lays.append((lay, d))
    eps = []
    for k, (lay, d) in enumerate(lays):
        if scn == 'A':
            if vla:
                for tc in ('red', 'blue'): eps.append(dict(k=k, lay=lay, dis=d, T='red', D='blue', target=tc, task=task_text(tc)))
            else:
                eps.append(dict(k=k, lay=lay, dis=d, T='red', D='blue', target=None, task=None))
        elif scn == 'B':
            eps.append(dict(k=k, lay=lay, dis=d, T='yellow', D='red', target='yellow', task=task_text('yellow')))
        else:
            eps.append(dict(k=k, lay=lay, dis=None, T='blue', D=None, target='blue', task=task_text('blue')))      # 妨害物は置かない
    return eps


def summarize_scenario(scn, results, vla, t_all):
    """条件別の成功数・Wilson区間・失敗の内訳を表示する([要約] を含む行を出す)"""
    def line(label, rs, key):
        k = sum(1 for r in rs if r.get(key)); n = len(rs); lo, hi = wilson(k, n)
        return '%s %d/%d (%.0f%%, 区間 %.0f〜%.0f%%)' % (label, k, n, 100.0 * k / max(1, n), lo, hi)
    valid = [r for r in results if not r['err']]
    parts = []
    if scn == 'A' and not vla:
        for c, nm in (('red', '対象=赤'), ('blue', '対象=青')):
            parts.append(line(nm, valid, 'ok_' + c))
    elif scn == 'A':
        for c, nm in (('red', '指示=赤'), ('blue', '指示=青')):
            parts.append(line(nm, [r for r in valid if r['target'] == c], 'ok'))
    elif scn == 'S':
        for kd in ('学習と同じ指示', '対象を入れ替えた指示'):
            parts.append(line(kd, [r for r in valid if r.get('kind') == kd], 'ok'))
    else:
        parts.append(line('全体', valid, 'ok'))
    print('\n[要約] 条件%s: %s / 所要 %.0f 秒 / 無効 %d 件' % (scn, ' ; '.join(parts), t_all, len(results) - len(valid)))
    cats = {}
    for r in valid:
        cats[r.get('outcome', '?')] = cats.get(r.get('outcome', '?'), 0) + 1
    print('  内訳(最終状態): ' + ' / '.join('%s %d' % (k, v) for k, v in sorted(cats.items())) + '   (ok=指示した積み木だけ箱に入った wrong=別の積み木が入った both=両方 none=どちらも入らない。指示を受け取れないACTの条件Aは red/blue=その色だけ箱に入った)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-path', required=True)
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--seed', type=int, default=2000)
    ap.add_argument('--name', default='eval')
    ap.add_argument('--max-sec', type=float, default=30.0, help='1回の制限時間(専門家は約20秒)')
    ap.add_argument('--block-th', type=float, nargs=2, default=[-90, -30])
    ap.add_argument('--block-r', type=float, nargs=2, default=[0.07, 0.12])
    ap.add_argument('--box-th', type=float, nargs=2, default=[30, 80])
    ap.add_argument('--box-r', type=float, nargs=2, default=[0.12, 0.18])
    ap.add_argument('--yaw-max', type=float, default=30)
    ap.add_argument('--no-side', action='store_true')
    ap.add_argument('--start-index', type=int, default=0, help='先頭のこの数の配置を飛ばして、そこから --n 件測る(無効になった回のやり直し用。推論の種も元の回と同じになる)')
    ap.add_argument('--tag', default='', help='記録の名前に付ける印(同じ設定で測り直しても、前の記録を上書きしない)')
    ap.add_argument('--te', action='store_true', help='時間方向のアンサンブル(毎コマ予測。名前に _te が付く)')
    ap.add_argument('--te-coeff', type=float, default=0.01, help='時間アンサンブルの係数(既定 0.01。大きいほど古い予測を重く見る。負なら新しい予測を重く見る)')
    ap.add_argument('--exec-n', type=int, default=0, help='時間アンサンブルなしのとき、1回の予測から実行するコマ数(0=学習時の設定のまま10)')
    ap.add_argument('--loop-delay', type=float, default=0.0, help='診断用: 1回の指令のあとに実時間で待つ秒数。0.19 で、推論が233 ms/回の端末(10/17の測定)と同じ速さのループになる')
    ap.add_argument('--no-stop-at-home', action='store_true', help='ホームに戻っても打ち切らず、制限時間まで続ける(やり直しも含めて測る)')
    ap.add_argument('--smolvla', action='store_true', help='SmolVLA で評価する(eval_smolvla.sh が推論サーバーを起動してから呼ぶ)')
    ap.add_argument('--port', type=int, default=6010, help='推論サーバーのポート')
    ap.add_argument('--server-url', default='', help='SmolVLA: Colab の推論サーバーの URL(指定すると、ローカルの推論は使わない)')
    ap.add_argument('--token', default='', help='SmolVLA: Colab の推論サーバーのトークン')
    ap.add_argument('--exec-steps', type=int, default=50, help='SmolVLA: 1回の予測(50コマ)のうち、実行するコマ数。小さいほど頻繁に画像を見直す(推論が増える)')
    ap.add_argument('--pause-infer', type=int, default=1, help='SmolVLA: 1=推論の間シミュレーションを一時停止(既定)。0=止めない(CPU推論が遅いと閉ループにならない)')
    ap.add_argument('--vla-seed', type=int, default=1000, help='SmolVLA: 推論の雑音の種。予測ごとに 種+1000×回の番号+予測の番号 を使うので、再試で同じ配置・同じ入力なら同じ出力になる')
    ap.add_argument('--task', default='put the red block in the box', help='SmolVLA: 言語指示')
    ap.add_argument('--grid', action='store_true', help='格子実験の15配置を使う(n は 15 にする)')
    ap.add_argument('--scenario', default='', choices=['', 'A', 'B', 'C', 'S'], help='ステージ2の評価。S=学習に使った配置の再現(各組み合わせ1件ずつ、学習と同じ指示と入れ替えた指示)。A=赤+青(指示を替える) B=黄色(未学習の色)が対象・赤が妨害物 C=青1個。配置の数は --n-layouts(--n は使わない)')
    ap.add_argument('--seen-data', default='s2_color_1024', help='条件S: 学習配置を読むデータ名')
    ap.add_argument('--n-layouts', type=int, default=10, help='ステージ2: 配置の数')
    ap.add_argument('--min-sep', type=float, default=STAGE2_SEP, help='ステージ2: 2個の積み木の中心間の最小距離(m)')
    ap.add_argument('--replay', default='', help='学習に使った配置を再現する(seen 条件)。データ名(例 s1_region)。先頭から n 件')
    ap.add_argument('--skip-env-gate', action='store_true', help='環境の事前確認を省く(原則使わない。省いた結果は環境未確認と明記する)')
    a = ap.parse_args()
    import env_gate
    if not env_gate.run(kind='eval', model_path=a.model_path, skip=a.skip_env_gate): sys.exit(3)
    a.grid_i = 0
    if a.grid: a.grid_cells = grid_cells()
    if a.replay: a.replay_cells = load_replay(os.path.join(NPZ_ROOT, a.replay), a.n)
    a.carry_angle, a.carry_z, a.close_deg, a.close_sec, a.release_z = 90, CARRY_Z, 30.0, 2.0, 0.10      # 専門家の可否判定用(sample が使う)
    if a.scenario:
        if a.block_th == [-90, -30]: a.block_th = list(STAGE2_BLOCK_TH)
        if a.block_r == [0.07, 0.12]: a.block_r = list(STAGE2_BLOCK_R)
    os.makedirs(OUTBOX, exist_ok=True)
    rng = random.Random(a.seed)
    remove('wood_cube_5cm')
    vla = dict(port=a.port, exec_steps=a.exec_steps, task=a.task, seed=a.vla_seed, pause=bool(a.pause_infer), url=a.server_url, token=a.token) if a.smolvla else None
    rclpy.init(); n = Runner(a.model_path, not a.no_side, a.te, vla, a.te_coeff, a.exec_n); n.loop_delay = a.loop_delay; n.spin_for(2.0)
    if vla and vla['pause']:
        try: n._world_pause(False)                  # 前の実行が止められたまま残した一時停止を解除する
        except Exception as ex: print('  [警告] 一時停止の解除を試せません:', ex, flush=True)
    if a.te: a.name += '_te'
    if a.scenario: a.name += '_s' + a.scenario
    if a.smolvla: a.name += '_e%d' % a.exec_steps
    if a.tag: a.name += '_' + a.tag
    results = []
    t0 = time.time()
    print('eval_act 版: 10/24 (ステージ2の条件A/B/C・積み木の連続記録・格子・学習配置の再現・SmolVLA対応・推論中の一時停止・ループ遅延・開始前の追従確認・追従なしの検出)', flush=True)
    print('評価 %d 回 / seed %d / 積み木 θ%s 箱 θ%s' % (a.n, a.seed, a.block_th, a.box_th), flush=True)
    episodes = None
    if a.scenario:
        episodes = build_scenario(a.scenario, rng, a, vla)
        a.n = len(episodes) - a.start_index
        print('ステージ2 条件%s: 配置 %d 個 → %d 回 / 積み木 θ%s r%s / 中心間 %.2f m 以上' % (a.scenario, a.n_layouts, len(episodes), a.block_th, a.block_r, a.min_sep), flush=True)
    else:
        for _ in range(a.start_index): sample(rng, a)
    remove(BLK); remove(BOX); remove(DIS); time.sleep(0.4)
    if not n.verify_tracking():
        print('  [中止] 腕が指令に追従しません(追従確認に失敗)。この評価は始めません。Gazebo を再生状態にして待ってから実行し直してください', flush=True)
        sys.exit(2)
    for i in range(a.start_index, a.start_index + a.n):
        ep = episodes[i] if episodes else None
        if ep: th, rx, yaw_rel, thb, rb = ep['lay']
        else: th, rx, yaw_rel, thb, rb = sample(rng, a)
        x, y = rx * math.cos(th), rx * math.sin(th); bx, by = rb * math.cos(thb), rb * math.sin(thb)
        if ep and vla and ep['task']: n.vla['task'] = ep['task']
        remove(BLK); remove(BOX); remove(DIS); time.sleep(0.4)          # 先に物を消して、指が引っかからない状態でホームへ戻す
        home_ok = n.go_home()
        for k in range(8):                                  # Gazebo 起動直後は腕が指令に追従しないことがある。追従するまで再送して待つ(最大8回=約7分)
            if home_ok: break
            print('  ホームに戻れません。指令を再送して待ちます(%d/8)' % (k + 1), flush=True)
            home_ok = n.go_home()
        if not home_ok:
            print('  [中止] 腕が指令に追従しません。開始姿勢が不正なので、この評価は無効です。Gazebo を再生にして1〜2分待ってから実行し直してください', flush=True)
            sys.exit(2)
        time.sleep(0.5)
        spawn(BLK, block_sdf(BLK, SIZE, COLORS[ep['T'] if ep else 'red'], density=700.0, mu=1.5), x, y, Z_REST, th + yaw_rel)
        if ep and ep['dis']:
            dth, dr_, dyaw = ep['dis']
            spawn(DIS, block_sdf(DIS, SIZE, COLORS[ep['D']], density=700.0, mu=1.5), dr_ * math.cos(dth), dr_ * math.sin(dth), Z_REST, dth + dyaw)
        spawn(BOX, box_sdf(BOX, INNER, wall_h=RIM), bx, by, TABLE_Z)
        time.sleep(1.5)
        n.ep_i = i; n.reset_policy(); n.t_inf = []; n.vla_skip = []
        over, side = [], []
        st_tr, cm_tr, mf = [], [], []
        rec = BlockRec(BLK); time.sleep(0.8)
        err = ''; stop = ''; rate = 0.0
        try:
            img0 = n.n_img
            for k in range(int(a.max_sec * FPS)):
                o, s = n.act_once()
                over.append(o); st_tr.append(n.js.copy()); cm_tr.append(n.cmd.copy()); mf.append(rec.n)
                if s is not None: side.append(s)
                if not a.no_stop_at_home and k >= 100 and n.js is not None and float(np.max(np.abs(n.js[:4].astype(np.float64) - np.array(HOME)))) < 0.12:
                    stop = 'ホームに戻った(%.1f秒)' % (k / FPS); break      # 1回の試行が終わった
            else:
                stop = '時間切れ'
            rate = (n.n_img - img0) / max(1, k + 1)          # 1回の指令あたりに進んだ画像の数(1なら全コマで指令、2なら1コマ飛ばし)
        except Exception as e:
            err = str(e)
            if vla and vla['pause']:
                try: n._world_pause(False)
                except Exception: pass
        blk_arr = rec.stop()
        no_follow = False; exc_c = exc_s = 0.0
        if len(cm_tr) and len(st_tr):                       # 指令は動いたのに腕が動かない回(腕が追従しない状態)を見分ける
            exc_c = float(np.max(np.abs(np.array(cm_tr)[:, :4] - np.array(HOME))))
            exc_s = float(np.max(np.abs(np.array(st_tr)[:, :4].astype(np.float64) - np.array(HOME))))
            if not err and exc_c > 0.3 and exc_s < 0.1:
                no_follow = True; err = '追従なし(指令は最大%.0f度動いたが腕は%.0f度しか動かない)' % (math.degrees(exc_c), math.degrees(exc_s))
        print('  積み木の姿勢記録: %d件中 %d件に積み木あり' % (len(blk_arr), int(np.sum(~np.isnan(blk_arr[:, 0])))) if len(blk_arr) else '  積み木の姿勢記録: 0件(記録できず)', flush=True)
        time.sleep(0.6)
        c = get_center(BLK, SIZE)
        ok = False; dist = -1.0
        if c and not err:
            dx, dy = c[0] - bx, c[1] - by
            dist = math.hypot(dx, dy) * 1000
            ok = abs(dx) <= INNER / 2 and abs(dy) <= INNER / 2 and c[2] - TABLE_Z < 0.045
        extra = {}
        if ep and not err:                                  # ステージ2: 2個の積み木それぞれが箱に入ったかで採点する
            cdis = get_center(DIS, SIZE) if ep['dis'] else None
            inb = {ep['T']: in_box(c, bx, by)}
            if ep['D']: inb[ep['D']] = in_box(cdis, bx, by)
            def one(tc):                                     # 色 tc が対象のときの成否
                return bool(inb.get(tc)) and not any(v for kk, v in inb.items() if kk != tc)
            if ep['target']:
                ok = one(ep['target'])
                oth = any(v for kk, v in inb.items() if kk != ep['target'])
                outcome = 'ok' if ok else ('both' if inb.get(ep['target']) and oth else ('wrong' if oth else 'none'))
            else:
                ok = False; outcome = 'red' if one('red') else ('blue' if one('blue') else ('both' if all(inb.values()) else 'none'))
                extra = dict(ok_red=one('red'), ok_blue=one('blue'))
            extra.update(scn=a.scenario, layout=ep['k'], T=ep['T'], D=ep['D'], target=ep['target'], task=ep['task'], outcome=outcome, in_box=inb, kind=ep.get('kind'))
        elif ep:
            extra = dict(scn=a.scenario, layout=ep['k'], T=ep['T'], D=ep['D'], target=ep['target'], task=ep['task'], outcome='invalid', kind=ep.get('kind'))
        results.append(dict(i=i, ok=ok, block_th=math.degrees(th), block_r=rx, yaw=math.degrees(yaw_rel), box_th=math.degrees(thb), box_r=rb,
                            dist_mm=dist, inf_ms=1000 * float(np.mean(n.t_inf)) if n.t_inf else 0, stop=stop, frames_per_cmd=rate, home_ok=home_ok, err=err, cmd_exc_deg=math.degrees(exc_c), state_exc_deg=math.degrees(exc_s), vla_calls=len(n.vla_skip), vla_skip_mean=float(np.mean(n.vla_skip)) if n.vla_skip else 0.0, **extra))
        try:                                                   # 指令と関節角の記録(診断用。trace_stats.bat で専門家と比べる)
            td = '/home/ubuntu/eval_traces/' + a.name; os.makedirs(td, exist_ok=True)
            np.savez(os.path.join(td, 'ep_%02d.npz' % i), state=np.array(st_tr), cmd=np.array(cm_tr), ok=ok, block_th=math.degrees(th), box_th=math.degrees(thb), block_r=rx, yaw=math.degrees(yaw_rel),
                     blk=blk_arr, msg_at_frame=np.array(mf, dtype=np.int64), blk0=np.array([x, y, Z_REST, th + yaw_rel]))
        except Exception as e:
            print('記録は保存できませんでした:', e)
        print('%3d/%d %s積み木(θ%+4.0f°,r%.3f,向き%+3.0f°) → 箱(θ%+4.0f°,r%.3f) %s 箱の中心から %.0f mm  推論 %.0f ms/回 画像/指令 %.1f [%s] %s' % (
            i + 1, a.start_index + a.n, (('[配置%d 位置T=%s D=%s 指示=%s 結果=%s] ' % (ep['k'], ep['T'], ep['D'], ep['task'] or '(なし)', extra.get('outcome', '?'))) if ep else ''), math.degrees(th), rx, math.degrees(yaw_rel), math.degrees(thb), rb, '成功' if ok else ('無効' if err else '失敗'), dist,
            results[-1]['inf_ms'], rate, stop, err), flush=True)
        if a.smolvla:
            print('      SmolVLA: 予測 %d 回 / 1回の推論 平均 %.2f 秒 / 推論中に進んだコマ(捨てた先頭の指令) 平均 %.1f' % (len(n.vla_skip), float(np.mean(n.vla_sec)) if n.vla_sec else 0, float(np.mean(n.vla_skip)) if n.vla_skip else 0), flush=True)
            n.vla_sec = []
        if no_follow:
            print('  [中止] 腕が指令に追従しなくなりました。この回は無効です。以降の回も同じ結果になるため、ここで止めます(--start-index %d でやり直せます)' % i, flush=True)
            break
        try:
            from expert_video import write_video
            write_video(over, os.path.join(OUTBOX, '%s_%02d_overhead.mp4' % (a.name, i)))
            if side: write_video(side, os.path.join(OUTBOX, '%s_%02d_front.mp4' % (a.name, i)))
        except Exception as e:
            print('動画は保存できませんでした:', e)
    n.step(HOME, OPEN, 2.0)
    remove(BLK); remove(BOX); remove(DIS)
    ok_n = sum(r['ok'] for r in results)
    json.dump(results, open(os.path.join(OUTBOX, a.name + '_results.json'), 'w'), ensure_ascii=False, indent=1)
    inv = sum(1 for r in results if r['err'])
    if inv: print('\n[注意] 無効(通信や一時停止の失敗など。方策の失敗ではない)が %d 件あります。この回は成功率の分母から外して読み、--start-index でやり直すこと' % inv)
    if a.scenario:
        summarize_scenario(a.scenario, results, vla, time.time() - t0)
    else:
        print('\n[要約] 成功 %d/%d (%.0f%%) / 所要 %.0f 秒 / 推論 平均 %.0f ms/回' % (ok_n, len(results), 100.0 * ok_n / max(1, len(results)), time.time() - t0,
          np.mean([r['inf_ms'] for r in results]) if results else 0))
    rclpy.shutdown()


if __name__ == '__main__':
    main()
