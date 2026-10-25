import shutil, subprocess, pathlib, sys
a = sys.argv[1:]
x, y, z = (a + ['0.15', '0', '1.55'][len(a):])[:3] if len(a) < 3 else a[:3]
engine = a[3] if len(a) > 3 else 'ogre2'
# 動画用のカメラ(デモ記録には使わない。学習にも使わない)。ロボットの真正面(+x側、約1 m)から、仰角24°で見る(遠くから望遠気味に。遠近のゆがみを減らす)。ホーム姿勢のアームは高さ約0.4 mあるので、頭まで入れるため注視点を高くしてある。
# 正方形(360x360)にしてあるのは、作業域+アームの映る範囲がほぼ正方形で、動画(1280x720)の左に大きく置けるため。
# 画像の左=-y、右=+y。天井カメラは左=+yなので、動画に並べるときは天井画像を180度回して向きを合わせる(expert_video.py)。
# 視点(x y z)は5〜7番目の引数で変えられる。注視点は作業域の中心
import math
TZ = 1.015
ex, ey, ez = [float(v) for v in a[4:7]] if len(a) >= 7 else (0.95, 0.0, TZ + 0.60)
lx, ly, lz = 0.04, 0.0, TZ + 0.19
yaw = math.atan2(ly - ey, lx - ex); pitch = math.atan2(ez - lz, math.hypot(lx - ex, ly - ey))
g = subprocess.check_output(['ros2', 'pkg', 'prefix', 'crane_plus_gazebo'], text=True).strip()
p = pathlib.Path(g) / 'share/crane_plus_gazebo/worlds/table.sdf'
bak = p.parent / 'table.sdf.orig'
if not bak.exists():
    shutil.copy(p, bak)
s = bak.read_text()
add = f"""
    <plugin filename="ignition-gazebo-sensors-system" name="ignition::gazebo::systems::Sensors">
      <render_engine>{engine}</render_engine>
    </plugin>
    <model name="overhead_camera">
      <static>true</static>
      <pose>{x} {y} {z} 0 1.5708 0</pose>
      <link name="link">
        <sensor name="camera" type="camera">
          <camera>
            <horizontal_fov>1.2</horizontal_fov>
            <image><width>320</width><height>240</height><format>R8G8B8</format></image>
            <clip><near>0.05</near><far>5</far></clip>
          </camera>
          <always_on>true</always_on>
          <update_rate>20</update_rate>
          <visualize>false</visualize>
          <topic>overhead_camera/image</topic>
        </sensor>
      </link>
    </model>
    <model name="side_camera">
      <static>true</static>
      <pose>{ex:.3f} {ey:.3f} {ez:.3f} 0 {pitch:.4f} {yaw:.4f}</pose>
      <link name="link">
        <sensor name="camera" type="camera">
          <camera>
            <horizontal_fov>0.50</horizontal_fov>
            <image><width>360</width><height>360</height><format>R8G8B8</format></image>
            <clip><near>0.05</near><far>5</far></clip>
          </camera>
          <always_on>true</always_on>
          <update_rate>20</update_rate>
          <visualize>false</visualize>
          <topic>side_camera/image</topic>
        </sensor>
      </link>
    </model>
"""
i = s.rindex('</world>')
p.write_text(s[:i] + add + s[i:])
print('camera at', x, y, z, 'side camera at %.2f %.2f %.2f' % (ex, ey, ez), 'engine', engine, '-> restart Gazebo to apply')
