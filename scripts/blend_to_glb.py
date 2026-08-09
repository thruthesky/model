"""리타게팅이 끝난 **.blend** 를 게임에 넣을 GLB 로 굽는다.

## 왜 이 스크립트가 따로 필요한가

`postprocess_glb.py` 는 **FBX** 를 입력으로 받고 Tripo 리그(`Hip`)를 전제한다. 그런데
ARP → Mixamo 경로의 산출물은 `retarget_to_arp_rig.py` 가 만든 **`.blend`** 이고
(FBX 왕복은 rest pose 를 깨뜨린다 → SKILL.md ⑦), 루트 본은 **`mixamorig:Hips`** 다.
그 둘을 그대로 이어 주는 것이 이 스크립트다.

⚠️ **SKILL.md 의 ⑧⑨(texture-pack)는 이 저장소에 해당하지 않는다.** 이 프로젝트는
2026-07-31 에 `flutter_scene` 3D 로 돌아왔고 런타임이 읽는 것은 스프라이트 아틀라스가
아니라 **GLB** 다(`lib/engine/scene/pc_model.dart`). 그래서 ⑦ 다음은 이 스크립트다.

## 맞춰야 하는 계약 — `assets/pc/astona.glb` 실측

| 항목 | 값 | 왜 |
|---|---|---|
| 애니메이션 이름 | `idle`·`walk`·`run` + `slash`·사격 2종 (+`death`) **접두사 없이** | `findAnimationByName` 은 부분 일치를 하지 않는다 |
| 본 이름 | `mixamorig:*` 52본 | ARP GE Export 의 rename 결과 |
| 키 | **0.98m** | `WorldScale.pcModelHeightMeters` 가 **상수 하나**다 — 모델마다 다르면 배율이 통째로 틀어진다 |
| 발 | 원점(min.z ≈ 0) | 지면에 세우는 기준 |
| root motion | **없음** | `inspect_glb.py` 의 `ROOT_MOTION_EPS = 0.001` 은 매우 엄격하다. Hips location 을 남기면 걷기 바운스까지 걸려 실패하고, 무엇보다 앵커 노드와 **두 번 움직인다** |

사용법:
  blender --background --python blend_to_glb.py -- <입력.blend> <출력.glb> [목표페이스수] [목표키]
"""
import bpy
import os
import sys
import json
import struct

ROOT_BONE = "mixamorig:Hips"


def action_fcurves(action):
    """Blender 4.4+ 슬롯 액션과 구버전 액션 모두에서 (컨테이너, F-커브) 쌍을 낸다."""
    if hasattr(action, "fcurves") and len(action.fcurves) > 0:
        yield action.fcurves, list(action.fcurves)
        return
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    bag = strip.channelbag(slot)
                    if bag:
                        yield bag.fcurves, list(bag.fcurves)


def decimate(meshes, target_faces):
    """전체 페이스 수가 target_faces 이하가 되도록 비율을 잡아 줄인다.

    COLLAPSE 는 vertex group(스킨 웨이트)을 보존하므로 리깅이 깨지지 않는다.
    """
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
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.modifier_apply(modifier=mod.name)

    after = sum(len(m.data.polygons) for m in meshes)
    print(f"[폴리곤] 감소 후 {after:,} 페이스 (비율 {ratio:.4f})")
    return after


def mesh_z_range(meshes):
    zs = []
    for m in meshes:
        for v in m.data.vertices:
            zs.append((m.matrix_world @ v.co).z)
    return (min(zs), max(zs)) if zs else (0.0, 0.0)


def normalize_height(arm, meshes, target_height):
    """아마추어를 목표 키에 맞춰 균일 스케일한다.

    ⚠️ **아마추어에만** 스케일을 건다. 메시에 따로 걸면 본과 메시가 어긋난다.
    """
    lo, hi = mesh_z_range(meshes)
    height = hi - lo
    if height <= 1e-6:
        print("[스케일] 키를 잴 수 없다 — 건너뛴다")
        return 1.0
    k = target_height / height
    arm.scale = tuple(s * k for s in arm.scale)
    bpy.context.view_layer.update()
    print(f"[스케일] 키 {height:.3f} → {target_height:.3f} (배율 {k:.4f})")
    return k


def align_feet(arm, meshes):
    """발바닥(min.z)을 원점에 맞춘다. 지면에 세우는 기준이다."""
    lo, _ = mesh_z_range(meshes)
    if abs(lo) < 1e-4:
        print(f"[발 정렬] 이미 원점 (min.z={lo:+.4f})")
        return
    arm.location.z -= lo
    bpy.context.view_layer.update()
    print(f"[발 정렬] min.z {lo:+.4f} → 0 (아마추어를 {-lo:+.4f} 이동)")


def strip_root_motion(root_bone):
    """루트 본의 location 키프레임을 제거해 제자리(in-place) 동작으로 만든다.

    게임에서 월드 이동은 캐릭터를 담은 앵커 노드가 담당한다. 클립에도 이동이
    남아 있으면 **두 번 움직인다**.
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

    `findAnimationByName` 은 **정확히 일치**해야 찾는다.
    """
    for action in bpy.data.actions:
        short = action.name.split("|")[-1]
        if short != action.name:
            print(f"[액션명] {action.name} → {short}")
            action.name = short


def push_actions_to_nla(arm, actions):
    """액션을 NLA 트랙으로 올려 glTF exporter 가 찾을 수 있게 한다.

    🛑 **이것이 없으면 애니메이션이 통째로 빠진다**(실측 2026-08-01 — `"animations": []`).
    `retarget_to_arp_rig.py` 는 마지막 액션의 포즈가 rest 처럼 보이지 않도록
    `animation_data.action = None` 으로 **떼어 두고** `use_fake_user` 로만 살려 둔다.
    그런데 Blender 의 glTF exporter 는 **오브젝트에 연결된 액션만** 내보내므로,
    fake user 만 붙은 액션은 `ACTIONS` 모드에서도 무시된다.

    트랙 하나에 스트립 하나씩 올리면 exporter 가 각각을 개별 glTF 애니메이션으로 굽는다.
    """
    ad = arm.animation_data or arm.animation_data_create()
    for track in list(ad.nla_tracks):
        ad.nla_tracks.remove(track)
    pushed = []
    for act in actions:
        track = ad.nla_tracks.new()
        track.name = act.name
        start = int(act.frame_range[0])
        strip = track.strips.new(act.name, start, act)
        strip.name = act.name
        # Blender 4.4+ 슬롯 액션 — 슬롯을 안 잡으면 스트립이 평가되지 않는다.
        if hasattr(strip, "action_slot") and getattr(strip, "action_slot", None) is None:
            slots = getattr(strip, "action_suitable_slots", None)
            if slots:
                strip.action_slot = slots[0]
        pushed.append(act.name)
    print(f"[NLA] 액션 {len(pushed)}개를 트랙으로: {pushed}")
    return pushed


def glb_summary(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        return None
    offset = 12
    while offset < len(data):
        length, ctype = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8: offset + 8 + length]
        if ctype == 0x4E4F534A:
            doc = json.loads(chunk.decode("utf-8"))
            skins = doc.get("skins", [])
            nodes = [n.get("name", "") for n in doc.get("nodes", [])]
            joints = [nodes[j] for j in skins[0]["joints"]] if skins else []
            return {
                "animations": [a.get("name") for a in doc.get("animations", [])],
                "skins": len(skins),
                "bones": len(joints),
                "mixamorig": sum(1 for j in joints if j.startswith("mixamorig")),
                "meshes": len(doc.get("meshes", [])),
                "images": len(doc.get("images", [])),
            }
        offset += 8 + length + ((4 - length % 4) % 4)
    return None


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src_blend, out_glb = argv[0], argv[1]
    target_faces = int(argv[2]) if len(argv) > 2 else 30000
    target_height = float(argv[3]) if len(argv) > 3 else 0.98

    bpy.ops.wm.open_mainfile(filepath=src_blend)

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if len(arms) != 1:
        raise SystemExit(f"아마추어가 {len(arms)}개다 — 정확히 1개여야 한다")
    arm = arms[0]
    print(f"[입력] 아마추어={arm.name} 본={len(arm.data.bones)} 메시={len(meshes)}")
    print(f"[입력] 액션={[a.name for a in bpy.data.actions]}")

    # 액션이 걸린 채면 그 포즈가 rest 처럼 잡혀 키 측정이 틀어진다.
    if arm.animation_data:
        arm.animation_data.action = None
    bpy.context.view_layer.update()

    decimate(meshes, target_faces)
    normalize_height(arm, meshes, target_height)
    align_feet(arm, meshes)
    strip_root_motion(ROOT_BONE)
    normalize_action_names()
    push_actions_to_nla(arm, list(bpy.data.actions))

    os.makedirs(os.path.dirname(os.path.abspath(out_glb)), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=out_glb,
        export_format="GLB",
        # 🛑 `ACTIONS` 가 아니라 `NLA_TRACKS` 다(실측 2026-08-01 · Blender 5.1).
        # 슬롯 액션(4.4+)에서는 `ACTIONS`·`BROADCAST` 가 **예외도 경고도 없이**
        # `"animations": []` 를 낸다. 트랙 이름을 액션 이름으로 지어 두었으므로
        # 이 모드에서 glTF 애니메이션 이름이 `idle`·`walk`·`run` 그대로 나온다.
        export_animation_mode="NLA_TRACKS",
        export_animations=True,
        export_skins=True,
        export_yup=True,
        export_apply=True,
        use_selection=True,
    )
    print(f"[출력] {out_glb}  ({os.path.getsize(out_glb):,} bytes)")
    print(f"[GLB 내용] {json.dumps(glb_summary(out_glb), ensure_ascii=False)}")


main()
