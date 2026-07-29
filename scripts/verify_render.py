"""
리타게팅 결과를 눈으로 검증한다. 각 동작의 대표 프레임을 PNG 로 렌더한다.

리타게팅은 조용히 실패한다(키는 들어갔는데 포즈가 뒤틀림). 반드시 이미지로 확인할 것.

사용법:
  blender --background --python verify_render.py -- <애니메이션FBX> <출력폴더>
"""
import bpy
import os
import sys
from mathutils import Vector

# 동작별로 특징이 잘 드러나는 지점(전체 길이 대비 비율)
SHOTS = {
    "idle": (0.0, 0.5),
    "walk": (0.25, 0.75),
    "run": (0.25, 0.75),
    "attack": (0.4, 0.7),
    "hit": (0.3, 0.6),
    "death": (0.5, 1.0),
}
DEFAULT_SHOTS = (0.0, 0.5)


def setup_scene(meshes):
    scene = bpy.context.scene
    # WORKBENCH 는 텍스처 색을 보여주면서도 EEVEE 보다 훨씬 빠르다
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 420
    scene.render.resolution_y = 640
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"

    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for m in meshes:
        for corner in m.bound_box:
            w = m.matrix_world @ Vector(corner)
            lo = Vector((min(lo[i], w[i]) for i in range(3)))
            hi = Vector((max(hi[i], w[i]) for i in range(3)))
    center = (lo + hi) / 2
    height = max(hi.z - lo.z, 1e-3)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = height * 1.9
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (center.x, center.y - height * 3, center.z)
    cam.rotation_euler = (1.5708, 0, 0)
    scene.camera = cam


def assign(obj, action):
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = action
    if hasattr(obj.animation_data, "action_slot") and len(action.slots):
        obj.animation_data.action_slot = action.slots[0]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    fbx_path, out_dir = argv[0], argv[1]
    os.makedirs(out_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx_path)

    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    setup_scene(meshes)

    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        label = action.name.split("|")[-1]
        assign(arm, action)
        f0, f1 = (int(round(v)) for v in action.frame_range)

        for idx, r in enumerate(SHOTS.get(label, DEFAULT_SHOTS)):
            frame = int(round(f0 + (f1 - f0) * r))
            bpy.context.scene.frame_set(frame)
            path = os.path.join(out_dir, f"{label}_{idx}_f{frame}.png")
            bpy.context.scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print(f"[렌더] {label} 프레임 {frame} -> {path}")


main()
