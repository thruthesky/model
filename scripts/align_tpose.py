#!/usr/bin/env python3
"""human 형 리그의 rest 를 **Mixamo T-포즈**에 정렬한다 — 메시도 함께 굽는다.

    # 판정만 (아무것도 고치지 않는다)
    blender --background --python align_tpose.py -- \
        <타겟.blend|.fbx> <참조 Mixamo 애니.fbx> --check-only

    # 정렬해서 저장
    blender --background --python align_tpose.py -- \
        <타겟.blend|.fbx> <참조 Mixamo 애니.fbx> <출력.blend>

## 🛑 왜 필요한가 — T-포즈가 아니면 애니메이션이 반드시 무너진다

Mixamo 애니메이션은 **T-포즈 rest** 를 전제한다. 그리고 리타게팅 공식

    (src_pose @ src_rest⁻¹) @ tgt_rest

은 타겟의 rest 자세를 **보존**한다 — 소스에서 가져오는 것은 *rest 대비 회전차* 뿐이고,
기준 자세는 **우리 리그의 rest** 다. 그래서 rest 가 A-포즈면 "T-포즈에서 팔을 내리는"
회전차가 **이미 내려간 팔에 또** 더해져 팔이 몸통을 관통한다.

**실측 (2026-09-04, `scrap` 메카)** — 리깅·검증(22/22 역할·교집합 52)을 전부 통과했는데도
애니가 전부 뒤틀렸다. 원인은 rest 각도차 하나였다:

    LeftArm      70.2°   타겟 (0.34, 0.18, -0.92) 아래   Mixamo (1, 0, 0) 수평
    LeftForeArm  83.1°
    LeftHand     86.3°
    Spine        21.3°   ·  Neck 19.0°  ·  LeftFoot 39.0°

정렬 후 각도차 **0.00°**, 발 접지·팔 자세가 정상으로 돌아왔다.

## 무엇을 정렬하고 무엇을 두는가

| 부위 | 기본 | 왜 |
|---|---|---|
| 팔(Shoulder·Arm·ForeArm·Hand·손가락) | ✅ 정렬 | 각도차가 70~86° 로 압도적. **여기가 원인의 대부분이다** |
| 척추·목·머리(Spine·Neck·Head) | ✅ 정렬 | 20° 안팎이지만 상체가 숙여진 채 굳는다 |
| **다리(UpLeg·Leg·Foot·Toe)** | 🛑 **두 번째 생각 없이 정렬하지 않는다** | T-포즈는 무릎을 곧게 편다. **각진 기계 부품·굽은 다리 모델은 그 과정에서 정강이·발 메시가 늘어나 찢어진다**(실측). 각도차가 15° 안팎이면 리타게팅이 감내한다 |

`--parts all` 로 다리까지 정렬할 수 있지만, **정렬 후 반드시 렌더해서 눈으로 본다.**

## 메시도 함께 굽는다

리그의 rest 만 바꾸면 메시가 따라오지 않아 스킨이 통째로 어긋난다. 그래서
① 포즈를 잡고 ② armature 모디파이어를 **복제해 적용**(현재 포즈를 메시에 굽는다)
③ `pose.armature_apply()` 로 포즈를 rest 로 굳힌다 — 이 순서를 지킨다.

메시가 T-포즈로 굳어도 **게임에서는 언제나 애니메이션 자세가 재생되므로 문제가 없다.**
T-포즈로 보이는 것은 `RESET` 액션뿐이고, 그것이 Godot 블렌딩의 올바른 기준 포즈다.

## 🛑 이 단계는 리깅 **뒤**, 리타게팅 **앞**이다

    ③ 리깅(ARP) → **align_tpose.py** → ⑦ 리타게팅 → ④ export_godot_glb.py

리깅 전에는 본이 없어 자세를 바꿀 수 없고, 리타게팅 뒤에는 이미 액션이 구워져 늦다.
"""

from __future__ import annotations

import json
import os
import sys

import bpy  # type: ignore
from mathutils import Matrix  # type: ignore


PREFIX = "mixamorig:"

ARM_KEYS = ("Shoulder", "Arm", "ForeArm", "Hand",
            "Thumb", "Index", "Middle", "Ring", "Pinky")
SPINE_KEYS = ("Spine", "Neck", "Head")
LEG_KEYS = ("UpLeg", "Leg", "Foot", "Toe")

# 이 각도를 넘는 본이 하나라도 있으면 "T-포즈가 아니다" 로 판정한다.
DEFAULT_THRESHOLD = 15.0


def log(msg: str) -> None:
    print(f"[tpose] {msg}", flush=True)


def parse_args(argv: list[str]) -> dict:
    out = {"target": None, "reference": None, "output": None,
           "check_only": False, "parts": "arms+spine",
           "threshold": DEFAULT_THRESHOLD}
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--check-only":
            out["check_only"] = True
        elif a == "--parts":
            i += 1
            out["parts"] = argv[i]
        elif a == "--threshold":
            i += 1
            out["threshold"] = float(argv[i])
        else:
            pos.append(a)
        i += 1
    if len(pos) < 2:
        raise SystemExit(
            "사용법: blender --background --python align_tpose.py -- "
            "<타겟.blend|.fbx> <참조 Mixamo 애니.fbx> [<출력.blend>] "
            "[--check-only] [--parts arms|arms+spine|all] [--threshold 15]")
    out["target"], out["reference"] = pos[0], pos[1]
    if len(pos) > 2:
        out["output"] = pos[2]
    return out


def selected(parts: str):
    """정렬 대상 판정 함수를 만든다."""
    keys = list(ARM_KEYS)
    include_legs = False
    if parts in ("arms+spine", "all"):
        keys += list(SPINE_KEYS)
    if parts == "all":
        include_legs = True

    def want(name: str) -> bool:
        if not include_legs and any(k in name for k in LEG_KEYS):
            return False
        if include_legs and any(k in name for k in LEG_KEYS):
            return True
        return any(k in name for k in keys)
    return want


def load_target(path: str):
    if os.path.splitext(path)[1].lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=path)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        raise SystemExit(f"아마추어가 없다: {path}")
    return max(arms, key=lambda o: len(o.data.bones))


def bone_dirs(rig) -> dict:
    out = {}
    for b in rig.data.bones:
        v = (rig.matrix_world @ b.tail_local) - (rig.matrix_world @ b.head_local)
        if v.length > 1e-6:
            out[b.name] = v.normalized()
    return out


def ordered_names(rig) -> list:
    """부모 → 자식 순서. 🛑 pose_bone.matrix 설정은 부모의 현재 상태를 기준으로
    로컬 변환을 역산하므로, 자식을 먼저 넣으면 부모가 나중에 움직이며 어긋난다."""
    out = []

    def walk(b):
        out.append(b.name)
        for c in b.children:
            walk(c)
    for b in rig.data.bones:
        if b.parent is None:
            walk(b)
    return out


def measure(tgt, src) -> list:
    import math
    dt, ds = bone_dirs(tgt), bone_dirs(src)
    rows = []
    for n in dt:
        if n in ds:
            rows.append((math.degrees(dt[n].angle(ds[n])), n))
    rows.sort(reverse=True)
    return rows


def report(rows, threshold: float) -> bool:
    """T-포즈면 True."""
    if not rows:
        log("[FAIL] 공통 본이 없다 — 본 이름이 mixamorig:* 인지 확인한다")
        return False
    worst = rows[0][0]
    log(f"rest 각도차 최대 {worst:.2f}° · 평균 "
        f"{sum(a for a, _ in rows) / len(rows):.2f}° (본 {len(rows)}개)")
    for a, n in rows[:8]:
        mark = " 🛑" if a > 30 else (" ⚠" if a > threshold else "")
        log(f"   {n.replace(PREFIX, ''):20} {a:6.2f}°{mark}")
    if worst > threshold:
        log(f"[FAIL] T-포즈가 아니다 (최대 {worst:.2f}° > 임계 {threshold}°) "
            f"— 이대로 리타게팅하면 애니메이션이 무너진다")
        return False
    log(f"[OK  ] T-포즈다 (최대 {worst:.2f}° ≤ 임계 {threshold}°)")
    return True


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parse_args(argv)

    tgt = load_target(args["target"])
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    keep = {o.name for o in bpy.data.objects}

    bpy.ops.import_scene.fbx(filepath=args["reference"])
    extra = [o for o in bpy.data.objects if o.name not in keep]
    src = next((o for o in extra if o.type == "ARMATURE"), None)
    if src is None:
        raise SystemExit(f"참조에 아마추어가 없다: {args['reference']}")

    rows = measure(tgt, src)
    ok = report(rows, args["threshold"])

    if args["check_only"]:
        sys.exit(0 if ok else 1)
    if args["output"] is None:
        raise SystemExit("출력 경로가 없다 — <출력.blend> 를 주거나 --check-only 를 쓴다")

    want = selected(args["parts"])
    result = {"target": args["target"], "reference": args["reference"],
              "parts": args["parts"], "before_max_deg": round(rows[0][0], 3) if rows else None,
              "aligned": [], "skipped": []}

    # ── 1. 소스 rest 회전을 타겟 포즈로 (부모 → 자식) ─────────────────────
    tgt_w_inv = tgt.matrix_world.to_3x3().normalized().inverted()
    src_w = src.matrix_world.to_3x3().normalized()
    bpy.context.view_layer.objects.active = tgt
    for name in ordered_names(tgt):
        pb = tgt.pose.bones.get(name)
        sb = src.data.bones.get(name)
        if pb is None or sb is None or not want(name):
            result["skipped"].append(name)
            continue
        arm_rot = tgt_w_inv @ (src_w @ sb.matrix_local.to_3x3().normalized())
        cur = pb.matrix.copy()
        pb.matrix = Matrix.Translation(cur.translation) @ arm_rot.to_4x4()
        bpy.context.view_layer.update()
        result["aligned"].append(name)

    # ── 2. 메시에 현재 포즈를 굽는다 (모디파이어 복제 후 적용) ────────────
    baked = 0
    for m in meshes:
        am = [x for x in m.modifiers if x.type == "ARMATURE"]
        if not am:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        m.select_set(True)
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.modifier_copy(modifier=am[0].name)
        dup = [x for x in m.modifiers if x.type == "ARMATURE"][1]
        bpy.ops.object.modifier_apply(modifier=dup.name)
        baked += 1
    result["meshes_baked"] = baked

    # ── 3. 포즈를 rest 로 굳힌다 ──────────────────────────────────────────
    bpy.ops.object.select_all(action="DESELECT")
    tgt.select_set(True)
    bpy.context.view_layer.objects.active = tgt
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode="OBJECT")

    # ── 4. 재측정 → 참조 제거 → 저장 ─────────────────────────────────────
    after = measure(tgt, src)
    result["after_max_deg"] = round(after[0][0], 3) if after else None
    for o in extra:
        bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    bpy.ops.wm.save_as_mainfile(filepath=args["output"])
    result["saved"] = args["output"]
    result["aligned_count"] = len(result["aligned"])

    log(f"정렬 {result['aligned_count']}본 · 메시 {baked}개에 포즈를 구웠다")
    log(f"rest 각도차 {result['before_max_deg']}° → {result['after_max_deg']}°")
    log(f"저장: {args['output']}")
    with open(args["output"] + ".log.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    # 다리를 뺀 정렬은 다리 각도차가 남는다 — 그것은 의도된 것이므로 실패로 보지 않는다.
    log("[OK  ] 완료 — 🛑 정렬 결과를 반드시 렌더해서 눈으로 확인한다")


main()
