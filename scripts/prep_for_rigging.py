"""Tripo 원본 FBX 를 ARP 리깅 직전 상태로 다듬어 `.blend` 로 저장한다.

## 왜 나누는가

ARP 의 Smart(마커 배치·`go_detect`)는 **3D 뷰 컨텍스트를 요구**해서 `--background`
로 돌릴 수 없다(SKILL.md ④-A 5번). 반대로 임포트·스케일·Decimate 는 GUI 가 전혀
필요 없다. 그래서 **GUI 없이 되는 일을 먼저 끝내** GUI 단계를 짧게 만든다.

## 여기서 보장하는 것 — ARP 가 어긋나는 원인 제거

| 항목 | 값 | 왜 |
|---|---|---|
| 스케일 | **1.0 (apply 됨)** | 스케일이 1 이 아니면 ARP 마커가 통째로 어긋난다 |
| 키 | **1.75m** | `astona.blend` 실측값. 사람 크기여야 ARP 의 비율 추정이 맞는다. GLB 로 구울 때 0.98 로 줄인다(`blend_to_glb.py`) |
| 발 | 원점(min.z = 0) | |
| 정면 | **−Y** | Blender·ARP 규약 |
| 페이스 | ~30,000 | Tripo HD 는 200만 페이스라 뷰포트 조작이 불가능하다. COLLAPSE 는 웨이트를 보존하지만 **아직 스킨이 없으므로** 여기서 줄이는 것이 가장 싸다 |
| 메시 | **1개로 합침** | 여러 개면 ARP 가 어느 것을 몸으로 볼지 헷갈린다 |

⚠️ **회전은 자동으로 정하지 않는다.** Tripo 의 `Blender` 프리셋 FBX 는 이미 Z-up 이고
정면이 −Y 다. 다르면 `--rot-z <도>` 로 돌린다 — 잘못 맞추면 리깅이 통째로 틀어지므로
**출력의 `[정면]` 진단을 반드시 눈으로 확인한다.**

사용법:
  blender --background --python prep_for_rigging.py -- <입력.fbx> <출력.blend> [목표페이스] [목표키] [--rot-z 도]
"""
import bpy
import math
import os
import sys


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def join_meshes(meshes):
    if len(meshes) <= 1:
        return meshes[0] if meshes else None
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    print(f"[메시] {len(meshes)}개 → 1개로 합침")
    return bpy.context.view_layer.objects.active


def world_bounds(obj):
    mw = obj.matrix_world
    pts = [mw @ v.co for v in obj.data.vertices]
    return (
        min(p.x for p in pts), max(p.x for p in pts),
        min(p.y for p in pts), max(p.y for p in pts),
        min(p.z for p in pts), max(p.z for p in pts),
    )


def apply_all(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def decimate(obj, target_faces):
    total = len(obj.data.polygons)
    print(f"[폴리곤] 원본 {total:,} 페이스")
    if total <= target_faces:
        print("[폴리곤] 목표 이하라 감소를 건너뛴다")
        return
    mod = obj.modifiers.new(name="decimate", type="DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = target_faces / total
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"[폴리곤] 감소 후 {len(obj.data.polygons):,} 페이스")


def leg_gap(obj):
    """양발 안쪽 간격 — 다리를 모았는지 판정하는 핵심 지표."""
    _, _, _, _, zlo, zhi = world_bounds(obj)
    h = zhi - zlo
    mw = obj.matrix_world
    low = [mw @ v.co for v in obj.data.vertices if (mw @ v.co).z < zlo + h * 0.08]
    left = [p.x for p in low if p.x > 0]
    right = [p.x for p in low if p.x < 0]
    if not left or not right:
        return None, h
    return min(left) - max(right), h


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src, out_blend = argv[0], argv[1]
    target_faces = int(argv[2]) if len(argv) > 2 and not argv[2].startswith("--") else 30000
    target_height = float(argv[3]) if len(argv) > 3 and not argv[3].startswith("--") else 1.75
    rot_z = 0.0
    if "--rot-z" in argv:
        rot_z = float(argv[argv.index("--rot-z") + 1])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = import_fbx(src)
    meshes = [o for o in objs if o.type == "MESH"]
    if not meshes:
        raise SystemExit("메시가 없다")
    # Tripo 원본은 리깅 전이라 아마추어가 없어야 한다. 있으면 지운다.
    for o in objs:
        if o.type == "ARMATURE":
            print(f"[정리] 아마추어 {o.name} 제거(리깅 전 상태로 만든다)")
            bpy.data.objects.remove(o, do_unlink=True)

    obj = join_meshes([o for o in meshes if o.name in bpy.data.objects])

    if rot_z:
        obj.rotation_euler[2] += math.radians(rot_z)
        print(f"[회전] Z {rot_z:+.1f}°")

    apply_all(obj)
    decimate(obj, target_faces)

    # 키 정규화 → 발을 원점으로
    x0, x1, y0, y1, z0, z1 = world_bounds(obj)
    h = z1 - z0
    k = target_height / h if h > 1e-6 else 1.0
    obj.scale = (k, k, k)
    apply_all(obj)
    x0, x1, y0, y1, z0, z1 = world_bounds(obj)
    obj.location.z -= z0
    apply_all(obj)
    x0, x1, y0, y1, z0, z1 = world_bounds(obj)
    print(f"[스케일] 키 {h:.3f} → {z1 - z0:.3f} (배율 {k:.4f})")
    print(f"[바운즈] x[{x0:+.3f},{x1:+.3f}] y[{y0:+.3f},{y1:+.3f}] z[{z0:+.3f},{z1:+.3f}]")

    # 정면 진단 — 사람은 앞뒤로 얇고 좌우로 넓다. 얼굴은 −Y 를 봐야 한다.
    depth, width = y1 - y0, x1 - x0
    print(f"[정면] 좌우 폭 {width:.3f} · 앞뒤 두께 {depth:.3f} "
          f"→ {'OK(좌우가 넓다)' if width > depth else '🛑 앞뒤가 더 넓다 — --rot-z 90 이 필요할 수 있다'}")

    gap, height = leg_gap(obj)
    if gap is not None:
        rel = gap / height
        verdict = ("OK — 모아져 있다" if rel < 0.03
                   else "경계 — 눈으로 확인" if rel < 0.06
                   else "🛑 벌어졌다 — 재생성 권장(리깅 후에는 못 고친다)")
        print(f"[다리] 양발 안쪽 간격 {gap:.4f}m (키의 {rel * 100:.1f}%) → {verdict}")

    os.makedirs(os.path.dirname(os.path.abspath(out_blend)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"##### 완료 — {out_blend}")


main()
