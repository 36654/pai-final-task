# 格子実験・学習配置の再現の結果を、表と検定にまとめる(標準ライブラリだけ。Gazebo不要)。
# usage: grid_report.py   (outbox の grid_*.txt / replay_*.txt を読む。無いものは飛ばす)
import math, os, re, sys
O = os.environ.get('GRID_O', '/home/ubuntu/outbox')
SRC = [('専門家', 'grid_1_expert.txt'), ('30k+TE', 'grid_2_30k.txt'), ('80k+TE', 'grid_3_80k.txt'), ('SmolVLA', 'smolvla_2_grid.txt')]
REP = [('30k+TE', 'replay_30k.txt'), ('80k+TE', 'replay_80k.txt')]
PAT = re.compile(r'積み木\(θ\s*([+-]?\d+)°,r([\d.]+),向き\s*([+-]?\d+)°\)\s*→\s*箱\(θ[^)]*\)\s*(成功|失敗)')


def load(fn):
    p = os.path.join(O, fn)
    if not os.path.exists(p): return None
    rows = []
    for l in open(p, encoding='utf-8', errors='replace'):
        m = PAT.search(l)
        if m: rows.append((int(m.group(1)), int(m.group(3)), m.group(4) == '成功'))
    return rows


def fisher(a, b, c, d):
    """2x2 の分割表 [[a,b],[c,d]] のフィッシャー正確検定(両側)。a,b = 条件内の成功,失敗 / c,d = 条件外の成功,失敗"""
    n1, n2, k = a + b, c + d, a + c
    def pr(x): return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n1 + n2, k)
    p0 = pr(a)
    return sum(pr(x) for x in range(max(0, k - n2), min(n1, k) + 1) if pr(x) <= p0 * (1 + 1e-9))


def axis_near(th, yaw):                  # 世界の向き(θ+yaw)を90°で折り返した値が、画像の縦横から18°以内か
    w = th + yaw
    return abs(((w + 45) % 90) - 45) <= 18


FEATS = [('相対yaw ≤ -12°(負の向き。物理の仮説)', lambda t, y: y <= -12),
         ('辺が画像の縦横に近い(|世界の向き mod 90| ≤ 18°。画像の仮説)', axis_near),
         ('θ = -85°(領域の端)', lambda t, y: t == -85),
         ('|yaw| = 25°(向きが大きい)', lambda t, y: abs(y) == 25)]


def table(name, rows):
    ok = {(t, y): s for t, y, s in rows}
    print('\n[%s] 成功 %d/%d  (行=積み木のθ、列=相対yaw。○成功 ×失敗 ・未実施。括弧は世界の向き θ+yaw)' % (name, sum(ok.values()), len(rows)))
    print('        ' + ''.join('%11s' % ('yaw%+d' % y) for y in (-25, -12, 0, 12, 25)))
    for t in (-40, -65, -85):
        cells = []
        for y in (-25, -12, 0, 12, 25):
            s = ok.get((t, y))
            cells.append('%s(%+4d)' % ('・' if s is None else ('○' if s else '×'), t + y))
        print('  θ%+4d  ' % t + ''.join('%11s' % c for c in cells))


def tests(name, rows):
    print('\n[%s] 検定(フィッシャー正確検定の両側 p。n=15 と小さいので、p が 0.05 を下回るのは差がかなり大きいときだけ。先に決めた4特徴のみ=探し回っていない)' % name)
    for fn, f in FEATS:
        ins = [s for t, y, s in rows if f(t, y)]; out = [s for t, y, s in rows if not f(t, y)]
        if not ins or not out: continue
        a, b, c, d = sum(ins), len(ins) - sum(ins), sum(out), len(out) - sum(out)
        print('  %-58s 条件内 成功%d/%d  条件外 成功%d/%d  p=%.3f' % (fn, a, a + b, c, c + d, fisher(a, b, c, d)))
    # 切り分け: yaw の列ごと / 世界の向きの帯ごと
    print('  yaw 別の成功数:   ' + '  '.join('%+d°: %d/%d' % (y, sum(s for t, yy, s in rows if yy == y), sum(1 for t, yy, s in rows if yy == y)) for y in (-25, -12, 0, 12, 25)))
    print('  θ 別の成功数:     ' + '  '.join('%+d°: %d/%d' % (t, sum(s for tt, y, s in rows if tt == t), sum(1 for tt, y, s in rows if tt == t)) for t in (-40, -65, -85)))


def main():
    print('=== 格子実験(箱 θ55° r0.15 m、積み木 r0.095 m 固定。θ3水準 × yaw5水準 = 15配置) ===')
    got = {}
    for name, fn in SRC:
        r = load(fn)
        if r is None: print('\n[%s] %s がありません(まだ終わっていない)' % (name, fn)); continue
        got[name] = r
        table(name, r)
        if name != '専門家': tests(name, r)
    if '専門家' in got and len(got['専門家']) and not all(s for _, _, s in got['専門家']):
        print('\n注意: 専門家が失敗した配置があります。その配置はACTの比較から外して読むこと(専門家でも届かない/失敗する配置)')
    print('\n=== 学習に使った配置の再現(seen。学習データそのものの最初の10配置) ===')
    for name, fn in REP:
        r = load(fn)
        if r is None: print('[%s] %s がありません' % (name, fn)); continue
        print('[%s] 成功 %d/%d  失敗した配置(θ,yaw): %s' % (name, sum(s for _, _, s in r), len(r), ', '.join('(%+d,%+d)' % (t, y) for t, y, s in r if not s) or 'なし'))
    print('\n読み方: seen(学習配置の再現)で成功率が低いなら「覚えた配置すら再現できない」=学習そのものの異常。seen は高く未知で低いなら、汎化の問題。')


main()
