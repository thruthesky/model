"""다리·무릎·발이 벌어진 캐릭터의 **다리를 모은다** — 재생성하지 않고 Blender 에서 고친다.

Tripo3D 는 프롬프트에 "legs together" 를 넣어도 다리를 A 자로 벌린 채 생성하는 일이 잦다.
예전에는 이럴 때 **재생성**밖에 답이 없었고(크레딧 55~65 재소모 + 4분 대기), 그마저도 다시
벌어져 나오면 무한 반복이었다. 이 스크립트는 **이미 리깅된 리그의 rest pose 를 고쳐**
그 반복을 없앤다.

무엇을 하나 — 좌우 다리마다:

1. **엉덩이(UpLeg.head)를 고정한 채 다리 전체를 안쪽으로 회전**해 발목을 목표 x 로 옮긴다.
   무릎은 다리에 매달려 있으므로 함께 따라 들어온다(= 무릎도 모인다).
2. **발(Foot·ToeBase)은 회전 전 방향을 그대로 복원**한다. 안 하면 다리를 기울인 만큼
   발바닥이 안쪽으로 들려 **까치발**이 된다.
3. 바뀐 포즈를 **rest pose 로 굳힌다**(메시의 Armature modifier 를 먼저 적용해 스킨을
   따라오게 한 뒤 `pose.armature_apply`). rest 를 바꾸는 것이라, 이후 붙는 Mixamo
   애니메이션도 모은 다리 기준으로 재생된다.
4. 회전으로 발이 지면을 뚫거나 뜨면 **전체를 z 이동해 발을 다시 지면(z=0)에 놓는다.**

목표 간격 — `check_leg_gap.py` 와 **같은 잣대**(발 하나 폭 대비 최대 간격 비율)를 쓰고,
그 잣대로 **재면서 회전각을 이분 탐색**한다(기본 목표 30%, PASS 기준은 50%).

🛑 **각도를 계산으로 한 번에 구하려 하지 말 것**(실측으로 두 번 틀렸다). 발 메시는 발목 본
바로 아래에 있지 않고 안쪽·바깥으로 퍼져 있어서, "발목 x 를 발폭×0.5×1.3 으로" 같은 식으로
풀면 목표 30% 자리에 **3%** 가 나온다. 게다가 발 폭 자체가 `(발 높이 스팬)/2` 라 다리를
모으면 **함께 줄어든다** — 처음 잰 발 폭을 고정해 쓰면 포즈 중 30% 가 rest 로 굳힌 뒤 66%
로 보인다. **매번 다시 재는 이분 탐색만이 정확하다.**

**벌리는 방향으로는 절대 움직이지 않는다** — 이미 모인 캐릭터를 건드려 망가뜨리지 않기
위해서다(기본은 PASS 인 모델을 건너뛰고, `--force` 로만 더 모은다).

🛑 **어느 시점에 돌리나 — ⑤(ARP→Mixamo export) 뒤, ⑦(rest pose 보정) 앞.**
⑦ 은 캐릭터의 rest pose 를 기준으로 애니메이션을 다시 굽는다. 다리를 ⑦ **뒤에** 모으면
이미 구워진 액션과 rest 가 어긋나 전신이 뒤틀린다. 반드시 ⑦ 앞에서 돌린다.

🛑 **출력은 `.blend` 다(FBX 아님).** 리그를 FBX 로 다시 내보내면 rest pose 가 달라질
위험이 있고(`retarget_to_arp_rig.py` 머리말의 실측 경고), 그러면 다리를 모은 의미가
없어진다. `retarget_to_arp_rig.py` 는 `.blend` 캐릭터 입력을 받는다.

사용:
  blender --background --python close_legs.py -- <입력.fbx|.blend> [출력.blend] [옵션]

옵션:
  --gap-ratio R    목표 간격(발 하나 폭 대비 비율). 기본 0.30
  --force          이미 모여 있어도(PASS 여도) 목표 간격까지 모은다
  --dry-run        측정만 하고 파일을 쓰지 않는다
  --no-ground-fix  발을 지면에 다시 놓는 z 보정을 끈다

종료 코드: 0 = 모았거나 모을 필요가 없었다 · 1 = 실패(리그·본을 못 찾음 등)
"""
import bpy
import math
import os
import sys
from mathutils import Matrix

# check_leg_gap.py 와 같은 판정 기준(발 하나 폭 대비 최대 간격 비율)
PASS_RATIO = 0.50
DEFAULT_GAP_RATIO = 0.30

SIDES = ("Left", "Right")
# mixamorig 접두는 리그마다 붙거나 안 붙는다 — 실행 시 실제 이름에서 찾아낸다.
CHAIN = ("UpLeg", "Leg", "Foot", "ToeBase")


def log(msg):
    print(msg, flush=True)


# ──────────────────────────────────────────────────────────────────────────
# 로드
# ──────────────────────────────────────────────────────────────────────────

def load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_homefile(use_empty=True)
        if ext == ".fbx":
            # use_image_search=False — 대용량 FBX 임포트 무한대기 방지(실측)
            bpy.ops.import_scene.fbx(filepath=path, use_image_search=False)
        elif ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        else:
            raise SystemExit(f"지원하지 않는 확장자: {ext}")

    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not arms:
        raise SystemExit("아마추어(리그)가 없다 — ⑤ ARP export 를 먼저 끝낼 것")
    arm = max(arms, key=lambda o: len(o.data.bones))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("메시가 없다")
    return arm, meshes


def find_bones(arm):
    """좌우 다리 체인의 실제 본 이름을 찾는다(mixamorig: 접두 유무 무관)."""
    names = [b.name for b in arm.data.bones]
    found = {}
    for side in SIDES:
        for part in CHAIN:
            key = side + part
            hit = [n for n in names if n.split(":")[-1] == key]
            if not hit:
                hit = [n for n in names if n.endswith(key)]
            if hit:
                found[key] = hit[0]
    missing = [s + p for s in SIDES for p in ("UpLeg", "Leg", "Foot") if (s + p) not in found]
    if missing:
        raise SystemExit(
            f"다리 본을 찾지 못했다: {missing}\n"
            f"   Mixamo 규격 리그(mixamorig:LeftUpLeg 등)여야 한다 — ⑥ 검증을 먼저 통과할 것")
    return found


# ──────────────────────────────────────────────────────────────────────────
# 측정
# ──────────────────────────────────────────────────────────────────────────

def eval_verts(meshes):
    """**포즈가 반영된** 월드 정점 좌표. `me.data.vertices` 는 rest 정점이라 포즈를 바꿔도
    변하지 않는다 — depsgraph 로 평가된 메시를 읽어야 회전 결과를 실시간으로 잴 수 있다."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for me in meshes:
        ob = me.evaluated_get(dg)
        m = ob.to_mesh()
        mw = ob.matrix_world
        out.extend(mw @ v.co for v in m.vertices)
        ob.to_mesh_clear()
    return out


def mesh_gap_ratio(meshes):
    """check_leg_gap.py 와 **똑같은 잣대**로 '최대 간격 / 발 하나 폭' 을 구한다.

    🛑 발 폭을 인자로 받아 고정하면 안 된다(실측으로 한 번 틀렸다). 발 폭은
    `(발 높이 구간의 좌우 스팬)/2` 로 정의되는데, 다리를 모으면 **스팬이 줄어들어 발 폭
    측정값도 같이 줄어든다.** 벌어진 상태의 발 폭(48.2cm)을 고정해 쓰면 포즈 중에는
    30% 로 보이던 것이 rest 로 굳힌 뒤 다시 재면 66% 가 된다 — 잣대가 달라서지 교정이
    풀린 것이 아니다. **매 측정마다 다시 재야** check_leg_gap.py 판정과 일치한다.
    """
    verts = eval_verts(meshes)
    zmin = min(v.z for v in verts)
    zmax = max(v.z for v in verts)
    lo = [v for v in verts if v.z < zmin + (zmax - zmin) * 0.07]
    foot_w = ((max(v.x for v in lo) - min(v.x for v in lo)) / 2.0) if lo else 0.0
    h = max(v.z for v in verts) - zmin
    worst = 0.0
    for z0, z1 in ((0.02, 0.12), (0.20, 0.35), (0.40, 0.50), (0.60, 0.75)):
        band = [v for v in verts if zmin + h * z0 <= v.z < zmin + h * z1]
        left = [v.x for v in band if v.x < 0]
        right = [v.x for v in band if v.x > 0]
        if not left or not right:
            continue
        worst = max(worst, max(0.0, min(right) - max(left)))
    return ((worst / foot_w) if foot_w else 9.9), worst, foot_w


# ──────────────────────────────────────────────────────────────────────────
# 교정
# ──────────────────────────────────────────────────────────────────────────

def leg_tilt(arm, bones, side):
    """엉덩이 대비 발목이 바깥으로 벌어진 각(라디안). 0 이면 다리가 수직이다."""
    hip = arm.pose.bones[bones[side + "UpLeg"]].matrix.translation
    ankle = arm.pose.bones[bones[side + "Foot"]].matrix.translation
    dz = hip.z - ankle.z
    if dz <= 1e-6:
        return 0.0
    return math.atan2(abs(ankle.x) - abs(hip.x), dz)


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()


def rotate_leg(arm, bones, side, delta, keep_foot=True):
    """엉덩이를 고정한 채 다리 전체를 `delta`(라디안, 음수=안쪽) 만큼 Y축 회전한다.

    회전축이 Y(캐릭터 앞뒤축)이므로 **좌우로만 모으고 앞뒤 자세는 건드리지 않는다.**
    무릎은 다리에 매달려 있어 함께 따라 들어온다.
    """
    if abs(delta) < 1e-6:
        return
    pb_up = arm.pose.bones[bones[side + "UpLeg"]]
    hip = pb_up.matrix.translation.copy()           # armature space
    sign = 1.0 if arm.pose.bones[bones[side + "Foot"]].matrix.translation.x >= 0 else -1.0

    # 발의 방향을 나중에 복원하기 위해 미리 저장(armature space 기준 3x3)
    foot_rots = {}
    if keep_foot:
        for part in ("Foot", "ToeBase"):
            n = bones.get(side + part)
            if n:
                foot_rots[n] = arm.pose.bones[n].matrix.to_3x3().copy()

    # 🛑 부호 주의(실측으로 한 번 틀렸다): tilt 는 dz = hip.z - ankle.z 를 **양수**로 놓고
    #    쟀는데 실제 다리 벡터의 z 성분은 **음수**(아래로 향한다)다. Y축 회전이
    #    x' = x·cosθ + z·sinθ 라서, 이 부호차 때문에 delta 를 그대로 쓰면 다리가
    #    **더 벌어진다**(실측: 발목 x 0.2402 → 0.3557). 그래서 -delta 를 쓴다.
    #    sign 은 오른다리(-x)에서 회전 방향이 뒤집히는 것을 맞춘다.
    R = Matrix.Rotation(-delta * sign, 4, "Y")
    pb_up.matrix = (Matrix.Translation(hip) @ R @ Matrix.Translation(-hip)) @ pb_up.matrix.copy()
    bpy.context.view_layer.update()

    # 발바닥 수평 복원 — 위치는 회전 결과를 그대로 두고 방향만 원래대로.
    # 안 하면 다리를 기울인 만큼 발이 안쪽으로 들려 까치발이 된다.
    for n, rot in foot_rots.items():
        pb = arm.pose.bones[n]
        loc = pb.matrix.translation.copy()
        pb.matrix = Matrix.Translation(loc) @ rot.to_4x4()
        bpy.context.view_layer.update()


def solve_close_ratio(arm, bones, meshes, target_ratio, tilt0):
    """실제 메시 간격을 재면서 '수직화 비율' t 를 이분 탐색한다.

    t = 0 이면 원래 자세, t = 1 이면 다리가 완전히 수직(발목 x = 엉덩이 x).
    t 를 키울수록 간격이 좁아지므로 단조 감소라 이분 탐색이 성립한다.

    왜 이분 탐색인가 — 목표를 '발 하나 폭 × 비율' 로 계산해 발목 x 를 직접 맞추면
    실제 간격이 크게 어긋난다(실측: 목표 30% 로 계산했는데 결과가 3% 였다).
    발 메시가 발목 본 바로 아래에 있지 않고 안쪽·바깥으로 퍼져 있기 때문이다.
    **재면서 맞추는 것이 유일하게 정확하다.**
    """
    def ratio_at(t):
        reset_pose(arm)
        for side in SIDES:
            rotate_leg(arm, bones, side, -tilt0[side] * t)
        r, _, _ = mesh_gap_ratio(meshes)
        return r

    lo, hi = 0.0, 1.0
    r_hi = ratio_at(hi)
    if r_hi > target_ratio:
        # 완전 수직으로도 부족하다 — 골반이 넓거나 발이 바깥으로 퍼진 모델.
        # 살짝 X 자까지 허용해 더 모아 본다(1.6 = 수직에서 60% 더).
        for extra in (1.2, 1.4, 1.6):
            r = ratio_at(extra)
            if r <= target_ratio:
                hi, r_hi = extra, r
                break
            lo, hi, r_hi = extra, extra, r
        if r_hi > target_ratio:
            return hi, r_hi          # 최선까지만 모으고 그대로 둔다
    for _ in range(18):              # 18회면 t 해상도가 1e-5 이하
        mid = (lo + hi) / 2
        if ratio_at(mid) <= target_ratio:
            hi = mid
        else:
            lo = mid
    r = ratio_at(hi)
    return hi, r


def apply_pose_as_rest(arm, meshes):
    """현재 포즈를 rest pose 로 굳힌다 — 메시 스킨이 따라오도록 modifier 를 먼저 적용."""
    for me in meshes:
        mods = [m for m in me.modifiers if m.type == "ARMATURE" and m.object == arm]
        if not mods:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        me.select_set(True)
        bpy.context.view_layer.objects.active = me
        for m in mods:
            # 복제본을 적용해 메시를 현재 포즈로 굳히고, 원본 modifier 는 남긴다
            # (남겨야 rest 를 바꾼 뒤에도 계속 리그를 따른다)
            bpy.ops.object.modifier_copy(modifier=m.name)
            dup = me.modifiers[m.name + ".001"] if (m.name + ".001") in me.modifiers else None
            if dup is None:
                # 이름 규칙이 다르면 새로 생긴 것을 찾는다
                dup = [x for x in me.modifiers if x.type == "ARMATURE" and x != m][-1]
            bpy.ops.object.modifier_apply(modifier=dup.name)

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode="OBJECT")


def ground_fix(arm, meshes):
    """발이 지면(z=0)에 오도록 전체를 z 이동. 회전하면 발목 높이가 미세하게 달라진다."""
    verts = []
    for me in meshes:
        mw = me.matrix_world
        verts.extend((mw @ v.co).z for v in me.data.vertices)
    if not verts:
        return 0.0
    dz = -min(verts)
    if abs(dz) < 1e-5:
        return 0.0
    for o in set(list(meshes) + [arm]):
        if o.parent in meshes or o.parent is arm:
            continue          # 부모가 함께 움직이면 두 번 이동한다
        o.location.z += dz
    bpy.context.view_layer.update()
    return dz


# ──────────────────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit(__doc__)

    positional = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]
    src = os.path.abspath(positional[0])
    dst = os.path.abspath(positional[1]) if len(positional) > 1 else \
        os.path.splitext(src)[0] + ".legs.blend"

    gap_ratio = DEFAULT_GAP_RATIO
    for f in flags:
        if f.startswith("--gap-ratio"):
            gap_ratio = float(f.split("=", 1)[1]) if "=" in f else \
                float(argv[argv.index(f) + 1])
    force = "--force" in flags
    dry = "--dry-run" in flags
    do_ground = "--no-ground-fix" not in flags

    if not dry and os.path.splitext(dst)[1].lower() != ".blend":
        raise SystemExit(
            f"🛑 출력은 .blend 여야 한다(받은 값: {os.path.basename(dst)}).\n"
            f"   리그를 FBX 로 다시 내보내면 rest pose 가 달라질 수 있어(⑦ 머리말 실측),\n"
            f"   다리를 모은 의미가 사라진다. retarget_to_arp_rig.py 는 .blend 를 받는다.")

    arm, meshes = load(src)
    bones = find_bones(arm)
    ratio0, worst0, foot_w = mesh_gap_ratio(meshes)

    log(f"\n=== 다리 모으기 — {os.path.basename(src)} ===")
    log(f"리그      : {arm.name} (본 {len(arm.data.bones)}개)")
    log(f"발 하나 폭 : {foot_w*100:.1f} cm")
    log(f"현재 간격 : {worst0*100:.1f} cm = 발 폭의 {ratio0*100:.0f}%"
        f"  [{'PASS' if ratio0 <= PASS_RATIO else 'FAIL'}]")

    tilt0 = {}
    for side in SIDES:
        tilt0[side] = leg_tilt(arm, bones, side)
        pb = arm.pose.bones[bones[side + "Foot"]]
        hip = arm.pose.bones[bones[side + "UpLeg"]].matrix.translation
        log(f"  {side:5} 엉덩이 x={hip.x:+.4f}  발목 x={pb.matrix.translation.x:+.4f}"
            f"  (바깥으로 {math.degrees(tilt0[side]):+.2f}°)")

    log(f"\n목표 간격 : 발 폭의 {gap_ratio*100:.0f}% 이하"
        f"  (PASS 기준 {PASS_RATIO*100:.0f}%)")

    if ratio0 <= gap_ratio and not force:
        log(f"[SKIP] 이미 목표만큼 모여 있다({ratio0*100:.0f}% ≤ {gap_ratio*100:.0f}%). "
            f"강제로 모으려면 --force")
        return 0
    if ratio0 <= PASS_RATIO and not force:
        log(f"[SKIP] 이미 모여 있다(발 폭의 {ratio0*100:.0f}% ≤ {PASS_RATIO*100:.0f}%). "
            f"강제로 모으려면 --force")
        return 0
    if max(tilt0.values()) <= math.radians(0.05):
        log("[SKIP] 다리가 이미 수직이다 — 회전으로 더 모을 수 없다"
            " (골반·발 폭 문제라면 ② 재생성이 답이다)")
        return 0
    if dry:
        log("[DRY-RUN] 여기서 멈춘다(파일을 쓰지 않는다)")
        return 0

    t, ratio_posed = solve_close_ratio(arm, bones, meshes, gap_ratio, tilt0)
    for side in SIDES:
        log(f"  {side:5} 회전 {-math.degrees(tilt0[side]*t):+.2f}°  → 발목 x="
            f"{arm.pose.bones[bones[side+'Foot']].matrix.translation.x:+.4f}")
    log(f"  수직화 비율 t={t:.3f} (1.0 = 완전 수직) → 포즈 상태 간격 {ratio_posed*100:.0f}%")

    apply_pose_as_rest(arm, meshes)
    dz = ground_fix(arm, meshes) if do_ground else 0.0
    if dz:
        log(f"  지면 보정 z {dz*100:+.2f} cm")

    ratio1, worst1, foot_w2 = mesh_gap_ratio(meshes)
    log(f"\n결과 간격 : {worst1*100:.1f} cm = 발 폭의 {ratio1*100:.0f}%"
        f"  [{'PASS' if ratio1 <= PASS_RATIO else 'FAIL'}]")

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=dst)
    log(f"저장      : {dst}")

    if ratio1 > PASS_RATIO:
        log(f"[WARN] 아직 발 폭의 {ratio1*100:.0f}% 다 — 다리가 아니라 몸통·골반이 넓거나,\n"
            f"       발 자체가 바깥으로 벌어진 모델일 수 있다. --gap-ratio 를 낮춰 다시 시도하거나\n"
            f"       ② 로 돌아가 재생성할 것")
        return 0
    log(f"[OK] 다리를 모았다 — 이어서 ⑦ retarget_to_arp_rig.py 에 이 .blend 를 넘긴다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
