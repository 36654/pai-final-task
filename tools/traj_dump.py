import glob, os, sys, numpy as np
TR = '/home/ubuntu/eval_traces'; NPZ = '/home/ubuntu/dataset/expert_npz/s1_region'
T = [0, 0.5, 1, 2, 3, 5, 8, 12, 20, 29]
def deg(x): return np.round(np.degrees(np.asarray(x, dtype=np.float64)), 0).astype(int)
def row(label, arr, ts):
    out = []
    for t in ts:
        k = int(t * 20)
        if k < len(arr): out.append('%2ds:%s' % (t, ','.join('%4d' % v for v in deg(arr[k][:5]))))
    print('    ' + label + ' ' + ' | '.join(out))
print('=== eval_traces (更新時刻順)')
for d in sorted(glob.glob(TR + '/*'), key=os.path.getmtime):
    print('  %s  %d件  %s' % (os.path.basename(d), len(glob.glob(d + '/ep_*.npz')), __import__('time').strftime('%m-%d %H:%M', __import__('time').localtime(os.path.getmtime(d)))))
names = sys.argv[1:] or ['eval_s1_region_te_chk0420', 'eval_s1_region_te_r1']
for nm in names:
    fs = sorted(glob.glob(os.path.join(TR, nm, 'ep_*.npz')))
    print('\n=== %s (%d件)  各行: 秒:関節1..4,手(度)。cmd=指令 st=実測' % (nm, len(fs)))
    for f in fs[:4]:
        z = np.load(f, allow_pickle=True); i = int(os.path.basename(f)[3:5])
        print('  ep%02d 成功=%s 積み木θ=%.0f° 箱θ=%.0f° コマ数=%d' % (i, bool(z['ok']), float(z['block_th']), float(z['box_th']), len(z['cmd'])))
        row('cmd', z['cmd'], T); row('st ', z['state'], T)
        c = z['cmd']; mv = np.where(np.abs(c[:, :4] - np.array([0.0, -1.16, -2.01, -0.73])).max(axis=1) > np.radians(3))[0]
        print('    指令がホームから3°以上離れた最初のコマ: %s / 閉じ指令(手>-0.4rad)が出た最初のコマ: %s' % (mv[0] if len(mv) else 'なし', (np.where(c[:, 4] > -0.4)[0][0] if (c[:, 4] > -0.4).any() else 'なし')))
        mfa = z['msg_at_frame'] if 'msg_at_frame' in z.files else None
        if mfa is not None and len(mfa) > 1: print('    1コマあたりの積み木の姿勢メッセージ数: 平均 %.2f(開始直後の最初の20コマ: %.2f)' % (float(np.diff(mfa).mean()), float(np.diff(mfa[:21]).mean())))
        if 'r1' in nm and os.path.exists(os.path.join(NPZ, 'ep_%04d.npz' % i)):
            e = np.load(os.path.join(NPZ, 'ep_%04d.npz' % i)); print('    [専門家のデモ ep_%04d の同じ時刻]' % i)
            row('act', e['action'], T); row('st ', e['state'], T)
