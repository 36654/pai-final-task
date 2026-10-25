#!/usr/bin/env python3
"""eval_act が記録した指令・関節角(/home/ubuntu/eval_traces/NAME)を、専門家のデモ(LeRobotデータセットの action)と比べる。
見るもの: 閉じ始めから持ち上げ始めまでの時間(専門家は2.0秒)、持ち上げ時の手の実測角、最大の閉じ指令、旋回の最大速度、運ぶ時間。"""
import glob, os, sys
import numpy as np

FPS = 20.0
OPEN = -0.5236
L1, L2, H = 0.083, 0.0935, 0.0714       # expert_lib と同じ(rclpy なしで使うため複製)


def fk4(q):
    """関節角から link4 の (半径, 高さ, 手先の向き[度]) を返す。高さは机の面から。向きは180=真下、90=水平。"""
    a1 = q[1]; a2 = a1 - q[2]; a3 = a2 - q[3]
    return L1 * np.sin(a1) + L2 * np.sin(a2), H + L1 * np.cos(a1) + L2 * np.cos(a2), float(np.degrees(a3))


def events(act, state=None):
    g = act[:, 4]
    idx = np.where(g > OPEN + 0.05)[0]
    if len(idx) == 0:
        return None
    tc = int(idx[0])                                        # 閉じ始め
    j2 = act[:, 1]
    d = np.where(np.abs(j2[tc:] - j2[tc]) > 0.03)[0]
    tl = tc + int(d[0]) if len(d) else None                 # 持ち上げ始め(関節2が動く)
    after = np.where(g[tc + 20:] < g[tc:].max() - 0.3)[0]
    tr = tc + 20 + int(after[0]) if len(after) else None    # 離し始め
    e = dict(gmax=float(g[tc:(tr or len(g))].max()), dwell=(tl - tc) / FPS if tl else None,
             carry=(tr - tl) / FPS if (tl and tr) else None, grip_state=float(state[tl, 4]) if (state is not None and tl) else None)
    if tl and state is not None:
        e['r4'], e['z4'], e['a3'] = fk4(state[tl])           # 持ち上げ始めの、手の位置と向き(実測)
    if tl:
        e['tl'], e['tr'] = tl, tr
        end = tr or len(act)
        e['peak_j1'] = float(np.max(np.abs(np.diff(act[tl:end, 0]))) * FPS) if end - tl > 2 else None
        w = min(end, tl + int(8 * FPS))                     # 持ち上げ後の8秒間(垂直→水平に起こす区間を含む)
        e['w'] = w
        if w - tl > 5:
            e['gc_min'] = float(g[tl:w].min())              # 運ぶ間の閉じ指令の最小(緩めていないか)
            if state is not None:
                e['gs_min'] = float(state[tl:w, 4].min())   # 運ぶ間の手の実測角の最小(積み木がずり落ちると小さくなる)
            if w - tl > 6:
                e['jit'] = float(np.mean(np.abs(np.diff(act[tl:w, 1:4], n=2, axis=0))) * 1000)   # 指令の震え(2階差分の平均, 1000倍)
            pitch = act[tl:w, 1] + act[tl:w, 2] + act[tl:w, 3]   # 手先の傾き(関節2+3+4)
            tot = pitch[-1] - pitch[0]
            if abs(tot) > 0.3:
                k = np.where(np.abs(pitch - pitch[0]) >= 0.9 * abs(tot))[0]
                e['tilt_s'] = float(k[0] / FPS) if len(k) else None   # 90%まで起こすのにかかった時間
    return e


TABLE_Z, HALF = 1.015, 0.025


def pose_stats(z, e):
    """評価中に記録した積み木の位置(blk)と関節角から、「手から見た積み木の位置」の変化を出す(expert_episode.bat --probe の「把持点」と同じ座標)。
    s=手の軸方向(真下向きのとき下が正), p=軸に直角で面内(真下向きのとき外向きが負), w=横(旋回方向)。いずれも link4 から見た積み木の中心(mm)。
    g*=閉じ終わった直後(持ち上げ始め) / s0,p0,w0=その1秒後 / ds,dp,dw=手を起こし終わるまでの変化(ずり落ちると ds が動く) / slip=その後の最大ずれ。
    gy,y1=積み木の向きの、手に対する角度(度。0=指と平行, ±45=対角)の、閉じ直後と起こし終わり。"""
    if 'blk' not in z.files or 'msg_at_frame' not in z.files or 'tl' not in e:
        return None
    blk, maf, state = z['blk'], z['msg_at_frame'], z['state']
    if len(blk) == 0:
        return None
    M = len(blk); valid = ~np.isnan(blk[:, 0])
    ff = np.maximum.accumulate(np.where(valid, np.arange(M), -1))
    x0, y0, z0, yaw0 = [float(v) for v in z['blk0']]
    init = np.array([x0, y0, z0, 0, 0, np.sin(yaw0 / 2), np.cos(yaw0 / 2)])

    def row_at(k):
        m = min(int(maf[k]) - 1, M - 1)
        return init if (m < 0 or ff[m] < 0) else blk[ff[m]]

    def center(k):
        qx, qy, qz, qw = row_at(k)[3:7]; r = row_at(k)
        return np.array([r[0] + 2 * (qx * qz + qw * qy) * HALF, r[1] + 2 * (qy * qz - qw * qx) * HALF, r[2] + (1 - 2 * (qx * qx + qy * qy)) * HALF])

    def yaw_rel(k):
        qx, qy, qz, qw = row_at(k)[3:7]
        yb = np.degrees(np.arctan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz)))
        return float((yb - np.degrees(state[k, 0]) + 45.0) % 90.0 - 45.0)

    tl, tr, w = e['tl'], e['tr'], e['w']
    n = len(state)

    def hand_coords(k):
        c = center(k); r4, z4, a3 = fk4(state[k]); a = np.radians(a3)
        rb = np.hypot(c[0], c[1]); thb = np.arctan2(c[1], c[0])
        d0, d1 = rb - r4, (c[2] - TABLE_Z) - z4
        s_ = d0 * np.sin(a) + d1 * np.cos(a); p_ = d0 * np.cos(a) - d1 * np.sin(a)
        w_ = (thb - state[k, 0]) * rb
        return np.array([s_, p_, w_]) * 1000, (c[2] - TABLE_Z) * 1000
    ks = list(range(tl, min(w, n)))
    if len(ks) < 25:
        return None
    t0 = min(tl + 20, n - 1)
    g, _ = hand_coords(tl)
    h0, _ = hand_coords(t0)
    tt = min(t0 + int((e.get('tilt_s') or 3.0) * FPS), n - 1)
    h1, _ = hand_coords(tt)
    track = np.array([hand_coords(k)[0] for k in ks]); zs = np.array([hand_coords(k)[1] for k in ks]) - HALF * 1000   # 中心高さ-半分=底面の高さ(mm)
    slip = float(np.max(np.linalg.norm(track - h0, axis=1)))
    out = dict(gs=g[0], gp=g[1], gw=g[2], s0=h0[0], p0=h0[1], w0=h0[2], ds=h1[0] - h0[0], dp=h1[1] - h0[1], dw=h1[2] - h0[2], slip=slip, zmax=float(zs.max()),
               gy=yaw_rel(tl), y1=yaw_rel(tt))
    out['agy'] = abs(out['gy'])
    zi = int(np.argmax(zs)); fell = np.where(zs[zi:] < 10.0)[0]       # 最高点のあと、底面が机から10 mm以内に戻った時刻
    out['drop_t'] = float((zi + fell[0]) / FPS) if (zs.max() > 15.0 and len(fell)) else None
    out['lifted'] = bool(zs.max() > 15.0)
    return out


def fmt(v, f='%.2f'):
    return '-' if v is None else f % v


def main():
    root = '/home/ubuntu/eval_traces'
    names = [os.path.basename(p) for p in sorted(glob.glob(root + '/*')) if os.path.isdir(p)]
    pick = sys.argv[1:]
    # 専門家
    import pandas as pd
    files = sorted(glob.glob('/home/ubuntu/dataset/lerobot_dataset/s1_region/data/*/episode_*.parquet'))
    ex = []
    for f in files:
        df = pd.read_parquet(f)
        a = np.stack(df['action'].to_numpy()); s = np.stack(df['observation.state'].to_numpy())
        e = events(a, s)
        if e: ex.append(e)
    def mean(es, k):
        v = [e[k] for e in es if e.get(k) is not None]
        return (np.mean(v), np.std(v)) if v else (None, None)
    print('trace_stats 版: 10/18 01:10 (積み木の連続記録・手から見た位置あり)')
    print('専門家(%d件): ' % len(ex) + ' / '.join('%s %s±%s' % (k, fmt(mean(ex, k)[0], '%.3f' if k == 'z4' else '%.2f'), fmt(mean(ex, k)[1], '%.3f' if k == 'z4' else '%.2f')) for k in ('dwell', 'gmax', 'grip_state', 'carry', 'peak_j1', 'gc_min', 'gs_min', 'tilt_s', 'z4', 'a3', 'jit')))
    print('  z4=持ち上げ始めのlink4の高さ(m。専門家は0.163。検出のタイミングに左右され、掴んだ高さとは別) a3=そのときの手先の向き(度。180=真下) jit=持ち上げ後8秒の指令の震え(関節2〜4の2階差分の平均×1000。大きいほど細かく揺れる) dr=link4の半径-積み木の半径(mm。新しい評価のみ)')
    print('  [新] 握り: dr=手の半径-積み木の半径 dt=旋回方向のずれ(mm) / s,p,w=link4から見た積み木の中心(mm。expert_episode.bat --probe の把持点と同じ座標。s=手の軸方向 p=直角 w=横) / 向き=積み木と指の角度(0=平行,±45=対角) / 最大ずれ=1秒後の位置からの最大移動(5 mm超えるとずり落ち)')
    print('  gc_min=運ぶ間の閉じ指令の最小 gs_min=運ぶ間の手の実測角の最小(0.09から下がるとずり落ち) tilt_s=手先を起こすのにかかった秒')
    print('  dwell=閉じ始め→持ち上げ始め(秒) gmax=最大の閉じ指令(rad) grip_state=持ち上げ時の手の実測角(rad) carry=持ち上げ→離す(秒) peak_j1=旋回の最大速度(rad/s)\n')
    for nm in names:
        if pick and nm not in pick: continue
        rows = []
        for f in sorted(glob.glob('%s/%s/ep_*.npz' % (root, nm))):
            z = np.load(f)
            e = events(z['cmd'], z['state'])
            if e is not None and 'r4' in e and 'block_r' in z.files:
                e['dr'] = (e['r4'] - float(z['block_r'])) * 1000
                e['adr'] = abs(e['dr'])
                e['dt'] = (float(z['state'][e['tl'], 0]) - np.radians(float(z['block_th']))) * e['r4'] * 1000      # 旋回方向の握りのずれ(mm)
                e['adt'] = abs(e['dt'])
                e['yaw'] = float(z['yaw'])
                e['ayaw'] = abs(e['yaw'])
            if e is not None:
                try:
                    ps = pose_stats(z, e)
                except Exception as ex:
                    ps = None; print('  (姿勢の解析に失敗: %s)' % ex)
                if ps: e.update(ps)
            rows.append((os.path.basename(f), bool(z['ok']), float(z['block_th']), e))
        print('=== %s ===' % nm)
        for fn, ok, th, e in rows:
            if e is None:
                print('%s %s θ%+4.0f° 閉じ指令なし' % (fn, '成功' if ok else '失敗', th)); continue
            print('%s %s θ%+4.0f°  dwell %s gmax %s grip_state %s carry %s peak_j1 %s | gc_min %s gs_min %s tilt_s %s | z4 %s a3 %s dr %s jit %s' % (
                fn, '成功' if ok else '失敗', th, fmt(e['dwell']), fmt(e['gmax']), fmt(e['grip_state']), fmt(e['carry']), fmt(e['peak_j1']),
                fmt(e.get('gc_min')), fmt(e.get('gs_min')), fmt(e.get('tilt_s')), fmt(e.get('z4'), '%.3f'), fmt(e.get('a3'), '%.0f'), fmt(e.get('dr'), '%.0f'), fmt(e.get('jit'), '%.2f')))
            if e.get('dt') is not None:
                line = '      握り: dr %s dt %s 置いた向き %s' % (fmt(e.get('dr'), '%+.0f'), fmt(e.get('dt'), '%+.0f'), fmt(e.get('yaw'), '%+.0f'))
                if 's0' in e:
                    line += ' | 閉じ直後 s%s p%s w%s 向き%s° | 1秒後 s%s p%s w%s | 起こし終わりまでの変化 ds%s dp%s dw%s 向き%s° | 最大ずれ %s mm | 最高の底面高 %s mm | %s' % (
                        fmt(e.get('gs'), '%+.0f'), fmt(e.get('gp'), '%+.0f'), fmt(e.get('gw'), '%+.0f'), fmt(e.get('gy'), '%+.0f'),
                        fmt(e.get('s0'), '%+.0f'), fmt(e.get('p0'), '%+.0f'), fmt(e.get('w0'), '%+.0f'),
                        fmt(e.get('ds'), '%+.0f'), fmt(e.get('dp'), '%+.0f'), fmt(e.get('dw'), '%+.0f'), fmt(e.get('y1'), '%+.0f'),
                        fmt(e.get('slip'), '%.0f'), fmt(e.get('zmax'), '%.0f'),
                        '持ち上がらず' if e.get('lifted') is False else ('落下 持ち上げ後%.1f秒' % e['drop_t'] if e.get('drop_t') is not None else '落下なし'))
                else:
                    line += ' | (積み木の連続記録なし)'
                print(line)
        for lab, sel in (('成功', True), ('失敗', False)):
            es = [e for _, ok, _, e in rows if ok == sel and e]
            if es:
                print('  %s平均(%d件): ' % (lab, len(es)) + ' / '.join('%s %s' % (k, fmt(mean(es, k)[0])) for k in ('dwell', 'gmax', 'grip_state', 'carry', 'peak_j1', 'gc_min', 'gs_min', 'tilt_s', 'z4', 'a3', 'jit')))
            ex_keys = ('adr', 'adt', 'ayaw', 'agy', 'gs', 'gp', 'gw', 's0', 'p0', 'w0', 'ds', 'dp', 'dw', 'slip', 'zmax', 'drop_t')
            if any(mean(es, k)[0] is not None for k in ex_keys):
                print('     握り・ずれの平均: ' + ' / '.join('%s %s' % (k, fmt(mean(es, k)[0], '%.1f')) for k in ex_keys if mean(es, k)[0] is not None))
        print()


if __name__ == '__main__':
    main()
