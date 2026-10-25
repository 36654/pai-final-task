"""SmolVLA の診断(Gazebo 不要。何も変更しない)。推論サーバー(Colab)に、学習デモの画像・関節角・指示を送って答えを見る。
 [1] 学習デモの画面での再現: 正しい指示で出る行動の塊(50コマ)を、専門家のデモの行動と比べる(誤差が大きいなら、学習か読み込みの問題)
 [2] 指示の効き: 同じ画面で、対象の色/妨害物の色の指示を替えたとき、旋回(関節1)の向かう先が指示した積み木の角度に近づくか
 [3] 評価中の記録: eval_traces にある直近の評価(名前に s2 を含む)で、各回の腕が、積み木の角度の近くで閉じたか(ACT と SmolVLA の比較用)
usage: vla_diag.py URL TOKEN [データ名]"""
import base64, glob, json, os, sys, time, urllib.request
import numpy as np
url, token = sys.argv[1].rstrip('/'), sys.argv[2]
NAME = sys.argv[3] if len(sys.argv) > 3 else 's2_color_1024'
NPZ = '/home/ubuntu/dataset/expert_npz/' + NAME
D = np.degrees


def predict(img, state, task, seed=7):
    body = json.dumps(dict(img=base64.b64encode(np.ascontiguousarray(img).tobytes()).decode(), h=int(img.shape[0]), w=int(img.shape[1]),
                           state=[float(x) for x in state], task=task, seed=seed)).encode()
    for k in range(4):
        try:
            rq = urllib.request.Request(url + '/predict', data=body, headers={'Content-Type': 'application/json', 'X-Token': token, 'User-Agent': 'pai-eval'})
            with urllib.request.urlopen(rq, timeout=180) as r: r = json.loads(r.read())
            if 'err' in r: raise RuntimeError(r['err'])
            return np.frombuffer(base64.b64decode(r['actions']), np.float32).reshape(r['n'], r['dim']).astype(np.float64)
        except Exception as ex:
            print('  [通信失敗 %d/4] %s' % (k + 1, str(ex)[:100]), flush=True); time.sleep(3)
    raise SystemExit('推論サーバーに接続できません')


def task_text(c): return 'put the %s block in the box' % c


js = sorted(glob.glob(NPZ + '/ep_*.json'))
if not js: raise SystemExit('学習デモがありません: ' + NPZ)
meta = [json.load(open(f)) for f in js]
pick = {}
for f, m in zip(js, meta):
    key = (m.get('target_color'), m.get('distractor_color'))
    if key not in pick: pick[key] = f[:-5]
print('=== [1][2] 学習デモの画面(データ %s、組み合わせ %d 通りから各1デモ)===' % (NAME, len(pick)))
print('指令の単位は度。関節1=旋回(専門家は積み木の角度θへ回す)。誤差=|方策-専門家|の平均(最初の10コマ/50コマ、関節1〜4と手)', flush=True)
fr = [0, 40, 100, 160]
follow = []; err10 = []; err50 = []
for key, base in sorted(pick.items(), key=lambda kv: str(kv[0])):
    z = np.load(base + '.npz'); m = json.load(open(base + '.json'))
    img, st, act = z['img'], z['state'].astype(np.float32), z['action'].astype(np.float64)
    T, Dc = key; thT = m['block_th']; thD = (m.get('distractor') or {}).get('th')
    print('\n-- %s 対象=%s(θ%+.0f°) 妨害物=%s(θ%+.0f°)  コマ数 %d' % (os.path.basename(base), T, thT, Dc, thD if thD is not None else float('nan'), len(img)), flush=True)
    for k in [x for x in fr if x < len(img)]:
        pT = predict(img[k], st[k], task_text(T))
        ref = act[k:k + 50]; n = len(ref)
        e = np.abs(pT[:n] - ref)
        e10 = D(e[:10].mean(axis=0)); e50 = D(e.mean(axis=0))
        err10.append(e10.mean()); err50.append(e50.mean())
        line = '   コマ%3d 指示=%s: 誤差10コマ %s / 50コマ %s' % (k, T, np.round(e10, 1), np.round(e50, 1))
        if k == 0:
            pD = predict(img[k], st[k], task_text(Dc))
            jT, jD, jE = D(pT[49, 0]), D(pD[49, 0]), D(act[49, 0])
            okf = abs(jT - thT) < abs(jT - thD) and abs(jD - thD) < abs(jD - thT)
            follow.append(okf)
            line += '\n           旋回(関節1)の49コマ先: 指示=%s→%+.0f° / 指示=%s→%+.0f° / 専門家%+.0f° (θ対象%+.0f° θ妨害物%+.0f°) → 指示どおりの向き: %s' % (
                T, jT, Dc, jD, jE, thT, thD, 'はい' if okf else 'いいえ')
        print(line, flush=True)
print('\n[1] 方策と専門家の指令のずれ(全体平均): 10コマ先まで %.1f° / 50コマ先まで %.1f°' % (np.mean(err10), np.mean(err50)))
print('[2] 指示を替えると旋回の向かう先が指示した積み木に変わった: %d/%d 組み合わせ(コマ0)。注意: 学習デモの画面そのものなので、画面を覚えていれば指示を使わなくても同じ結果になる。指示の効きは stage2_eval.bat seen で測る' % (sum(follow), len(follow)))

print('\n=== [3] 評価中の腕の動き(eval_traces のうち名前に s2 を含むもの)===')
print('閉じた=手の指令が閉じ側(>0)になった回。閉じた時の旋回-θ=閉じた時点の関節1の実測と積み木の角度の差(度。数°以内なら積み木の真上で閉じた)', flush=True)
for d in sorted(glob.glob('/home/ubuntu/eval_traces/*')):
    if 's2' not in os.path.basename(d): continue
    fs = sorted(glob.glob(d + '/ep_*.npz'))
    if not fs: continue
    print('\n-- %s (%d 回)' % (os.path.basename(d), len(fs)))
    nc = 0
    for f in fs:
        z = np.load(f); st, cm = z['state'].astype(np.float64), z['cmd'].astype(np.float64)
        th = float(z['block_th']); ok = bool(z['ok'])
        c = np.where(cm[:, 4] > 0)[0]
        if len(c):
            nc += 1; i0 = int(c[0]); s = '閉じた コマ%d 閉じた時の旋回-θ %+.0f° ' % (i0, D(st[i0, 0]) - th)
        else:
            s = '閉じなかった '
        j1 = D(cm[:, 0])
        print('   %s %-4s θ%+4.0f° 指令の旋回の範囲 %+.0f〜%+.0f° %s(%d コマ)' % (os.path.basename(f)[3:5], '成功' if ok else '失敗', th, j1.min(), j1.max(), s, len(cm)))
    print('   閉じた回: %d/%d' % (nc, len(fs)))
print('\nRESULT=OK')
