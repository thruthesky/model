"""비행체(드론·호버 유닛)형 액터를 Auto-Rig Pro 로 리깅한다.

🛑 **왜 또 다른 경로인가 — 드론에는 다리가 없다.**

| 경로 | 전제 | 드론에서 무슨 일이 나나 |
|---|---|---|
| SKILL.md ④ ARP **Smart** | 메시에서 *사람 몸* 을 찾는다 | 팔·다리·척추가 없어 감지가 성립하지 않는다 |
| non-humanoid `rig_animal_arp.py` | **지면에 닿는 발끝**을 클러스터링해 다리를 센다 | 드론은 떠 있어 접지점이 없다 → 발끝 0개로 `fail()` |

그래서 드론은 **다리를 아예 만들지 않고** ARP `free` 프리셋 + `spine` limb 하나로
몸통만 리깅한다. 실제 비행체는 관절이 없는 **강체** 라 이것이 물리적으로도 옳다 —
드론의 움직임은 관절 굽힘이 아니라 기체 전체의 자세(pitch/roll/yaw)와 부양이다.

거기에 **무기 본(`weapon`) 하나만 따로 붙인다.** 사용자 요구가 "공격할 때 무기를 쏘는
액션" 이므로, 발사 반동으로 포신이 뒤로 밀렸다 돌아오는 움직임이 필요하기 때문이다.
몸통 하나로만 굳히면 기체가 통째로 흔들릴 뿐 "쏜다" 로 읽히지 않는다.

    arp.append_arp(rig_preset='free')      # 빈 ARP 아마추어
    arp.add_limb(limbs_presets='spine')    # 몸통(기체)
    → spine reference bone 을 기체 중심축으로 이동
    → arp.match_to_rig() → arp.bind_to_rig()
    → 무기 영역 정점을 실측해 `weapon` deform 본 + vertex group 을 추가

사용:
    blender --background --python rig_drone_arp.py -- <입력.fbx|.glb> <출력.blend>
      [--front auto|+y|-y] [--weapon-front 0.30] [--weapon-z 0.55] [--no-weapon]
"""
import bpy
import sys
import os
import json
import math
from mathutils import Vector


# ─────────────────────────────── 인자 ───────────────────────────────
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    print("usage: rig_drone_arp.py -- <입력모델> <출력.blend> [--front auto|+y|-y]")
    sys.exit(1)

SRC = os.path.abspath(argv[0])
DST = os.path.abspath(argv[1])

FRONT_MODE = "auto"     # auto = 무기(돌출부) 방향을 정면으로 자동 판정
WEAPON_FRONT = 0.30     # 정면 쪽 이 비율만큼의 깊이 구간을 무기 후보로 본다
WEAPON_Z = 0.55         # 전체 높이의 이 비율보다 **아래**를 무기 후보로 본다(포드는 하부 장착)
WEAPON_MIN = 40         # 무기 정점이 이보다 적으면 무기 본을 만들지 않는다
TARGET_SPAN = 1.6       # 기체 최대 수평 지름(m). 스프라이트는 bbox 프레이밍이라 화면 크기와 무관
MAKE_WEAPON = True

for i, a in enumerate(argv):
    if a == "--front" and i + 1 < len(argv):
        FRONT_MODE = argv[i + 1]
    elif a == "--weapon-front" and i + 1 < len(argv):
        WEAPON_FRONT = float(argv[i + 1])
    elif a == "--weapon-z" and i + 1 < len(argv):
        WEAPON_Z = float(argv[i + 1])
    elif a == "--weapon-min" and i + 1 < len(argv):
        WEAPON_MIN = int(argv[i + 1])
    elif a == "--span" and i + 1 < len(argv):
        TARGET_SPAN = float(argv[i + 1])
    elif a == "--no-weapon":
        MAKE_WEAPON = False

LOG = {"src": SRC, "dst": DST, "steps": [], "errors": []}


def step(name, **kw):
    LOG["steps"].append({"step": name, **kw})
    print(f"[STEP] {name} " + " ".join(f"{k}={v}" for k, v in kw.items()))


def _write_log():
    try:
        with open(DST + ".log.json", "w", encoding="utf-8") as f:
            json.dump(LOG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("로그 기록 실패:", e)


def fail(msg):
    LOG["errors"].append(msg)
    print(f"[FAIL] {msg}")
    _write_log()
    sys.exit(1)


# ── ARP 를 창 없이(background) 돌리기 위한 최소 패치 ─────────────────────────
# 🛑 ARP 는 3D 뷰를 전제한다 — `--background` 에서는 `bpy.context.space_data` 가 None 이라
# `'NoneType' object has no attribute 'overlay'` 로 죽는다. 실제로 뷰를 만지는 곳은
# 표시 설정 한 줄씩 두 함수뿐이므로 그 문장만 no-op 으로 바꿔 모듈에 다시 심는다.
# (rig_animal_arp.py 와 동일한 패치 — 원리는 그쪽 주석 참조)
def _patch_arp_for_background():
    if not bpy.app.background:
        return []
    import inspect
    import sys as _sys
    mods = [m for n, m in list(_sys.modules.items())
            if n.endswith("auto_rig_pro.src.auto_rig") and m is not None]
    done = []
    NEEDLE = "bpy.context.space_data.overlay.show_relationship_lines = False"
    for m in mods:
        for fname in ("_append_arp", "_add_limb"):
            fn = getattr(m, fname, None)
            if fn is None:
                continue
            try:
                src = inspect.getsource(fn)
            except Exception:
                continue
            if NEEDLE not in src:
                continue
            src = src.replace(NEEDLE, "pass  # [patched] background: 3D 뷰 없음")
            lines = src.splitlines()
            pad = len(lines[0]) - len(lines[0].lstrip())
            src = "\n".join(l[pad:] if len(l) >= pad else l for l in lines)
            try:
                exec(compile(src, f"<arp_patch:{fname}>", "exec"), m.__dict__)
                done.append(f"{m.__name__.split('.')[-3]}:{fname}")
            except Exception as e:
                print(f"[WARN] ARP 패치 실패 {fname}: {e}")
    return done


_PATCHED = _patch_arp_for_background()
if bpy.app.background:
    step("arp_background_patch", applied=_PATCHED)


def arp_ctx():
    wm = bpy.context.window_manager
    for w in getattr(wm, "windows", []):
        scr = getattr(w, "screen", None)
        if not scr:
            continue
        for a in scr.areas:
            if a.type == "VIEW_3D":
                rg = next((r for r in a.regions if r.type == "WINDOW"), None)
                if rg:
                    return {"window": w, "area": a, "region": rg,
                            "space_data": a.spaces.active}
    return None


_CTX = arp_ctx()


def arp_op(fn, *a, **kw):
    """ARP 연산자를 3D 뷰 컨텍스트로 감싸 실행."""
    if _CTX:
        with bpy.context.temp_override(**_CTX):
            return fn(*a, **kw)
    return fn(*a, **kw)


def deselect_all():
    """🛑 `bpy.ops.object.select_all` 은 area 컨텍스트를 요구해 background 에서 죽는다."""
    for o in bpy.context.view_layer.objects:
        try:
            o.select_set(False)
        except Exception:
            pass


# ────────────────────────── 0) 씬 비우기 · 임포트 ──────────────────────────
# 🛑 `read_factory_settings()` 는 ARP 확장까지 꺼버린다 — 오브젝트만 지운다.
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

ext = os.path.splitext(SRC)[1].lower()
if ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC, use_image_search=False)
elif ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=SRC)
elif ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=SRC)
else:
    fail(f"지원하지 않는 형식: {ext}")

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if not meshes:
    fail("메시가 없습니다")

for o in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
    bpy.data.objects.remove(o, do_unlink=True)   # 리깅 전 원본이어야 한다

step("import", meshes=len(meshes), polys=sum(len(m.data.polygons) for m in meshes))


# ────────────────────── 1) 메시 정리: 합치기 · 변환 적용 ──────────────────────
deselect_all()
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
mesh = bpy.context.view_layer.objects.active
mesh.name = "drone_body"

bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 바닥이 원점, 중심이 XY 원점 — 스프라이트 렌더의 기준을 통일한다
verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
minz = min(v.z for v in verts)
cx = (min(v.x for v in verts) + max(v.x for v in verts)) / 2.0
cy = (min(v.y for v in verts) + max(v.y for v in verts)) / 2.0
mesh.location.x -= cx
mesh.location.y -= cy
mesh.location.z -= minz
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
w = max(v.x for v in verts) - min(v.x for v in verts)
d = max(v.y for v in verts) - min(v.y for v in verts)
span = max(w, d)
if span > 1e-6:
    s = TARGET_SPAN / span
    mesh.scale = (s, s, s)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
step("normalize", span_before=round(span, 4), target=TARGET_SPAN)

npoly = len(mesh.data.polygons)
if npoly > 60000:
    dec = mesh.modifiers.new("dec", "DECIMATE")
    dec.ratio = max(0.02, 40000.0 / npoly)
    bpy.ops.object.modifier_apply(modifier=dec.name)
step("decimate", polys_before=npoly, polys_after=len(mesh.data.polygons))

verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
H = max(v.z for v in verts)
R = max(math.hypot(v.x, v.y) for v in verts)
YMIN = min(v.y for v in verts)
YMAX = max(v.y for v in verts)
step("bbox", height=round(H, 4), radius=round(R, 4),
     y_range=(round(YMIN, 3), round(YMAX, 3)))


# ────────── 2) 정면축 판정 — 무기가 튀어나온 쪽이 앞이다 ──────────
# 🛑 정면을 상수로 박지 않는다. 드론은 앞뒤가 분명한 액터라, 축을 잘못 잡으면
# **뒤로 날면서 뒤통수로 쏘는** 결과가 나온다(거미는 방사대칭이라 안 보이던 결함).
# 하부(포드가 달리는 높이)에서 y 로 더 멀리 돌출된 쪽을 정면으로 본다.
def detect_front_y():
    low = [v for v in verts if v.z < H * WEAPON_Z]
    if not low:
        return -1.0
    # 하부 정점의 y 분포에서 양끝의 '돌출 정도' 를 비교한다
    ys = sorted(v.y for v in low)
    n = max(1, len(ys) // 20)
    reach_neg = abs(sum(ys[:n]) / n)          # -Y 쪽 평균 돌출
    reach_pos = abs(sum(ys[-n:]) / n)         # +Y 쪽 평균 돌출
    return -1.0 if reach_neg >= reach_pos else 1.0


if FRONT_MODE == "auto":
    FRONT_Y = detect_front_y()
elif FRONT_MODE in ("+y", "y", "1"):
    FRONT_Y = 1.0
else:
    FRONT_Y = -1.0
step("front_axis_detect", mode=FRONT_MODE, front_y=FRONT_Y)


# ─────────────────────────── 3) ARP 리그 만들기 ───────────────────────────
if not hasattr(bpy.ops, "arp"):
    fail("Auto-Rig Pro 가 활성화돼 있지 않습니다")

deselect_all()
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)

arp_op(bpy.ops.arp.append_arp, rig_preset="free")     # 빈 ARP 아마추어
rig = next((o for o in bpy.data.objects
            if o.type == "ARMATURE" and o.name.startswith("rig")), None)
if rig is None:
    rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if rig is None:
    fail("append_arp 후 아마추어를 찾지 못했습니다")
step("append_arp", rig=rig.name)

deselect_all()
bpy.context.view_layer.objects.active = rig
rig.select_set(True)

# 몸통(spine) 하나 — 드론은 강체라 관절 분할이 필요 없다
for _pn, _pv in (("arp_spine_master", False), ("arp_spine_count", 1)):
    try:
        setattr(bpy.context.scene, _pn, _pv)
    except Exception:
        pass
arp_op(bpy.ops.arp.add_limb, limbs_presets="spine")
step("add_limb", limb="spine")


# ──────────────── 4) reference bone 을 기체 중심축으로 이동 ────────────────
deselect_all()
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = rig.data.edit_bones
rig.data.use_mirror_x = False

body_z = H * 0.55                    # 기체 중심 높이
placed, missing = [], []
for nm, head, tail in (
    ("root_ref.x", Vector((0, -FRONT_Y * 0.10 * R, body_z)),
                   Vector((0, FRONT_Y * 0.02 * R, body_z))),
    ("spine_01_ref.x", Vector((0, -FRONT_Y * 0.10 * R, body_z)),
                       Vector((0, FRONT_Y * 0.16 * R, body_z * 1.04))),
):
    b = eb.get(nm)
    if b:
        b.head, b.tail = head, tail
        placed.append(nm)
    else:
        missing.append(nm)

bpy.ops.object.mode_set(mode="OBJECT")
step("place_refs", placed=placed, missing=missing)
if missing:
    fail(f"spine reference bone 이 없습니다: {missing}")


# ──────────────────────── 5) Match to Rig → Bind ────────────────────────
deselect_all()
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
try:
    arp_op(bpy.ops.arp.match_to_rig)
    step("match_to_rig", ok=True)
except Exception as e:
    fail(f"match_to_rig 실패: {e}")

deselect_all()
mesh.select_set(True)                      # 메시를 먼저, 리그를 active 로
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
try:
    arp_op(bpy.ops.arp.bind_to_rig)
    step("bind_to_rig", ok=True)
except Exception as e:
    fail(f"bind_to_rig 실패: {e}")

nvg = len(mesh.vertex_groups)
has_arm_mod = any(m.type == "ARMATURE" for m in mesh.modifiers)
step("verify_bind", vertex_groups=nvg, armature_modifier=has_arm_mod,
     deform_bones=sum(1 for b in rig.data.bones if b.use_deform))
if not has_arm_mod or nvg == 0:
    fail("바인딩이 되지 않았습니다(armature modifier 또는 vertex group 없음)")


# ─────────── 6) 무기 본 — 발사 반동을 표현할 유일한 수단 ───────────
# 🛑 bind **뒤에** 붙인다. match_to_rig 는 ARP 가 관리하는 본만 남기므로 그 전에 넣으면
# 지워진다. deform 본 + vertex group 을 직접 만들어 무기 정점만 이 본에 매단다.
weapon_info = {"made": False}
if MAKE_WEAPON:
    # 정면 쪽으로 가장 돌출되고, 하부에 달린 정점 = 포신·미사일 포드
    depth = (YMAX - YMIN)
    if FRONT_Y < 0:
        y_cut = YMIN + depth * WEAPON_FRONT          # -Y 가 앞 → 앞쪽 = 작은 y
        def is_front(v): return v.y <= y_cut
    else:
        y_cut = YMAX - depth * WEAPON_FRONT
        def is_front(v): return v.y >= y_cut

    idxs = [i for i, vv in enumerate(mesh.data.vertices)
            if is_front(mesh.matrix_world @ vv.co)
            and (mesh.matrix_world @ vv.co).z < H * WEAPON_Z]

    if len(idxs) >= WEAPON_MIN:
        pts = [mesh.matrix_world @ mesh.data.vertices[i].co for i in idxs]
        cx2 = sum(p.x for p in pts) / len(pts)
        cy2 = sum(p.y for p in pts) / len(pts)
        cz2 = sum(p.z for p in pts) / len(pts)
        tip_y = min(p.y for p in pts) if FRONT_Y < 0 else max(p.y for p in pts)

        bpy.ops.object.mode_set(mode="OBJECT")
        deselect_all()
        bpy.context.view_layer.objects.active = rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        eb = rig.data.edit_bones
        wb = eb.get("weapon") or eb.new("weapon")
        # 뿌리는 기체 쪽, 끝은 포구 쪽 — 축이 사격 방향과 같아야 반동이 자연스럽다
        wb.head = Vector((cx2, cy2 - FRONT_Y * 0.10 * R, cz2))
        wb.tail = Vector((cx2, tip_y, cz2))
        if (wb.tail - wb.head).length < 1e-3:
            wb.tail = wb.head + Vector((0, FRONT_Y * 0.05 * R, 0))
        wb.use_deform = True
        parent = None
        for pn in ("spine_01.x", "root.x", "c_spine_01.x", "c_root.x"):
            if pn in eb:
                parent = eb[pn]
                break
        if parent is not None:
            wb.parent = parent
            wb.use_connect = False
        bpy.ops.object.mode_set(mode="OBJECT")

        # vertex group 재배정 — 무기 정점은 weapon 본이 100% 로 끌고 간다
        for g in mesh.vertex_groups:
            if g.name != "weapon":
                try:
                    g.remove(idxs)
                except Exception:
                    pass
        vg = mesh.vertex_groups.get("weapon") or mesh.vertex_groups.new(name="weapon")
        vg.add(idxs, 1.0, "REPLACE")

        weapon_info = {"made": True, "verts": len(idxs),
                       "head": [round(cx2, 3), round(cy2 - FRONT_Y * 0.10 * R, 3), round(cz2, 3)],
                       "tail": [round(cx2, 3), round(tip_y, 3), round(cz2, 3)]}
    else:
        weapon_info = {"made": False, "verts": len(idxs),
                       "reason": f"무기 후보 정점이 {len(idxs)}개로 최소 {WEAPON_MIN} 미만"}

step("weapon_bone", **weapon_info)
LOG["weapon"] = weapon_info

# 정면축을 리그에 남긴다 — anim_drone.py 가 이것을 읽어 전진·사격 방향을 정한다.
# 여기가 이 값의 유일한 출처다(rig_animal_arp.py §FRONT_Y 와 같은 원칙).
rig["laryen_front_y"] = FRONT_Y
rig["laryen_actor_kind"] = "drone"
step("front_axis", front_y=FRONT_Y)

os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=DST)
LOG["ok"] = True
LOG["rig"] = rig.name
LOG["mesh"] = mesh.name
LOG["bones"] = [b.name for b in rig.data.bones if b.use_deform]
_write_log()
print(f"[DONE] {DST}")

if _CTX:
    bpy.ops.wm.quit_blender()
