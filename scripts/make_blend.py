"""
애니메이션이 적용된 FBX 를 읽어, 모든 동작을 타임라인에 순서대로 이어 붙인 .blend 를 만든다.

목적: Blender 를 모르는 사람이 파일을 열자마자(또는 play.py 와 함께) 아무 조작 없이
모든 동작을 순서대로 확인할 수 있게 한다.

사용법:
  blender --background --python make_blend.py -- <애니메이션FBX> <출력blend>
"""
import bpy
import sys
from mathutils import Vector

PREFERRED_ORDER = ["idle", "walk", "run", "attack", "hit", "death"]
GAP = 10          # 동작 사이 여유 프레임
FPS = 30          # Mixamo 기본 프레임레이트


def label_of(action):
    # FBX 임포트 시 액션 이름이 "Armature|Armature|idle" 형태가 된다
    return action.name.split("|")[-1]


def build_camera(meshes):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for m in meshes:
        for corner in m.bound_box:
            w = m.matrix_world @ Vector(corner)
            lo = Vector((min(lo[i], w[i]) for i in range(3)))
            hi = Vector((max(hi[i], w[i]) for i in range(3)))
    center = (lo + hi) / 2
    height = max(hi.z - lo.z, 1e-3)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.type = "ORTHO"
    # 쓰러지거나 이동하는 동작까지 담기도록 캐릭터 키의 약 2배 폭
    cam_data.ortho_scale = height * 2.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (center.x, center.y - height * 4, center.z)
    cam.rotation_euler = (1.5708, 0, 0)     # 정면 시점
    bpy.context.scene.camera = cam
    return cam


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    fbx_path, blend_path = argv[0], argv[1]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx_path)

    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    by_label = {label_of(a): a for a in bpy.data.actions}
    head = [n for n in PREFERRED_ORDER if n in by_label]
    order = head + sorted(n for n in by_label if n not in head)

    ad = arm.animation_data or arm.animation_data_create()
    ad.action = None
    for t in list(ad.nla_tracks):
        ad.nla_tracks.remove(t)
    track = ad.nla_tracks.new()
    track.name = "동작 모음"

    scene = bpy.context.scene
    scene.timeline_markers.clear()

    cursor = 1
    for name in order:
        action = by_label[name]
        f0, f1 = (int(round(v)) for v in action.frame_range)

        strip = track.strips.new(name, int(cursor), action)
        strip.frame_start = cursor
        strip.frame_end = cursor + (f1 - f0)
        # NOTHING 이 아니면 앞 스트립의 마지막 포즈가 뒤 구간까지 유지되어 섞인다
        strip.extrapolation = "NOTHING"
        strip.blend_type = "REPLACE"

        scene.timeline_markers.new(name, frame=int(cursor))
        print(f"[배치] {name}: {int(strip.frame_start)} ~ {int(strip.frame_end)}")
        cursor = int(strip.frame_end) + GAP

    scene.frame_start = 1
    scene.frame_end = int(cursor - GAP)
    scene.frame_current = 1
    scene.render.fps = FPS
    # 무거운 메시에서도 재생 속도를 유지하도록 프레임을 건너뛴다
    scene.sync_mode = "FRAME_DROP"

    build_camera(meshes)

    # 파일을 열었을 때 바로 보기 좋은 뷰포트 상태로 저장한다.
    # SOLID + TEXTURE 는 8K 텍스처를 써도 가볍고 색이 보인다 (MATERIAL 은 무겁다).
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                space.shading.type = "SOLID"
                space.shading.color_type = "TEXTURE"
                space.shading.light = "STUDIO"
                space.shading.show_shadows = True
                space.overlay.show_overlays = False
                space.region_3d.view_perspective = "CAMERA"

    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"[저장] {blend_path}  총 {scene.frame_end} 프레임 @ {FPS}fps")


main()
