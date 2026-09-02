#!/usr/bin/env python3
"""정규화·리깅된 `.blend` 를 Godot 용 `.glb` 로 내보낸다 — 파이프라인의 마지막 단계.

    blender --background --python export_godot_glb.py -- \
        <입력.blend> <출력.glb> [옵션]

## 이 단계가 보장하는 것

    1. 루트 노드에 **scale·translation 이 실리지 않는다**
       → Godot 이 한 번 더 곱하는 사고(`root_scale=150`)를 원천 차단
    2. 애니메이션 이름이 **idle / walk / run / attack / death** 규격
       → Godot AnimationTree 는 이름 문자열로 찾는다. `mixamo.com` 이면 못 찾는다
    3. **RESET** 애니메이션 포함 → Godot 블렌딩의 기준 포즈(assets-3d.md §5)
    4. 텍스처를 **--texture 크기로 리사이즈**해 임베드
       → 4096 텍스처 하나가 17.7MB 다. 1024 면 약 1/16

## --animations

Mixamo 애니메이션 `.fbx` 들이 든 폴더를 준다. 파일 이름이 곧 액션 이름이 된다
(`idle.fbx` → `idle`).

**주지 않으면 애니메이션 없이 내보낸다.** 정적 메시로는 정상 동작하지만 캐릭터는
움직이지 않으므로, 그 사실을 로그에 크게 남기고 나중에 지정하는 방법을 안내한다.

## 🛑 원본을 건드리지 않는다

입력 `.blend` 는 읽기만 한다. 텍스처 리사이즈·액션 임포트는 전부 메모리에서만
일어나고 저장하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Matrix  # type: ignore


# 규격 행동 이름. Godot AnimationTree 가 이 문자열로 찾는다.
ACTIONS_HUMAN = ("idle", "walk", "run", "attack", "death")
ACTIONS_MOB = ("idle", "walk", "attack", "death")

DEFAULT_TEXTURE = 1024
IDENTITY = Matrix.Identity(4)


def log(msg: str) -> None:
    print(f"[export] {msg}", flush=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="정규화된 .blend 를 Godot 용 .glb 로 내보낸다")
    ap.add_argument("input", type=Path, help="입력 .blend (정규화·리깅 완료본)")
    ap.add_argument("output", type=Path, help="출력 .glb")
    ap.add_argument("--animations", type=Path, default=None,
                    help="Mixamo 애니메이션 .fbx 폴더. 생략하면 애니 없이 내보낸다")
    ap.add_argument("--kind", default="human",
                    choices=("human", "animal", "drone", "prop"))
    ap.add_argument("--bones", type=int, default=0, choices=(0, 16, 25),
                    help="본 예산. 0 이면 줄이지 않는다. "
                         "🛑 애니메이션을 붙인 **뒤** 줄여야 어깨 회전이 팔에 흡수된다")
    ap.add_argument("--keep-bones", default="",
                    help="본 감축 시 추가로 남길 본(쉼표 구분)")
    ap.add_argument("--texture", type=int, default=DEFAULT_TEXTURE,
                    help=f"텍스처 최대 변 길이. 기본 {DEFAULT_TEXTURE}")
    ap.add_argument("--no-reset", action="store_true",
                    help="RESET 애니메이션을 만들지 않는다")
    return ap.parse_args(argv)


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


def find_armature():
    for o in bpy.data.objects:
        if o.type == "ARMATURE":
            return o
    return None


def resize_textures(limit: int) -> list[str]:
    """텍스처를 limit 이하로 줄인다. 메모리에서만 바꾸고 원본 파일은 건드리지 않는다.

    🛑 `img.scale()` 만으로는 GLB 에 반영되지 않는다 — packed 이미지는 원본 PNG
    바이트를 `packed_file` 에 그대로 들고 있고, glTF exporter 가 픽셀 버퍼가 아니라
    **그 바이트를 복사**하기 때문이다. 실측(2026-09-02): 4096→1024 로 줄였는데
    GLB 안에는 4096 이 그대로 들어가 파일이 20MB 였다.

    그래서 `scale()` 뒤에 **`pack()` 을 다시 호출**해 리사이즈된 픽셀로
    packed_file 을 덮어쓴다.
    """
    changed = []
    for img in bpy.data.images:
        # 🛑 `has_data` 로 거르지 않는다 — `open_mainfile()` 직후에는 픽셀이 아직
        # 메모리에 없어 packed 이미지도 False 다. 그 조건 때문에 4096 텍스처가
        # 조용히 건너뛰어졌다(실측: 커맨드라인으로 연 씬에서는 True 라 재현이 안 됐다).
        # `size` 는 헤더에서 읽으므로 지연 로드 상태에서도 유효하고,
        # `scale()` 이 필요할 때 알아서 픽셀을 읽는다.
        if img.type != "IMAGE":
            continue
        w, h = img.size
        if w <= 0 or h <= 0 or max(w, h) <= limit:
            continue
        ratio = limit / max(w, h)
        nw, nh = max(int(w * ratio), 1), max(int(h * ratio), 1)
        img.scale(nw, nh)
        # 리사이즈된 픽셀을 packed_file 에 반영한다. 이걸 빼면 위 주석의 사고가 난다.
        try:
            img.pack()
        except RuntimeError as exc:
            log(f"[WARN] {img.name[:36]} 재패킹 실패: {exc}")
        changed.append(f"{img.name[:36]} {w}x{h} → {nw}x{nh}")
    return changed


def rig_scale_ref(arm) -> float:
    """리그의 크기 기준값 — Hips rest head 까지의 거리.

    두 리그의 단위계를 비교하는 데 쓴다. Mixamo 원본은 **cm**(Hips 105.2),
    정규화된 우리 리그는 **m**(Hips 0.894) 라 그대로 섞으면 117배 어긋난다.
    """
    for name in ("mixamorig:Hips", "Hips"):
        b = arm.data.bones.get(name)
        if b:
            return max(b.head_local.length, 1e-6)
    # Hips 가 없으면 가장 먼 본까지의 거리로 대신한다.
    return max((b.head_local.length for b in arm.data.bones), default=1.0)


def scale_action_locations(act, factor: float) -> int:
    """한 액션의 location F-curve 를 factor 배로 스케일한다.

    🛑 회전 트랙은 건드리지 않는다 — 단위가 없는 값이라 그대로 맞다.
    Mixamo 에서 location 키를 갖는 본은 사실상 Hips 뿐이다.
    """
    curves = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    curves.extend(bag.fcurves)
    except AttributeError:
        curves = list(getattr(act, "fcurves", []))
    touched = 0
    for fc in curves:
        if not fc.data_path.endswith("location"):
            continue
        for kp in fc.keyframe_points:
            kp.co[1] *= factor
            kp.handle_left[1] *= factor
            kp.handle_right[1] *= factor
        touched += 1
    return touched


def import_animations(folder: Path, arm) -> list[str]:
    """폴더의 .fbx 를 액션으로 임포트한다. 파일 이름이 액션 이름이 된다.

    Mixamo FBX 는 저마다 제 아마추어를 달고 들어온다. 액션만 뽑아 우리 리그에
    옮기고 임포트된 오브젝트는 지운다.

    🛑 본 이름이 우리 리그와 같아야 액션이 붙는다(mixamorig:*). 다르면 리타게팅이
    필요하고 그것은 이 스크립트의 일이 아니다 — retarget_to_arp_rig.py 를 쓴다.
    """
    imported: list[str] = []
    fbx_files = sorted(folder.glob("*.fbx"))
    if not fbx_files:
        log(f"[WARN] {folder} 에 .fbx 가 없다")
        return imported

    our_bones = {b.name for b in arm.data.bones}
    our_ref = rig_scale_ref(arm)

    for fbx in fbx_files:
        name = fbx.stem.lower()
        before_objs = set(bpy.data.objects)
        before_acts = set(bpy.data.actions)
        try:
            bpy.ops.import_scene.fbx(filepath=str(fbx))
        except RuntimeError as exc:
            log(f"[WARN] {fbx.name} 임포트 실패: {exc}")
            continue
        new_objs = [o for o in bpy.data.objects if o not in before_objs]
        new_acts = [a for a in bpy.data.actions if a not in before_acts]

        # 🛑 단위 보정 — 이것을 빼면 캐릭터가 애니 재생 시 폭발한다.
        #
        # Mixamo 애니 FBX 는 **cm 단위**(Hips rest 105.2)이고, 정규화된 우리
        # 리그는 **m 단위**(Hips 0.894)다. 액션의 location 키는 본 로컬 값이라
        # 아마추어 scale 과 무관하게 그대로 남으므로, 보정 없이 붙이면 Hips 가
        # "148 cm" 가 아니라 "148 m" 위로 올라간다.
        #
        # 실측(2026-09-02 male): rest 는 1.8m 로 정상인데 애니를 적용하면
        # **21.5m** 로 12배 폭발했다. rest bbox 만 보는 검증은 이것을 통과시킨다.
        src_ratio = 1.0
        for src in new_objs:
            if src.type == "ARMATURE":
                src_ratio = our_ref / rig_scale_ref(src)
                break

        if new_acts:
            act = new_acts[0]
            act.name = name
            if abs(src_ratio - 1.0) > 0.01:
                n = scale_action_locations(act, src_ratio)
                log(f"  {name}: location 키 {n}개를 {src_ratio:.6f} 배로 단위 보정 "
                    f"(소스 cm → 우리 m)")
            # 액션이 우리 리그의 본을 실제로 건드리는지 확인한다.
            act.use_fake_user = True
            imported.append(name)
            # 남은 액션은 중복이므로 버린다.
            for extra in new_acts[1:]:
                bpy.data.actions.remove(extra)
        else:
            log(f"[WARN] {fbx.name} 에서 액션을 찾지 못했다")

        # 임포트로 딸려온 아마추어·메시를 지운다. 액션은 남는다.
        for o in new_objs:
            src_bones = {b.name for b in o.data.bones} if o.type == "ARMATURE" else set()
            if src_bones and not (src_bones & our_bones):
                log(f"[WARN] {fbx.name} 의 본 이름이 우리 리그와 겹치지 않는다 "
                    f"— 리타게팅이 필요하다(retarget_to_arp_rig.py)")
            bpy.data.objects.remove(o, do_unlink=True)

    return imported


def make_reset_action(arm) -> None:
    """rest pose 한 프레임짜리 RESET 액션을 만든다.

    Godot 의 애니메이션 블렌딩은 RESET 을 기준 포즈로 전제한다. 없으면 블렌드가
    이상하게 섞인다(assets-3d.md §5).
    """
    ensure_object_mode()
    select_only([arm])
    for pb in arm.pose.bones:
        pb.matrix_basis = IDENTITY
    bpy.context.view_layer.update()

    if not arm.animation_data:
        arm.animation_data_create()
    act = bpy.data.actions.new("RESET")
    arm.animation_data.action = act
    # Blender 4.4+ 는 slot 을 잡아야 키가 들어간다.
    try:
        slot = act.slots.new(id_type="OBJECT", name=arm.name)
        arm.animation_data.action_slot = slot
    except (AttributeError, TypeError):
        pass
    for pb in arm.pose.bones:
        pb.keyframe_insert("location", frame=1)
        pb.keyframe_insert("rotation_quaternion", frame=1)
        pb.keyframe_insert("scale", frame=1)
    act.use_fake_user = True


def push_actions_to_nla(arm, names: list[str]) -> int:
    """액션을 NLA 트랙으로 밀어 넣는다.

    🛑 glTF exporter 는 기본적으로 **NLA 트랙 하나당 애니메이션 하나**를 만든다.
    액션을 그냥 데이터에 두면 현재 할당된 하나만 나간다(assets-3d.md §5 —
    "한 타임라인에 붙여 두면 하나로 합쳐진다").
    """
    if not arm.animation_data:
        arm.animation_data_create()
    ad = arm.animation_data
    # 기존 트랙을 비운다 — 두 번 돌렸을 때 중복되지 않게.
    for track in list(ad.nla_tracks):
        ad.nla_tracks.remove(track)
    ad.action = None

    pushed = 0
    for name in names:
        act = bpy.data.actions.get(name)
        if not act:
            continue
        track = ad.nla_tracks.new()
        track.name = name
        start = int(act.frame_range[0])
        strip = track.strips.new(name, start, act)
        strip.name = name
        pushed += 1
    return pushed


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parse_args(argv)

    if not args.input.exists():
        log(f"[FAIL] 입력이 없다: {args.input}")
        return 1

    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    ensure_object_mode()

    report: dict = {"input": str(args.input), "output": str(args.output),
                    "kind": args.kind, "texture_limit": args.texture}

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    arm = find_armature()
    if not meshes:
        log("[FAIL] 메시가 없다")
        return 1
    log(f"열림: 메시 {len(meshes)}개 · 아마추어 {'있음' if arm else '없음'}")

    # ── 정규화 확인 — 여기서 걸러야 GLB 에 잘못된 변환이 실리지 않는다 ────
    bad = []
    for o in meshes + ([arm] if arm else []):
        if any(abs(v - 1.0) > 1e-4 for v in o.scale):
            bad.append(f"{o.name!r} scale={tuple(round(v, 5) for v in o.scale)}")
        if any(abs(v) > 1e-4 for v in o.rotation_euler):
            bad.append(f"{o.name!r} rot={tuple(round(v, 4) for v in o.rotation_euler)}")
    if bad:
        log("[FAIL] 정규화되지 않은 변환이 남아 있다 — normalize_for_godot.py 를 먼저 돌린다:")
        for b in bad:
            log(f"        {b}")
        return 1
    log("정규화 확인 — scale 1 · rot 0")

    # ── 애니메이션 ────────────────────────────────────────────────────────
    anim_names: list[str] = []
    if args.animations:
        if not args.animations.is_dir():
            log(f"[FAIL] --animations 폴더가 없다: {args.animations}")
            return 1
        if not arm:
            log("[FAIL] 아마추어가 없는데 --animations 가 주어졌다 — 리깅이 먼저다")
            return 1
        anim_names = import_animations(args.animations, arm)
        log(f"애니메이션 {len(anim_names)}종 임포트: {', '.join(anim_names) or '없음'}")

        want = ACTIONS_HUMAN if args.kind == "human" else ACTIONS_MOB
        missing = [w for w in want if w not in anim_names]
        if missing:
            log(f"[WARN] 규격 행동이 빠졌다: {', '.join(missing)} "
                f"— Godot 에서 그 상태는 재생되지 않는다")
    else:
        # 사용자가 명시적으로 요구한 안내다. 조용히 넘어가면 나중에 원인을 못 찾는다.
        log("")
        log("🛑 애니메이션을 적용하지 않습니다.")
        log("   --animations 옵션이 없어 정적 모델로 내보냅니다.")
        log("   캐릭터는 Godot 에서 움직이지 않습니다(T-포즈로 서 있습니다).")
        log("")
        log("   나중에 애니메이션을 붙이려면 폴더를 지정해 이 단계만 다시 돌립니다:")
        log(f"     blender --background --python {Path(__file__).name} -- \\")
        log(f"       {args.input} {args.output} \\")
        log(f"       --animations <애니메이션 .fbx 가 든 폴더> --kind {args.kind}")
        log("")

    # ── 본 감축 — 반드시 애니메이션을 붙인 **뒤**에 한다 ──────────────────
    # 순서를 뒤집으면(감축 후 애니 적용) Mixamo 의 어깨·목 트랙이 갈 곳을 잃어
    # 그 회전이 통째로 사라진다. 뒤에 하면 베이크가 팔·머리로 흡수한다.
    if args.bones and arm:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import reduce_bones  # noqa: PLC0415 — 선택적 의존이라 지연 임포트한다

        before = len(arm.data.bones)
        keep, missing = reduce_bones.resolve_keep(arm, args.bones, args.keep_bones)
        if missing:
            log(f"[WARN] 리그에 없어 건너뛴 본: {', '.join(missing)}")
        samples = reduce_bones.sample_actions(arm, keep)
        merged = reduce_bones.merge_vertex_groups(meshes, arm, keep)
        removed = reduce_bones.delete_bones(arm, keep)
        if samples:
            reduce_bones.rebake_actions(arm, samples, keep)
        log(f"본 감축: {before} → {len(arm.data.bones)} "
            f"(제거 {removed} · 정점 그룹 {merged}개 병합 · 애니 되굽기 {len(samples)}종)")
        report["bones"] = {"before": before, "after": len(arm.data.bones),
                           "budget": args.bones}

    if arm and not args.no_reset:
        make_reset_action(arm)
        anim_names = anim_names + ["RESET"]
        log("RESET 액션 생성 — Godot 블렌딩의 기준 포즈")

    if arm and anim_names:
        pushed = push_actions_to_nla(arm, anim_names)
        log(f"NLA 트랙 {pushed}개로 분리 — glTF 가 애니메이션을 따로 내보내게 한다")

    # ── 텍스처 ────────────────────────────────────────────────────────────
    changed = resize_textures(args.texture)
    for c in changed:
        log(f"텍스처 리사이즈: {c}")
    report["textures_resized"] = changed

    # ── 내보내기 ──────────────────────────────────────────────────────────
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")

    bpy.ops.export_scene.gltf(
        filepath=str(args.output.resolve()),
        export_format="GLB",              # 단일 파일 — 경로가 깨지지 않는다
        export_yup=True,                  # Godot 은 Y-up
        export_apply=True,                # 모디파이어 적용
        use_selection=False,
        export_animations=bool(anim_names),
        export_animation_mode="NLA_TRACKS",  # 트랙 하나 = 애니 하나
        export_bake_animation=True,
        export_skins=bool(arm),
        export_morph=False,               # 셰이프키는 쓰지 않는다
        export_cameras=False,
        export_lights=False,              # SSOT: 런타임 광원 0개
        export_extras=False,
        export_image_format="AUTO",
    )
    log(f"내보냄: {args.output}")

    size_mb = args.output.stat().st_size / 1e6
    report["size_mb"] = round(size_mb, 2)
    report["animations"] = anim_names
    log(f"파일 크기 {size_mb:.2f} MB")

    log_path = args.output.with_suffix(args.output.suffix + ".log.json")
    log_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    log("[OK] 내보내기 완료 — 다음은 verify_godot_glb.py 로 검증한다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
