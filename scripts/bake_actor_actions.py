"""리깅·애니가 끝난 ARP `.blend` 를 **스프라이트로 굽기 좋은 순수 아마추어**로 정리한다.

왜 필요한가 — ARP 리그는 IK·제약·컨트롤러 위젯·씬 프로퍼티가 얽힌 "저작용" 리그다.
그대로 sheet.py 에 넘기면 두 가지가 걸린다(둘 다 실측):

  1. 렌더 실패 — ARP 의 씬 로드 핸들러가 `arp_debug_mode` 등 GUI 전용 프로퍼티를 찾다가
     `KeyError: key must be a string or tuple, not NoneType` 로 죽는다.
  2. 세우기 오판 — `_sheet_render.py` 는 `head` 본이 없으면 mesh bbox 로 폴백해
     "높이 < 폭×0.7 이면 누운 것" 으로 본다. 거미처럼 **넓적한 것이 정상**인 액터는
     이 규칙에 걸려 통째로 90° 눕혀진다(실측: hz=1.32 < max(2.00,1.41)×0.7=1.40).

그래서 여기서 ① 포즈를 본에 **베이크**(IK/제약 결과를 로컬 변환으로 구움)하고 ② 제약과
컨트롤러 위젯을 걷어내고 ③ 세우기 판정용 `head` 본을 세워 둔다. 결과는 제약이 하나도 없는
평범한 아마추어 + 액션이라, 어떤 렌더러에 넣어도 같은 그림이 나온다.

사용:
    blender --background <애니.blend> --python bake_actor_actions.py -- <출력.blend>
"""
import bpy
import sys
import os
import json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("usage: blender --background <입력.blend> --python bake_actor_actions.py -- <출력.blend>")
    sys.exit(1)
DST = os.path.abspath(argv[0])
LOG = {"dst": DST, "baked": {}, "removed": {}}

rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if rig is None:
    print("[FAIL] 아마추어가 없습니다")
    sys.exit(1)

# ── 0) ARP 컨트롤러 위젯 메시 제거 ────────────────────────────────────────
# 이름이 cs_* 인 것들은 본 모양(custom shape)일 뿐 캐릭터가 아니다. sheet.py 도 "머티리얼
# 없는 메시" 로 걸러내지만, 남겨 두면 bbox·씬 정리에 잡음이 된다.
widgets = [o for o in bpy.data.objects
           if o.type == "MESH" and (o.name.startswith("cs_") or o.name.startswith("cs "))]
for o in widgets:
    bpy.data.objects.remove(o, do_unlink=True)
LOG["removed"]["widget_meshes"] = len(widgets)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
print(f"[INFO] rig={rig.name} bones={len(rig.data.bones)} meshes={[m.name for m in meshes]} "
      f"widgets_removed={len(widgets)}")

# ── 0-b) 텍스처 경로 복구 ───────────────────────────────────────────────
# 🛑 Tripo ZIP 을 `<NAME>_raw.fbm` 으로 rename 하면 blend 안 이미지는 **옛 폴더**
# (`tripo_convert_<uuid>.fbm/`)를 계속 가리킨다. 그대로 구우면 텍스처가 통째로 빠져
# **마젠타(또는 회색) 스프라이트**가 나온다(실측). 파일 이름만 같으면 실제 위치를 찾아
# 다시 연결한다 — 이 한 단계가 "색이 이상하다" 의 대부분을 없앤다.
blend_dir = os.path.dirname(bpy.data.filepath) or os.path.dirname(DST)
cands = {}
for root, _dirs, files in os.walk(blend_dir):
    for fn in files:
        cands.setdefault(fn.lower(), os.path.join(root, fn))

fixed, missing = [], []
for im in bpy.data.images:
    if not im.filepath:
        continue
    cur = bpy.path.abspath(im.filepath)
    if os.path.exists(cur):
        continue                                  # 이미 올바른 경로
    want = os.path.basename(im.filepath.replace("\\", "/"))
    hit = cands.get(want.lower())
    if hit:
        im.filepath = hit                         # 절대경로로 확실히 붙인다
        try:
            im.reload()
        except Exception:
            pass
        # 🛑 `im.has_data` 로 판정하지 말 것 — Blender 는 픽셀을 지연 로딩하므로
        # reload 직후에도 False 다(실측: 파일이 멀쩡한데 '찾지 못했다'로 오판).
        # 판정은 **파일 존재**로 한다.
        (fixed if os.path.exists(bpy.path.abspath(im.filepath)) else missing).append(want)
    else:
        missing.append(want)
LOG["textures"] = {"fixed": fixed, "missing": missing}
print(f"[INFO] 텍스처 복구 fixed={fixed} missing={missing}")
if missing:
    print(f"[WARN] 텍스처를 찾지 못했습니다 — 스프라이트 색이 빠집니다: {missing}")

bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="POSE")
# 🛑 Blender 5.x 에는 `Bone.select` 가 없다(실측: AttributeError). 아래 bake 는
# `only_selected=False` 라 선택 상태와 무관하므로 선택 루프 자체가 불필요하다.

# ── 1) 액션마다 visual keying 으로 베이크 ────────────────────────────────
# 🛑 `clear_constraints=True` 를 여기서 주면 안 된다 — 첫 액션에서 IK 제약이 사라져
# 나머지 액션이 다리 없는 포즈로 구워진다. 제약 제거는 **전부 베이크한 뒤** 한 번에.
actions = [a for a in bpy.data.actions]
print(f"[INFO] actions={[a.name for a in actions]}")

for act in actions:
    if rig.animation_data is None:
        rig.animation_data_create()
    rig.animation_data.action = act
    slots = getattr(rig.animation_data, "action_suitable_slots", None)
    if slots:
        rig.animation_data.action_slot = slots[0]
    fs, fe = act.frame_range
    fs, fe = int(fs), int(fe)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = fs, fe
    try:
        bpy.ops.nla.bake(frame_start=fs, frame_end=fe, step=1,
                         only_selected=False, visual_keying=True,
                         clear_constraints=False, clear_parents=False,
                         use_current_action=True, bake_types={"POSE"})
        LOG["baked"][act.name] = {"start": fs, "end": fe}
        print(f"[OK] baked {act.name} ({fs}~{fe})")
    except Exception as e:
        print(f"[FAIL] bake {act.name}: {e}")
        LOG.setdefault("errors", []).append(f"bake {act.name}: {e}")

# ── 2) 제약 전부 제거 — 베이크가 끝났으니 이중 적용을 막는다 ────────────────
ncons = 0
for pb in rig.pose.bones:
    for c in list(pb.constraints):
        pb.constraints.remove(c)
        ncons += 1
LOG["removed"]["constraints"] = ncons
print(f"[INFO] constraints removed={ncons}")

# ── 3) 세우기 판정용 `head` 본 — 이미 서 있는 액터가 눕혀지는 것을 막는다 ────
# `_sheet_render.py` 는 head 본과 foot 본의 **실제 위치**로 세울지 말지를 정한다
# (`_upright_by_bones`). 발→머리 벡터가 이미 +Z 면 "서있음(보정 불필요)" 로 끝난다.
bpy.ops.object.mode_set(mode="OBJECT")

FOOT_KEYS = ("foot", "ankle", "toe", "ball")     # _sheet_render.py FOOT_KEYWORDS 와 같아야 한다
fbs = [pb for pb in rig.pose.bones
       if any(k in pb.name.lower() for k in FOOT_KEYS)
       and "ik" not in pb.name.lower() and "ctrl" not in pb.name.lower()]
need_head = "head" not in rig.data.bones
# 🛑 **발 본이 하나도 없는 액터**(드론·호버 유닛 등 비행체)를 위한 분기다. `_upright_by_bones`
# 는 head 와 foot 을 *둘 다* 찾지 못하면 곧바로 False 를 돌려주고, 그러면 mesh bbox 폴백이
# "높이 < 폭×0.7 이면 누운 것" 으로 판정한다. 드론처럼 **넓적한 것이 정상**인 기체는 이
# 규칙에 그대로 걸려 90° 눕혀진 채 구워진다(실측: 높이 0.80 < max(1.60,1.43)×0.7 = 1.12).
# 그래서 지면에 더미 발 본을 세워 "발→머리 = +Z" 를 성립시킨다. 발이 이미 있는 액터
# (사람·거미)는 이 분기를 타지 않으므로 기존 결과가 달라지지 않는다.
need_foot = not fbs

if need_head or need_foot:
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones
    pts = [m.matrix_world @ vv.co for m in meshes for vv in m.data.vertices]
    top = max((p.z for p in pts), default=1.0)
    bottom = min((p.z for p in pts), default=0.0)
    # 🛑 x·y 를 0 으로 두지 않는다 — `_upright_by_bones` 는 **발 본 평균 → head 본** 벡터가
    # +Z 인지로 판정하므로, 발 평균이 원점에서 조금만 치우쳐도 그 각도만큼 액터가 기운 채
    # 구워진다(실측: 15° 기울어짐). head 를 발 평균 바로 위에 세워 벡터를 수직으로 만든다.
    if fbs:
        fx = sum(rig.data.bones[pb.name].head_local.x for pb in fbs) / len(fbs)
        fy = sum(rig.data.bones[pb.name].head_local.y for pb in fbs) / len(fbs)
    elif pts:
        fx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2.0
        fy = (min(p.y for p in pts) + max(p.y for p in pts)) / 2.0
    else:
        fx = fy = 0.0

    parent = (eb.get("spine_02.x") or eb.get("spine_01.x") or eb.get("root.x")
              or eb.get("c_spine_01.x") or eb.get("c_root.x"))

    if need_foot:
        fb = eb.new("foot_ground")       # 이름에 "foot" 이 들어가야 판정에 잡힌다
        fb.head = Vector((fx, fy, bottom))
        fb.tail = Vector((fx, fy, bottom + max(top - bottom, 1e-3) * 0.05))
        fb.use_deform = False            # 스킨에 영향 주지 않는다(판정 전용)
        if parent:
            fb.parent = parent
        LOG["foot_bone"] = {"x": round(fx, 4), "y": round(fy, 4), "z": round(bottom, 4)}
        print(f"[OK] 'foot_ground' 본 추가(비행체 세우기 판정용) z={bottom:.3f}")

    if need_head:
        b = eb.new("head")
        b.head = Vector((fx, fy, top * 0.75))
        b.tail = Vector((fx, fy, top * 1.02))
        b.use_deform = False             # 스킨에 영향 주지 않는다(판정 전용)
        if parent:
            b.parent = parent
        LOG["head_bone"] = {"z_head": round(top * 0.75, 4), "z_tail": round(top * 1.02, 4)}
        print(f"[OK] 'head' 본 추가(세우기 판정용) z={top * 0.75:.3f}→{top * 1.02:.3f}")

    bpy.ops.object.mode_set(mode="OBJECT")

# ── 4) ARP 씬/오브젝트 커스텀 프로퍼티 제거 ──────────────────────────────
# 남겨 두면 ARP 핸들러가 이 파일을 "ARP 리그" 로 인식해 GUI 전용 프로퍼티를 찾다 죽는다.
nprop = 0
for holder in [bpy.context.scene, rig, rig.data] + list(meshes):
    for k in [k for k in list(holder.keys()) if str(k).startswith("arp")]:
        del holder[k]
        nprop += 1
LOG["removed"]["arp_props"] = nprop
print(f"[INFO] arp custom props removed={nprop}")

# 액션은 파일에 남아야 한다(sheet.py 가 내장 애니로 읽는다)
for a in bpy.data.actions:
    a.use_fake_user = True
if rig.animation_data:
    rig.animation_data.action = None

os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=DST)
LOG["ok"] = True
LOG["actions_final"] = [a.name for a in bpy.data.actions]
with open(DST + ".log.json", "w", encoding="utf-8") as f:
    json.dump(LOG, f, ensure_ascii=False, indent=2)
print(f"[DONE] {DST} actions={LOG['actions_final']}")
