# 専門家(自前IK)の共通部品。expert_*.py から import して使う。
import math, re, time, subprocess
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

ARM = ['crane_plus_joint1', 'crane_plus_joint2', 'crane_plus_joint3', 'crane_plus_joint4']
HAND = ['crane_plus_joint_hand']
L1, L2, H = 0.083, 0.0935, 0.0714
LIM = {2: (-1.825, 1.784), 3: (-2.557, 2.454), 4: (-1.840, 1.768)}
OPEN, CLOSE = math.radians(-30), math.radians(10)
ZP, ZG = 0.17, 0.14            # 運搬の高さ / 把持の高さ(link4)。差の3 cmが持ち上げ量
HOME = [0.0, -1.16, -2.01, -0.73]
TABLE_Z = 1.015
Z_REST = 1.016                 # 積み木を置く高さ(モデル原点は底面)


def ik(r, z, a3=math.pi):
    dz = z - H
    d = math.hypot(r, dz)
    if d > L1 + L2 + 0.002 or d < abs(L1 - L2) - 0.002:
        raise ValueError('IK解なし(届かない)')
    phi = math.atan2(r, dz)
    b = math.acos(max(-1, min(1, (L1**2 + d**2 - L2**2) / (2 * L1 * d))))
    for s in (1, -1):
        a1 = phi + s * b
        p3 = (L1 * math.sin(a1), H + L1 * math.cos(a1))
        a2 = math.atan2(r - p3[0], z - p3[1])
        t2, t3, t4 = a1, a1 - a2, a2 - a3
        t3 = (t3 + math.pi) % (2 * math.pi) - math.pi
        t4 = (t4 + math.pi) % (2 * math.pi) - math.pi
        if all(LIM[k][0] <= v <= LIM[k][1] for k, v in ((2, t2), (3, t3), (4, t4))):
            return [t2, t3, t4]
    raise ValueError('IK解なし')


def pose(th, r, z):
    return [th] + ik(r, z)


D_BLOCK = 0.115   # link4から、つかんだ積み木の中心までの距離(真下向きで、積み木の底が指先の高さ)


def fk(q):
    """関節角 [th1,t2,t3,t4] から link4 の位置 (x, y, 高さ) と手先の向き a3(rad) を返す(ikの逆)。"""
    th, t2, t3, t4 = q[:4]
    a1 = t2; a2 = a1 - t3; a3 = a2 - t4
    r = L1 * math.sin(a1) + L2 * math.sin(a2)
    z = H + L1 * math.cos(a1) + L2 * math.cos(a2)
    return r * math.cos(th), r * math.sin(th), z, a3


def hand_frame(q, c):
    """link4 から見た積み木の中心 c=(x,y,z絶対) の位置 (手の軸方向, 手の軸に直角で面内, 接線方向) [m]と手先の向き[度]。
    手の軸方向は、垂直把持で積み木の中心が指先側(下)なら正。D_BLOCK と同じ向き。"""
    x4, y4, z4, a = fk(q)
    th = q[0]
    dr = (c[0] - x4) * math.cos(th) + (c[1] - y4) * math.sin(th)
    dt = -(c[0] - x4) * math.sin(th) + (c[1] - y4) * math.cos(th)
    dz = (c[2] - TABLE_Z) - z4
    along = dr * math.sin(a) + dz * math.cos(a)
    perp = dr * math.cos(a) - dz * math.sin(a)
    return along, perp, dt, math.degrees(a)


def pose_tilt(th, rc, zc, a_deg, d=D_BLOCK):
    """積み木の中心を (半径rc, 机からの高さzc) に置く姿勢。手先の向き a_deg: 180=真下、90=水平。"""
    a = math.radians(a_deg)
    return [th] + ik(rc - d * math.sin(a), zc - d * math.cos(a), a)


def run(cmd, timeout=8):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ''


class Arm(Node):
    def __init__(self, name='expert'):
        super().__init__(name)
        self.pa = self.create_publisher(JointTrajectory, '/crane_plus_arm_controller/joint_trajectory', 10)
        self.pg = self.create_publisher(JointTrajectory, '/crane_plus_gripper_controller/joint_trajectory', 10)

    def send(self, pub, names, pos, sec):
        t = JointTrajectory(); t.joint_names = names
        p = JointTrajectoryPoint(); p.positions = [float(x) for x in pos]
        p.time_from_start = Duration(sec=int(sec), nanosec=int((sec % 1) * 1e9))
        t.points = [p]; pub.publish(t)

    def spin_for(self, s):
        t0 = time.time()
        while time.time() - t0 < s:
            rclpy.spin_once(self, timeout_sec=0.05)

    def step(self, arm, hand, sec):
        if arm is not None: self.send(self.pa, ARM, arm, sec)
        if hand is not None: self.send(self.pg, HAND, [hand], sec)
        self.spin_for(sec + 0.4)


# ---- Gazebo のモデル操作 ----
def block_sdf(name, size, rgb, density=700.0, mu=1.0):
    m = density * size ** 3
    i = m * size * size / 6.0
    c = '%.2f %.2f %.2f 1' % rgb
    return ('<?xml version="1.0"?><sdf version="1.6"><model name="%s"><link name="l"><pose>0 0 %.4f 0 0 0</pose>'
            '<inertial><mass>%.5f</mass><inertia><ixx>%.3e</ixx><iyy>%.3e</iyy><izz>%.3e</izz></inertia></inertial>'
            '<collision name="c"><geometry><box><size>%.4f %.4f %.4f</size></box></geometry>'
            '<surface><friction><ode><mu>%.2f</mu><mu2>%.2f</mu2></ode></friction></surface></collision>'
            '<visual name="v"><geometry><box><size>%.4f %.4f %.4f</size></box></geometry>'
            '<material><ambient>%s</ambient><diffuse>%s</diffuse></material></visual>'
            '</link></model></sdf>') % (name, size / 2, m, i, i, i, size, size, size, mu, mu, size, size, size, c, c)


def box_sdf(name, inner, wall_h=0.012, wall_t=0.006, floor_t=0.003, rgb=(0.55, 0.40, 0.25)):
    """上が開いた箱(静止物体)。モデル原点は底面の中心。内寸 inner、縁の高さ wall_h(机の面から)。"""
    c = '%.2f %.2f %.2f 1' % rgb
    outer = inner + 2 * wall_t

    def part(n, sx, sy, sz, px, py, pz):
        return ('<collision name="c_%s"><pose>%.4f %.4f %.4f 0 0 0</pose><geometry><box><size>%.4f %.4f %.4f</size></box></geometry></collision>'
                '<visual name="v_%s"><pose>%.4f %.4f %.4f 0 0 0</pose><geometry><box><size>%.4f %.4f %.4f</size></box></geometry>'
                '<material><ambient>%s</ambient><diffuse>%s</diffuse></material></visual>') % (
                    n, px, py, pz, sx, sy, sz, n, px, py, pz, sx, sy, sz, c, c)
    k = inner / 2 + wall_t / 2
    body = (part('floor', outer, outer, floor_t, 0, 0, floor_t / 2) +
            part('w1', wall_t, outer, wall_h, k, 0, wall_h / 2) + part('w2', wall_t, outer, wall_h, -k, 0, wall_h / 2) +
            part('w3', inner, wall_t, wall_h, 0, k, wall_h / 2) + part('w4', inner, wall_t, wall_h, 0, -k, wall_h / 2))
    return '<?xml version="1.0"?><sdf version="1.6"><model name="%s"><static>true</static><link name="l">%s</link></model></sdf>' % (name, body)


def _call(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return (r.stdout + r.stderr).strip()


def spawn(name, sdf_text, x, y, z, yaw=0.0):
    f = '/tmp/%s.sdf' % name
    open(f, 'w').write(sdf_text)
    req = ('sdf_filename: "%s" name: "%s" pose: {position: {x: %.4f y: %.4f z: %.4f} orientation: {x: 0 y: 0 z: %.5f w: %.5f}}'
           % (f, name, x, y, z, math.sin(yaw / 2), math.cos(yaw / 2)))
    return 'true' in _call(['ign', 'service', '-s', '/world/default/create', '--reqtype', 'ignition.msgs.EntityFactory',
                            '--reptype', 'ignition.msgs.Boolean', '--timeout', '3000', '--req', req])


def remove(name):
    return 'true' in _call(['ign', 'service', '-s', '/world/default/remove', '--reqtype', 'ignition.msgs.Entity',
                            '--reptype', 'ignition.msgs.Boolean', '--timeout', '3000', '--req', 'name: "%s" type: MODEL' % name])


def set_pose(name, x, y, z, yaw=0.0):
    req = 'name: "%s" position: {x: %.4f y: %.4f z: %.4f} orientation: {x: 0 y: 0 z: %.5f w: %.5f}' % (
        name, x, y, z, math.sin(yaw / 2), math.cos(yaw / 2))
    out = run("ign service -s /world/default/set_pose --reqtype ignition.msgs.Pose --reptype ignition.msgs.Boolean "
              "--timeout 3000 --req '%s'" % req)
    return 'true' in out


def get_pose(name):
    """(x, y, z, 傾き°) 傾き = 上向き軸と鉛直のなす角。動く物体のみ取得できる"""
    r = run('ign topic -e -t /world/default/dynamic_pose/info -n 1')
    m = re.search(r'pose \{\s*name: "%s".*?position \{(.*?)\}(?:\s*orientation \{(.*?)\})?' % re.escape(name), r, re.S)
    if not m:
        return None

    def val(txt, k):
        mm = re.search(r'\b%s: (\S+)' % k, txt or '')
        return float(mm.group(1)) if mm else 0.0
    x, y, z = (val(m.group(1), k) for k in 'xyz')
    qx, qy = val(m.group(2), 'x'), val(m.group(2), 'y')
    c = max(-1.0, min(1.0, 1 - 2 * (qx * qx + qy * qy)))
    return x, y, z, math.degrees(math.acos(c))


def get_center(name, size):
    """積み木の中心 (x, y, z, 傾き°)。モデル原点は底面の中心なので、傾いたときのずれを姿勢から補正する。"""
    r = run('ign topic -e -t /world/default/dynamic_pose/info -n 1')
    m = re.search(r'pose \{\s*name: "%s".*?position \{(.*?)\}(?:\s*orientation \{(.*?)\})?' % re.escape(name), r, re.S)
    if not m:
        return None

    def val(txt, k, d=0.0):
        mm = re.search(r'\b%s: (\S+)' % k, txt or '')
        return float(mm.group(1)) if mm else d
    x, y, z = (val(m.group(1), k) for k in 'xyz')
    qx, qy, qz = val(m.group(2), 'x'), val(m.group(2), 'y'), val(m.group(2), 'z')
    qw = val(m.group(2), 'w', 1.0 if not m.group(2) else 0.0)
    ax = 2 * (qx * qz + qw * qy)              # 回転行列の第3列(積み木の上向き軸)
    ay = 2 * (qy * qz - qw * qx)
    az = 1 - 2 * (qx * qx + qy * qy)
    h = size / 2
    return x + ax * h, y + ay * h, z + az * h, math.degrees(math.acos(max(-1.0, min(1.0, az))))
