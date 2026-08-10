"""리깅 전 메시를 실측해 ARP Smart 마커 좌표를 제안한다.

## 왜 이 스크립트가 있나

SKILL.md ④-B 의 마커 좌표표는 **다리를 벌린 옛 모델에서 잰 값**이라 그대로 베끼면
다리 본이 몸 밖으로 나간다. 문서도 "매번 메시에서 다시 잰다" 고 못박는다. 그 재는
일을 눈대중이 아니라 수치로 한다.

## 무엇을 어떻게 재는가

| 마커 | 측정 방법 |
|---|---|
| `neck` | 팔 상단과 머리(헬멧) 하단 사이 |
| `chin` | 머리 구간의 앞면(−Y) 보다 살짝 안쪽 |
| `shoulder` | 몸통 폭의 안쪽, 팔 중심 높이 |
| `hand` | 팔 구간에서 단면 두께(dz)가 급히 얇아지는 x — 손목 |
| `root` | 가랑이(다리가 갈라지는 높이) 바로 위 |
| `foot` | 발 구간 x 범위의 중앙 |

⚠️ **제안값이지 정답이 아니다.** 헬멧·백팩·어깨 장갑이 크면 어긋난다. 반드시
`--dump` 출력(높이별 폭 프로파일)을 함께 보고, 리깅 후 마커를 눈으로 확인한다.

사용법:
  blender --background --python measure_markers.py -- <모델.fbx> [--dump]
"""
import bpy
import sys
from collections import defaultdict


def import_any(path):
    before = set(bpy.data.objects)
    low = path.lower()
    if low.endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    elif low.endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    elif low.endswith(".blend"):
        # 🛑 `prep_for_rigging.py` 의 산출물을 그대로 잰다. 원본 FBX 를 재면
        # **키 정규화 전 좌표**가 나오는데(실측: 0.978 → 1.750, 배율 1.79),
        # ARP 마커는 prep 된 리깅 대상 위에 놓이므로 그 좌표여야 맞는다.
        bpy.ops.wm.open_mainfile(filepath=path)
        return list(bpy.data.objects)
    else:
        raise SystemExit(f"지원하지 않는 형식: {path}")
    return [o for o in bpy.data.objects if o not in before]


def world_verts(meshes):
    pts = []
    for m in meshes:
        mw = m.matrix_world
        for v in m.data.vertices:
            pts.append(mw @ v.co)
    return pts


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    path = argv[0]
    dump = "--dump" in argv

    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = import_any(path)
    meshes = [o for o in objs if o.type == "MESH"]
    pts = world_verts(meshes)
    if not pts:
        raise SystemExit("메시 정점이 없다")

    zmin = min(p.z for p in pts)
    zmax = max(p.z for p in pts)
    height = zmax - zmin
    print(f"[키] {height:.4f}  (z {zmin:+.4f} .. {zmax:+.4f})")
    print(f"[정점] {len(pts):,}")

    # 높이를 60구간으로 나눠 각 구간의 |x| 최대·y 범위를 본다.
    BINS = 60
    bins = defaultdict(list)
    for p in pts:
        i = min(BINS - 1, int((p.z - zmin) / height * BINS))
        bins[i].append(p)

    prof = []
    for i in range(BINS):
        bp = bins.get(i, [])
        if not bp:
            prof.append(None)
            continue
        z0 = zmin + (i + 0.5) * height / BINS
        prof.append({
            "z": z0,
            "xmax": max(abs(p.x) for p in bp),
            "ymin": min(p.y for p in bp),
            "ymax": max(p.y for p in bp),
            "n": len(bp),
        })

    if dump:
        print("\n[높이별 프로파일]  z / |x|max / y범위 / 정점수")
        for i, e in enumerate(prof):
            if e:
                print(f"  {i:2d} z={e['z']:+.3f}  |x|max={e['xmax']:.3f}  "
                      f"y=[{e['ymin']:+.3f},{e['ymax']:+.3f}]  n={e['n']}")

    filled = [e for e in prof if e]
    # 팔 구간 = |x|max 가 전체 최대의 60% 를 넘는 높이대
    xtop = max(e["xmax"] for e in filled)
    arm_bins = [e for e in filled if e["xmax"] > xtop * 0.6]
    arm_z = sum(e["z"] for e in arm_bins) / len(arm_bins)
    arm_top = max(e["z"] for e in arm_bins)

    # 머리 = 팔 구간 위쪽에서 폭이 다시 좁아지는 곳
    head_bins = [e for e in filled if e["z"] > arm_top]
    head_bottom = min((e["z"] for e in head_bins), default=arm_top)
    head_front = min((e["ymin"] for e in head_bins), default=0.0)

    # 몸통 폭 = 팔 높이대에서 x 가 작은 정점들의 폭(어깨 안쪽 추정)
    torso_pts = [p for p in pts if abs(p.z - arm_z) < height * 0.03]
    torso_half = 0.0
    if torso_pts:
        xs = sorted(abs(p.x) for p in torso_pts)
        torso_half = xs[int(len(xs) * 0.75)]

    # 손목 = 팔 구간에서 x 를 따라가며 단면 두께(dz)가 가장 잘록한 곳
    arm_pts = [p for p in pts if abs(p.z - arm_z) < height * 0.06 and p.x > torso_half]
    wrist_x = None
    if arm_pts:
        xhi = max(p.x for p in arm_pts)
        steps, best = 24, None
        for s in range(steps // 2, steps):
            x0 = torso_half + (xhi - torso_half) * s / steps
            x1 = torso_half + (xhi - torso_half) * (s + 1) / steps
            seg = [p for p in arm_pts if x0 <= p.x < x1]
            if len(seg) < 8:
                continue
            dz = max(p.z for p in seg) - min(p.z for p in seg)
            if best is None or dz < best[0]:
                best = (dz, (x0 + x1) / 2)
        if best:
            wrist_x = best[1]

    # 가랑이 = 아래쪽에서 x≈0 부근에 정점이 사라지는 높이
    crotch_z = zmin + height * 0.5
    for e in filled:
        if e["z"] < zmin + height * 0.65:
            near = [p for p in pts if abs(p.z - e["z"]) < height / BINS
                    and abs(p.x) < height * 0.02]
            if not near:
                crotch_z = e["z"]

    # 발 = 아래 8% 구간의 x 범위
    foot_pts = [p for p in pts if p.z < zmin + height * 0.08 and p.x > 0]
    foot_x = 0.0
    foot_y = 0.0
    if foot_pts:
        foot_x = (min(p.x for p in foot_pts) + max(p.x for p in foot_pts)) / 2
        foot_y = (min(p.y for p in foot_pts) + max(p.y for p in foot_pts)) / 2

    # 양발 간격 — 다리를 모았는지 판정하는 핵심 지표
    inner = [p for p in pts if p.z < zmin + height * 0.08]
    gap = None
    if inner:
        left = [p.x for p in inner if p.x > 0]
        right = [p.x for p in inner if p.x < 0]
        if left and right:
            gap = min(left) - max(right)

    print("\n[제안 마커]  (world 좌표 — arp_markers 로컬과 같다)")
    print(f"  neck     (0, {(-torso_half * 0.3):+.3f}, {(arm_top + head_bottom) / 2:.3f})")
    print(f"  chin     (0, {head_front * 0.9:+.3f}, {head_bottom + (zmax - head_bottom) * 0.35:.3f})")
    print(f"  shoulder ({torso_half * 0.9:.3f}, {(-torso_half * 0.3):+.3f}, {arm_z:.3f})")
    if wrist_x:
        print(f"  hand     ({wrist_x:.3f}, {(-torso_half * 0.2):+.3f}, {arm_z:.3f})")
    print(f"  root     (0, {(-torso_half * 0.35):+.3f}, {crotch_z + height * 0.03:.3f})")
    print(f"  foot     ({foot_x:.3f}, {foot_y:+.3f}, {zmin + height * 0.055:.3f})")

    print("\n[다리 모음 판정]")
    if gap is not None:
        rel = gap / height
        verdict = "OK — 모아져 있다" if rel < 0.03 else (
            "경계 — 눈으로 확인" if rel < 0.06 else "🛑 벌어졌다 — 재생성 권장")
        print(f"  양발 안쪽 간격 {gap:.4f}m (키의 {rel * 100:.1f}%) → {verdict}")
    else:
        print("  판정 불가(한쪽 발만 잡힘)")


main()
