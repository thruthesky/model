"""Mixamo 애니메이션을 ARP 로 리깅한 캐릭터의 rest pose 에 맞춰 다시 굽고,
캐릭터 + 액션 5종을 담은 **.blend** 를 만든다. sheet.py 에 그 .blend 를
`--animations built-in` 으로 주면 그대로 렌더된다.

왜 이 단계가 필요한가 (실측 2026-07-30):

1. **sheet.py 는 본 이름이 8개 이상 겹치면 rest pose 보정 없이 액션을 그대로
   할당한다**(_sheet_render.py 의 "직접적용(본 N개 일치)" 경로). Mixamo 로 리깅된
   캐릭터끼리는 rest 가 같아 문제없지만, ARP 로 리깅한 캐릭터는 **본 이름만 Mixamo
   이고 rest pose 가 다르다** — 그대로 붙이면 팔이 만세로 올라간다.

2. **보정은 월드 기준이어야 한다.** _sheet_render.py 의 retarget_action 은
   로컬 기준(tgt_rest @ src_rest⁻¹ @ src_pose)인데, 그 식은 두 리그의 **본 로컬
   축(roll)이 대응할 때만** 맞다. ARP GE Export 는 본 축을 자체 규약으로 정해
   Mixamo 와 어긋나므로, 로컬 기준으로 옮기면 **다리는 맞고 팔만 틀어진다**(실측).
   두 리그 모두 T-포즈 rest 이므로 월드 기준이 정확하다:
       target_obj = (src_pose @ src_rest⁻¹) @ tgt_rest

3. **결과를 FBX 로 내보내면 안 된다.** 리타게팅 직후에는 포즈가 정확한데,
   Blender FBX exporter 로 내보내 다시 임포트하면 rest pose 가 달라져 **다시
   T-포즈로 벌어진다**(실측 — 캐릭터 FBX 는 ARP GE Export 가, 애니 FBX 는 Blender
   기본 exporter 가 만들어 본 축 규약이 갈린다). 그래서 왕복이 없는 .blend 로 낸다.

사용법:
  blender --background --python retarget_to_arp_rig.py -- <캐릭터.fbx> <애니폴더> <출력.blend>
"""
import bpy
import os
import sys
from mathutils import Matrix

ACTIONS = ["idle", "walk", "run", "attack", "death"]


def rotm(M):
    """순수 회전 3x3 (scale 제거)."""
    return M.to_quaternion().to_matrix()


def bone_order(arm):
    """root-first 로 나열 — 부모 회전을 먼저 확정해야 자식 basis 를 구할 수 있다."""
    order = []

    def rec(b):
        order.append(b.name)
        for c in b.children:
            rec(c)

    for b in arm.data.bones:
        if not b.parent:
            rec(b)
    return order


def rel_rest(arm, order):
    """각 본의 부모-상대 rest 회전."""
    rel = {}
    for bn in order:
        bone = arm.data.bones[bn]
        M = (bone.parent.matrix_local.inverted() @ bone.matrix_local) if bone.parent else bone.matrix_local
        rel[bn] = rotm(M)
    return rel


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def retarget(tgt, src_arm, src_act, out_name):
    """src_act 를 tgt 의 rest 기준(월드 상대 회전)으로 다시 구워 새 액션을 돌려준다."""
    common = {b.name for b in tgt.data.bones} & {b.name for b in src_arm.data.bones}
    if len(common) < 8:
        raise SystemExit(f"공통 본이 {len(common)}개뿐 — 리타게팅 불가")

    tgt_rest = {n: rotm(tgt.matrix_world @ tgt.data.bones[n].matrix_local) for n in common}
    src_rest = {n: rotm(src_arm.matrix_world @ src_arm.data.bones[n].matrix_local) for n in common}
    arm_t_inv = rotm(tgt.matrix_world).inverted()

    f0, f1 = int(src_act.frame_range[0]), int(src_act.frame_range[1])
    if not src_arm.animation_data:
        src_arm.animation_data_create()
    src_arm.animation_data.action = src_act

    scn = bpy.context.scene
    src_pose = {}
    src_hips = {}
    hips = "mixamorig:Hips"
    for f in range(f0, f1 + 1):
        scn.frame_set(f)
        src_pose[f] = {n: rotm(src_arm.matrix_world @ src_arm.pose.bones[n].matrix) for n in common}
        if hips in common:
            src_hips[f] = (src_arm.pose.bones[hips].matrix.translation
                           - src_arm.data.bones[hips].head_local)

    order = bone_order(tgt)
    rel = rel_rest(tgt, order)

    act = bpy.data.actions.new(out_name)
    if not tgt.animation_data:
        tgt.animation_data_create()
    tgt.animation_data.action = act
    # Blender 4.4+ 의 slotted action — slot 을 안 잡으면 액션이 평가되지 않는다.
    ad = tgt.animation_data
    if hasattr(ad, "action_suitable_slots"):
        s = ad.action_suitable_slots
        if s and getattr(ad, "action_slot", None) is None:
            ad.action_slot = s[0]
    for pb in tgt.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # Hips 이동은 두 리그의 다리 길이 비로 맞춘다(걷기의 상하 바운스·죽음의 쓰러짐).
    hips_scale = None
    if hips in common:
        def leg_len(a):
            try:
                return (a.data.bones["mixamorig:LeftUpLeg"].head_local
                        - a.data.bones["mixamorig:LeftFoot"].head_local).length
            except KeyError:
                return None
        lt, ls = leg_len(tgt), leg_len(src_arm)
        if lt and ls:
            hips_scale = lt / ls

    for f in range(f0, f1 + 1):
        objr = {}
        for bn in order:
            bone = tgt.data.bones[bn]
            par = objr[bone.parent.name] if bone.parent else Matrix.Identity(3)
            if bn in common:
                # 월드 기준: src 가 자기 rest 에서 월드 공간으로 돈 양을 tgt rest 에 얹는다.
                world_rot = src_pose[f][bn] @ src_rest[bn].inverted()
                target_obj = arm_t_inv @ (world_rot @ tgt_rest[bn])
                basis = (par @ rel[bn]).inverted() @ target_obj
            else:
                basis = Matrix.Identity(3)
            pb = tgt.pose.bones[bn]
            pb.rotation_quaternion = basis.to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=f)
            objr[bn] = par @ rel[bn] @ basis

        if hips_scale:
            tpb = tgt.pose.bones[hips]
            # pose_bone.location 은 *본 rest 로컬 축* 기준이다 — 오브젝트 공간 델타를
            # rest 행렬의 역으로 되돌려야 한다(순서를 바꾸면 엉뚱한 축으로 이동한다).
            rest3 = tgt.data.bones[hips].matrix_local.to_3x3()
            tpb.location = rest3.inverted() @ (src_hips[f] * hips_scale)
            tpb.keyframe_insert("location", frame=f)

    act.use_fake_user = True        # .blend 저장 시 사라지지 않게
    return act, f0, f1


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    char_path, anim_dir, out_blend = argv[0], argv[1], argv[2]
    os.makedirs(os.path.dirname(out_blend) or ".", exist_ok=True)

    # 캐릭터는 FBX(⑤ ARP export) 또는 **.blend**(⑤-L close_legs.py 산출)로 온다.
    # .blend 를 받는 이유 — 다리를 모으는 등 rest pose 를 고친 리그를 FBX 로 다시 내보내면
    # 위 3번 경고대로 rest 가 달라져 교정이 풀릴 수 있다. 왕복 없이 그대로 받는다.
    if os.path.splitext(char_path)[1].lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=char_path)
        char_objs = list(bpy.data.objects)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        char_objs = import_fbx(char_path)
    arms = [o for o in char_objs if o.type == "ARMATURE"]
    if not arms:
        raise SystemExit(f"캐릭터에 아마추어가 없다: {char_path}")
    tgt = max(arms, key=lambda o: len(o.data.bones))

    made = []
    for name in ACTIONS:
        src_path = os.path.join(anim_dir, name + ".fbx")
        if not os.path.exists(src_path):
            print(f"[건너뜀] {name}: 원본 없음 {src_path}")
            continue

        src_objs = import_fbx(src_path)
        src_arm = next(o for o in src_objs if o.type == "ARMATURE")
        src_act = src_arm.animation_data.action if src_arm.animation_data else None
        if src_act is None:
            print(f"[실패] {name}: 액션이 없다")
            for o in src_objs:
                bpy.data.objects.remove(o, do_unlink=True)
            continue

        act, f0, f1 = retarget(tgt, src_arm, src_act, name)
        made.append((name, f1 - f0 + 1))
        print(f"[OK] {name}: {f1 - f0 + 1}프레임 → 액션 '{act.name}'")

        # 애니 원본은 지운다 — 아마추어가 둘이면 sheet.py 가 어느 것을 캐릭터로 볼지 헷갈린다.
        for o in src_objs:
            bpy.data.objects.remove(o, do_unlink=True)
        for a in list(bpy.data.actions):
            if a is not act and a.name not in [m[0] for m in made]:
                a.use_fake_user = False
                if a.users == 0:
                    bpy.data.actions.remove(a)
        reset_pose(tgt)

    # 마지막 액션이 걸린 채로 저장되면 그 포즈가 rest 처럼 보인다 — 떼어 둔다.
    if tgt.animation_data:
        tgt.animation_data.action = None
    reset_pose(tgt)

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"##### 완료 — {out_blend}  액션 {len(made)}종: "
          + ", ".join(f"{n}({c}f)" for n, c in made))


main()
