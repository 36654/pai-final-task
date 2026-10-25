import sys, time, zlib, struct
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

OUT = '/home/ubuntu/cam.png'

def png(path, w, h, data):
    raw = b''.join(b'\x00' + data[y*w*3:(y+1)*w*3] for y in range(h))
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n'
                + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw))
                + chunk(b'IEND', b''))

if __name__ == '__main__':
    rclpy.init()
    n = Node('grab')
    got, got2 = [], []
    n.create_subscription(Image, '/overhead_camera/image', got.append, 10)
    n.create_subscription(Image, '/side_camera/image', got2.append, 10)
    end = time.time() + 20
    while not got and time.time() < end:
        rclpy.spin_once(n, timeout_sec=0.5)
    if not got:
        print('NO IMAGE received in 20 s (run camera_check.bat)')
        sys.exit(1)
    end = time.time() + 5
    while not got2 and time.time() < end:
        rclpy.spin_once(n, timeout_sec=0.5)
    for m, path in ((got[0], OUT), (got2[0] if got2 else None, OUT.replace('.png', '_side.png'))):
        if m is None:
            print('side camera: NO IMAGE (set_camera.bat を実行して、Gazeboを再起動したか確認)')
            continue
        if m.encoding != 'rgb8':
            print('unexpected encoding:', m.encoding)
            sys.exit(1)
        png(path, m.width, m.height, bytes(m.data))
        print('saved', path, m.width, m.height)
