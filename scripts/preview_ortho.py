"""모델을 위/앞/옆 정사영으로 렌더해 형상을 눈으로 확인한다(다리 개수·배치 판정용).

blender --background --python preview_ortho.py -- <모델> <출력디렉토리>
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(SRC)[1].lower()
if ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC, use_image_search=False)
elif ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=SRC)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

ms = [o for o in bpy.data.objects if o.type == "MESH"]
V = []
for m in ms:
    V += [m.matrix_world @ v.co for v in m.data.vertices]
minz = min(v.z for v in V)
cx = (min(v.x for v in V) + max(v.x for v in V)) / 2
cy = (min(v.y for v in V) + max(v.y for v in V)) / 2
R = max(math.hypot(v.x - cx, v.y - cy) for v in V)
H = max(v.z for v in V) - minz
cz = minz + H / 2

scn = bpy.context.scene
scn.render.engine = "BLENDER_WORKBENCH"
scn.render.resolution_x = scn.render.resolution_y = 700
scn.render.film_transparent = False
try:
    scn.display.shading.light = "STUDIO"
    scn.display.shading.color_type = "SINGLE"
    scn.display.shading.single_color = (0.75, 0.75, 0.78)
    scn.display.shading.show_object_outline = True
except Exception:
    pass

cam_data = bpy.data.cameras.new("c")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max(R * 2.3, H * 1.5)
cam = bpy.data.objects.new("c", cam_data)
scn.collection.objects.link(cam)
scn.camera = cam

views = {
    "top":   (Vector((cx, cy, cz + R * 4)), (0, 0, 0)),
    "front": (Vector((cx, cy - R * 4, cz)), (math.pi / 2, 0, 0)),
    "side":  (Vector((cx + R * 4, cy, cz)), (math.pi / 2, 0, math.pi / 2)),
}
for name, (loc, rot) in views.items():
    cam.location = loc
    cam.rotation_euler = rot
    scn.render.filepath = os.path.join(OUT, f"ortho_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] {scn.render.filepath}")
