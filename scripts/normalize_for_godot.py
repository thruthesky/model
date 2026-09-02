#!/usr/bin/env python3
"""Tripo3D 원본을 Godot 규약으로 정규화한다 — **리깅 전에** 돌린다.

    blender --background --python normalize_for_godot.py -- \
        <입력.fbx|.glb|.obj|.blend> <출력.blend> [옵션]

## 왜 이 단계가 있는가

Tripo3D 는 **Y-up · 1.0 단위 · 원점이 제각각**인 메시를 준다. Mixamo 리그는
**Z-up · cm 단위(Hips 63.49)** 다. 이 둘을 정규화 없이 붙이면 두 좌표계가 섞이고,
그 섞임은 리깅·리타게팅·익스포트를 거치며 **증폭**된다.

실제로 일어난 일(laryen3d `male.blend`, 2026-09-02 실측):

    human 메시   : 데이터 Y-up + 오브젝트 rot X +90°  → 월드에서 똑바로 섬 ✅
    Armature     : 데이터 Z-up + 오브젝트 rot X +90°  → 90° 더 돌아 누움 ❌
                   게다가 scale 0.01 이 살아 있어 단위계까지 섞임

    → GLB 로 내보내니 메시가 원점 **아래로** 매달리고(Y −2.17 ~ 0),
      Godot 에서 안 보임 → `.import` 에 root_scale=150 을 넣어 덮음(땜질)
      → GLB 를 고친 뒤에도 150 이 남아 이번엔 **270m 거인**이 됨

**증상을 Godot 에서 덮으면 반드시 다음 단계에서 더 크게 터진다.** 그래서 정규화를
파이프라인의 **가장 앞**에 둔다. 캐릭터 5종·몬스터 30종에서 같은 문제가 반복되지
않게 하는 유일한 방법이다.

## 무엇을 보장하는가 (Godot 규약)

    1. Blender 월드에서 **Z-up · 정면 −Y**       → Godot 이 Y-up · 정면 −Z 로 변환
    2. **키 1.8 m**                              → --height 로 조정
    3. **발바닥이 원점**(bbox Z_min = 0), 좌우·앞뒤 중심이 원점
    4. **loc 0 · rot 0 · scale 1** — 전부 데이터에 구움 → glTF 루트에 변환이 실리지 않는다
    5. 메시 1개 · 머티리얼 1개로 합침(--no-join 으로 끌 수 있다)
    6. **삼각형 예산**(--triangles) — Tripo 는 100만 삼각형을 준다. 리깅 전에 줄인다

## 🛑 정규화가 조용히 실패하는 네 가지 (2026-09-02 전부 실측)

이 스크립트의 본문은 대부분 아래 네 함정을 피하는 코드다. **넷 다 오류를 내지
않고 잘못된 결과만 남기므로**, 직접 구현할 때 반드시 알아야 한다.

| # | 함정 | 증상 | 이 스크립트의 대응 |
|---|---|---|---|
| 1 | **숨겨진 오브젝트는 `select_set(True)` 가 무시된다** | `transform_apply` 가 `{'FINISHED'}` 를 반환하고도 아마추어에 적용 안 됨 → scale 0.01 · rot 90° 잔존 | `select_only()` 가 `hide_set(False)` 를 먼저 부른다 |
| 2 | **애니메이션이 붙으면 `transform_apply` 가 거부**한다 | 위와 같은 잔존 | `detach_actions()` 로 떼고 굽고 되돌린다 |
| 3 | **`data.transform()` 은 rest 만 바꾸고 pose 는 안 바꾼다** | armature modifier 가 그 차이만큼 폭발 (키 1.0 → 89.3, 약 100배) | 데이터 직접 변환 대신 연산자에 맡긴다 |
| 4 | **부모·자식을 함께 변환하면 이중 적용된다** | 키 1.8 을 노렸는데 10.03 | `unparent_keep_transform()` 으로 끊고 작업 후 복원 |

여기에 **측정 함정**이 하나 더 있다 — `evaluated_get()`(모디파이어 적용)으로 bbox 를
재면 armature modifier 때문에 값이 흔들려, 스케일을 맞춘 직후에 재도 다른 값이
나온다. 정규화는 **데이터 공간(rest)** 을 다루므로 `world_bbox()` 는 원본 메시를 쓴다.

## 🛑 리깅 전에 돌린다

리깅 후에 스케일을 바꾸면 **본 길이와 액션의 위치 키가 어긋난다.** 이미 리깅된
파일을 고쳐야 하면 `--rigged` 를 준다 — 리그·메시·액션 location 키를 함께 변환한다.
그래도 리깅 전에 하는 것보다 위험하다.

## 원본을 건드리지 않는다

입력 파일은 읽기만 한다. 결과는 **출력으로 지정한 새 파일**에만 쓴다.
`.blend` 를 입력으로 줘도 그 파일에 저장하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Matrix, Vector  # type: ignore


# ── 기본 규격 ────────────────────────────────────────────────────────────────
DEFAULT_HEIGHT = 1.8  # 인간형 캐릭터 키(m). 라리엔 PC 기준.

# 삼각형 예산 사다리. 앞으로 갈수록 가볍다.
# 라리엔 저사양 예산은 LOD0 3,000~6,000 (assets-3d.md §4) 이므로 기본은 4800.
TRIANGLE_LADDER = (1600, 3200, 4800, 6400, 7200)
DEFAULT_TRIANGLES = 4800

EPS = 1e-6
IDENTITY = Matrix.Identity(4)


def log(msg: str) -> None:
    print(f"[normalize] {msg}", flush=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Tripo3D 원본을 Godot 규약(Z-up·1.8m·발바닥 원점)으로 정규화")
    ap.add_argument("input", type=Path, help="입력 .fbx / .glb / .gltf / .obj / .blend")
    ap.add_argument("output", type=Path, help="출력 .blend (새 파일로만 쓴다)")
    ap.add_argument("--height", type=float, default=DEFAULT_HEIGHT,
                    help=f"목표 키(m). 기본 {DEFAULT_HEIGHT}")
    ap.add_argument("--kind", default="human",
                    choices=("human", "animal", "drone", "prop"),
                    help="형태. prop 은 키 정규화를 건너뛰고 원점만 맞춘다")
    ap.add_argument("--triangles", type=int, default=DEFAULT_TRIANGLES,
                    help=f"삼각형 예산. 권장 사다리 {TRIANGLE_LADDER}. "
                         f"기본 {DEFAULT_TRIANGLES}. 0 이면 줄이지 않는다")
    ap.add_argument("--rigged", action="store_true",
                    help="이미 리깅된 파일을 고친다(위험 — 리깅 전 실행이 원칙)")
    ap.add_argument("--no-join", action="store_true",
                    help="메시를 합치지 않는다(무기 등 분리 유지가 필요할 때)")
    ap.add_argument("--no-center", action="store_true",
                    help="좌우·앞뒤 중심을 원점에 맞추지 않는다")
    ap.add_argument("--dry-run", action="store_true",
                    help="측정만 하고 저장하지 않는다")
    return ap.parse_args(argv)


def clear_scene() -> None:
    """빈 씬에서 시작한다 — 임포트 결과만 남기기 위해서다."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_any(path: Path) -> None:
    """확장자에 맞는 임포터를 고른다.

    임포터는 저마다 축 변환을 **오브젝트 회전으로** 싣는다(FBX 는 rot X +90°).
    그 회전은 뒤에서 데이터에 구워 없앤다.
    """
    ext = path.suffix.lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif ext == ".blend":
        # .blend 는 임포트가 아니라 연다. 단 저장은 출력 경로로만 한다.
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        raise SystemExit(f"[FAIL] 지원하지 않는 확장자: {ext}")


def scene_meshes() -> list:
    return [o for o in bpy.data.objects if o.type == "MESH"]


def scene_armatures() -> list:
    return [o for o in bpy.data.objects if o.type == "ARMATURE"]


def ensure_object_mode() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def select_only(objs: list) -> None:
    """선택을 objs 로 바꾼다.

    🛑 `hide_set(False)` 를 먼저 부른다 — **숨겨진 오브젝트는 `select_set(True)`
    가 조용히 무시된다.** 실측(2026-09-02 male.blend): 아마추어가 숨겨져 있어
    `transform_apply` 가 `{'FINISHED'}` 를 반환하고도 **아마추어에는 적용되지
    않아** scale 0.01 · rot 90° 가 그대로 남았다. 오류도 경고도 없었다.

    같은 함정이 ARP `go_detect` 의 `poll() failed` 에서도 나온다(SKILL.md ④-A 4번).
    """
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        if o.hide_get():
            o.hide_set(False)
        o.hide_viewport = False
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def world_bbox(objs: list) -> tuple[Vector, Vector]:
    """오브젝트들의 월드 bbox — **원본 메시 데이터** 기준.

    🛑 `evaluated_get()`(모디파이어 적용) 으로 재면 안 된다. armature modifier 가
    끼어 있으면 리그 상태에 따라 값이 흔들려, 스케일을 맞춘 직후에 재도 목표와
    다른 값이 나온다(실측: 1.8 로 맞췄는데 10.03 으로 측정됨 → 보정이 폭주).

    정규화가 다루는 것은 **데이터 공간(rest)** 이지 평가된 포즈가 아니다.
    Decimate 는 apply 하므로 원본에 이미 반영돼 있다.
    """
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in objs:
        if o.type != "MESH":
            continue
        mw = o.matrix_world
        for corner in o.bound_box:
            w = mw @ Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return lo, hi


def detach_actions(objs: list) -> list:
    """액션을 임시로 뗀다.

    🛑 `transform_apply` 는 **애니메이션 데이터가 붙은 오브젝트를 거부**한다
    ("Objects have animation data"). 실측에서 그 결과 아마추어에 scale 0.01 ·
    rot 90° 가 그대로 남았는데 로그에는 성공으로 찍혔다.

    반대로 `data.transform()` 으로 직접 굽는 것도 안 된다 — 본의 **rest** 만
    바뀌고 **pose** 는 그대로라 armature modifier 가 그 차이만큼 폭발한다
    (실측: 키 1.0 → 89.3, 약 100배).

    그래서 액션을 떼고 포즈를 초기화한 뒤 연산자에 맡긴다. Blender 가 rest 와
    pose 를 일관되게 처리해 준다. 액션은 뒤에서 되돌린다.
    """
    saved = []
    for o in objs:
        ad = o.animation_data
        if not ad or not ad.action:
            continue
        slot = getattr(ad, "action_slot", None)
        saved.append((o, ad.action, slot))
        ad.action = None
    # 액션을 떼도 포즈는 마지막 평가 상태로 남는다. rest 로 되돌려야 한다.
    for o in objs:
        if o.type != "ARMATURE":
            continue
        for pb in o.pose.bones:
            pb.matrix_basis = IDENTITY
    bpy.context.view_layer.update()
    return saved


def reattach_actions(saved: list) -> None:
    """뗐던 액션을 되돌린다. slot 을 안 잡으면 조용히 평가되지 않는다."""
    for o, act, slot in saved:
        if not o.animation_data:
            o.animation_data_create()
        o.animation_data.action = act
        if slot is not None:
            try:
                o.animation_data.action_slot = slot
            except (AttributeError, TypeError):
                pass


def unparent_keep_transform(objs: list) -> list:
    """부모 관계를 위치를 유지한 채 일시 해제한다.

    🛑 부모와 자식을 **둘 다** 선택한 채 `transform.resize` + `transform_apply`
    를 부르면 부모의 변환이 자식 데이터에 **두 번** 들어간다(실측: 키 1.8 을
    노렸는데 10.03 이 나왔다). 루트에만 변환을 걸어도 apply 단계에서 같은 일이
    벌어진다.

    그래서 부모를 끊어 모든 오브젝트를 독립적으로 만든 뒤 변환한다. 스키닝은
    부모 관계가 아니라 **armature modifier + 정점 그룹**이 담당하므로 끊어도
    깨지지 않는다. 마지막에 되돌린다.
    """
    children = [o for o in objs if o.parent is not None]
    if not children:
        return []
    saved = [(o, o.parent) for o in children]
    select_only(children)
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    return saved


def reparent(saved: list) -> None:
    """끊었던 부모 관계를 되돌린다(위치 유지)."""
    for child, parent in saved:
        select_only([child])
        parent.hide_set(False)
        parent.select_set(True)
        bpy.context.view_layer.objects.active = parent
        bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)


def apply_transforms(objs: list) -> None:
    """loc/rot/scale 을 정점·본에 구워 넣는다.

    이것이 "glTF 루트에 scale 이 실려 Godot 이 한 번 더 곱하는" 사고를 막는
    유일한 조치다. 부모·자식이 함께 선택돼 있어야 공간이 어긋나지 않는다.
    """
    ensure_object_mode()
    select_only(objs)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.view_layer.update()


def scale_action_locations(factor: float) -> int:
    """액션의 location F-curve 를 같은 배율로 스케일한다.

    본 길이를 스케일하면 이동 키도 같이 줄여야 발이 미끄러지지 않는다.
    Blender 4.4+ 의 slotted action 구조(layers→strips→channelbags)를 탄다.
    """
    touched = 0
    for act in bpy.data.actions:
        curves = []
        try:
            for layer in act.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        curves.extend(bag.fcurves)
        except AttributeError:
            curves = list(getattr(act, "fcurves", []))
        for fc in curves:
            if not fc.data_path.endswith("location"):
                continue
            for kp in fc.keyframe_points:
                kp.co[1] *= factor
                kp.handle_left[1] *= factor
                kp.handle_right[1] *= factor
            touched += 1
    return touched


def join_meshes(meshes: list) -> list:
    """메시를 하나로 합친다 — 머티리얼 슬롯 1개가 드로우콜 예산의 전제다."""
    ensure_object_mode()
    select_only(meshes)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    return scene_meshes()


def count_triangles(meshes: list) -> int:
    """원본 메시의 삼각형 수. n-gon 은 (정점수−2)로 센다.

    world_bbox 와 같은 이유로 평가된 메시를 쓰지 않는다 — armature modifier 는
    삼각형 수를 바꾸지 않으므로 원본으로 세도 결과가 같고, 리그 상태에
    영향받지 않아 안정적이다.
    """
    return sum(
        sum(max(len(p.vertices) - 2, 0) for p in o.data.polygons)
        for o in meshes
    )


def decimate_to(meshes: list, budget: int) -> tuple[int, int]:
    """삼각형 예산까지 Decimate(COLLAPSE)로 줄인다.

    🛑 리깅 **전에** 줄인다. 리깅 후에 줄이면 정점 그룹 웨이트가 재분배되며
    관절이 뭉개진다. Tripo 는 100만 삼각형을 주므로 이 단계가 사실상 필수다.
    """
    before = count_triangles(meshes)
    if budget <= 0 or before <= budget:
        return before, before
    ensure_object_mode()
    for o in meshes:
        tris = count_triangles([o])
        if tris <= 0:
            continue
        # 오브젝트별 비례 배분 — 큰 메시를 더 많이 깎는다.
        share = max(int(budget * tris / before), 8)
        ratio = min(max(share / tris, 0.0005), 1.0)
        mod = o.modifiers.new(name="GodotDecimate", type="DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        # 🛑 스택 맨 앞으로 옮긴다. ARMATURE 뒤에 두고 적용하면 Blender 가
        # "Applied modifier was not first, result may not be as expected" 를
        # 내고 변형된 상태로 구워질 수 있다(--rigged 에서 실측).
        if len(o.modifiers) > 1:
            o.modifiers.move(len(o.modifiers) - 1, 0)
        select_only([o])
        bpy.ops.object.modifier_apply(modifier=mod.name)
    after = count_triangles(meshes)
    return before, after


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parse_args(argv)

    if not args.input.exists():
        log(f"[FAIL] 입력이 없다: {args.input}")
        return 1
    if args.input.resolve() == args.output.resolve():
        log("[FAIL] 입력과 출력이 같다 — 원본을 덮어쓰지 않는다")
        return 1
    if args.triangles and args.triangles not in TRIANGLE_LADDER:
        log(f"[WARN] --triangles {args.triangles} 는 권장 사다리 {TRIANGLE_LADDER} 밖이다")

    report: dict = {"input": str(args.input), "output": str(args.output),
                    "kind": args.kind, "target_height": args.height,
                    "target_triangles": args.triangles}

    if args.input.suffix.lower() != ".blend":
        clear_scene()
    import_any(args.input)
    ensure_object_mode()

    meshes = scene_meshes()
    arms = scene_armatures()
    if not meshes:
        log("[FAIL] 메시가 하나도 없다")
        return 1
    log(f"임포트: 메시 {len(meshes)}개 · 아마추어 {len(arms)}개")

    if arms and not args.rigged:
        log("[FAIL] 아마추어가 있다 — 이 파일은 이미 리깅됐다.")
        log("       정규화는 리깅 **전에** 하는 것이 원칙이다(본 길이·액션 키가 어긋난다).")
        log("       그래도 진행하려면 --rigged 를 준다.")
        return 1

    # ── 측정: 정규화 전 ────────────────────────────────────────────────────
    lo0, hi0 = world_bbox(meshes)
    h0 = hi0.z - lo0.z
    tris0 = count_triangles(meshes)
    report["before"] = {"bbox_min": [round(v, 5) for v in lo0],
                        "bbox_max": [round(v, 5) for v in hi0],
                        "height": round(h0, 5), "triangles": tris0}
    log(f"정규화 전: 키 {h0:.4f} · bbox z {lo0.z:+.4f} ~ {hi0.z:+.4f} · 삼각형 {tris0:,}")
    for o in meshes + arms:
        log(f"  {o.type:8} {o.name!r} loc={tuple(round(v, 4) for v in o.location)} "
            f"rot={tuple(round(math.degrees(v), 2) for v in o.rotation_euler)} "
            f"scale={tuple(round(v, 5) for v in o.scale)}")

    if h0 < EPS:
        log("[FAIL] 높이가 0 이다 — 메시가 비었거나 평면이다")
        return 1

    if args.dry_run:
        log("--dry-run — 여기서 멈춘다")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    # 아마추어의 오브젝트 스케일이 곧 리그의 단위계 배율이다(Mixamo cm → m 이면 0.01).
    # 액션의 location 키는 이 배율만큼 함께 줄여야 발이 미끄러지지 않는다.
    rig_scale = arms[0].scale.x if arms else 1.0

    # ── 1. 축·스케일을 정점·본에 굽는다 ───────────────────────────────────
    # 임포터가 실어 둔 rot X +90°(Y-up→Z-up)와 scale 을 여기서 없앤다.
    saved_actions = detach_actions(meshes + arms)
    if saved_actions:
        log(f"액션 {len(saved_actions)}개를 임시로 뗐다 — transform_apply 가 거부하지 않도록")
    apply_transforms(meshes + arms)
    log("Apply All Transforms — 임포터가 실은 축 변환·스케일이 정점·본에 구워졌다")

    # ── 2. 삼각형 줄이기 (리깅 전에 한다) ─────────────────────────────────
    if args.triangles:
        t_before, t_after = decimate_to(meshes, args.triangles)
        if t_before != t_after:
            log(f"Decimate: 삼각형 {t_before:,} → {t_after:,} (예산 {args.triangles:,})")
        else:
            log(f"삼각형 {t_after:,} — 이미 예산 {args.triangles:,} 안이다")
        report["triangles_after_decimate"] = t_after

    # ── 3. 메시 합치기 ────────────────────────────────────────────────────
    if not args.no_join and len(meshes) > 1:
        meshes = join_meshes(meshes)
        log(f"메시 합침 → {len(meshes)}개")

    # ── 4. 키 맞추기 + 원점을 발바닥으로 ──────────────────────────────────
    lo, hi = world_bbox(meshes)
    h = hi.z - lo.z
    factor = 1.0 if args.kind == "prop" else args.height / h
    targets = meshes + arms

    # 🛑 부모를 끊어 이중 적용을 막는다(unparent_keep_transform 주석 참조).
    parenting = unparent_keep_transform(targets)
    if parenting:
        log(f"부모 관계 {len(parenting)}건을 일시 해제 — 변환 이중 적용 방지")

    if abs(factor - 1.0) > 1e-4:
        ensure_object_mode()
        select_only(targets)
        bpy.ops.transform.resize(value=(factor, factor, factor))
        apply_transforms(targets)
        log(f"키 {h:.4f} → {args.height:.4f} ({factor:.6f} 배)")

    # 스케일이 끝난 뒤 다시 재서 이동량을 잡는다 — 순서를 섞으면 어긋난다.
    lo, hi = world_bbox(meshes)
    shift = Vector((0.0, 0.0, -lo.z))
    if not args.no_center:
        shift.x = -(lo.x + hi.x) / 2.0
        shift.y = -(lo.y + hi.y) / 2.0
    if shift.length > 1e-5:
        ensure_object_mode()
        select_only(targets)
        bpy.ops.transform.translate(value=tuple(shift))
        apply_transforms(targets)
        log(f"원점을 발바닥으로 — {tuple(round(v, 5) for v in shift)} 이동")
    else:
        log("원점이 이미 발바닥에 있다")

    if parenting:
        reparent(parenting)
        log("부모 관계 복원")

    # 액션을 되돌리고 location 키를 총 배율로 맞춘다.
    # 총 배율 = 임포터 스케일 제거(rig_scale) × 키 맞추기(factor)
    if saved_actions:
        reattach_actions(saved_actions)
        total = rig_scale * factor
        if abs(total - 1.0) > 1e-9:
            n = scale_action_locations(total)
            log(f"액션 복원 · location 키 {n}개를 {total:.6f} 배 "
                f"(리그단위 {rig_scale:g} × 키맞춤 {factor:.6f})로 스케일")
        else:
            log("액션 복원 — 배율 1.0 이라 키 조정 없음")

    # ── 5. 검증 ───────────────────────────────────────────────────────────
    lo, hi = world_bbox(meshes)
    h = hi.z - lo.z
    tris = count_triangles(meshes)
    report["after"] = {"bbox_min": [round(v, 5) for v in lo],
                       "bbox_max": [round(v, 5) for v in hi],
                       "height": round(h, 5), "scale_factor": round(factor, 6),
                       "triangles": tris}
    log(f"정규화 후: 키 {h:.4f} · bbox z {lo.z:+.5f} ~ {hi.z:+.5f} · 삼각형 {tris:,}")

    problems = []
    if abs(lo.z) > 1e-3:
        problems.append(f"발바닥이 원점에서 {lo.z:+.5f} 벗어났다")
    if args.kind != "prop" and abs(h - args.height) > 1e-3:
        problems.append(f"키가 {h:.5f} 로 목표 {args.height} 와 다르다")
    if args.triangles and tris > args.triangles * 1.05:
        problems.append(f"삼각형 {tris:,} 이 예산 {args.triangles:,} 를 넘는다")
    for o in bpy.data.objects:
        if o.type not in ("MESH", "ARMATURE"):
            continue
        if any(abs(v - 1.0) > 1e-4 for v in o.scale):
            problems.append(f"{o.name!r} 에 scale {tuple(round(v, 5) for v in o.scale)} 이 남았다")
        if any(abs(v) > 1e-4 for v in o.rotation_euler):
            problems.append(f"{o.name!r} 에 rot "
                            f"{tuple(round(math.degrees(v), 2) for v in o.rotation_euler)} 이 남았다")

    report["problems"] = problems

    # ── 6. 저장 ───────────────────────────────────────────────────────────
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    log(f"저장: {args.output}")

    log_path = args.output.with_suffix(args.output.suffix + ".log.json")
    log_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if problems:
        for p in problems:
            log(f"[FAIL] {p}")
        return 1
    log("[OK] Godot 규약 정규화 완료 — Z-up · 발바닥 원점 · scale 1 · rot 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
