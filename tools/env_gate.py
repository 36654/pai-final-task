# env_gate.py : 評価・デモ生成の開始時に、実験環境が意図どおりかを確かめる(10/25 追加)。
#   eval_act.py と expert_episode.py が、引数の解析の直後に env_gate.run() を呼ぶ。外れていれば終了コード3で測定を始めない。
#   確認する項目: (1) 指の摩擦 mu1 が xacro(src と install)の6か所すべて期待値  (2) Gazebo サーバーの起動が xacro の更新より新しい
#                 (3) チェックポイントのハッシュ(記録のみ)。(1)が外れていれば finger_friction.sh で書き換えてから確かめ直す。
#   環境変数 XACRO_SRC / XACRO_INST / FRICTION_SH / EXPECT_MU1 は試験用。標準ライブラリだけで動く。
import glob, hashlib, os, re, subprocess, sys, time

SRC = '/home/ubuntu/airobot_ws/src/crane_plus/crane_plus_description/urdf/crane_plus.gazebo.xacro'
INST = '/home/ubuntu/airobot_ws/install/crane_plus_description/share/crane_plus_description/urdf/crane_plus.gazebo.xacro'
FRIC = '/home/ubuntu/tools/finger_friction.sh'
PS_RE = re.compile(r'^\s*([A-Za-z]{3} [A-Za-z]{3} +\d+ \d\d:\d\d:\d\d \d{4}) ign gazebo server( .*)?$')


def count_mu1(path, expect):
    try: t = open(path, encoding='utf-8', errors='replace').read()
    except OSError: return -1, -1
    return t.count('<mu1>%s</mu1>' % expect), t.count('<mu1>')


def gazebo_start():
    """引数が「ign gazebo server」で始まるプロセスの起動時刻(エポック秒)。複数あれば一番古いもの(古い Gazebo が残っていれば検出する)。"""
    out = subprocess.run(['ps', '-eo', 'lstart,args'], capture_output=True, text=True).stdout
    ts = []
    for line in out.splitlines():
        m = PS_RE.match(line)
        if m:
            try: ts.append((time.mktime(time.strptime(' '.join(m.group(1).split()), '%a %b %d %H:%M:%S %Y')), m.group(1)))
            except ValueError: pass
    return min(ts) if ts else (None, '')


def ckpt_hash(model_path):
    if not model_path: return None, None
    fs = sorted(glob.glob(os.path.join(model_path, '**', '*.safetensors'), recursive=True))
    if not fs: return None, model_path
    h = hashlib.sha256()
    with open(fs[0], 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()[:16], fs[0]


def run(kind='eval', model_path=None, skip=False, fix=True):
    src = os.environ.get('XACRO_SRC', SRC); inst = os.environ.get('XACRO_INST', INST)
    fric = os.environ.get('FRICTION_SH', FRIC); expect = os.environ.get('EXPECT_MU1', '1.5')
    P = lambda s: print(s, flush=True)
    P('[環境確認] %s / 種別=%s' % (time.strftime('%F %T %Z'), kind))
    if skip:
        P('[環境確認] 省略(--skip-env-gate)。この結果は環境を確認せずに測ったもの。結果に必ず書くこと'); return True
    ok = True
    if fix and count_mu1(src, expect)[0] != 6 and os.path.isfile(fric):
        P('  指の摩擦が %s ではないため、finger_friction.sh %s を実行して書き換えます' % (expect, expect))
        r = subprocess.run(['bash', fric, expect], capture_output=True, text=True)
        for l in (r.stdout + r.stderr).splitlines(): P('    ' + l)
    for f in (src, inst):
        n1, na = count_mu1(f, expect)
        P('  指の摩擦 mu1: %s -> %s が %d か所 / mu1 全体 %d か所(6か所すべて %s が必要)' % (f, expect, n1, na, expect))
        if not (n1 == 6 and na == 6): ok = False
    try: xm = os.path.getmtime(src)
    except OSError: xm = 0
    g, gs = gazebo_start()
    if g is None:
        P('  Gazebo サーバー: 起動していません'); ok = False
    else:
        P('  Gazebo サーバーの起動: %s / xacro の更新: %s' % (gs, time.strftime('%a %b %d %H:%M:%S %Y', time.localtime(xm))))
        if not g > xm:
            P('  -> Gazebo の起動が xacro の更新より古い(摩擦が反映されていない)。Gazebo とロボットを起動し直してください'); ok = False
    if model_path:
        h, f = ckpt_hash(model_path)
        P('  チェックポイント: %s sha16=%s' % (f, h) if h else '  チェックポイント: %s の .safetensors が見つかりません(記録のみ)' % model_path)
    P('[環境確認] OK' if ok else '[環境確認] NG: 測定を始めません。上の表示を確かめ、Gazebo とロボットを起動し直してから、同じコマンドをもう一度実行してください')
    return ok


if __name__ == '__main__':
    # 単独実行(env_check.bat): 何も変更しない確認だけ。例: env_gate.py --no-fix [チェックポイントのパス]
    args = [x for x in sys.argv[1:] if x != '--no-fix']
    sys.exit(0 if run(kind='check', model_path=args[0] if args else None, fix=('--no-fix' not in sys.argv)) else 3)
