"""ARP 자동 감지가 빗나간 **reference bones** 를 실측값으로 고쳐 다시 리깅한다.

## 왜 필요한가 (실측 2026-08-01)

ARP Smart 의 `go_detect` 는 마커를 힌트로 쓸 뿐 **자체 알고리즘으로 본을 배치**한다.
그래서 마커를 정확히 놓아도 결과가 어긋날 수 있다 — 실측 사례:

| | 자동 감지 | 메시 실측 | 증상 |
|---|---|---|---|
| `foot_ref.l` x | **0.240** | 발은 x 0.013~0.110 | 다리 본이 **몸 밖**으로 나가 웨이트가 무너진다 |
| 팔 z | 어깨 1.335 → 손목 **1.172** | 팔은 z≈1.385 수평 | T-포즈인데 **팔이 아래로 기운** 리그가 된다 |

reference bones 는 `match_to_rig` 의 입력이므로, **여기를 고치고 다시 match 하면**
리그 전체가 따라온다. 마커를 다시 놓는 것보다 정확하고 재현 가능하다.

## 🛑 두 가지 함정 — 둘 다 실제로 겪었다

1. **`use_mirror_x` 를 끄지 않으면 수정이 덮인다.** `.l` 을 고치는 순간 ARP 가 `.r` 을
   자동 미러하고, 이어서 `.r` 을 고치면 그 미러된 값을 기준으로 또 변환해 **양쪽이 다
   틀어진다**(실측: 손목이 목표 z=1.385 대신 1.191 로 남았고 발은 아예 안 움직였다).
2. **좌표를 읽으면서 쓰면 안 된다.** 체인의 뒷 본을 옮길 때 앞 본은 이미 새 값이다.
   **먼저 전부 스냅샷**해 두고 그 값으로 변환한다.

## 어떻게 고치는가 — 체인 전체에 하나의 아핀 변환

관절을 하나씩 옮기면 손가락 20여 개를 일일이 맞춰야 한다. 대신 **피벗(어깨/허벅지)을
고정하고 끝점(손목/발목)을 목표로 보내는 회전+균일스케일**을 체인 전체에 적용한다 —
손가락·발가락이 상대 위치를 유지한 채 따라온다.

    v ↦ P' + s · R · (v − P)      R: (W−P) → (W'−P') 최소 회전,  s = |W'−P'| / |W−P|

사용법:
  blender --background --python fix_arp_refs.py -- <리그.blend> <출력.blend> \\
      --arm-pivot 0.150,0,1.385 --arm-end 0.666,0,1.385 --leg-end 0.062,0.010,0.085

좌표는 **왼쪽(+x) 기준**이며 오른쪽은 x 부호를 뒤집어 자동 적용한다.
"""
import bpy
import os
import sys
from mathutils import Vector

ARM_CHAIN = ['arm_ref', 'forearm_ref', 'hand_ref',
             'thumb1_ref', 'thumb2_ref', 'thumb3_ref',
             'index1_base_ref', 'index1_ref', 'index2_ref', 'index3_ref',
             'middle1_base_ref', 'middle1_ref', 'middle2_ref', 'middle3_ref',
             'ring1_base_ref', 'ring1_ref', 'ring2_ref', 'ring3_ref',
             'pinky1_base_ref', 'pinky1_ref', 'pinky2_ref', 'pinky3_ref']
LEG_CHAIN = ['thigh_ref', 'leg_ref', 'foot_ref', 'toes_ref',
             'foot_heel_ref', 'foot_bank_01_ref', 'foot_bank_02_ref']


def vec_arg(argv, flag, default):
    if flag not in argv:
        return default
    return Vector([float(x) for x in argv[argv.index(flag) + 1].split(',')])


def chain_transform(eb, snap, chain, side, P, W, Pp, Wp, label, log):
    """피벗 P 를 P' 로, 끝점 W 를 W' 로 보내는 회전+스케일을 체인에 적용."""
    a, b = (W - P), (Wp - Pp)
    if a.length < 1e-6 or b.length < 1e-6:
        log.append(f"[건너뜀] {label}{side}: 길이가 0")
        return
    R = a.normalized().rotation_difference(b.normalized()).to_matrix()
    s = b.length / a.length
    moved = 0
    for base in chain:
        bn = eb.get(base + side)
        if not bn or (base + side) not in snap:
            continue
        h0, t0 = snap[base + side]
        bn.head = Pp + (R @ (h0 - P)) * s
        bn.tail = Pp + (R @ (t0 - P)) * s
        moved += 1
    log.append(f"[{label}{side}] 본 {moved}개 · 스케일 {s:.4f} · "
               f"끝점 ({W.x:+.3f},{W.z:+.3f}) → ({Wp.x:+.3f},{Wp.z:+.3f})")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src, out_blend = argv[0], argv[1]
    arm_pivot = vec_arg(argv, "--arm-pivot", Vector((0.150, 0.0, 1.385)))
    arm_end = vec_arg(argv, "--arm-end", Vector((0.666, 0.0, 1.385)))
    leg_end = vec_arg(argv, "--leg-end", Vector((0.062, 0.010, 0.085)))

    bpy.ops.wm.open_mainfile(filepath=src)
    rig = bpy.data.objects['rig']
    mesh = [o for o in bpy.data.objects
            if o.type == 'MESH' and not o.name.startswith('cs_')][0]

    # 🛑 미러를 끄지 않으면 아래 수정이 반대쪽에 덮여 양쪽 다 틀어진다.
    rig.data.use_mirror_x = False

    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones

    # 🛑 쓰기 전에 전부 읽는다 — 체인 뒷부분이 앞부분의 새 값을 보면 안 된다.
    snap = {b.name: (b.head.copy(), b.tail.copy()) for b in eb}

    log = []
    for side in ('.l', '.r'):
        sgn = 1.0 if side == '.l' else -1.0
        mir = lambda v: Vector((v.x * sgn, v.y, v.z))

        if ('arm_ref' + side) in snap and ('hand_ref' + side) in snap:
            chain_transform(eb, snap, ARM_CHAIN, side,
                            snap['arm_ref' + side][0], snap['hand_ref' + side][0],
                            mir(arm_pivot), mir(arm_end), "팔", log)
            sh = eb.get('shoulder_ref' + side)
            if sh:
                sh.tail = eb['arm_ref' + side].head.copy()

        if ('thigh_ref' + side) in snap and ('foot_ref' + side) in snap:
            LP = snap['thigh_ref' + side][0]
            chain_transform(eb, snap, LEG_CHAIN, side,
                            LP, snap['foot_ref' + side][0],
                            LP, mir(leg_end), "다리", log)

    after = {k: (round(eb[k].head.x, 4), round(eb[k].head.z, 4))
             for k in ('arm_ref.l', 'hand_ref.l', 'foot_ref.l', 'foot_ref.r')
             if k in eb}
    bpy.ops.object.mode_set(mode='OBJECT')

    for line in log:
        print(line)
    print(f"[ref 결과] {after}")

    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.arp.match_to_rig()
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    print("[match_to_rig] 완료")

    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.arp.bind_to_rig()
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    print(f"[bind_to_rig] 완료 · 정점그룹 {len(mesh.vertex_groups)}개")

    for k in ('foot.l', 'foot.r', 'hand.l', 'hand.r', 'arm_stretch.l', 'root.x'):
        b = rig.data.bones.get(k)
        if b:
            h = rig.matrix_world @ b.head_local
            print(f"[본] {k:16s} ({h.x:+.4f}, {h.y:+.4f}, {h.z:+.4f})")

    os.makedirs(os.path.dirname(os.path.abspath(out_blend)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"##### 완료 — {out_blend}")


main()
