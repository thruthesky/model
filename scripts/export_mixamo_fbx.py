"""ARP 리그를 **Mixamo 본 이름(`mixamorig:*`)** 의 FBX 로 내보낸다(SKILL.md ⑤).

ARP 의 Game Engine Export 가 컨트롤러를 걷어내고 deform 본만 남긴 스켈레톤을 굽고,
그때 **Rename Bones from File** 로 본 이름을 Mixamo 규격으로 바꾼다. 그러면 Mixamo
애니메이션이 리타게팅 없이 이름만으로 대응된다.

## 🛑 기본값이 틀린 것 셋 — 끄는 것이 수동 작업이다

| 설정 | 우리 값 | ARP 기본 | 안 고치면 |
|---|---|---|---|
| `arp_export_twist` | **False** | ⚠️ True | Mixamo 에 대응 본이 없는 twist 본이 섞인다 |
| `arp_units_x100` | **False** | ⚠️ True | **100배 크기**로 나간다. 아틀라스/GLB 는 bbox 로 맞추므로 **당장은 안 드러나고** 나중에 다른 자산과 섞일 때 튄다 |
| `arp_bake_anim` | **False** | ⚠️ True | 이 단계는 리그만 내보낸다. 애니메이션은 리타게팅이 따로 붙인다 |

## 실행 방식

`bpy.ops.arp.arp_export_fbx_panel` 은 ExportHelper 라 GUI 에서는 파일 대화상자를 열지만,
`EXEC_DEFAULT` + `filepath` 로 부르면 곧바로 `ARP_OT_export.execute` 를 탄다.
**background 에서 동작한다**(실측 2026-08-01 — GUI 가 필요한 것은 `go_detect` 뿐이다).

⚠️ 로그에 `Invalid renaming syntax, skip:` 이 수십 줄 찍히는 것은 **정상**이다 —
매핑표의 주석·빈 줄마다 나온다. 진짜 실패는 `verify_mixamo_rig.py` 로 가린다.

사용법:
  blender --background --python export_mixamo_fbx.py -- <리그.blend> <출력.fbx> [매핑표.txt]
"""
import bpy
import os
import sys

DEFAULT_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arp_to_mixamo.txt")


def set_if_exists(scn, name, value):
    if hasattr(scn, name):
        try:
            setattr(scn, name, value)
            return True
        except Exception as e:
            print(f"[경고] {name} = {value} 설정 실패: {e}")
    return False


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src_blend, out_fbx = argv[0], argv[1]
    rename_fp = os.path.abspath(argv[2]) if len(argv) > 2 else DEFAULT_MAP
    if not os.path.exists(rename_fp):
        raise SystemExit(f"매핑표가 없다: {rename_fp}")

    bpy.ops.wm.open_mainfile(filepath=src_blend)
    scn = bpy.context.scene

    # enum 값은 버전마다 다를 수 있으므로 실제 목록에서 고른다.
    def pick_enum(prop, *candidates):
        try:
            items = scn.bl_rna.properties[prop].enum_items.keys()
        except Exception:
            return candidates[0]
        for c in candidates:
            if c in items:
                return c
        print(f"[경고] {prop}: {candidates} 중 없음. 가능한 값 = {list(items)}")
        return list(items)[0] if items else candidates[0]

    rig_type = pick_enum('arp_export_rig_type', 'HUMANOID', 'humanoid')
    engine = pick_enum('arp_engine_type', 'OTHERS', 'UNITY')

    set_if_exists(scn, 'arp_export_rig_type', rig_type)
    set_if_exists(scn, 'arp_engine_type', engine)
    set_if_exists(scn, 'arp_export_renaming', True)
    set_if_exists(scn, 'arp_rename_fp', rename_fp)
    set_if_exists(scn, 'arp_export_twist', False)      # ⚠️ 기본 True
    set_if_exists(scn, 'arp_units_x100', False)        # ⚠️ 기본 True
    set_if_exists(scn, 'arp_bake_anim', False)         # ⚠️ 기본 True
    set_if_exists(scn, 'arp_full_facial', False)
    set_if_exists(scn, 'arp_ge_export_metacarp', False)
    set_if_exists(scn, 'arp_rename_for_ue', False)
    set_if_exists(scn, 'arp_rename_for_godot', False)

    print(f"[설정] rig_type={rig_type} engine={engine} rename={rename_fp}")

    rig = bpy.data.objects['rig']
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig

    os.makedirs(os.path.dirname(os.path.abspath(out_fbx)), exist_ok=True)
    bpy.ops.arp.arp_export_fbx_panel('EXEC_DEFAULT', filepath=out_fbx)

    if os.path.exists(out_fbx):
        print(f"##### 완료 — {out_fbx} ({os.path.getsize(out_fbx):,} bytes)")
    else:
        raise SystemExit(f"🛑 export 실패 — {out_fbx} 가 만들어지지 않았다")


main()
