# ロボットの摩擦係数(crane_plus.gazebo.xacro の mu1 / mu2)を書き換える。元の値は 0.2(10/14に確認)。
# 使い方: finger_friction.py [MU=1.5] [--restore]    何回実行しても、必ず元のファイル(.orig)から作り直す。
# 反映には、Gazeboとロボットの起動し直しが必要(xacroは起動時に展開される)。
import os, re, shutil, sys

FILES = ['/home/ubuntu/airobot_ws/src/crane_plus/crane_plus_description/urdf/crane_plus.gazebo.xacro',
         '/home/ubuntu/airobot_ws/install/crane_plus_description/share/crane_plus_description/urdf/crane_plus.gazebo.xacro']
args = [a for a in sys.argv[1:] if not a.startswith('--')]
mu = float(args[0]) if args else 1.5
restore = '--restore' in sys.argv[1:]
seen = set()
for f in FILES:
    if not os.path.exists(f):
        print('ない:', f); continue
    real = os.path.realpath(f)
    if real in seen:
        print('同じファイル(リンク):', f); continue
    seen.add(real)
    orig = real + '.orig'
    if not os.path.exists(orig):
        shutil.copy2(real, orig)
    if restore:
        shutil.copy2(orig, real); print('元に戻した:', real); continue
    text = open(orig, encoding='utf-8').read()
    log = []

    def patch(m):
        body = m.group(2)
        old = re.findall(r'<mu1>\s*([^<\s]+)\s*</mu1>', body)
        new = re.sub(r'(<mu1>)[^<]*(</mu1>)', r'\g<1>%g\g<2>' % mu, body)
        new = re.sub(r'(<mu2>)[^<]*(</mu2>)', r'\g<1>%g\g<2>' % mu, new)
        log.append('  %-30s mu1: %s -> %g' % (m.group(1), old[0] if old else '(なし)', mu))
        return m.group(0).replace(body, new)
    out = re.sub(r'<gazebo\s+reference="([^"]+)">(.*?)</gazebo>', patch, text, flags=re.S)
    open(real, 'w', encoding='utf-8').write(out)
    print('書き換えた:', real)
    print('\n'.join(log))
print('\n反映するには、Gazeboとロボットをいつもの方法で起動し直してください。')
