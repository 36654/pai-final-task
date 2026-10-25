#!/usr/bin/env python3
"""video_build.py : 動画の組み立て(コンテナ内で動く。video_WRITE.bat が呼ぶ)。
usage: python3 video_build.py IN_DIR OUT_MP4
IN_DIR/plan.txt の各行(UTF-8、#で始まる行は無視):
  card|秒数|1行目\\n2行目...        文字だけの場面
  clip|番号|倍速|上の見出し|下の説明    IN_DIR/clip<番号>_front.mp4 と clip<番号>_overhead.mp4 を左右に並べる(天井は180度回転)
  diagram|秒数                         実験環境のシステム構成図(ポンチ絵。このプログラムが描く)
  image|秒数|番号                      スライド画像(IN_DIR/image<番号>.png、1280x720)を指定の秒数だけ表示
  jingle|番号                          講座のオープニング/エンディング(IN_DIR/jingle<番号>.mp4。1280x720・30fpsに揃える)
全体を1280x720、30fps、H.264(yuv420p)に揃える。元の動画は変更しない。
"""
import os, subprocess, sys, shutil, glob
from PIL import Image, ImageDraw, ImageFont
W, H, FPS = 1280, 720, 30
VH, VW = 400, 620          # 1つの映像の枠
VY = 120                   # 映像の上端

def find_font():
    cands = []
    try:
        r = subprocess.run(['fc-match', '-f', '%{file}', ':lang=ja'], capture_output=True, text=True)
        if r.stdout.strip(): cands.append(r.stdout.strip())
    except Exception: pass
    cands += glob.glob('/usr/share/fonts/**/*CJK*Regular*', recursive=True) + glob.glob('/usr/share/fonts/**/*CJK*', recursive=True)
    cands += glob.glob('/usr/share/fonts/**/*ipag*', recursive=True) + glob.glob('/usr/share/fonts/**/*Gothic*', recursive=True)
    for c in cands:
        try:
            ImageFont.truetype(c, 20); return c
        except Exception: continue
    return None

FONT = find_font()
if not FONT:
    sys.exit('STOP: 日本語フォントがコンテナにありません(fc-list :lang=ja が空)')

def font(sz):
    try: return ImageFont.truetype(FONT, sz, index=0)
    except Exception: return ImageFont.truetype(FONT, sz)

def text_center(d, y, s, sz, fill=(255, 255, 255), bold=0):
    f = font(sz); w = d.textlength(s, font=f); d.text(((W - w) / 2, y), s, font=f, fill=fill, stroke_width=bold, stroke_fill=fill)

def card_png(path, lines):
    im = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(im)
    n = len(lines); sizes = [48] + [34] * (n - 1) if n > 1 else [48]
    total = sum(int(s * 1.6) for s in sizes); y = (H - total) / 2
    for s, sz in zip(lines, sizes):
        text_center(d, y, s, sz); y += int(sz * 1.6)
    im.save(path)

def overlay_png(path, head, foot):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 100], fill=(255, 255, 255, 255)); d.rectangle([0, VY + VH + 20, W, H], fill=(255, 255, 255, 255))
    text_center(d, 24, head, 44, fill=(11, 11, 11), bold=1)
    text_center(d, VY + VH + 34, foot, 42, fill=(160, 90, 0), bold=1)
    text_center(d, VY + VH + 104, '左：正面カメラ　右：天井カメラ（AIの目・180°回転して表示）', 34, fill=(70, 70, 70), bold=1)
    im.save(path)


def box(d, xy, title, lines, col, tsz=30, lsz=24):
    x0, y0, x1, y1 = xy
    d.rounded_rectangle(xy, radius=14, outline=col, width=4, fill=(20, 20, 20))
    d.text((x0 + 18, y0 + 12), title, font=font(tsz), fill=col)
    y = y0 + 12 + int(tsz * 1.5)
    for s in lines:
        d.text((x0 + 18, y), s, font=font(lsz), fill=(235, 235, 235)); y += int(lsz * 1.45)

def arrow(d, a, b, col=(255, 220, 120), w=5, label=None, off=(0, -34)):
    d.line([a, b], fill=col, width=w)
    import math
    ang = math.atan2(b[1] - a[1], b[0] - a[0]); L = 20
    for da in (2.6, -2.6):
        d.line([b, (b[0] + L * math.cos(ang + da), b[1] + L * math.sin(ang + da))], fill=col, width=w)
    if label:
        f = font(22); tw = d.textlength(label, font=f)
        d.text(((a[0] + b[0]) / 2 - tw / 2 + off[0], (a[1] + b[1]) / 2 + off[1]), label, font=f, fill=col)

def diagram_png(path):
    im = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(im)
    text_center(d, 18, '実験環境のシステム構成(すべてシミュレーション)', 40)
    blue, green, orange = (120, 190, 255), (130, 220, 140), (255, 180, 100)
    box(d, (40, 100, 520, 400), 'シミュレーション(PC の Docker)',
        ['Gazebo + CRANE+ V2(5関節+グリッパー)', '積み木(赤・青・緑)と箱', '俯瞰カメラ: AIが見る画像', '正面カメラ: 録画だけ', 'ROS 2 で関節の指令・計測'], blue)
    box(d, (760, 100, 1240, 400), 'AI 方策',
        ['ACT: コンテナ内で推論(言語なし)', 'SmolVLA(VLA): Colab の GPU で推論', '  指示文を入力: put the red block', '  in the box(HTTP + トンネル)', '入力: 俯瞰画像 + 関節角(+ 指示文)'], green)
    arrow(d, (520, 190), (760, 190), label='画像・関節角', off=(0, -34))
    arrow(d, (760, 310), (520, 310), label='関節の指令', off=(0, 8))
    box(d, (40, 470, 1240, 680), '学習(Colab A100 / 模倣学習)',
        ['専門家(ルールベース)が、シミュレーターの正確な位置を使い、デモを自動生成',
         'デモ(画像・関節角・行動)を LeRobot 形式に変換 → ACT と SmolVLA を学習(報酬は使わない)',
         '段階1: 赤1個(150件)   段階2: 積み木2個 + 言語指示(色の組と対象を入れ替えた画面も追加)'], orange, lsz=23)
    arrow(d, (1000, 470), (1000, 405), col=orange, w=4, label='学習済みモデル', off=(-110, -14))
    im.save(path)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('ffmpeg 失敗:', ' '.join(cmd)[:300]); print(r.stderr[-1500:]); sys.exit(2)

def dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)

def main():
    ind, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    work = os.path.join(ind, '_seg'); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    segs = []; total = 0.0
    enc = ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', str(FPS), '-preset', 'medium', '-crf', '20', '-an']
    for ln, line in enumerate(open(os.path.join(ind, 'plan.txt'), encoding='utf-8-sig').read().split('\n')):
        line = line.strip()
        if not line or line.startswith('#'): continue
        p = [x.strip() for x in line.split('|')]
        seg = os.path.join(work, 'seg%02d.mp4' % len(segs))
        if p[0] == 'card':
            png = os.path.join(work, 'c%02d.png' % len(segs)); card_png(png, p[2].replace('\\n', '\n').split('\n'))
            run(['ffmpeg', '-y', '-loop', '1', '-t', p[1], '-i', png] + enc + [seg])
        elif p[0] == 'image':
            src = os.path.join(ind, 'image%s.png' % p[2])
            if not os.path.isfile(src): sys.exit('STOP: 素材がありません: ' + src)
            run(['ffmpeg', '-y', '-loop', '1', '-t', p[1], '-i', src, '-vf', 'scale=%d:%d,setsar=1' % (W, H)] + enc + [seg])
        elif p[0] == 'jingle':
            src = os.path.join(ind, 'jingle%s.mp4' % p[1])
            if not os.path.isfile(src): sys.exit('STOP: 素材がありません: ' + src)
            run(['ffmpeg', '-y', '-i', src, '-vf', 'scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=%d' % (W, H, W, H, FPS)] + enc + [seg])
        elif p[0] == 'diagram':
            png = os.path.join(work, 'd%02d.png' % len(segs)); diagram_png(png)
            run(['ffmpeg', '-y', '-loop', '1', '-t', p[1], '-i', png] + enc + [seg])
        elif p[0] == 'clip':
            n, sp = p[1], float(p[2])
            fr, ov = os.path.join(ind, 'clip%s_front.mp4' % n), os.path.join(ind, 'clip%s_overhead.mp4' % n)
            for f in (fr, ov):
                if not os.path.isfile(f): sys.exit('STOP: 素材がありません: ' + f)
            png = os.path.join(work, 'o%02d.png' % len(segs)); overlay_png(png, '%s' % p[3], '%s ・ %g倍速' % (p[4], sp) if sp != 1 else p[4])
            box = 'scale=w=%d:h=%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:white,setsar=1' % (VW, VH, VW, VH)
            fg = ('[0:v]setpts=PTS/%g,fps=%d,%s[a];[1:v]setpts=PTS/%g,fps=%d,hflip,vflip,%s[b];[a][b]hstack=inputs=2[h];'
                  'color=c=white:s=%dx%d:r=%d[bg];[bg][h]overlay=(W-w)/2:%d:shortest=1[v0];[v0][2:v]overlay=0:0[v]') % (sp, FPS, box, sp, FPS, box, W, H, FPS, VY)
            run(['ffmpeg', '-y', '-i', fr, '-i', ov, '-i', png, '-filter_complex', fg, '-map', '[v]'] + enc + [seg])
        else:
            sys.exit('STOP: plan.txt の %d 行目が読めません: %s' % (ln + 1, line))
        d = dur(seg); total += d; segs.append(seg); print('  %-5s %5.1f 秒  %s' % (p[0], d, (p[3] if p[0] == 'clip' else (p[2] if p[0] == 'card' else ('構成図' if p[0] == 'diagram' else ('スライド ' + p[2] if p[0] == 'image' else '講座のジングル'))))[:40].replace('\\n', ' / ')))
        if p[0] == 'clip': print('        元の動画: 前 %.1f 秒 / 天井 %.1f 秒 → %g 倍速 → %.1f 秒(元の長さ ÷ 倍速 = %.1f 秒)' % (dur(fr), dur(ov), sp, d, dur(fr) / sp))
    lst = os.path.join(work, 'list.txt'); open(lst, 'w').write(''.join("file '%s'\n" % s for s in segs))
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', '-movflags', '+faststart', out])
    print('合計 %.1f 秒 -> %s' % (total, out))
    print('RESULT=OK' if 60 <= total <= 180 else 'RESULT=CHECK(長さが1〜3分の範囲外: %.1f 秒)' % total)

main()
