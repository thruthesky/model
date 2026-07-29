"""
리타게팅이 끝난 FBX 를 게임에 넣을 수 있는 GLB 로 다듬는다.

왜 필요한가 — retarget.py 가 내보내는 GLB 는 Tripo `HD Model` 의 원본 폴리곤을
그대로 갖고 있다(수십만~수백만 페이스). 모바일 GPU 에서 그대로 그릴 수 없으므로
Decimate 로 줄인다. Decimate(COLLAPSE)는 vertex group(스킨 웨이트)을 보존하므로
리깅이 깨지지 않는다.

추가로 하는 일:
  - 캐릭터 키를 지정한 높이로 정규화한다(게임 월드 단위에 맞춘다).
  - glTF 애니메이션 이름을 실제로 무엇으로 내보냈는지 출력한다
    (flutter_scene 의 findAnimationByName 이 이 이름을 그대로 쓴다).

사용법:
  blender --background --python postprocess_glb.py -- <입력FBX> <출력GLB> [목표페이스수] [목표키]
"""
import bpy
import os
import sys
import json
import struct


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def decimate(meshes, target_faces):
    """전체 페이스 수가 target_faces 이하가 되도록 비율을 잡아 줄인다."""
    total = sum(len(m.data.polygons) for m in meshes)
    print(f"[폴리곤] 원본 {total:,} 페이스")
    if total <= target_faces:
        print("[폴리곤] 목표 이하라 감소를 건너뛴다")
        return total

    ratio = target_faces / total
    for m in meshes:
        mod = m.modifiers.new(name="decimate", type="DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        # 모디파이어를 적용해야 glTF 로 내보낼 때 반영된다.
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.modifier_apply(modifier=mod.name)

    after = sum(len(m.data.polygons) for m in meshes)
    print(f"[폴리곤] 감소 후 {after:,} 페이스 (비율 {ratio:.4f})")
    return after


def normalize_height(arm, meshes, target_height):
    """아마추어를 포함한 전체를 목표 키에 맞춰 균일 스케일한다.

    ⚠️ 아마추어에만 스케일을 걸어야 스킨이 함께 따라간다. 메시에 따로 걸면
    본과 메시가 어긋난다.
    """
    zs = []
    for m in meshes:
        for v in m.data.vertices:
            zs.append((m.matrix_world @ v.co).z)
    if not zs:
        return 1.0
    height = max(zs) - min(zs)
    if height <= 1e-6:
        return 1.0
    k = target_height / height
    arm.scale = (arm.scale[0] * k, arm.scale[1] * k, arm.scale[2] * k)
    print(f"[스케일] 키 {height:.3f} → {target_height:.3f} (배율 {k:.4f})")
    return k


def action_fcurves(action):
    """Blender 4.4+ 슬롯 액션과 구버전 액션 모두에서 (컨테이너, F-커브) 쌍을 낸다."""
    if hasattr(action, "fcurves"):
        yield action.fcurves, list(action.fcurves)
        return
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                bag = strip.channelbag(slot)
                if bag:
                    yield bag.fcurves, list(bag.fcurves)


def strip_root_motion(root_bone):
    """루트 본의 location 키프레임을 제거해 제자리(in-place) 동작으로 만든다.

    ⚠️ 왜 필요한가 — Mixamo 의 `walk` 는 **전진하는** 동작이다(실측: Hip 이
    1.4초에 0.712 이동 = 초당 0.51m). 게임에서 월드 이동은 캐릭터를 담은 앵커
    노드가 담당하므로, 클립에도 이동이 있으면 **두 번 움직인다**.

    회전은 남기고 위치만 지운다. 걷기의 상하 바운스도 함께 사라지지만, 실측한
    커브가 바운스가 아니라 단조 전진이었으므로 손실이 거의 없다.
    """
    removed = 0
    for action in bpy.data.actions:
        for container, curves in action_fcurves(action):
            for fc in curves:
                if "location" in fc.data_path and f'"{root_bone}"' in fc.data_path:
                    container.remove(fc)
                    removed += 1
    print(f"[root motion] {root_bone} location F-커브 {removed}개 제거")


def normalize_action_names():
    """액션 이름에서 오브젝트 접두사를 떼어낸다.

    ⚠️ FBX 왕복을 거치면 `idle` 이 `Armature|Armature|idle` 이 된다(실측).
    Blender glTF exporter 는 액션 이름을 그대로 glTF animation name 으로 쓰고,
    flutter_scene 의 `findAnimationByName` 은 **정확히 일치**해야 찾는다
    (`node.dart:522`). 그래서 내보내기 직전에 여기서 잘라 둔다.
    """
    for action in bpy.data.actions:
        short = action.name.split("|")[-1]
        if short != action.name:
            print(f"[액션명] {action.name} → {short}")
            action.name = short


def glb_animation_names(path):
    """내보낸 GLB 의 JSON 청크를 직접 읽어 애니메이션 이름을 확인한다.

    flutter_scene 의 findAnimationByName 은 이 이름을 그대로 쓰므로,
    'idle' 인지 'Armature|idle' 인지가 통합 코드의 성패를 가른다.
    """
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        return None
    offset = 12
    while offset < len(data):
        length, ctype = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8: offset + 8 + length]
        if ctype == 0x4E4F534A:  # 'JSON'
            doc = json.loads(chunk.decode("utf-8"))
            return {
                "animations": [a.get("name") for a in doc.get("animations", [])],
                "skins": len(doc.get("skins", [])),
                "nodes": len(doc.get("nodes", [])),
                "meshes": len(doc.get("meshes", [])),
                "images": len(doc.get("images", [])),
            }
        offset += 8 + length + ((4 - length % 4) % 4)
    return None


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src_fbx, out_glb = argv[0], argv[1]
    target_faces = int(argv[2]) if len(argv) > 2 else 30000
    target_height = float(argv[3]) if len(argv) > 3 else 1.7

    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = import_fbx(src_fbx)
    arm = next(o for o in objs if o.type == "ARMATURE")
    meshes = [o for o in objs if o.type == "MESH"]
    print(f"[입력] 아마추어={arm.name} 본={len(arm.data.bones)} 메시={len(meshes)}")
    print(f"[입력] 액션={[a.name for a in bpy.data.actions]}")

    decimate(meshes, target_faces)
    normalize_height(arm, meshes, target_height)
    strip_root_motion("Hip")
    normalize_action_names()

    os.makedirs(os.path.dirname(os.path.abspath(out_glb)), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=out_glb,
        export_format="GLB",
        export_animation_mode="ACTIONS",
        export_animations=True,
        export_skins=True,
        export_yup=True,
        export_apply=True,
        use_selection=True,
    )
    print(f"[출력] {out_glb}  ({os.path.getsize(out_glb):,} bytes)")

    info = glb_animation_names(out_glb)
    print(f"[GLB 내용] {json.dumps(info, ensure_ascii=False)}")


main()
