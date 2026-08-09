"""
Auto-Rig Pro 로 리깅해 내보낸 캐릭터가 texture-packer 의 sheet.py 로 구울 수 있는
상태인지 검사한다.

sheet.py 는 애니메이션을 붙일 수 있는지를 *본 이름으로* 판단하는데, 붙지 않아도
예외를 내지 않는다 — "모든 행동이 같은 T-포즈인 아틀라스" 가 조용히 나오고,
896장을 다 렌더한 뒤에야 눈으로 알 수 있다. 그 전에 여기서 잡는다.

⚠️ 판정 기준은 `_sheet_render.py` 의 것을 **그대로** 옮겼다. 두 가지가 다르다:

  1. **리그 종류 판정** — `detect_rig`: Mixamo 22역할 중 8개 이상이면 그 리그로 인정
     (`_sheet_render.py:321`).
  2. **애니 직접 적용 판정** — 역할이 아니라 **본 이름 교집합**:
     `len(char∩anim) >= max(8, int(len(anim) * 0.5))` (`_sheet_render.py:451`).

  2가 1보다 훨씬 엄격하다. 22역할을 다 채워도(=몸통·사지만 rename) 손가락이 빠지면
  교집합이 애니 본의 절반에 못 미쳐 **정적**이 된다. 그리고 이때 구제 경로가 없다 —
  `_sheet_render.py:457` 은 두 리그가 *다를* 때만 retarget 하는데, 캐릭터와 애니가
  둘 다 mixamorig 로 감지되면 그 조건이 거짓이라 곧바로 정적으로 떨어진다.

  sheet.py 쪽 임계·정규화가 바뀌면 아래 MIN_ROLES·ANIM_COMMON_RATIO 도 같이 고칠 것.

사용법:
  blender --background --python verify_mixamo_rig.py -- <캐릭터파일> [애니메이션폴더]

  <캐릭터파일>     .fbx / .glb / .gltf / .blend
  [애니메이션폴더] 지정하면 런타임 이동·slash·사격·death 파일을 실제로 열어
                   "리타게팅 없이 직접 적용되는가" 까지 확인한다.

종료 코드: 0 = 통과, 1 = 실패(모든 FAIL 을 출력한 뒤 종료)
"""
import bpy
import os
import re
import sys

# _sheet_render.py 의 RIG_BONES["mixamorig"] 와 같아야 한다.
MIXAMO_ROLES = {
    "hips": "mixamorig:Hips",
    "spine": "mixamorig:Spine",
    "spine1": "mixamorig:Spine1",
    "spine2": "mixamorig:Spine2",
    "neck": "mixamorig:Neck",
    "head": "mixamorig:Head",
    "l_shoulder": "mixamorig:LeftShoulder",
    "l_arm": "mixamorig:LeftArm",
    "l_forearm": "mixamorig:LeftForeArm",
    "l_hand": "mixamorig:LeftHand",
    "r_shoulder": "mixamorig:RightShoulder",
    "r_arm": "mixamorig:RightArm",
    "r_forearm": "mixamorig:RightForeArm",
    "r_hand": "mixamorig:RightHand",
    "l_upleg": "mixamorig:LeftUpLeg",
    "l_leg": "mixamorig:LeftLeg",
    "l_foot": "mixamorig:LeftFoot",
    "l_toe": "mixamorig:LeftToeBase",
    "r_upleg": "mixamorig:RightUpLeg",
    "r_leg": "mixamorig:RightLeg",
    "r_foot": "mixamorig:RightFoot",
    "r_toe": "mixamorig:RightToeBase",
}
MIN_ROLES = 8               # _sheet_render.py:321 — detect_rig 의 리그 *종류* 판정
ANIM_COMMON_MIN = 8         # _sheet_render.py:451 — 교집합 하한
ANIM_COMMON_RATIO = 0.5     # _sheet_render.py:451 — 애니 본 수 대비 비율
ACTIONS = [
    "idle", "walk", "run", "slash",
    "standing_gun_shooting", "walking_gun_shooting", "death",
]

_fails = []


def ok(msg):
    print(f"[OK  ] {msg}")


def fail(msg):
    print(f"[FAIL] {msg}")
    _fails.append(msg)


def warn(msg):
    print(f"[경고] {msg}")


def load(path):
    """확장자로 import 를 분기한다. .blend 는 열고, 나머지는 빈 씬에 임포트한다."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise SystemExit(f"지원하지 않는 확장자: {ext}")


def matched_roles(bone_names):
    """이 리그가 채우는 Mixamo 역할 집합."""
    names = set(bone_names)
    return {role for role, bn in MIXAMO_ROLES.items() if bn in names}


def mixamo_prefix(bone_names):
    """본 이름에서 `mixamorig` 접두사를 찾는다(`mixamorig1:` 같은 중복 export 포함)."""
    for n in bone_names:
        m = re.match(r"^(mixamorig\d*):", n)
        if m:
            return m.group(1)
    return None


def normalize_prefix(anim_names, char_prefix):
    """애니 본의 `mixamorig\\d*:` 를 캐릭터 접두사에 맞춘다.

    `_sheet_render.py:430-445` 가 렌더 직전에 하는 일과 같다. 이걸 재현하지 않으면
    캐릭터가 `mixamorig:` 인데 애니가 `mixamorig1:` 인 흔한 경우에 **sheet.py 는 정상
    처리하는데 여기서만 실패**하는 거짓 경보가 난다.
    """
    if not char_prefix:
        return set(anim_names), 0
    out, n = set(), 0
    for name in anim_names:
        new = re.sub(r"^mixamorig\d*:", char_prefix + ":", name)
        if new != name:
            n += 1
        out.add(new)
    return out, n


def anim_threshold(anim_count):
    """sheet.py 가 애니를 직접 적용하는 최소 교집합 크기."""
    return max(ANIM_COMMON_MIN, int(anim_count * ANIM_COMMON_RATIO))


def check_character(path):
    load(path)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    print(f"\n=== 캐릭터: {path} ===")
    if not arms:
        fail("아마추어 없음 — 리깅되지 않은 파일이다"
             "(ARP 는 Smart → **Match to Rig** → Bind 순서를 모두 거쳐야 한다)")
        return None
    if len(arms) > 1:
        warn(f"아마추어가 {len(arms)}개다: {[a.name for a in arms]} — 첫 번째로 검사한다")

    arm = arms[0]
    names = {b.name for b in arm.data.bones}
    print(f"아마추어 {arm.name!r}  본 {len(names)}개  메시 {[m.name for m in meshes]}")

    have = matched_roles(names)
    miss = sorted(set(MIXAMO_ROLES) - have)
    if len(have) >= MIN_ROLES:
        ok(f"Mixamo 리그로 감지됨 ({len(have)}/{len(MIXAMO_ROLES)} 역할)")
    else:
        fail(f"Mixamo 리그로 감지되지 않는다 ({len(have)}/{len(MIXAMO_ROLES)} 역할, "
             f"최소 {MIN_ROLES} 필요) — 본 이름이 ARP 규격 그대로일 수 있다. "
             f"GE Export 의 'Rename Bones from File' 이 켜져 있었는지, "
             f"arp_to_mixamo.txt 경로가 맞는지 확인")
    if miss:
        warn(f"비어 있는 역할 {len(miss)}개: {miss}")
        if "spine2" in miss:
            warn("  spine2 가 비었다 → Spine Count 가 3 이면 ARP 가 spine_03.x 를 지운다. "
                 "4 로 올려야 Mixamo 의 Spine2 에 대응한다(auto_rig_ge.py:6322)")

    # ARP 이름이 남아 있으면 rename 이 부분적으로만 됐다는 뜻이다.
    leftover = [n for n in names if n.endswith((".x", ".l", ".r")) and not n.startswith("mixamorig")]
    if leftover:
        warn(f"ARP 이름이 남아 있는 본 {len(leftover)}개(twist·metacarpal 은 정상): "
             f"{sorted(leftover)[:12]}{' …' if len(leftover) > 12 else ''}")

    # 스킨: 메시가 이 아마추어를 실제로 참조하는가.
    skinned = [m for m in meshes
               if any(mod.type == "ARMATURE" and mod.object == arm for mod in m.modifiers)]
    if skinned:
        ok(f"스킨 연결됨 (메시 {len(skinned)}개)")
    else:
        fail("아마추어 모디파이어를 가진 메시가 없다 — Bind 가 되지 않았다(ARP Bind to Rig)")

    # 정점 그룹이 본 이름과 맞는지. rename 후 vgroup 이름이 안 따라오면 스킨이 죽는다.
    if skinned:
        for m in skinned:
            vgs = {vg.name for vg in m.vertex_groups}
            orphan = sorted(vgs - names)
            if orphan:
                fail(f"메시 {m.name!r} 의 정점 그룹 {len(orphan)}개가 본과 이름이 다르다 "
                     f"(스킨이 끊긴다): {orphan[:10]}{' …' if len(orphan) > 10 else ''}")
            else:
                ok(f"메시 {m.name!r} 의 정점 그룹이 전부 본과 일치")

    # 발 높이: 아이소 스프라이트는 발이 바닥이다. sheet.py 의 align_feet 가
    # 픽셀 단계에서 보정하지만, 모델이 통째로 떠 있으면 방향별로 어긋난다.
    zs = [b.head_local.z for b in arm.data.bones] + [b.tail_local.z for b in arm.data.bones]
    zmin, zmax = min(zs), max(zs)
    height = zmax - zmin
    if height <= 0:
        warn("본 높이를 잴 수 없다(z 범위 0) — Y-up 원본일 수 있다")
    elif abs(zmin) > height * 0.05:
        warn(f"발이 원점에서 {round(zmin, 3)} 만큼 떨어져 있다(높이 {round(height, 3)}) "
             f"— sheet.py 의 align_feet 로 보정되지만 원점을 발에 맞추는 편이 안전하다")
    else:
        ok(f"발이 원점 근처 (z {round(zmin, 3)} ~ {round(zmax, 3)})")

    return names


def check_animations(anim_dir, char_bones):
    print(f"\n=== 애니메이션: {anim_dir} ===")
    char_prefix = mixamo_prefix(char_bones)
    if char_bones and not char_prefix:
        warn("캐릭터 본에 mixamorig 접두사가 없다 — sheet.py 의 assert_mixamo_rig 가 "
             "굽기 전에 즉시 종료시킨다(sheet.py:398-411)")

    exts = (".fbx", ".glb", ".gltf")
    for act in ACTIONS:
        path = next((os.path.join(anim_dir, act + e) for e in exts
                     if os.path.exists(os.path.join(anim_dir, act + e))), None)
        if path is None:
            fail(f"{act}: 파일 없음 ({anim_dir}/{act}.[fbx|glb|gltf]) — 그 행동은 정적 프레임이 된다")
            continue

        load(path)
        arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
        if not arms:
            fail(f"{act}: 아마추어 없음")
            continue
        acts = list(bpy.data.actions)
        if not acts:
            fail(f"{act}: 액션(키프레임) 이 없다 — 정적 프레임이 된다")
            continue

        raw = {b.name for b in arms[0].data.bones}
        names, renamed = normalize_prefix(raw, char_prefix)
        if renamed:
            print(f"       (접두사 정규화 {renamed}본 → {char_prefix}: — sheet.py 도 같은 일을 한다)")

        frames = max(int(a.frame_range[1] - a.frame_range[0]) for a in acts)
        roles = len(matched_roles(names))
        thr = anim_threshold(len(names))
        common = len(names & char_bones) if char_bones else 0

        if roles < MIN_ROLES:
            fail(f"{act}: Mixamo 리그가 아니다 ({roles}/{len(MIXAMO_ROLES)} 역할)")
            continue
        if not char_bones:
            warn(f"{act}: 애니 본 {len(names)}개 · {frames}프레임 (캐릭터를 못 읽어 교집합 미검사)")
            continue

        if common >= thr:
            ok(f"{act}: 애니본 {len(names)} · {frames}프레임 · 교집합 {common} ≥ {thr} "
               f"→ 리타게팅 없이 직접 적용")
        else:
            fail(f"{act}: 교집합 {common} < {thr}(애니본 {len(names)}의 50%) "
                 f"→ **정적 프레임 확정**. 캐릭터와 애니가 둘 다 mixamorig 로 감지되므로 "
                 f"retarget 으로 구제되지 않는다(_sheet_render.py:457). "
                 f"손가락 30본이 rename 됐는지 확인할 것")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    if not argv:
        raise SystemExit("사용법: verify_mixamo_rig.py -- <캐릭터파일> [애니메이션폴더]")

    char_bones = check_character(argv[0])
    if len(argv) > 1:
        check_animations(argv[1], char_bones or set())

    print()
    if _fails:
        print(f"##### 실패 {len(_fails)}건")
        for f in _fails:
            print("  -", f)
        _exit(1)
    print("##### 통과 — sheet.py 로 texture-pack 할 수 있다")
    _exit(0)


def _exit(code):
    """Blender 는 --python 스크립트의 sys.exit() 를 삼켜 항상 0 으로 끝난다(실측).
    os._exit 로 프로세스를 직접 끝내야 종료 코드가 호출자에게 간다.
    버퍼를 건너뛰므로 flush 가 먼저다."""
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


# Blender 의 `--python` 은 이 파일을 `__main__` 으로 실행한다. 가드를 둔 이유는
# test_verify_mixamo_rig.py 가 bpy 를 스텁으로 갈아 끼우고 판정 함수만 import 해
# **Blender 없이** 검사할 수 있게 하려는 것이다.
if __name__ == "__main__":
    main()
