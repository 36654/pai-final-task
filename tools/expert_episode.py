# 専門家(自前IK)が、積み木をつかんで箱に入れるデモを生成して記録する。Gazebo起動後、アームがhomeの状態で実行。
# 使い方: expert_episode.py N [--name NAME] [--seed S] [--color red] [--block-th -90 -30] [--block-r 0.07 0.12]
#         ステージ2(積み木2個・言語指示): --colors red,blue,green(毎回異なる2色を順列で巡回。対象=1つ目)または --target-color C --distractor-color D
#                                        --abort-after 10 --abort-below 0.7 (最初の10件の成功率が70%未満なら自動停止)
#                              [--box-th 30 80] [--box-r 0.12 0.18] [--keep-failures]
# 画像が届くたび(シミュレーションの20 Hz)に、1コマ(画像・関節角・次の指令)を記録して、指令を1歩進める。
import argparse, json, math, os, random, sys, time
import numpy as np
import rclpy
from sensor_msgs.msg import Image, JointState
from expert_lib import *

FPS = 20
JN = ARM + HAND
COLORS = {'red': (0.85, 0.12, 0.12), 'blue': (0.15, 0.30, 0.85), 'green': (0.15, 0.65, 0.25),
          'yellow': (0.90, 0.80, 0.10), 'purple': (0.55, 0.25, 0.70), 'white': (0.92, 0.92, 0.92)}
BLK, BOX, DIS = 'blk', 'box', 'dis'      # 対象の積み木 / 箱 / 妨害物(ステージ2。別の色の積み木)
SIZE, INNER, RIM = 0.05, 0.12, 0.06      # 積み木5 cm、箱の内寸12 cm、縁の高さ6 cm
CAL_R, CAL_T = -0.020, -0.018               # 運ぶ先の補正(m)。閉じ指令30度では、補正-0.010 mで着地が半径方向に平均+10 mm外側になった(10/15の実測)ので、さらに-0.010 m。接線方向は、同じ条件でも±15 mmばらつくので補正しない。実行結果の平均ずれで見直す
X_MIN_BOX, X_MIN_BLOCK = -0.03, -0.07     # 箱の中心と積み木の中心のx下限(m)。箱の外縁(±0.066)まで視野(x>-0.112)に収める
CARRY_Z = 0.14                           # 運ぶときの、積み木の中心の高さ(机から)。真下から45°傾けた姿勢での上限(IK)。縁6 cmに対し、角の分を引いても約2.5 cmの余裕
# ステージ2(積み木2個)の範囲。1個の領域(θ −90〜−30°、r 0.07〜0.12 m)では、2個を 9 cm 以上離して置ける配置が少ないので、
# 10/16の150件が覆っていた範囲(θ −120〜−30°。−95°以下は専門家の失敗が多い)まで広げる
STAGE2_BLOCK_TH, STAGE2_BLOCK_R, STAGE2_SEP = [-112, -30], [0.065, 0.125], 0.09
ROOT = '/home/ubuntu/dataset/expert_npz'
OUTBOX = '/home/ubuntu/outbox'


class Runner(Arm):
    def __init__(self):
        super().__init__('expert_episode')
        self.img = None; self.n_img = 0; self.js = None; self.rec = None; self.side = None; self.err_max = 0.0; self.err_last = 0.0
        self.create_subscription(Image, '/overhead_camera/image', self._on_img, 10)
        self.create_subscription(Image, '/side_camera/image', self._on_side, 10)      # 動画用の斜めカメラ(学習には使わない)
        self.create_subscription(JointState, '/joint_states', self._on_js, 10)
        self.cmd = np.array(HOME + [OPEN], dtype=np.float64)

    def _on_img(self, m):
        if m.encoding != 'rgb8':
            return
        self.img = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3).copy()
        self.n_img += 1

    def _on_side(self, m):
        if m.encoding == 'rgb8':
            self.side = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3).copy()

    def _on_js(self, m):
        d = dict(zip(m.name, m.position))
        if all(k in d for k in JN):
            self.js = np.array([d[k] for k in JN], dtype=np.float32)

    def tick(self, new_cmd):
        """新しい画像が届くのを待ち、(画像, 関節角, 次の指令)を記録して、指令を送る"""
        n0 = self.n_img; t0 = time.time()
        while self.n_img == n0:
            rclpy.spin_once(self, timeout_sec=0.05)
            if time.time() - t0 > 10:
                raise RuntimeError('画像が届きません(camera_check.bat で確認)')
        if self.rec is not None and self.js is not None:
            self.rec['img'].append(self.img); self.rec['state'].append(self.js.copy())
            if self.side is not None: self.rec['side'].append(self.side)
            self.rec['action'].append(np.array(new_cmd, dtype=np.float32))
        if self.js is not None:                                    # 追従誤差: 前に出した指令と実測のずれ(何かに当たると、遅い動きでも大きく残る)
            e = float(np.max(np.abs(self.js[:4].astype(np.float64) - self.cmd[:4])))
            self.err_max = max(self.err_max, e); self.err_last = e
        self.cmd = np.array(new_cmd, dtype=np.float64)
        self.send(self.pa, ARM, new_cmd[:4], 2.0 / FPS)
        self.send(self.pg, HAND, [new_cmd[4]], 2.0 / FPS)

    def move(self, target, sec):
        a = self.cmd.copy(); b = np.array(target, dtype=np.float64); n = max(1, int(round(sec * FPS)))
        for k in range(1, n + 1):
            s = k / n; s = 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5       # なめらかな加減速
            self.tick(a + (b - a) * s)


def _move_path(self, fn, sec):
    """各コマで逆運動学を解いて、経路を指定する(高さを一定に保って運ぶため)。fn(s): s=0..1 -> 腕の4関節"""
    n = max(1, int(round(sec * FPS)))
    for k in range(1, n + 1):
        s = k / n; s = 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5
        tgt = self.cmd.copy(); tgt[:4] = fn(s)
        self.tick(tgt)


Runner.move_path = _move_path


def plan(th, rx, thb, rb, A=135, zc=CARRY_Z, close=CLOSE, close_sec=2.0, zr=None):
    """(腕の目標4関節 or 経路の関数 or None, 手の目標 or None, 秒) の列。逆運動学が解けなければ ValueError。
    A: 運ぶときの手先の向き(180=真下、90=水平)、zc: 運ぶときの積み木の中心の高さ、zr: 離すときの積み木の中心の高さ(zc未満なら、箱の真上で止まってから真下へ降ろして離す)"""
    rbc = rb + CAL_R
    thbc = thb + CAL_T / rb

    def swing(u):                                            # 高さ一定で、円弧に沿って箱の上へ
        return pose_tilt(th + (thbc - th) * u, rx + (rbc - rx) * u, zc, A)
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        swing(u)                                             # 途中で届かない配置は、ここで ValueError にして除く
    lower = zr is not None and zr < zc - 1e-6
    Ar = A
    if lower:                                                # 手を水平のままだと関節の限界で降ろせない(箱が近いほど)ので、降ろしながら手先を少し下へ傾ける
        for cand in range(int(A), 181):
            try:
                for u in (0.0, 0.25, 0.5, 0.75, 1.0):
                    pose_tilt(thbc, rbc, zc + (zr - zc) * u, A + (cand - A) * u)
                Ar = cand; break
            except ValueError:
                continue
        else:
            raise ValueError('IK解なし(降ろせない)')
        Ar = min(180, Ar + 3)                               # 限界ぎりぎりを避ける余裕

    def descend(u):                                          # 箱の真上から、真下へ降ろす(高さzc→zr、手先の向きA→Ar)
        return pose_tilt(thbc, rbc, zc + (zr - zc) * u, A + (Ar - A) * u)
    angles = [x for x in (165, 150, 135, 120, 105) if x > A] + [A]      # 手先を少しずつ傾ける(積み木が指の中で回って落ちるのを避ける)
    tilt = []
    for i, ang in enumerate(angles):
        z = 0.075 + (zc - 0.075) * (i + 1) / len(angles)
        tilt.append((pose_tilt(th, rx, z, ang), None, 0.7))
    return [
        (None, None, 0.5),
        ([th] + HOME[1:], OPEN, 1.2),                       # 折りたたんだまま、向きを変える
        (pose(th, rx, ZP), OPEN, 1.5),                      # 積み木の真上
        (pose(th, rx, ZG), OPEN, 1.5),                      # 降ろす
        (None, close, close_sec),                           # つかむ(片側の指だけが動くので、閉じ切るまで待つ)
        (pose(th, rx, ZP), None, 1.2),                      # 持ち上げる
    ] + tilt + [
        (swing, None, max(2.5, 1.5 + 0.8 * abs(thbc - th))),  # 箱の上へ(高さ一定)。旋回角が大きいほど長く(約200°で4.3秒。腕が追いつく前に離すのを避ける)
        (None, None, 0.6),                                  # 腕が着き切るのを待つ
    ] + ([(descend, None, 0.8 + 10 * (zc - zr))] if lower else []) + [   # 底の近くまで降ろす(落差7 cmで約1.5秒)
        (None, OPEN, 1.0),                                  # 離す
        (None, None, 0.5),
        ([thb] + HOME[1:], None, 1.8),                      # 折りたたむ
        (HOME[:], None, 1.8),                               # home へ
        (None, None, 0.5),
    ]


# 格子実験(積み木の旋回角 θ × 積み木の向き yaw を、箱と半径を固定して振る)。専門家・ACT・SmolVLA で同じ15配置を、同じ順番で使う
GRID_TH, GRID_YAW = [-40, -65, -85], [-25, -12, 0, 12, 25]
GRID_BLOCK_R, GRID_BOX_TH, GRID_BOX_R = 0.095, 55.0, 0.15


def grid_cells():
    cells = [(t, y) for t in GRID_TH for y in GRID_YAW]
    random.Random(7).shuffle(cells)                      # 順番は固定の乱数で入れ替える(時間経過の影響が θ や yaw と重ならないように)
    return cells


def load_replay(d, n):
    """学習に使った配置(専門家のデモの json)を、先頭から n 件読む。成功した件だけ(学習データは成功のみ)"""
    out = []
    if not os.path.isdir(d):                              # 別PCでは npz がない。sync_out/sync_in で運んだ配置の json を使う
        d2 = os.path.join(os.path.dirname(os.path.dirname(d)), 'layouts', os.path.basename(d))
        if os.path.isdir(d2): d = d2
    if not os.path.isdir(d): raise SystemExit('学習配置の json がありません: ' + d + '(デモを作ったPCで sync_out.bat を実行し、このPCで sync_in.bat を実行する)')
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            j = json.load(open(os.path.join(d, f)))
            if j.get('success', True):
                out.append((j['block_th'], j['block_r'], j['block_yaw_rel'], j['box_th'], j['box_r']))
        if len(out) >= n: break
    if not out: raise SystemExit('学習配置の json が見つかりません: ' + d)
    return out


def sample(rng, a):
    gc = getattr(a, 'grid_cells', None)
    if gc:                                               # 格子実験: 固定の配置を順に返す(届くかを確認し、届かなければ止める)
        t, yw = gc[a.grid_i % len(gc)]; a.grid_i += 1
        th, r, thb, rb = math.radians(t), GRID_BLOCK_R, math.radians(GRID_BOX_TH), GRID_BOX_R
        plan(th, r, thb, rb, a.carry_angle, a.carry_z, math.radians(a.close_deg), a.close_sec, a.release_z)       # 届かなければ ValueError で止まる
        return th, r, math.radians(yw), thb, rb
    rc = getattr(a, 'replay_cells', None)
    if rc:                                               # 学習に使った配置の再現(seen 条件)
        t, r, yw, tb, rb = rc[a.grid_i % len(rc)]; a.grid_i += 1
        return math.radians(t), r, math.radians(yw), math.radians(tb), rb
    for _ in range(2000):
        th = math.radians(rng.uniform(*a.block_th)); r = rng.uniform(*a.block_r)
        thb = math.radians(rng.uniform(*a.box_th)); rb = rng.uniform(*a.box_r)
        x, y = r * math.cos(th), r * math.sin(th); bx, by = rb * math.cos(thb), rb * math.sin(thb)
        if math.hypot(x - bx, y - by) < INNER / 2 + 0.006 + 0.036 + 0.025:      # 箱の外縁と積み木が離れていること
            continue
        if bx < X_MIN_BOX or x < X_MIN_BLOCK:                                   # 俯瞰カメラの視野に入っていること(視野は x>-0.112 m)
            continue
        yaw_rel = math.radians(rng.uniform(-a.yaw_max, a.yaw_max))
        try:
            plan(th, r, thb, rb, a.carry_angle, a.carry_z, math.radians(a.close_deg), a.close_sec, a.release_z)
        except ValueError:
            continue
        return th, r, yaw_rel, thb, rb
    raise SystemExit('条件を満たす配置が見つかりません(領域が狭すぎる?)')


def task_text(color):
    """言語指示(ステージ2の学習データと評価で、同じ文を使う)"""
    return 'put the %s block in the box' % color


def in_box(c, bx, by):
    """積み木の中心 c=(x,y,z,傾き) が箱の内側にあり、縁に乗っていないか"""
    return bool(c) and abs(c[0] - bx) <= INNER / 2 and abs(c[1] - by) <= INNER / 2 and c[2] - TABLE_Z < 0.045


def sample_distractor(rng, a, th, r, thb, rb, min_sep=0.10, tries=400):
    """妨害物(別の色の積み木)の位置。対象と min_sep(m) 以上離し、箱とも対象と同じ距離を空け、専門家が運べる配置だけにする
    (対象と妨害物の色は入れ替わるので、どちらの位置も運べる必要がある)。戻り値 (θ, r, 向き)"""
    x, y = r * math.cos(th), r * math.sin(th); bx, by = rb * math.cos(thb), rb * math.sin(thb)
    for _ in range(tries):
        dth = math.radians(rng.uniform(*a.block_th)); dr = rng.uniform(*a.block_r)
        dx, dy = dr * math.cos(dth), dr * math.sin(dth)
        if math.hypot(dx - x, dy - y) < min_sep: continue
        if math.hypot(dx - bx, dy - by) < INNER / 2 + 0.006 + 0.036 + 0.025: continue
        if dx < X_MIN_BLOCK: continue
        try:
            plan(dth, dr, thb, rb, a.carry_angle, a.carry_z, math.radians(a.close_deg), a.close_sec, a.release_z)
        except ValueError:
            continue
        return dth, dr, math.radians(rng.uniform(-a.yaw_max, a.yaw_max))
    return None                                    # 置ける場所がない配置(呼び出し側で配置を引き直す)


def preview(eps, path):
    from grab import png
    rows = []
    for e in eps[:4]:
        rows.append(np.hstack([e['img'][0], e['img'][-1]]))
    if rows:
        im = np.vstack(rows)
        png(path, im.shape[1], im.shape[0], im.astype(np.uint8).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int)
    ap.add_argument('--name', default='test')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--color', default='red', choices=list(COLORS))
    ap.add_argument('--block-th', type=float, nargs=2, default=[-90, -30], help='積み木の角度の範囲(度)。10/16の150件(範囲は-120〜-30/30〜105)で、失敗10件はすべて、積み木が-95°以下か箱が+85°以上の配置(その範囲は62件中10件失敗、残り88件は0失敗)だった。そこで、専門家が安定して成功する範囲に絞った')
    ap.add_argument('--block-r', type=float, nargs=2, default=[0.07, 0.12])
    ap.add_argument('--box-th', type=float, nargs=2, default=[30, 80], help='箱の角度の範囲(度)。--block-th の説明を参照')
    ap.add_argument('--box-r', type=float, nargs=2, default=[0.12, 0.18])
    ap.add_argument('--close-sec', type=float, default=2.0, help='閉じる動作にかける秒数(1.0だと閉じ切る前に持ち上げ始め、積み木が持ち上げ中に10 mm横へずれた)')
    ap.add_argument('--yaw-max', type=float, default=30, help='積み木の向き(グリッパーに対する角度)の最大値。+-43度付近は角をつかんで失敗するため既定30度')
    ap.add_argument('--keep-failures', action='store_true')
    ap.add_argument('--colors', default='', help='ステージ2: 色の候補(例 red,blue,green)。毎回、異なる2色(対象・妨害物)を順列で巡回して使う')
    ap.add_argument('--target-color', default='', help='ステージ2: 対象の色(--colors を使わないとき)')
    ap.add_argument('--distractor-color', default='', help='ステージ2: 妨害物の色(省略すると妨害物なし)')
    ap.add_argument('--min-sep', type=float, default=STAGE2_SEP, help='対象と妨害物の中心間の最小距離(m)')
    ap.add_argument('--abort-after', type=int, default=0, help='この件数を試した時点で成功率が --abort-below 未満なら、自動で止める(0=無効)')
    ap.add_argument('--abort-below', type=float, default=0.7)
    ap.add_argument('--mu', type=float, default=1.5, help='積み木の摩擦係数(指の摩擦 finger_friction.bat と同じ 1.5 にそろえる)')
    ap.add_argument('--close-deg', type=float, default=30.0, help='つかむときの手の指令角(度)。大きいほど深く閉じる(握る力が上がる)。10→20→30度で、持ち上げ中のずり落ちが 8→4→1 mm に減った')
    ap.add_argument('--density', type=float, default=700.0, help='積み木の密度(kg/m3)。700で5 cmが約88 g')
    ap.add_argument('--carry-angle', type=float, default=90, help='運ぶときの手先の向き(180=真下、90=水平)')
    ap.add_argument('--carry-z', type=float, default=CARRY_Z, help='運ぶときの積み木の中心の高さ(m)')
    ap.add_argument('--release-z', type=float, default=0.10, help='離すときの積み木の中心の高さ(m)。箱の真上で止まってから真下へ降ろして離す。運ぶ高さ(0.14)以上を指定すると降ろさず、落とす。10/15の掃引で、0.11/0.10/0.09 m はどれも8/8成功で、縁への接触の兆候もなかった。0.10を既定にした')
    ap.add_argument('--no-side', action='store_true', help='斜めカメラ(動画用)の映像を保存しない')
    ap.add_argument('--probe', action='store_true', help='持ち上げ直後と離す直前の積み木の位置を測る(測定中に1秒ほど止まるので、診断専用)')
    ap.add_argument('--grid', action='store_true', help='格子実験の15配置を使う(n は 15 にする)')
    ap.add_argument('--swap-of', default='', help='ステージ2: 既存のデモ(データ名)と同じ配置・同じ色で、対象を入れ替えた(もう一方の積み木を箱に入れる)デモを作る。先頭から n 件(成功したデモのみ)')
    ap.add_argument('--replay', default='', help='学習に使った配置を再現する。データ名(例 s1_region)。先頭から n 件')
    ap.add_argument('--skip-env-gate', action='store_true', help='環境の事前確認を省く(原則使わない。省いた結果は環境未確認と明記する)')
    a = ap.parse_args()
    import env_gate
    if not env_gate.run(kind='demo', model_path=None, skip=a.skip_env_gate): sys.exit(3)
    a.grid_i = 0
    pairs = None
    if a.colors:
        import itertools
        cols = [c.strip() for c in a.colors.split(',') if c.strip()]
        for c in cols:
            if c not in COLORS: raise SystemExit('未知の色: ' + c)
        pairs = list(itertools.permutations(cols, 2)); random.Random(3).shuffle(pairs)
    for c in (a.target_color, a.distractor_color):
        if c and c not in COLORS: raise SystemExit('未知の色: ' + c)
    if pairs or a.target_color:                       # ステージ2の既定の範囲(明示した --block-th/--block-r はそのまま使う)
        if a.block_th == [-90, -30]: a.block_th = list(STAGE2_BLOCK_TH)
        if a.block_r == [0.07, 0.12]: a.block_r = list(STAGE2_BLOCK_R)
    if a.grid: a.grid_cells = grid_cells()
    if a.replay: a.replay_cells = load_replay(os.path.join(ROOT, a.replay), a.n)
    swap_js = []
    if a.swap_of:
        sd = os.path.join(ROOT, a.swap_of)
        for f in sorted(os.listdir(sd)):
            if f.endswith('.json'):
                j = json.load(open(os.path.join(sd, f)))
                if j.get('success', True) and j.get('distractor'): swap_js.append(j)
        if not swap_js: raise SystemExit('入れ替え元のデモの json がありません: ' + sd)
    out = os.path.join(ROOT, a.name); os.makedirs(out, exist_ok=True); os.makedirs(OUTBOX, exist_ok=True)
    start_idx = len([f for f in os.listdir(out) if f.endswith('.npz')])
    rng = random.Random(a.seed + 1000 * start_idx)
    remove('wood_cube_5cm')                          # 元の立方体は障害物になる
    rclpy.init(); n = Runner(); n.spin_for(2.0)
    saved, prev, t0, errs, oks, lifts, carries, hfs, dists = 0, [], time.time(), [], [], [], [], [], []
    trks = []
    print('生成 %d 件 -> %s(既存 %d 件)' % (a.n, out, start_idx), flush=True)
    for i in range(a.n):
        th, rx, yaw_rel, thb, rb = sample(rng, a)
        x, y = rx * math.cos(th), rx * math.sin(th); bx, by = rb * math.cos(thb), rb * math.sin(thb)
        if pairs: tcol, dcol = pairs[i % len(pairs)]
        elif a.target_color: tcol, dcol = a.target_color, (a.distractor_color or '')
        else: tcol, dcol = a.color, ''
        dis = None
        if dcol:
            for _try in range(200):                                  # 妨害物を置ける配置が出るまで、対象・箱の配置ごと引き直す
                d_ = sample_distractor(rng, a, th, rx, thb, rb, a.min_sep)
                if d_: break
                th, rx, yaw_rel, thb, rb = sample(rng, a)
            else:
                raise SystemExit('妨害物を置ける配置が見つかりません(--min-sep を小さくするか、範囲を広げる)')
            dth, dr_, dyaw = d_
            x, y = rx * math.cos(th), rx * math.sin(th); bx, by = rb * math.cos(thb), rb * math.sin(thb)
            dis = (dth, dr_, dyaw, dr_ * math.cos(dth), dr_ * math.sin(dth))
        if swap_js:                                          # 元のデモと同じ画面(同じ位置・同じ色)で、対象だけ入れ替える
            j = swap_js[i % len(swap_js)]
            tcol, dcol = j['distractor_color'], j['target_color']
            dj = j['distractor']
            th, rx, yaw_rel = math.radians(dj['th']), dj['r'], math.radians(dj['yaw'])
            thb, rb = math.radians(j['box_th']), j['box_r']
            dth, dr_, dyaw = math.radians(j['block_th']), j['block_r'], math.radians(j['block_yaw_rel'])
            x, y = rx * math.cos(th), rx * math.sin(th); bx, by = rb * math.cos(thb), rb * math.sin(thb)
            dis = (dth, dr_, dyaw, dr_ * math.cos(dth), dr_ * math.sin(dth))
        n.step(HOME, OPEN, 3.0); n.cmd = np.array(HOME + [OPEN], dtype=np.float64)
        remove(BLK); remove(BOX); remove(DIS); time.sleep(0.4)
        spawn(BLK, block_sdf(BLK, SIZE, COLORS[tcol], density=a.density, mu=a.mu), x, y, Z_REST, th + yaw_rel)
        if dis: spawn(DIS, block_sdf(DIS, SIZE, COLORS[dcol], density=a.density, mu=a.mu), dis[3], dis[4], Z_REST, dis[0] + dis[2])
        spawn(BOX, box_sdf(BOX, INNER, wall_h=RIM), bx, by, TABLE_Z)
        time.sleep(1.5)
        s0 = get_pose(BLK)
        n.rec = dict(img=[], state=[], action=[], side=[])
        err = ''; probe = {}; serr = []; steps = []
        try:
            steps = plan(th, rx, thb, rb, a.carry_angle, a.carry_z, math.radians(a.close_deg), a.close_sec, a.release_z)
            kp, kc = 5, 5 + sum(1 for st in steps if not callable(st[0]) and st[2] == 0.7) + 2      # probeの位置: 持ち上げ直後 / 離す直前
            for k, (arm, hand, sec) in enumerate(steps):
                n.err_max = 0.0
                if callable(arm):
                    n.move_path(arm, sec)
                else:
                    tgt = n.cmd.copy()
                    if arm is not None: tgt[:4] = arm
                    if hand is not None: tgt[4] = hand
                    n.move(tgt, sec)
                serr.append((n.err_max, n.err_last))
                if a.probe and k in (4, kp, kc):
                    c = get_center(BLK, SIZE)
                    if c and s0 and k == 4:                                           # 閉じた直後(持ち上げ前): 把持点
                        probe['hf0'] = hand_frame(n.js, c)
                    elif c and s0:
                        if k == kp:
                            probe['hf'] = hand_frame(n.js, c)
                            probe['lift'] = c[2] - s0[2]                       # 持ち上げ直後の上昇量
                        else: probe['carry'] = math.hypot(c[0] - bx, c[1] - by)       # 離す直前の、箱の中心までの水平距離
        except Exception as e:
            err = str(e)
        rec, n.rec = n.rec, None
        trk = None
        kc_ = [k for k, st in enumerate(steps) if callable(st[0])]
        if kc_ and len(serr) > kc_[0] + 1:                              # 旋回(最大) / 待機(最後のコマ=離す直前に残るずれ) / 降下(最後のコマ=降ろし終わりに残るずれ)  (度)
            d_ = serr[kc_[1]][1] if len(kc_) > 1 and len(serr) > kc_[1] else 0.0
            trk = (math.degrees(serr[kc_[0]][0]), math.degrees(serr[kc_[0] + 1][1]), math.degrees(d_))
            trks.append(trk)
        time.sleep(0.6)
        s1 = get_center(BLK, SIZE)
        ok = False; e_r = e_t = 0.0; wrong = False
        if s0 and s1 and not err:
            dx, dy = s1[0] - bx, s1[1] - by
            ok = abs(dx) <= INNER / 2 and abs(dy) <= INNER / 2 and s1[2] - TABLE_Z < 0.045     # 中心が箱の内側で、縁に乗っていない
            if dis:                                                                             # 妨害物が箱に入っていない(取り違えは失敗)
                cd = get_center(DIS, SIZE)
                if in_box(cd, bx, by): ok = False; err = err or ''; wrong = True
            e_r = math.hypot(s1[0], s1[1]) - rb; e_t = (math.atan2(s1[1], s1[0]) - thb) * rb
        T = len(rec['action'])
        if s0 and s1 and not err:
            errs.append((e_r, e_t)); dists.append(math.hypot(dx, dy) * 1000)
        oks.append(ok)
        if probe:
            lifts.append(probe.get('lift', 0) * 1000); carries.append(probe.get('carry', 0) * 1000)
            if 'hf0' in probe and 'hf' in probe:
                hfs.append(list(probe['hf0'][:3]) + list(probe['hf'][:3]) + [probe['hf'][3]])
        print('%3d/%d %s積み木(θ%+4.0f°,r%.3f,向き%+3.0f°) → 箱(θ%+4.0f°,r%.3f) %s%s  %d コマ  半径方向%+5.1f mm 接線方向%+5.1f mm %s' % (
            i + 1, a.n, ('[対象%s・妨害物%s] ' % (tcol, dcol)) if dcol else '', math.degrees(th), rx, math.degrees(yaw_rel), math.degrees(thb), rb, '成功' if ok else '失敗', '(妨害物が箱に入った)' if wrong else '', T, e_r * 1000, e_t * 1000, err + (' [診断] 持ち上げ後の上昇 %.0f mm / 離す直前の箱中心までの距離 %.0f mm' % (probe.get('lift', 0) * 1000, probe.get('carry', 0) * 1000) if probe else '') + ((' 追従誤差[旋回 %.1f° 待機 %.1f° 降下 %.1f°]' % trk) if trk else '') + (' / 把持点[軸 %+.0f 直角 %+.0f 接線 %+.0f mm]→持ち上げ後[軸 %+.0f 直角 %+.0f 接線 %+.0f mm 手先%.0f°]' % tuple([v * 1000 for v in probe['hf0'][:3]] + [v * 1000 for v in probe['hf'][:3]] + [probe['hf'][3]]) if 'hf0' in probe and 'hf' in probe else '')), flush=True)
        if ok or a.keep_failures:
            idx = start_idx + saved
            np.savez_compressed(os.path.join(out, 'ep_%04d.npz' % idx), img=np.stack(rec['img']),
                                state=np.stack(rec['state']), action=np.stack(rec['action']))
            json.dump(dict(success=ok, color=tcol, target_color=tcol, distractor_color=dcol, task=task_text(tcol), distractor=(dict(th=math.degrees(dis[0]), r=dis[1], yaw=math.degrees(dis[2])) if dis else None), wrong_block=wrong, block_th=math.degrees(th), block_r=rx, block_yaw_rel=math.degrees(yaw_rel),
                           box_th=math.degrees(thb), box_r=rb, inner=INNER, rim=RIM, size=SIZE, frames=T,
                           e_r=e_r, e_t=e_t, trk=list(trk) if trk else None), open(os.path.join(out, 'ep_%04d.json' % idx), 'w'), ensure_ascii=False)
            if rec['side'] and len(rec['side']) == len(rec['img']) and not a.no_side:      # 斜めカメラの映像は、小さいmp4にして別に貯める(npzには入れない)
                try:
                    from expert_video import write_video
                    write_video(rec['side'], os.path.join(out, 'ep_%04d_side.mp4' % idx))
                except Exception as e:
                    print('斜めカメラの動画は保存できませんでした:', e)
            saved += 1
            if len(prev) < 4:
                prev.append(dict(img=np.stack(rec['img'])))
        if a.abort_after and len(oks) == a.abort_after and sum(oks) < a.abort_below * a.abort_after:
            print('[自動停止] 最初の %d 件の成功率が %d/%d で、基準(%.0f%%)未満です。配置・色・妨害物の設定を確かめてから実行し直してください' % (a.abort_after, sum(oks), len(oks), 100 * a.abort_below), flush=True)
            n.step(HOME, 0.0, 2.0); remove(BLK); remove(BOX); remove(DIS)
            rclpy.shutdown(); sys.exit(3)
    n.step(HOME, 0.0, 2.0)
    remove(BLK); remove(BOX); remove(DIS)
    t_gen = time.time() - t0
    print('[時間] 生成 %d 件 %.0f 秒(%.1f 秒/件。動画の作成は含まない)' % (a.n, t_gen, t_gen / max(1, a.n)), flush=True)
    if prev:
        preview(prev, os.path.join(OUTBOX, 'episodes_preview.png'))
    try:
        from expert_video import make_video
        print('動画:', make_video(out, os.path.join(OUTBOX, a.name + '_demo.mp4'), n=6 if a.keep_failures else 4, speed=2, failures=a.keep_failures))
    except Exception as e:
        print('動画は作れませんでした:', e)
    if errs:
        er = np.array(errs) * 1000
        print('\n着地のずれ(積み木の中心、mm): 半径方向 平均%+.1f 標準偏差%.1f / 接線方向 平均%+.1f 標準偏差%.1f (n=%d)' % (
            er[:, 0].mean(), er[:, 0].std(), er[:, 1].mean(), er[:, 1].std(), len(er)))
    if hfs:
        h = np.array(hfs); m = h.mean(0) * np.array([1000] * 6 + [1]); sd = h.std(0) * np.array([1000] * 6 + [1])
        print('[把持点] link4から見た積み木の中心(mm、平均±標準偏差)。軸=手の向きに沿う方向(積み木の中心が指先側なら正、積み木が5 cmなので中心を挟む指なら約115) 直角=手の面内で軸に直角 接線=横方向')
        print('  閉じた直後: 軸 %+.0f±%.0f 直角 %+.0f±%.0f 接線 %+.0f±%.0f' % (m[0], sd[0], m[1], sd[1], m[2], sd[2]))
        print('  持ち上げ後(手先%.0f°): 軸 %+.0f±%.0f 直角 %+.0f±%.0f 接線 %+.0f±%.0f / 持ち上げ中の変化: 軸 %+.0f 直角 %+.0f 接線 %+.0f' % (m[6], m[3], sd[3], m[4], sd[4], m[5], sd[5], m[3] - m[0], m[4] - m[1], m[5] - m[2]))
    if trks:
        t_ = np.array(trks)
        print('[追従誤差] 指令と実測の関節角のずれ(度、平均/最大)。旋回=旋回中の最大(動きに遅れてついてくる分)、待機=静止の最後のコマ、降下=降ろし終わり。待機と降下は、動きが止まっているので0に近いはず。大きく残るなら、腕が目標に届く前に離している/何かに押されている')
        print('  旋回 %.1f/%.1f  待機 %.1f/%.1f  降下 %.1f/%.1f' % (t_[:, 0].mean(), t_[:, 0].max(), t_[:, 1].mean(), t_[:, 1].max(), t_[:, 2].mean(), t_[:, 2].max()))
    print('[要約] mu=%.1f 閉じ指令=%.0f° 閉じ時間=%.1f秒 密度=%.0f 運び=%.0f°/%.2f m 離す高さ=%s: 成功 %d/%d / 箱の中心からの着地距離 平均%.0f mm 最大%.0f mm%s' % (
        a.mu, a.close_deg, a.close_sec, a.density, a.carry_angle, a.carry_z, ('%.2f m' % a.release_z) if a.release_z is not None else '運ぶ高さ', sum(oks), len(oks),
        np.mean(dists) if dists else 0, np.max(dists) if dists else 0,
        (' / 持ち上げ後の上昇 平均%.1f mm / 離す直前の箱中心までの距離 平均%.0f mm 最大%.0f mm' % (np.mean(lifts), np.mean(carries), np.max(carries))) if lifts else ''))
    print('\n保存 %d 件 / 試行 %d 件(%.0f 秒)。プレビュー: outbox/episodes_preview.png' % (saved, a.n, time.time() - t0))
    rclpy.shutdown()


if __name__ == '__main__':
    main()
