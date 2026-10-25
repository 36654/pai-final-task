# 記録済みの専門家デモ(npz)から、確認用の動画(mp4)を作る。シミュレーションは動かさない。
# 使い方: expert_video.py NAME [件数=4] [倍速=2] [--failures]   -> outbox/NAME_demo.mp4
import glob, json, os, shutil, subprocess, sys
import numpy as np

ROOT = '/home/ubuntu/dataset/expert_npz'
OUTBOX = '/home/ubuntu/outbox'
FPS = 20


def caption(frame, text, zoom=2):
    """フレームをzoom倍に拡大して、下に字幕の帯をつける"""
    big = np.repeat(np.repeat(frame, zoom, axis=0), zoom, axis=1) if zoom > 1 else frame
    bar = np.zeros((28, big.shape[1], 3), np.uint8)
    out = np.vstack([big, bar])
    try:
        from PIL import Image, ImageDraw, ImageFont
        im = Image.fromarray(out); d = ImageDraw.Draw(im)
        try:
            font = ImageFont.load_default(size=15)
        except TypeError:
            font = ImageFont.load_default()
        d.text((8, big.shape[0] + 6), text, fill=(255, 255, 255), font=font)
        out = np.asarray(im)
    except Exception:
        pass
    return out


def write_video(frames, path, fps=FPS):
    h, w, _ = frames[0].shape
    if shutil.which('ffmpeg'):
        p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (w, h),
                              '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
        for f in frames:
            p.stdin.write(f.tobytes())
        p.stdin.close(); p.wait()
        if p.returncode == 0:
            return path
    try:
        import cv2
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
        for f in frames:
            vw.write(f[:, :, ::-1])
        vw.release()
        return path
    except Exception:
        pass
    from PIL import Image
    gif = path.rsplit('.', 1)[0] + '.gif'
    ims = [Image.fromarray(f) for f in frames]
    ims[0].save(gif, save_all=True, append_images=ims[1:], duration=int(1000 / fps), loop=0)
    return gif


def read_video(path):
    """mp4 -> フレームのリスト(RGB)。ffmpeg、なければcv2"""
    try:
        import cv2
        cap = cv2.VideoCapture(path); fr = []
        while True:
            ok, im = cap.read()
            if not ok: break
            fr.append(im[:, :, ::-1].copy())
        cap.release()
        if fr: return fr
    except Exception:
        pass
    if shutil.which('ffprobe') and shutil.which('ffmpeg'):
        wh = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                      '-of', 'csv=p=0', path], text=True).strip().split(',')
        w, h = int(wh[0]), int(wh[1])
        raw = subprocess.check_output(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        return list(np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3))
    return []


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def compose(side, over, lines, W=1280, H=720, left_w=720):
    """16:9のキャンバス。左: 正面カメラ(正方形、Gazeboの画)、右: 天井カメラ(AIが見ている画)と字幕。
    正面カメラは左右が天井と逆なので、天井画像を180度回して向きを合わせる(表示だけ。記録とAIの入力はそのまま)。"""
    from PIL import Image, ImageDraw
    canvas = Image.new('RGB', (W, H), (0, 0, 0))
    canvas.paste(Image.fromarray(np.ascontiguousarray(side)).resize((left_w, H), Image.BILINEAR), (0, 0))
    rw = W - left_w
    oh = int(round(rw * over.shape[0] / over.shape[1]))
    o = Image.fromarray(np.ascontiguousarray(over[::-1, ::-1])).resize((rw, oh), Image.BILINEAR)
    canvas.paste(o, (left_w, 24))
    d = ImageDraw.Draw(canvas); f = _font(22)
    y = 24 + oh + 14
    for t in lines:
        d.text((left_w + 16, y), t, fill=(255, 255, 255), font=f); y += 30
    return np.asarray(canvas)


def make_video(npz_dir, out_path, n=4, speed=2, failures=False):
    files = sorted(glob.glob(os.path.join(npz_dir, 'ep_*.npz')))
    eps = []
    for f in files:
        meta = json.load(open(f[:-4] + '.json'))
        if not meta.get('success') and not failures:
            continue
        img = np.load(f)['img'][::speed]
        sp = f[:-4] + '_side.mp4'
        side = read_video(sp)[::speed] if os.path.exists(sp) else []
        if len(side) != len(img):
            side = []                                                  # 正面カメラがない/コマ数が合わないとき
        eps.append((f, meta, img, side))
        if len(eps) >= n:
            break
    if not eps:
        raise RuntimeError('動画にするデモがありません')
    use_compose = any(e[3] for e in eps)                               # 1件でも正面カメラがあれば、全件を同じ大きさの左右並べにそろえる
    frames = []
    for f, meta, img, side in eps:
        info = ['ep %s  (%s)  x%d' % (os.path.basename(f)[3:7], 'success' if meta.get('success') else 'failure', speed),
                'block th%+.0f r%.2f -> box th%+.0f r%.2f' % (meta['block_th'], meta['block_r'], meta['box_th'], meta['box_r'])]
        lines = info + ['right: overhead camera (what the AI sees),', 'shown rotated 180 deg']
        blank = np.zeros((360, 360, 3), np.uint8)
        for k, im in enumerate(img):
            if use_compose:
                frames.append(compose(side[k] if side else blank, im, lines))
            else:
                frames.append(caption(im, ' | '.join(info)))
    return write_video(frames, out_path)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    name = args[0]
    n = int(args[1]) if len(args) > 1 else 4
    speed = int(args[2]) if len(args) > 2 else 2
    os.makedirs(OUTBOX, exist_ok=True)
    print('動画:', make_video(os.path.join(ROOT, name), os.path.join(OUTBOX, name + '_demo.mp4'), n, speed, '--failures' in sys.argv))
