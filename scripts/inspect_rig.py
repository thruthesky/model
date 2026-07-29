"""
FBX/GLB 의 리그 구조를 조사한다.

리타게팅 전에 소스(Mixamo)와 타겟(Tripo) 양쪽에서 반드시 실행할 것.
본 이름·계층·스케일·좌표계를 모르면 본 매핑을 만들 수 없다.

사용법:
  blender --background --python inspect_rig.py -- <모델파일> [--tree]
"""
import bpy
import sys


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    path = argv[0]
    show_tree = "--tree" in argv

    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.lower().endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)

    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    print(f"\n=== {path} ===")
    print(f"메시: {[m.name for m in meshes]}")

    if not armatures:
        print("아마추어 없음 — 스켈레톤이 포함되지 않은 파일이다")
        print("  (Tripo 에서 Export Skeleton 을 켜고 다시 내보낼 것)")
        return

    for arm in armatures:
        bones = arm.data.bones
        zs = [b.head_local.z for b in bones] + [b.tail_local.z for b in bones]
        ys = [b.head_local.y for b in bones] + [b.tail_local.y for b in bones]

        print(f"\n아마추어: {arm.name}  본 {len(bones)}개")
        print(f"  오브젝트 스케일: {tuple(round(v, 4) for v in arm.scale)}")
        # 높이가 z 축이면 Z-up, y 축이면 Y-up 원본이다 (스케일 보정 판단에 쓴다)
        print(f"  z 범위: {round(min(zs), 4)} ~ {round(max(zs), 4)}")
        print(f"  y 범위: {round(min(ys), 4)} ~ {round(max(ys), 4)}")
        print(f"  루트 본: {[b.name for b in bones if b.parent is None]}")

        if show_tree:
            def walk(b, d=0):
                print("    " + "  " * d + "> " + b.name)
                for c in b.children:
                    walk(c, d + 1)
            print("  계층:")
            for b in bones:
                if b.parent is None:
                    walk(b)
        else:
            print("  본 목록:")
            for b in bones:
                print("    -", b.name)

    for a in bpy.data.actions:
        print(f"액션: {a.name}  프레임 {tuple(round(v) for v in a.frame_range)}")


main()
