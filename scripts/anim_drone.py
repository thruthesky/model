"""비행체(드론) 리그에 idle/walk/attack/death 액션을 절차적으로 만든다.

🛑 **왜 직접 만드나** — Mixamo 는 2족 인간형 모션만 제공한다. "호버링하는 드론이 포를
쏘는" 원본은 세상에 없으므로 리타게팅할 소스 자체가 없다. `anim_animal.py` 도 쓸 수 없다
— 그쪽은 IK 발 컨트롤러 4개 이상을 전제해 드론에서는 `sys.exit(1)` 로 즉시 멈춘다.

드론은 관절이 없는 **강체** 다. 그래서 움직임의 문법이 다족보행과 완전히 다르다:

| | 다족(거미) | 비행체(드론) |
|---|---|---|
| 이동의 정체 | 발이 지면을 밀어낸다 | 기체가 **기울어** 그 방향으로 떠간다 |
| 정지 상태 | 발로 서 있다(고정) | **떠 있다** — 가만히 있어도 계속 흔들린다 |
| 공격 | 다리를 들어 내려찍는다 | **포를 쏜다** → 반동으로 기체가 젖혀지고 포신이 후퇴 |
| 죽음 | 다리가 풀려 주저앉는다 | 양력 상실 → **회전하며 추락** |

조작 대상은 두 개뿐이다 — 몸통 컨트롤러와 `weapon` 본(rig_drone_arp.py 가 만든다).
무기 본이 없으면 몸통만으로 진행하되, 발사가 "기체가 흔들리는 것" 으로만 보인다.

사용:
    blender --background <리그.blend> --python anim_drone.py -- <출력.blend>
"""
import bpy
import sys
import os
import json
import math
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("usage: blender --background <리그.blend> --python anim_drone.py -- <출력.blend>")
    sys.exit(1)
DST = os.path.abspath(argv[0])

# 행동별 길이(프레임). sheet.py 가 이 구간을 균등 샘플링하므로 넉넉하게 둔다.
LEN = {"idle": 48, "walk": 32, "attack": 40, "death": 48}
SHOTS = 3                      # attack 한 사이클에 쏘는 발수
LOG = {"dst": DST, "actions": {}, "errors": []}

rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if rig is None:
    print("[FAIL] 아마추어가 없습니다")
    sys.exit(1)

# 🛑 ARP 컨트롤러 위젯(`cs_*`)을 크기 계산에서 반드시 뺀다 — 위젯은 리그를 감싸도록 크게
# 퍼져 있어, 섞어서 재면 기체가 실제보다 몇 배 커 보인다(실측: 실제 1.6 인 드론이 5.24 로
# 나와 모든 진폭이 3.3배 과장됐다). 판정은 이름이 아니라 **armature modifier 유무**가
# 우선이다 — 위젯에는 그것이 없고, 스킨된 본체에는 반드시 있다.
def _body_meshes():
    real = [o for o in bpy.data.objects
            if o.type == "MESH"
            and not o.name.lower().startswith("cs_")
            and any(m.type == "ARMATURE" for m in o.modifiers)]
    if real:
        return real
    return [o for o in bpy.data.objects
            if o.type == "MESH" and not o.name.lower().startswith("cs_")]


meshes = _body_meshes()

bpy.context.view_layer.objects.active = rig
rig.select_set(True)
if rig.mode != "POSE":
    bpy.ops.object.mode_set(mode="POSE")

# ── 조작 대상 확보 ──────────────────────────────────────────────────────
# 몸통: ARP `free`+spine 리그의 최상위 컨트롤러부터 훑는다(리그 버전마다 이름이 다르다).
BODY = [b for b in ("c_root_master.x", "c_root.x", "c_spine_01.x", "c_spine_02.x")
        if b in rig.pose.bones]
if not BODY:
    # 컨트롤러를 못 찾으면 deform 본이라도 잡는다 — 강체라 어느 것이든 전체가 움직인다
    BODY = [b.name for b in rig.pose.bones if b.bone.use_deform][:1]
if not BODY:
    print("[FAIL] 몸통으로 쓸 본을 찾지 못했습니다")
    sys.exit(1)
ROOT = BODY[0]
WEAPON = "weapon" if "weapon" in rig.pose.bones else None

# 기체 크기 — 모든 진폭의 기준. 스프라이트가 128px 로 줄어들므로 이 값에 비례해 과장한다.
pts = [m.matrix_world @ v.co for m in meshes for v in m.data.vertices] if meshes else []
if pts:
    SPAN = max(max(p.x for p in pts) - min(p.x for p in pts),
               max(p.y for p in pts) - min(p.y for p in pts))
    HGT = max(p.z for p in pts) - min(p.z for p in pts)
else:
    SPAN, HGT = 1.6, 0.6

# FRONT_Y — 정면이 향하는 Y 축 부호. **리깅 스크립트가 정하고 여기서는 읽기만 한다.**
# 🛑 여기에 값을 직접 써넣지 말 것 — 두 파일이 갈리면 몸이 향한 반대로 날면서
# 뒤통수로 쏘게 된다(rig_animal_arp.py 가 겪은 실제 결함).
FRONT_Y = float(rig.get("laryen_front_y", -1.0))

print(f"[INFO] body={BODY} weapon={WEAPON} span={SPAN:.3f} height={HGT:.3f} front_y={FRONT_Y:+.0f}")
LOG.update({"body": BODY, "weapon": WEAPON, "span": round(SPAN, 4),
            "front_y": FRONT_Y})


# ── 포즈 헬퍼 ──────────────────────────────────────────────────────────
def reset_pose():
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def set_body(loc=(0, 0, 0), rot=(0, 0, 0)):
    pb = rig.pose.bones[ROOT]
    pb.location = Vector(loc)
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = Euler(rot)


def pitch(amount):
    """+amount = 기수를 **앞으로 숙인다**(전진 자세). 정면축 부호를 흡수한다.

    🛑 X 회전의 부호는 정면이 어느 쪽이냐에 따라 뒤집힌다 — 앞이 −Y 면 +X 가 숙이는
    방향이고, 앞이 +Y 면 −X 가 숙이는 방향이다. 호출부가 이걸 매번 따지지 않도록
    여기서 한 번만 변환한다."""
    return -FRONT_Y * amount


def set_weapon(recoil=0.0, rot=(0, 0, 0)):
    """무기 본을 사격 반대 방향으로 물린다(recoil>0 = 후퇴).
    본 로컬 Y+ 가 tail(포구) 방향이므로 음수를 주면 뒤로 밀린다."""
    if not WEAPON:
        return
    pb = rig.pose.bones[WEAPON]
    pb.rotation_mode = "XYZ"
    pb.location = Vector((0, -recoil, 0))
    pb.rotation_euler = Euler(rot)


def key_all(frame):
    """이 프레임의 포즈를 키로 굳힌다. 조작한 본 전부를 찍어야 보간이 새지 않는다."""
    for b in BODY:
        pb = rig.pose.bones[b]
        pb.keyframe_insert("location", frame=frame)
        if pb.rotation_mode == "QUATERNION":
            pb.keyframe_insert("rotation_quaternion", frame=frame)
        else:
            pb.keyframe_insert("rotation_euler", frame=frame)
    if WEAPON:
        pb = rig.pose.bones[WEAPON]
        pb.keyframe_insert("location", frame=frame)
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
    """🛑 Blender 4.4+ slotted action 에는 `act.fcurves` 가 없다 — channelbag 으로 내려간다."""
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


# ── idle — 제자리 부양. 가만히 있어도 계속 흔들리는 것이 비행체의 '정지' 다 ────
def make_idle():
    n = LEN["idle"]
    act = new_action("idle")
    for f in range(n + 1):
        t = f / n
        bob = math.sin(t * 2 * math.pi)                 # 주 부양 주기
        sway = math.sin(t * 2 * math.pi * 1.5 + 0.7)    # 어긋난 주기 → 기계적 반복감 제거
        set_body(loc=(sway * SPAN * 0.055, 0, bob * SPAN * 0.14),
                 rot=(pitch(sway * 0.10), 0, bob * 0.12))
        set_weapon(recoil=0.0, rot=(sway * 0.06, 0, 0))
        key_all(f + 1)
    finish(act, n)


# ── walk — 비행 이동. 다리가 없으므로 '기울여 떠간다' 로 표현한다 ──────────────
def make_walk():
    n = LEN["walk"]
    act = new_action("walk")
    # 🛑 진폭은 과장한다 — 128px 셀로 줄면 사실적인 크기의 움직임은 보이지 않는다
    # (거미에서 보폭 0.30→0.52 로 올린 뒤에야 걸음이 눈에 띈 실측과 같은 이유).
    lean = 0.34                                          # 전진 자세(기수 숙임)
    for f in range(n + 1):
        t = f / n
        bob = math.sin(t * 2 * math.pi)
        roll = math.sin(t * 2 * math.pi + 1.2)
        set_body(loc=(roll * SPAN * 0.090, 0, bob * SPAN * 0.11),
                 rot=(pitch(lean + bob * 0.14), roll * 0.24, roll * 0.12))
        set_weapon(recoil=0.0, rot=(bob * 0.07, 0, 0))
        key_all(f + 1)
    finish(act, n)


# ── attack — 포격. 반동으로 기체가 젖혀지고 포신이 후퇴했다 복귀한다 ────────────
def make_attack():
    n = LEN["attack"]
    act = new_action("attack")
    aim_end = 0.22                 # 조준 구간
    fire_end = 0.82                # 사격 구간
    for f in range(n + 1):
        t = f / n
        if t < aim_end:                                   # ① 조준 — 기수를 들며 자세를 잡는다
            s = t / aim_end
            set_body(loc=(0, 0, s * SPAN * 0.075),
                     rot=(pitch(-0.28 * s), 0, 0))
            set_weapon(recoil=0.0)
        elif t < fire_end:                                # ② 연사 — 발마다 반동
            s = (t - aim_end) / (fire_end - aim_end)
            ph = (s * SHOTS) % 1.0                        # 한 발의 진행도
            kick = math.exp(-ph * 6.0)                    # 발사 순간 최대 → 급감(총기 반동 곡선)
            set_body(loc=(0, -FRONT_Y * kick * SPAN * 0.16, SPAN * (0.075 + kick * 0.075)),
                     rot=(pitch(-0.28 - kick * 0.45), 0, kick * 0.13))
            set_weapon(recoil=kick * SPAN * 0.17, rot=(-kick * 0.22, 0, 0))
        else:                                             # ③ 복귀
            s = (t - fire_end) / (1.0 - fire_end)
            set_body(loc=(0, 0, (1 - s) * SPAN * 0.075),
                     rot=(pitch(-0.28 * (1 - s)), 0, 0))
            set_weapon(recoil=0.0)
        key_all(f + 1)
    finish(act, n)


# ── death — 양력 상실. 회전하며 추락해 지면에 처박힌다 ──────────────────────
def make_death():
    n = LEN["death"]
    act = new_action("death")
    # 🛑 추락을 z 하강만으로 표현하지 않는다 — sheet.py 는 프레임마다 bbox 를 셀에 맞춰
    # 정렬하므로 **평행이동은 화면에서 상쇄된다**. 눈에 남는 것은 자세(회전)뿐이라
    # 기울기·스핀을 주역으로 두고 하강은 거들게 한다.
    for f in range(n + 1):
        t = f / n
        if t < 0.18:                                      # ① 피격 경련
            s = t / 0.18
            j = math.sin(s * math.pi * 4) * (1 - s)
            set_body(loc=(j * SPAN * 0.05, 0, j * SPAN * 0.03),
                     rot=(pitch(j * 0.18), j * 0.25, j * 0.12))
            set_weapon(recoil=0.0, rot=(j * 0.12, 0, 0))
        elif t < 0.72:                                    # ② 동력 상실 — 기울며 스핀 하강
            s = (t - 0.18) / 0.54
            e = s * s                                     # 가속 낙하
            set_body(loc=(math.sin(s * 6.0) * SPAN * 0.06, 0, -e * HGT * 0.55),
                     rot=(pitch(-0.30 - e * 0.55), s * 5.2, math.sin(s * 4.0) * 0.30))
            set_weapon(recoil=0.0, rot=(-e * 0.25, 0, 0))
        elif t < 0.86:                                    # ③ 지면 충돌 — 튕김
            s = (t - 0.72) / 0.14
            b = math.sin(s * math.pi) * (1 - s * 0.5)
            set_body(loc=(0, 0, -HGT * 0.55 + b * HGT * 0.16),
                     rot=(pitch(-0.85 + b * 0.22), 5.2 + s * 0.5, 0.30 + b * 0.12))
            set_weapon(recoil=0.0, rot=(-0.25, 0, 0))
        else:                                             # ④ 정지 — 기울어 처박힌 채
            s = (t - 0.86) / 0.14
            set_body(loc=(0, 0, -HGT * 0.58),
                     rot=(pitch(-0.92), 5.7, 0.38))
            set_weapon(recoil=0.0, rot=(-0.25, 0, 0))
        key_all(f + 1)
    finish(act, n)


make_idle()
make_walk()
make_attack()
make_death()

# 액션은 파일에 남아야 한다(sheet.py 가 내장 애니로 읽는다)
for a in bpy.data.actions:
    a.use_fake_user = True
if rig.animation_data:
    rig.animation_data.action = None

bpy.ops.object.mode_set(mode="OBJECT")
os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=DST)
LOG["ok"] = True
LOG["actions_final"] = [a.name for a in bpy.data.actions]
with open(DST + ".log.json", "w", encoding="utf-8") as f:
    json.dump(LOG, f, ensure_ascii=False, indent=2)
print(f"[DONE] {DST} actions={LOG['actions_final']}")
