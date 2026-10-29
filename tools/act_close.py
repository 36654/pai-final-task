# ACT の段階2A/2B の記録(eval_traces)から、手を閉じた位置が「対象」「もう一方の積み木」「中間」のどれかを調べる(読み取り専用。Gazebo 不要)
# usage: act_close.py [モデル名に含まれる文字列(既定 act30k_1029)]   配置は seed 2000 の10通り(BLUE_TH はその妨害物の角度)
import glob, os, sys
PAT = sys.argv[1] if len(sys.argv) > 1 else 'act30k_1029'
import numpy as np
D = np.degrees
BLUE_TH = [-33, -111, -30, -37, -111, -36, -47, -103, -44, -36]   # 配置0〜9の妨害物(青=A / 赤=B)の角度(seed 2000 から再現。赤の位置はログと一致を確認済み)
for scn in ('A', 'B'):
    ds = [d for d in sorted(glob.glob('/home/ubuntu/eval_traces/*')) if PAT in d and ('_s%s_' % scn) in d]
    if not ds: print('段階2%s: 記録なし(%s)' % (scn, PAT)); continue
    d = ds[-1]; fs = sorted(glob.glob(d + '/ep_*.npz'))
    print('\n=== 段階2%s %s (%d 回) ===' % (scn, os.path.basename(d), len(fs)))
    print('角度は第1関節(度)。T=対象位置(A:赤 B:黄) D=もう一方の位置(A:青 B:赤) 中間=TとDの中点。閉じ角=手の指令が最初に閉じ側になった時点の実測の旋回角。\n判定: 閉じ角が T か D の8°以内ならその積み木の上で閉じた、中間から8°以内でどちらからも17°以上離れていれば「中間」')
    print('回 T      D      中間   閉じコマ 閉じ角   |閉じ角-T| |閉じ角-D| |閉じ角-中間| 判定')
    cnt = {'T': 0, 'D': 0, '中間': 0, 'その他': 0, '閉じず': 0}
    for f in fs:
        i = int(os.path.basename(f)[3:5]); z = np.load(f)
        st, cm = z['state'].astype(np.float64), z['cmd'].astype(np.float64)
        T = float(z['block_th']); Dd = BLUE_TH[i]; M = (T + Dd) / 2
        c = np.where(cm[:, 4] > 0)[0]
        if not len(c):
            cnt['閉じず'] += 1; print('%2d %+5.0f° %+5.0f° %+5.0f° 閉じず' % (i, T, Dd, M)); continue
        i0 = int(c[0]); e = float(D(st[i0, 0]))
        dT, dD, dM = abs(e - T), abs(e - Dd), abs(e - M)
        j = 'T' if dT <= 8 and dT <= dD else 'D' if dD <= 8 else '中間' if dM <= 8 and dT >= 17 and dD >= 17 else 'その他'
        cnt[j] += 1
        print('%2d %+5.0f° %+5.0f° %+5.0f° %6d  %+6.0f°  %6.0f°  %6.0f°  %6.0f°    %s' % (i, T, Dd, M, i0, e, dT, dD, dM, j))
    print('集計: ' + ' / '.join('%s %d' % (k, v) for k, v in cnt.items()))
print('\nRESULT=OK')
