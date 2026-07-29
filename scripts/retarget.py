"""
Mixamo 애니메이션(FBX)을 Tripo 오토리깅 캐릭터에 리타게팅한다.

두 리그는 본 이름·본 개수·스케일·좌표계가 모두 다르다.
  - Mixamo: 65본, "mixamorig:" 접두사, cm 단위, 원본 Y-up
  - Tripo(v1.0 Humanoid): 41본, "Hip/Waist/L_Upperarm" 식 이름, m 단위, Z-up
따라서 본 이름만 바꿔치기하면 회전축이 어긋나 팔다리가 뒤틀린다.

해결: 각 본의 "월드 공간 회전 델타"를 옮긴다.
    delta = (소스 포즈 월드행렬) x (소스 rest 월드행렬)^-1
    타겟 회전 = delta x (타겟 rest 월드 회전)
이러면 rest 자세(둘 다 T-포즈)를 기준으로 한 상대 회전만 전달되어
본 길이·축 방향이 달라도 동작이 그대로 재현된다.

사용법:
  blender --background --python retarget.py -- <타겟FBX> <애니메이션폴더> <출력폴더> [출력이름]
"""
import bpy
import os
import sys
from mathutils import Matrix

# Mixamo 본 -> Tripo(v1.0 Humanoid) 본.
# 다른 리그를 쓰면 inspect_rig.py 로 본 이름을 확인해 이 표만 고치면 된다.
# Twist 본(*Twist01/02)은 Mixamo 에 대응이 없으므로 매핑하지 않는다.
# 억지로 매핑하면 팔이 뒤틀린다.
BONE_MAP = {
    "mixamorig:Hips": "Hip",
    "mixamorig:Spine": "Waist",
    "mixamorig:Spine1": "Spine01",
    "mixamorig:Spine2": "Spine02",
    "mixamorig:Neck": "NeckTwist01",
    "mixamorig:Head": "Head",
    "mixamorig:LeftShoulder": "L_Clavicle",
    "mixamorig:LeftArm": "L_Upperarm",
    "mixamorig:LeftForeArm": "L_Forearm",
    "mixamorig:LeftHand": "L_Hand",
    "mixamorig:RightShoulder": "R_Clavicle",
    "mixamorig:RightArm": "R_Upperarm",
    "mixamorig:RightForeArm": "R_Forearm",
    "mixamorig:RightHand": "R_Hand",
    "mixamorig:LeftUpLeg": "L_Thigh",
    "mixamorig:LeftLeg": "L_Calf",
    "mixamorig:LeftFoot": "L_Foot",
    "mixamorig:LeftToeBase": "L_ToeBase",
    "mixamorig:RightUpLeg": "R_Thigh",
    "mixamorig:RightLeg": "R_Calf",
    "mixamorig:RightFoot": "R_Foot",
    "mixamorig:RightToeBase": "R_ToeBase",
}
ROOT_SRC = "mixamorig:Hips"     # 유일하게 위치까지 옮기는 본
ROOT_TGT = "Hip"

# 이 순서대로 먼저 처리하고, 목록에 없는 fbx 는 이름순으로 뒤에 붙인다
PREFERRED_ORDER = ["idle", "walk", "run", "attack", "hit", "death"]


def count_fcurves(action):
    """Blender 4.4+ 슬롯 액션과 구버전 액션 모두에서 F-커브 수를 센다."""
    if hasattr(action, "fcurves"):
        return len(action.fcurves)
    total = 0
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                bag = strip.channelbag(slot)
                if bag:
                    total += len(bag.fcurves)
    return total


def assign_action(obj, action):
    """액션 연결. Blender 4.4+ 는 슬롯까지 지정해야 키가 반영된다."""
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = action
    if not hasattr(obj.animation_data, "action_slot"):
        return
    slot = action.slots[0] if len(action.slots) else None
    if slot is None:
        try:
            slot = action.slots.new(id_type="OBJECT", name=obj.name)
        except (TypeError, RuntimeError):
            slot = None
    if slot is not None:
        obj.animation_data.action_slot = slot


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def find_armature(objs):
    return next(o for o in objs if o.type == "ARMATURE")


def world_rest(arm, bone_name):
    return arm.matrix_world @ arm.data.bones[bone_name].matrix_local


def world_pose(arm, bone_name):
    return arm.matrix_world @ arm.pose.bones[bone_name].matrix


def ordered_targets(tgt_arm, pairs):
    """부모가 먼저 처리되도록 계층 깊이순으로 정렬한다.
    자식의 월드 위치는 부모 포즈에 의존하므로 순서가 틀리면 본이 어긋난다."""
    depth = {}
    for _, tname in pairs:
        b = tgt_arm.data.bones[tname]
        d = 0
        p = b.parent
        while p:
            d += 1
            p = p.parent
        depth[tname] = d
    return sorted(pairs, key=lambda p: depth[p[1]])


def retarget(src_arm, tgt_arm, action_name):
    src_action = src_arm.animation_data.action
    f_start, f_end = (int(round(v)) for v in src_action.frame_range)

    pairs = [(s, t) for s, t in BONE_MAP.items()
             if s in src_arm.data.bones and t in tgt_arm.data.bones]
    pairs = ordered_targets(tgt_arm, pairs)

    # 힙 높이 비율로 이동량을 맞춘다 (Mixamo cm ↔ Tripo m 차이 흡수)
    src_hip_z = world_rest(src_arm, ROOT_SRC).to_translation().z
    tgt_hip_z = world_rest(tgt_arm, ROOT_TGT).to_translation().z
    scale = tgt_hip_z / src_hip_z if abs(src_hip_z) > 1e-9 else 1.0

    rest_cache = {t: world_rest(tgt_arm, t) for _, t in pairs}
    src_rest_cache = {s: world_rest(src_arm, s) for s, _ in pairs}

    for _, tname in pairs:
        tgt_arm.pose.bones[tname].rotation_mode = "QUATERNION"

    action = bpy.data.actions.new(action_name)
    assign_action(tgt_arm, action)

    tgt_world_inv = tgt_arm.matrix_world.inverted()

    for frame in range(f_start, f_end + 1):
        bpy.context.scene.frame_set(frame)

        for sname, tname in pairs:
            src_pose_w = world_pose(src_arm, sname)
            delta_q = (src_pose_w @ src_rest_cache[sname].inverted()).to_quaternion()
            target_q = delta_q @ rest_cache[tname].to_quaternion()

            pb = tgt_arm.pose.bones[tname]

            if tname == ROOT_TGT:
                offset = src_pose_w.to_translation() - src_rest_cache[sname].to_translation()
                loc_w = rest_cache[tname].to_translation() + offset * scale
            else:
                # 부모까지 반영된 현재 head 위치를 그대로 써서 본이 끊어지지 않게 한다
                bpy.context.view_layer.update()
                loc_w = (tgt_arm.matrix_world @ pb.matrix).to_translation()

            new_w = Matrix.Translation(loc_w) @ target_q.to_matrix().to_4x4()
            pb.matrix = tgt_world_inv @ new_w
            bpy.context.view_layer.update()

        for _, tname in pairs:
            pb = tgt_arm.pose.bones[tname]
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            if tname == ROOT_TGT:
                pb.keyframe_insert("location", frame=frame)

    action.use_fake_user = True
    return action, f_start, f_end


def collect_animations(anim_dir):
    """폴더의 모든 fbx 를 모으되 PREFERRED_ORDER 를 앞세운다."""
    names = [f[:-4] for f in os.listdir(anim_dir) if f.lower().endswith(".fbx")]
    head = [n for n in PREFERRED_ORDER if n in names]
    tail = sorted(n for n in names if n not in head)
    return head + tail


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    target_fbx, anim_dir, out_dir = argv[0], argv[1], argv[2]
    out_name = argv[3] if len(argv) > 3 else "animated"

    bpy.ops.wm.read_factory_settings(use_empty=True)

    tgt_objs = import_fbx(target_fbx)
    tgt_arm = find_armature(tgt_objs)
    tgt_meshes = [o for o in tgt_objs if o.type == "MESH"]
    print(f"[타겟] 아마추어={tgt_arm.name} 본={len(tgt_arm.data.bones)} 메시={len(tgt_meshes)}")

    missing = [t for t in BONE_MAP.values() if t not in tgt_arm.data.bones]
    if missing:
        print(f"[경고] 타겟에 없는 본 {len(missing)}개: {missing}")
        print("       inspect_rig.py 로 실제 본 이름을 확인하고 BONE_MAP 을 고칠 것")

    results = []
    for name in collect_animations(anim_dir):
        path = os.path.join(anim_dir, f"{name}.fbx")
        src_objs = import_fbx(path)
        src_arm = find_armature(src_objs)

        action, f0, f1 = retarget(src_arm, tgt_arm, name)
        n_curves = count_fcurves(action)
        results.append((name, f0, f1, n_curves))
        print(f"[리타게팅] {name}: 프레임 {f0}~{f1}, F-커브 {n_curves}개")
        if n_curves == 0:
            print(f"[경고] {name} 액션에 키프레임이 기록되지 않았다")

        for o in src_objs:
            bpy.data.objects.remove(o, do_unlink=True)

    # 첫 액션을 활성 상태로 둬서 파일을 열자마자 보이게 한다
    if results:
        first = bpy.data.actions.get(results[0][0])
        if first:
            assign_action(tgt_arm, first)

    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")

    fbx_out = os.path.join(out_dir, f"{out_name}.fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx_out,
        use_selection=True,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,   # 액션마다 AnimStack 을 만든다
        bake_anim_use_nla_strips=False,
        path_mode="COPY",
        embed_textures=True,
        mesh_smooth_type="FACE",
    )
    print(f"[출력] {fbx_out}")

    glb_out = os.path.join(out_dir, f"{out_name}.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb_out,
        export_format="GLB",
        export_animation_mode="ACTIONS",
        export_animations=True,
        use_selection=True,
    )
    print(f"[출력] {glb_out}")

    print("\n=== 요약 ===")
    for name, f0, f1, n in results:
        print(f"  {name}: {f0}-{f1} 프레임, {n} F-커브")


main()
