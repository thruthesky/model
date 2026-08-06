"""ARP 리그(`*_rig.blend`)를 **Mixamo 본 이름 FBX** 로 export 한다 — `--background` 로 돈다.

    blender --background --python arp_export_mixamo.py -- <rig.blend> <out.fbx> [옵션]

      --rename-fp <path>   본 이름 매핑표 (기본: 이 스크립트 옆의 arp_to_mixamo.txt)
      --keep-twist         twist 본을 함께 내보낸다 (기본: 끔)
      --units-x100         100배 스케일로 내보낸다 (기본: 끔)
      --no-spine-fix       spine 4분할 자동 보정을 하지 않는다 (기본: 보정함)

🛑 **이 단계는 GUI 가 필요 없다.** 리깅(④ `arp_autorig.py`)만 3D 뷰 컨텍스트를 요구하고,
export 는 `--background` 에서 완주한다. 근거 — `ARP_OT_GE_export_fbx_panel.execute()` 는
`ARP_OT_export.execute()` 를 그대로 부르므로(auto_rig_ge.py:11842-11843), `'EXEC_DEFAULT'`
로 호출하면 파일 브라우저 `invoke` 를 건너뛰고 바로 실행된다. 실측(2026-08-06 suit_bot):
`{'FINISHED'}` · 1.6MB FBX · verify_mixamo_rig 통과(21/22 역할 · 교집합 51).

  ⚠️ 이 사실을 몰라 "ARP 로는 Mixamo 리그를 못 만든다" 고 판단하고 mixamo.com 웹 업로드로
  우회한 이력이 있다(2026-08-03). ARP 경로는 **정상 동작한다** — 없던 것은 이 스크립트다.

무엇을 하나:
  ① `<rig.blend>` 열기 → 메시+리그 선택, 리그를 active 로
  ② 텍스처 경로 복구 — Tripo FBX 를 `<NAME>_raw.fbx` 로 rename 하면 `.fbm` 폴더명도 바뀌는데
     blend 안 이미지 경로는 옛 `tripo_convert_*.fbm` 을 가리킨 채 남는다. 그대로 export 하면
     `embedding file … failed` 가 뜨고 **텍스처 없는 회색 스프라이트**가 나온다
  ②-b spine 4분할 보정 — `spine_count` 가 3 이면 ARP 가 export 에서 `spine_03.x` 를 지워
     `mixamorig:Spine2` 가 빈다(21/22). `set_spine(4)` + `match_to_rig()` 로 되살린다
  ③ SKILL.md ⑤ 설정표를 그대로 적용 (Humanoid · rename ON · twist/units_x100/bake_anim OFF)
  ④ `arp.arp_export_fbx_panel('EXEC_DEFAULT', quick_export=True)` 로 export
  ⑤ 결과 FBX 를 다시 열어 **Mixamo 본이 실제로 들어갔는지 자가 검증**

결과는 `<out.fbx>.log.json` 에도 기록한다.
"""
import bpy
import sys
import os
import json
import glob
import traceback

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    print("사용: blender --background --python arp_export_mixamo.py -- <rig.blend> <out.fbx>")
    sys.exit(2)

BLEND = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
LOG = OUT + ".log.json"
RENAME_FP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arp_to_mixamo.txt")
KEEP_TWIST = "--keep-twist" in argv
UNITS_X100 = "--units-x100" in argv
SPINE_FIX = "--no-spine-fix" not in argv
for i, a in enumerate(argv):
    if a == "--rename-fp" and i + 1 < len(argv):
        RENAME_FP = os.path.abspath(argv[i + 1])

state = {"blend": BLEND, "out": OUT, "rename_fp": RENAME_FP, "steps": []}


def log(step, **kw):
    state["steps"].append({"step": step, **kw})
    print(f"[arp_export] {step} {kw}")


def object_mode():
    """ARP 연산자는 모드·active 를 바꿔 놓는다 — 다음 ops 가 `poll() failed` 로 막히지
    않게 매번 OBJECT 로 되돌린다(실측: match_to_rig 뒤 select_all 이 막혔다)."""
    if bpy.context.view_layer.objects.active is None:
        vis = [o for o in bpy.data.objects if not o.hide_get()]
        if vis:
            bpy.context.view_layer.objects.active = vis[0]
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def fix_texture_paths():
    """깨진 이미지 경로를 blend 폴더 안에서 파일명으로 찾아 되살린다.

    Tripo ZIP 을 풀고 `tripo_convert_*.fbx/.fbm` 을 `<NAME>_raw.*` 로 rename 하면
    blend 안 경로만 옛 이름으로 남는다(실측 suit_bot). 파일명은 그대로이므로
    폴더를 훑어 같은 이름을 찾으면 복구된다."""
    base = os.path.dirname(BLEND)
    disk = {}
    for p in glob.glob(os.path.join(base, "**", "*"), recursive=True):
        if os.path.isfile(p):
            disk.setdefault(os.path.basename(p).lower(), p)

    fixed, missing = [], []
    for img in bpy.data.images:
        if not img.filepath or img.packed_file:
            continue
        abs_p = bpy.path.abspath(img.filepath)
        if os.path.exists(abs_p):
            continue
        hit = disk.get(os.path.basename(abs_p).lower())
        if hit:
            img.filepath = hit
            img.reload()
            fixed.append(os.path.basename(hit))
        else:
            missing.append(os.path.basename(abs_p))
    if fixed or missing:
        log("texture_paths", fixed=fixed, missing=missing)
    return missing


def fix_spine(rig):
    """spine 을 4분할로 보정한다 — Mixamo 의 Spine/Spine1/Spine2 에 대응시키기 위해.

    ARP 는 `root_ref.x['spine_count'] == 3` 이면 export 에서 `spine_03.x` 를 **지운다**
    (auto_rig_ge.py:6322). 그러면 `mixamorig:Spine2` 가 비어 21/22 가 된다 — 애니메이션은
    붙지만(교집합 임계는 통과) 상체 굽힘이 한 마디 준다.

    🛑 씬 기본값은 이미 4 인데(auto_rig_smart.py:8421) 리그에는 3 이 박힌다(실측 suit_bot).
    `_set_skeleton` 의 `set_spine` 호출이 Smart 자동 경로에서 타지 않기 때문으로, 리깅을
    다시 하지 않고 **여기서 사후 보정**한다. `set_spine` 은 `spine_update_vgroups=True` 가
    기본이라 스킨 웨이트도 함께 따라온다. blend 는 저장하지 않으므로 원본은 그대로다."""
    rr = rig.data.bones.get("root_ref.x")
    cnt = rr.get("spine_count") if rr else None
    before = sorted(b.name for b in rig.data.bones
                    if b.name.startswith("spine_") and "_ref" not in b.name)
    if cnt is None or cnt >= 4:
        log("spine_check", bones=before, root_ref_spine_count=cnt, fixed=False)
        return cnt
    if not SPINE_FIX:
        log("spine_check", bones=before, root_ref_spine_count=cnt, fixed=False)
        print(f"⚠️ spine_count={cnt} — mixamorig:Spine2 가 빈 채로 나간다(--no-spine-fix)")
        return cnt

    import importlib
    ar = importlib.import_module("bl_ext.user_default.auto_rig_pro.src.auto_rig")
    object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    rig.hide_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    ar.set_spine(count=4, grid_align=True, bottom=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    r = bpy.ops.arp.match_to_rig()          # 리그를 다시 맞춰야 반영된다
    object_mode()                           # match_to_rig 이 모드·active 를 바꿔 놓는다
    after = sorted(b.name for b in rig.data.bones
                   if b.name.startswith("spine_") and "_ref" not in b.name)
    rr = rig.data.bones.get("root_ref.x")
    log("spine_fixed", before=before, after=after, match_to_rig=list(r),
        root_ref_spine_count=rr.get("spine_count") if rr else None)
    return rr.get("spine_count") if rr else None


def verify(path):
    """export 된 FBX 를 열어 Mixamo 본이 실제로 들어갔는지 확인한다."""
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path, use_image_search=False)
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if arm is None:
        return {"ok": False, "reason": "armature 없음"}
    names = [b.name for b in arm.data.bones]
    mixamo = [n for n in names if n.startswith("mixamorig:")]
    leftover = [n for n in names if not n.startswith("mixamorig:")]
    return {
        "ok": len(mixamo) >= 20,
        "bones": len(names),
        "mixamo_bones": len(mixamo),
        "leftover": leftover[:12],
        "leftover_count": len(leftover),
    }


def run():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    scn = bpy.context.scene

    rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if rig is None:
        raise RuntimeError("armature 가 없다 — 리깅된 .blend 인지 확인할 것")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("메시가 없다")

    # 🛑 Smart 세션 후 Match to Rig 를 안 눌렀으면 ARP 가 export 를 거부한다
    #    (auto_rig_ge.py:1651 'Click "Match to Rig" before exporting')
    mtr = rig.data.get("has_match_to_rig")
    if mtr is False:
        raise RuntimeError('has_match_to_rig=False — 리깅 단계에서 arp.match_to_rig() 를 부르지 않았다')
    log("opened", rig=rig.name, meshes=[m.name for m in meshes],
        bones=len(rig.data.bones), has_match_to_rig=mtr)

    missing_tex = fix_texture_paths()
    fix_spine(rig)

    if not os.path.exists(RENAME_FP):
        # ARP 는 파일이 없어도 "Skip renaming" 만 찍고 진행한다(auto_rig_ge.py:10406) —
        # 그러면 ARP 이름 그대로 나가 sheet.py 가 "Mixamo rig 가 아닙니다" 로 즉시 죽는다.
        raise RuntimeError(f"매핑표가 없다: {RENAME_FP}")

    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.hide_set(False)
        m.select_set(True)
    rig.hide_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig

    # ── SKILL.md ⑤ 설정표 ──────────────────────────────────
    scn.arp_engine_type = "OTHERS"          # 엔진별 추가 rename 규칙을 타지 않게
    scn.arp_export_rig_type = "HUMANOID"    # 매핑표가 이 타입의 본 이름을 전제한다
    scn.arp_export_renaming = True          # 이 스킬의 핵심
    scn.arp_rename_fp = RENAME_FP
    scn.arp_export_twist = KEEP_TWIST       # 기본 ON 이라 끄는 것이 수동 작업
    scn.arp_full_facial = False
    scn.arp_units_x100 = UNITS_X100         # 기본 ON — 켜면 100배로 나간다
    scn.arp_ge_export_metacarp = False
    scn.arp_bake_anim = False               # 리그만. 애니는 ⑦ 이 붙인다
    log("settings", rig_type="HUMANOID", renaming=True, twist=KEEP_TWIST,
        units_x100=UNITS_X100, bake_anim=False)

    r = bpy.ops.arp.arp_export_fbx_panel("EXEC_DEFAULT", filepath=OUT, quick_export=True)
    if "FINISHED" not in r or not os.path.exists(OUT):
        raise RuntimeError(f"export 실패: {r}")
    log("exported", result=list(r), size=os.path.getsize(OUT))

    v = verify(OUT)
    log("verify", **v)
    state["ok"] = bool(v["ok"])
    state["missing_textures"] = missing_tex
    if not v["ok"]:
        raise RuntimeError(f"export 는 됐는데 Mixamo 본이 없다: {v}")


try:
    run()
    print(f"\n✅ Mixamo 본 이름으로 export 완료\n   {OUT}")
    s = next(x for x in state["steps"] if x["step"] == "verify")
    print(f"   본 {s['bones']}개 중 mixamorig:* {s['mixamo_bones']}개"
          + (f" · ARP 이름 잔존 {s['leftover_count']}개 {s['leftover']}" if s["leftover_count"] else ""))
    if state.get("missing_textures"):
        print(f"   ⚠️ 못 찾은 텍스처 {state['missing_textures']} — 스프라이트 색이 빠진다")
    print("   다음: verify_mixamo_rig.py 로 검증 → retarget_to_arp_rig.py 로 .blend 생성")
except Exception as e:
    state["ok"] = False
    state["error"] = f"{type(e).__name__}: {e}"
    state["traceback"] = traceback.format_exc()
    print(f"\n❌ {state['error']}")
    traceback.print_exc()
finally:
    with open(LOG, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)

sys.exit(0 if state.get("ok") else 1)
