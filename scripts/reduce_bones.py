#!/usr/bin/env python3
"""Mixamo 65본 리그를 저사양 예산(16 또는 25본)으로 줄인다.

    blender --background --python reduce_bones.py -- \
        <입력.blend> <출력.blend> --bones 16

## 왜 본을 줄이는가

본 행렬은 **매 프레임 GPU 로 업로드**된다. 캐릭터 90개가 동시에 보이는 라리엔의
AOI 예산에서 65본과 16본은 대역폭이 4배 차이 난다. 저사양 3GB 기기는 RAM 보다
**GPU 대역폭이 먼저 막힌다**(SSOT.md §3).

Mixamo 65본 중 **40본이 손가락**이다. 고정 −45° 피치에 직교 투영인 라리엔
카메라에서 손가락은 **한 픽셀도 구분되지 않는다**(assets-3d.md §4 "손가락 본 제외").

## 🛑 본을 그냥 지우면 포즈가 무너진다

Blender 에서 본을 지우면 자식이 조부모에 연결되고 **rest 는 유지**되지만,
애니메이션은 부모의 로컬 회전 기준이라 **지운 본의 회전이 통째로 사라진다.**
예를 들어 `LeftShoulder` 를 지우면 어깨 회전이 빠져 팔이 몸통에 붙어 돈다.

그래서 이 스크립트는 **지우기 전에 애니메이션을 아마추어 공간으로 샘플링**하고,
지운 뒤 **새 계층에서 다시 굽는다**. 남는 본의 화면상 궤적이 보존된다.

    1. 각 액션 × 각 프레임에서 남길 본의 pose matrix(아마추어 공간)를 기록
    2. 지울 본의 정점 그룹 웨이트를 **가장 가까운 남은 조상**으로 합산
    3. 본 제거
    4. 기록한 matrix 를 부모→자식 순서로 되적용하며 키 삽입

## 본 구성

**16본(최저·기본)** — 어깨·목·발가락·손가락을 뺀 최소 골격:

    Hips, Spine, Spine1, Head,
    L/R Arm, ForeArm, Hand,
    L/R UpLeg, Leg, Foot

**25본** — 위에 어깨·목·척추 한 마디·발가락을 더한 22본 표준 + 모델 고유 3본 여유:

    Hips, Spine, Spine1, Spine2, Neck, Head,
    L/R Shoulder, Arm, ForeArm, Hand,
    L/R UpLeg, Leg, Foot, ToeBase

**무엇을 잃는가** — 16본은 어깨 흔들림과 발가락 굴림이 사라진다. 걷기·달리기의
자연스러움이 25본보다 눈에 띄게 떨어지므로, **근거리에 오래 보이는 PC 는 25**,
멀리서 다수가 보이는 몹은 16 을 권한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Matrix  # type: ignore


PREFIX = "mixamorig:"

# 16본 — 저사양 최저 구성. 어깨·목·발가락·손가락 없음.
BONES_16 = (
    "Hips", "Spine", "Spine1", "Head",
    "LeftArm", "LeftForeArm", "LeftHand",
    "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot",
    "RightUpLeg", "RightLeg", "RightFoot",
)

# 25본 — 22본 표준(손가락 제외 전신) + 모델 고유 본 3개 여유.
BONES_25 = (
    "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
    "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase",
)

BONE_SETS = {16: BONES_16, 25: BONES_25}
IDENTITY = Matrix.Identity(4)


def log(msg: str) -> None:
    print(f"[bones] {msg}", flush=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Mixamo 리그를 16 또는 25본으로 줄인다")
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--bones", type=int, default=16, choices=(16, 25),
                    help="본 예산. 기본 16(최저)")
    ap.add_argument("--keep", default="",
                    help="추가로 남길 본 이름(쉼표 구분). 무기 그립·꼬리 등 모델 고유 본")
    ap.add_argument("--dry-run", action="store_true", help="계획만 출력한다")
    return ap.parse_args(argv)


def find_armature():
    for o in bpy.data.objects:
        if o.type == "ARMATURE":
            return o
    return None


def ensure_object_mode() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def select_only(objs: list) -> None:
    """숨겨진 오브젝트는 select_set 이 무시되므로 먼저 드러낸다."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        if o.hide_get():
            o.hide_set(False)
        o.hide_viewport = False
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def resolve_keep(arm, budget: int, extra: str) -> tuple[set[str], list[str]]:
    """남길 본 이름을 실제 리그 이름으로 해석한다.

    `mixamorig:` 접두사가 있을 수도 없을 수도 있으므로 둘 다 시도한다.
    """
    have = {b.name for b in arm.data.bones}
    keep: set[str] = set()
    missing: list[str] = []
    for short in BONE_SETS[budget]:
        for cand in (PREFIX + short, short):
            if cand in have:
                keep.add(cand)
                break
        else:
            missing.append(short)
    for name in (n.strip() for n in extra.split(",") if n.strip()):
        for cand in (name, PREFIX + name):
            if cand in have:
                keep.add(cand)
                break
        else:
            missing.append(name)
    return keep, missing


def nearest_kept_ancestor(bone, keep: set[str]) -> str | None:
    """가장 가까운 남은 조상 본의 이름. 없으면 None."""
    p = bone.parent
    while p is not None:
        if p.name in keep:
            return p.name
        p = p.parent
    return None


def action_fcurves(act):
    """slotted action(4.4+)과 옛 구조를 모두 지원해 F-curve 를 모은다."""
    try:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        if out:
            return out
    except AttributeError:
        pass
    return list(getattr(act, "fcurves", []))


def action_frames(act) -> list[int]:
    lo, hi = act.frame_range
    return list(range(int(lo), int(hi) + 1))


def sample_actions(arm, keep: set[str]) -> dict:
    """각 액션 × 각 프레임에서 남길 본의 pose matrix(아마추어 공간)를 기록한다.

    `pose_bone.matrix` 는 아마추어 오브젝트 공간의 행렬이라 **계층이 바뀌어도
    화면상 위치가 같다.** 이것이 본을 지워도 궤적이 보존되는 근거다.
    """
    scene = bpy.context.scene
    if not arm.animation_data:
        return {}
    saved_action = arm.animation_data.action
    saved_slot = getattr(arm.animation_data, "action_slot", None)

    data: dict = {}
    for act in list(bpy.data.actions):
        arm.animation_data.action = act
        # slot 을 안 잡으면 액션이 조용히 평가되지 않는다(4.4+).
        try:
            slots = list(act.slots)
            if slots:
                arm.animation_data.action_slot = slots[0]
        except (AttributeError, TypeError):
            pass
        frames = {}
        for f in action_frames(act):
            scene.frame_set(f)
            frames[f] = {n: arm.pose.bones[n].matrix.copy()
                         for n in keep if n in arm.pose.bones}
        data[act.name] = frames

    arm.animation_data.action = saved_action
    if saved_slot is not None:
        try:
            arm.animation_data.action_slot = saved_slot
        except (AttributeError, TypeError):
            pass
    return data


def merge_vertex_groups(meshes: list, arm, keep: set[str]) -> int:
    """지울 본의 정점 그룹 웨이트를 가장 가까운 남은 조상으로 합산한다.

    합산하지 않고 그냥 지우면 그 정점들이 **아무 본에도 묶이지 않아** 제자리에
    남는다 — 팔을 들면 손가락 끝 정점만 공중에 떠 있는 결과가 된다.
    """
    merged = 0
    for me in meshes:
        vg = me.vertex_groups
        # 지울 그룹 → 받을 그룹 이름
        plan: dict[str, str] = {}
        for g in vg:
            if g.name in keep:
                continue
            bone = arm.data.bones.get(g.name)
            target = nearest_kept_ancestor(bone, keep) if bone else None
            if target:
                plan[g.name] = target

        for src_name, dst_name in plan.items():
            src = vg.get(src_name)
            dst = vg.get(dst_name)
            if src is None:
                continue
            if dst is None:
                dst = vg.new(name=dst_name)
            src_idx = src.index
            for v in me.data.vertices:
                for ge in v.groups:
                    if ge.group != src_idx:
                        continue
                    w = ge.weight
                    if w <= 0.0:
                        continue
                    try:
                        cur = dst.weight(v.index)
                    except RuntimeError:
                        cur = 0.0
                    dst.add([v.index], min(cur + w, 1.0), "REPLACE")
            merged += 1

        # 합산이 끝난 뒤 지운다 — 중간에 지우면 인덱스가 밀린다.
        for name in list(plan) + [g.name for g in vg if g.name not in keep
                                  and g.name not in plan
                                  and arm.data.bones.get(g.name)]:
            g = vg.get(name)
            if g:
                vg.remove(g)
    return merged


def delete_bones(arm, keep: set[str]) -> int:
    """남길 본 외를 제거한다. 자식은 자동으로 남은 조상에 연결된다."""
    ensure_object_mode()
    select_only([arm])
    bpy.ops.object.mode_set(mode="EDIT")
    removed = 0
    for eb in list(arm.data.edit_bones):
        if eb.name not in keep:
            arm.data.edit_bones.remove(eb)
            removed += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    return removed


def rebake_actions(arm, samples: dict, keep: set[str]) -> int:
    """기록한 pose matrix 를 새 계층에 되굽는다.

    🛑 부모 → 자식 순서로 적용해야 한다. `pose_bone.matrix` 설정은 부모의 현재
    상태를 기준으로 로컬 변환을 역산하므로, 자식을 먼저 넣으면 부모가 나중에
    움직이며 어긋난다.
    """
    scene = bpy.context.scene

    def depth(name: str) -> int:
        b = arm.data.bones.get(name)
        d = 0
        while b and b.parent:
            d += 1
            b = b.parent
        return d

    order = sorted((n for n in keep if n in arm.pose.bones), key=depth)
    baked = 0

    for act_name, frames in samples.items():
        act = bpy.data.actions.get(act_name)
        if not act:
            continue
        # 기존 키를 비우고 새로 만든다 — 지운 본의 트랙도 함께 사라진다.
        new_act = bpy.data.actions.new(act_name + "__tmp")
        arm.animation_data.action = new_act
        try:
            slot = new_act.slots.new(id_type="OBJECT", name=arm.name)
            arm.animation_data.action_slot = slot
        except (AttributeError, TypeError):
            pass

        for f in sorted(frames):
            scene.frame_set(f)
            mats = frames[f]
            for name in order:
                m = mats.get(name)
                if m is None:
                    continue
                pb = arm.pose.bones[name]
                pb.matrix = m
                bpy.context.view_layer.update()
            for name in order:
                pb = arm.pose.bones[name]
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)
                pb.keyframe_insert("scale", frame=f)
        baked += 1

        bpy.data.actions.remove(act)
        new_act.name = act_name
        new_act.use_fake_user = True

    return baked


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parse_args(argv)

    if not args.input.exists():
        log(f"[FAIL] 입력이 없다: {args.input}")
        return 1
    if args.input.resolve() == args.output.resolve():
        log("[FAIL] 입력과 출력이 같다 — 원본을 덮어쓰지 않는다")
        return 1

    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    ensure_object_mode()

    arm = find_armature()
    if not arm:
        log("[FAIL] 아마추어가 없다 — 리깅된 파일을 넣는다")
        return 1
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    before = len(arm.data.bones)
    keep, missing = resolve_keep(arm, args.bones, args.keep)
    log(f"본 {before}개 → 목표 {args.bones}개 (남길 본 {len(keep)}개)")
    if missing:
        log(f"[WARN] 리그에 없어 건너뛴 본: {', '.join(missing)}")

    report = {"input": str(args.input), "output": str(args.output),
              "bones_before": before, "bones_budget": args.bones,
              "keep": sorted(keep), "missing": missing}

    if args.dry_run:
        drop = sorted(b.name for b in arm.data.bones if b.name not in keep)
        log(f"제거 예정 {len(drop)}개: {', '.join(drop[:12])}"
            f"{' …' if len(drop) > 12 else ''}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    # ── 1. 애니메이션을 아마추어 공간으로 샘플링 ──────────────────────────
    samples = sample_actions(arm, keep)
    total_frames = sum(len(f) for f in samples.values())
    log(f"애니 {len(samples)}종 · {total_frames}프레임을 아마추어 공간으로 샘플링")

    # ── 2. 웨이트를 남은 조상으로 합산 ────────────────────────────────────
    merged = merge_vertex_groups(meshes, arm, keep)
    log(f"정점 그룹 {merged}개를 남은 조상으로 합산")

    # ── 3. 본 제거 ────────────────────────────────────────────────────────
    removed = delete_bones(arm, keep)
    log(f"본 {removed}개 제거 → {len(arm.data.bones)}개 남음")

    # ── 4. 새 계층에 되굽기 ───────────────────────────────────────────────
    if samples:
        baked = rebake_actions(arm, samples, keep)
        log(f"애니 {baked}종을 새 계층에 되구움 — 남는 본의 궤적이 보존된다")

    after = len(arm.data.bones)
    report["bones_after"] = after
    ok = after <= args.bones

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    log(f"저장: {args.output}")

    args.output.with_suffix(args.output.suffix + ".log.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if not ok:
        log(f"[FAIL] 본 {after}개 > 예산 {args.bones}")
        return 1
    log(f"[OK] 본 {before} → {after} (예산 {args.bones})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
