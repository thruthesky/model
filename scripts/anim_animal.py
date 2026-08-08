"""거미형 리그(ARP `free` + leg limb N개)에 idle/walk/attack/death 액션을 절차적으로 만든다.

🛑 **왜 직접 만드나** — Mixamo 는 인간형(2족) 애니메이션만 제공한다. 거미의 방사형 다족
보행은 리타게팅할 원본 자체가 없으므로, 리그를 읽어 **발 위치를 시간축으로 계산**해 키프레임을
굽는다. model 스킬 ⑦(rest pose 보정 리타게팅)의 자리를 이 스크립트가 대신한다.

보행은 곤충의 **삼각보행(tripod gait)** 을 쓴다 — 다리를 방위각 순으로 정렬해 번갈아 두
그룹으로 나누면, 어느 순간에도 서로 이웃하지 않는 다리들이 지면을 딛고 있어 몸이 넘어지지
않는다. 다리 개수가 6이든 8이든 같은 규칙으로 동작한다.

조작 대상은 ARP 의 IK 발 컨트롤러(`c_foot_ik*`)다. 발을 월드 좌표로 옮기면 무릎·허벅지가
IK 로 따라오므로, 관절마다 각도를 지어내지 않아도 다리가 자연스럽게 접힌다.

사용:
    blender --background <리그.blend> --python anim_animal.py -- <출력.blend>
"""
import bpy
import sys
import os
import json
import math
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("usage: blender --background <리그.blend> --python anim_animal.py -- <출력.blend>")
    sys.exit(1)
DST = os.path.abspath(argv[0])

# 행동별 길이(프레임). sheet.py 가 이 구간을 균등 샘플링하므로 넉넉하게 둔다.
LEN = {"idle": 48, "walk": 32, "attack": 40, "death": 48}
LOG = {"dst": DST, "actions": {}, "errors": []}

rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
mesh = next((o for o in bpy.data.objects if o.type == "MESH"), None)
if rig is None:
    print("[FAIL] 아마추어가 없습니다")
    sys.exit(1)

bpy.context.view_layer.objects.active = rig
rig.select_set(True)
if rig.mode != "POSE":
    bpy.ops.object.mode_set(mode="POSE")


# ── 다리 정보 수집 — 리그에서 직접 읽는다(추정 금지) ─────────────────────────
def collect_legs():
    legs = []
    for pb in rig.pose.bones:
        n = pb.name
        if not n.startswith("c_foot_ik"):
            continue
        if "roll" in n or n.startswith("c_p_"):
            continue
        rest = rig.data.bones[n].head_local.copy()      # rest pose 의 armature 공간 위치
        ang = math.degrees(math.atan2(rest.y, rest.x)) % 360.0
        legs.append({"bone": n, "rest": rest, "ang": ang,
                     "r": math.hypot(rest.x, rest.y)})
    legs.sort(key=lambda l: l["ang"])
    return legs


legs = collect_legs()
if len(legs) < 4:
    print(f"[FAIL] IK 발 컨트롤러를 {len(legs)}개만 찾았습니다")
    sys.exit(1)

# 삼각보행 그룹 — 방위각 정렬 후 교대 배정(이웃끼리 다른 그룹)
for i, l in enumerate(legs):
    l["grp"] = i % 2
    l["dir"] = Vector((math.cos(math.radians(l["ang"])), math.sin(math.radians(l["ang"])), 0.0))

BODY = [b for b in ("c_root_master.x", "c_root.x", "c_spine_01.x", "c_spine_02.x")
        if b in rig.pose.bones]
ROOT = BODY[0] if BODY else None
SPAN = max(l["r"] for l in legs)

# FRONT_Y — 몸의 정면이 향하는 Y 축 부호. **리깅 스크립트가 정하고 여기서는 읽기만 한다**
# (rig_animal_arp.py 가 spine 을 배치할 때 같은 값으로 리그에 기록한다).
#
# 🛑 여기에 값을 직접 써넣지 말 것 — 과거 rig 는 −Y 를 정면으로 잡는데 이 파일만 +Y 로
# 전진시켜 **몸이 향한 반대로 걷고 뒷다리로 내려찍는** 결함이 있었다. 거미처럼 방사대칭인
# 액터에서는 안 보였지만 앞뒤가 분명한 액터에서는 그대로 드러난다.
# 구 리그(이 값이 없는 .blend)는 그때의 동작인 +Y 로 폴백해 결과가 바뀌지 않게 한다.
FRONT_Y = float(rig.get("laryen_front_y", 1.0))

# ── 다리 개수에 따른 진폭 스케일 (2026-08-09) ────────────────────────────────
#
# 🛑 **4족은 6~8족과 같은 진폭을 쓰면 몸이 일그러진다**(사용자 신고: "걷기·공격에서 라몬이
# 이상하게 일그러진다"). 이유는 접지 다리 수다:
#   · 8족: 한 조(4개)를 들어도 4개가 buttresses 처럼 남아 몸이 안정적이다.
#   · 4족: 한 조가 **2개뿐** — 절반을 들면 두 다리로 서 있는 셈이라, 같은 보폭·들어올림을
#          주면 몸이 크게 흔들리고 IK 가 다리를 뻗을 수 있는 한계를 넘어 **다리가 늘어난다**
#          (그것이 화면에서 "일그러짐" 으로 보인다).
# 그래서 다리가 적을수록 진폭을 줄인다. 6족 이상은 종전 값 그대로라 기존 액터
# (spider_cannon)를 재생성해도 결과가 달라지지 않는다.
NLEG = len(legs)
AMP = 0.62 if NLEG <= 4 else (0.82 if NLEG <= 5 else 1.0)
# 공격 때 드는 앞다리 수 — 4족이 2개를 들면 남는 접지가 2개뿐이라 무너져 보인다.
FRONT_LIFT_N = 1 if NLEG <= 4 else 2
print(f"[INFO] legs={NLEG} amp={AMP} front_lift={FRONT_LIFT_N} "
      f"(다리가 적을수록 진폭을 줄여 IK 한계 초과로 인한 일그러짐을 막는다)")
print(f"[INFO] legs={len(legs)} span={SPAN:.3f} groups={[l['grp'] for l in legs]}")
print(f"[INFO] body_ctrl={BODY}")
print(f"[INFO] front_y={FRONT_Y:+.0f} (리그가 기록한 정면축 — 걷기·내려찍기 방향의 기준)")
LOG["front_y"] = FRONT_Y
LOG["legs"] = [{"bone": l["bone"], "ang": round(l["ang"], 1), "grp": l["grp"]} for l in legs]


# ── 포즈 설정 헬퍼 ──────────────────────────────────────────────────────
def reset_pose():
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def set_foot(leg, offset):
    """IK 발을 rest 위치 + 월드 오프셋으로 옮긴다.
    🛑 `location` 에 그대로 넣으면 본 로컬축 기준이라 다리마다 엉뚱한 방향으로 간다
    (방사형 리그라 본마다 축이 다르다). armature 공간 행렬로 직접 지정한다."""
    pb = rig.pose.bones[leg["bone"]]
    m = pb.matrix.copy()
    m.translation = leg["rest"] + offset
    pb.matrix = m


def set_body(loc=(0, 0, 0), rot=(0, 0, 0), bone=None):
    b = bone or ROOT
    if not b or b not in rig.pose.bones:
        return
    pb = rig.pose.bones[b]
    pb.location = Vector(loc)
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = Euler(rot)


def key_all(frame):
    """이 프레임의 포즈를 키로 굳힌다. 컨트롤러 전체를 찍어야 보간이 새지 않는다."""
    for leg in legs:
        rig.pose.bones[leg["bone"]].keyframe_insert("location", frame=frame)
        rig.pose.bones[leg["bone"]].keyframe_insert("rotation_quaternion", frame=frame)
    for b in BODY:
        pb = rig.pose.bones[b]
        pb.keyframe_insert("location", frame=frame)
        if pb.rotation_mode == "QUATERNION":
            pb.keyframe_insert("rotation_quaternion", frame=frame)
        else:
            pb.keyframe_insert("rotation_euler", frame=frame)


def new_action(name):
    reset_pose()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if rig.animation_data is None:
        rig.animation_data_create()
    rig.animation_data.action = act
    # Blender 4.4+ slotted action — slot 을 안 잡으면 액션이 조용히 평가되지 않는다
    slots = getattr(rig.animation_data, "action_suitable_slots", None)
    if slots:
        rig.animation_data.action_slot = slots[0]
    return act


def action_fcurves(act):
    """🛑 Blender 4.4+ 의 slotted action 에는 `act.fcurves` 가 없다(실측 5.1:
    `'Action' object has no attribute 'fcurves'`). layer→strip→channelbag 으로 내려간다."""
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in getattr(layer, "strips", []):
            bags = getattr(strip, "channelbags", None)
            if bags is None:
                continue
            for cb in bags:
                out.extend(cb.fcurves)
    return out


def finish(act, nframes):
    fcs = action_fcurves(act)
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    try:
        act.frame_end = nframes
    except Exception:
        pass
    LOG["actions"][act.name] = {"frames": nframes, "fcurves": len(fcs)}
    print(f"[OK] {act.name} frames={nframes} fcurves={len(fcs)}")


# ── idle — 숨 쉬듯 몸통이 오르내리고 다리가 미세하게 흔들린다 ─────────────────
def make_idle():
    n = LEN["idle"]
    act = new_action("idle")
    for f in range(n + 1):
        t = f / n
        s = math.sin(t * 2 * math.pi)
        set_body(loc=(0, 0, s * SPAN * 0.045), rot=(s * 0.035, 0, 0))
        for i, leg in enumerate(legs):
            ph = math.sin(t * 2 * math.pi + i * 1.1)
            # 발끝을 아주 조금 들었다 놓는다(접지 유지)
            set_foot(leg, Vector((0, 0, max(0.0, ph) * SPAN * 0.055)))
        key_all(f + 1)
    finish(act, n)


# ── walk — 삼각보행. 두 그룹이 반주기 어긋나게 스윙/접지 ──────────────────────
def make_walk():
    n = LEN["walk"]
    act = new_action("walk")
    stride = SPAN * 0.52 * AMP    # 앞뒤 보폭(스프라이트에서 보이려면 과장해야 한다)
    lift = SPAN * 0.34 * AMP      # 스윙 때 드는 높이
    for f in range(n + 1):
        t = f / n
        for leg in legs:
            ph = (t + (0.5 if leg["grp"] else 0.0)) % 1.0
            fwd = Vector((0, FRONT_Y, 0))               # 진행 방향 = 몸이 향한 쪽
            if ph < 0.5:                                # 접지: 몸이 나아가니 발은 뒤로
                s = ph / 0.5
                off = fwd * (stride * (0.5 - s))
                off.z = 0.0
            else:                                       # 스윙: 들어서 앞으로
                s = (ph - 0.5) / 0.5
                off = fwd * (stride * (s - 0.5))
                off.z = math.sin(s * math.pi) * lift
            set_foot(leg, off)
        # 몸통은 걸음에 맞춰 위아래·좌우로 흔들린다(다족 특유의 리듬)
        # 🛑 4족에서는 이 흔들림도 줄인다 — 접지가 2개뿐이라 같은 폭이 "휘청임" 으로 보인다.
        bob = math.sin(t * 4 * math.pi) * SPAN * 0.055 * AMP
        sway = math.sin(t * 2 * math.pi) * SPAN * 0.040 * AMP
        set_body(loc=(sway, 0, bob), rot=(0, sway * 0.5, 0))
        key_all(f + 1)
    finish(act, n)


# ── attack — 몸을 낮췄다가 앞다리를 들어 내려찍고 포탑이 반동한다 ──────────────
def make_attack():
    n = LEN["attack"]
    act = new_action("attack")
    # 몸이 향한 쪽(FRONT_Y)으로 가장 멀리 뻗은 다리 = 앞다리.
    # 🛑 +Y 로 고정하면 정면이 −Y 인 리그에서 **뒷다리로 내려찍는다**.
    # 🛑 드는 개수는 다리 수에 따른다 — 4족이 2개를 들면 접지가 2개뿐이라 무너져 보인다.
    front = sorted(legs, key=lambda l: -FRONT_Y * l["rest"].y)[:FRONT_LIFT_N]
    for f in range(n + 1):
        t = f / n
        # 몸통 진폭도 AMP 를 탄다 — 4족에서 크게 숙이면 두 다리로 버티는 모양이 무너진다.
        if t < 0.30:                       # 준비: 몸을 낮추고 뒤로 당긴다
            s = t / 0.30
            body_z = -SPAN * 0.16 * AMP * s
            body_y = -SPAN * 0.13 * AMP * s
            pitch = 0.26 * AMP * s
            rear = s
        elif t < 0.52:                     # 타격: 앞으로 튀어나가며 내려찍는다
            s = (t - 0.30) / 0.22
            body_z = (-SPAN * 0.16 + SPAN * 0.30 * s) * AMP
            body_y = (-SPAN * 0.13 + SPAN * 0.42 * s) * AMP
            pitch = (0.26 - 0.72 * s) * AMP
            rear = 1.0 - s
        else:                              # 복귀
            s = (t - 0.52) / 0.48
            body_z = SPAN * 0.14 * AMP * (1 - s)
            body_y = SPAN * 0.29 * AMP * (1 - s)
            pitch = -0.46 * AMP * (1 - s)
            rear = 0.0
        # body_y·pitch 는 "앞으로 튀어나가며 앞을 숙인다" 를 +Y 기준으로 계산한 값이라
        # 정면축을 곱해 실제 정면 쪽으로 돌린다(FRONT_Y=+1 이면 계산 그대로).
        set_body(loc=(0, FRONT_Y * body_y, body_z), rot=(FRONT_Y * pitch, 0, 0))
        for leg in legs:
            if leg in front:
                # 앞다리: 들어올렸다가 내려친다. 🛑 들어올림(0.60)이 다리 길이에 비해 크면
                # IK 가 못 따라가 다리가 늘어난다 — AMP 로 다리 수에 맞춰 줄인다.
                if t < 0.30:
                    off = Vector((0, 0, SPAN * 0.60 * AMP * rear)) + leg["dir"] * (-SPAN * 0.14 * AMP * rear)
                elif t < 0.52:
                    s2 = (t - 0.30) / 0.22
                    off = Vector((0, 0, SPAN * 0.60 * AMP * (1 - s2))) + leg["dir"] * (SPAN * 0.26 * AMP * s2)
                else:
                    s2 = (t - 0.52) / 0.48
                    off = leg["dir"] * (SPAN * 0.26 * AMP * (1 - s2))
            else:
                off = Vector((0, 0, 0))    # 나머지 다리는 버틴다
            set_foot(leg, off)
        key_all(f + 1)
    finish(act, n)


# ── death — 다리가 바깥으로 꺾이며 몸이 주저앉고 옆으로 기운다 ────────────────
def make_death():
    n = LEN["death"]
    act = new_action("death")
    for f in range(n + 1):
        t = f / n
        e = t * t * (3 - 2 * t)                     # smoothstep — 처음엔 버티다 무너진다
        twitch = math.sin(t * 14) * (1 - t) * 0.05  # 마지막 경련
        set_body(loc=(0, 0, -SPAN * 0.62 * e),
                 rot=(0.18 * e + twitch, 0.95 * e, 0.22 * e))
        for i, leg in enumerate(legs):
            # 다리를 몸 바깥으로 뻗으며 지면에 붙인다(관절이 풀린 모습)
            spread = leg["dir"] * (SPAN * 0.48 * AMP * e)
            spread.z = -SPAN * 0.10 * e + max(0.0, math.sin(t * 9 + i)) * (1 - t) * SPAN * 0.07
            set_foot(leg, spread)
        key_all(f + 1)
    finish(act, n)


make_idle()
make_walk()
make_attack()
make_death()

reset_pose()
rig.animation_data.action = None
bpy.ops.object.mode_set(mode="OBJECT")

os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=DST)
LOG["ok"] = True
with open(DST + ".log.json", "w", encoding="utf-8") as f:
    json.dump(LOG, f, ensure_ascii=False, indent=2)
print(f"[DONE] {DST}")
