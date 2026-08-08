"""거미형(방사형 다리 N개) 액터를 Auto-Rig Pro 로 리깅한다.

model 스킬의 ④ 는 humanoid 전용(ARP Smart = 사람 몸 자동 감지)이라 8다리 거미에는 쓸 수 없다.
대신 ARP 의 **`free` 프리셋(빈 아마추어) + `add_limb` 반복** 경로를 쓴다:

    arp.append_arp(rig_preset='free')      # 빈 ARP 아마추어
    arp.add_limb(limbs_presets='spine')    # 몸통
    arp.add_limb(limbs_presets='leg.l') ×N/2
    arp.add_limb(limbs_presets='leg.r') ×N/2
    → reference bone 을 메시에서 실측한 다리 축으로 이동
    → arp.match_to_rig() → arp.bind_to_rig()

🛑 Smart(`id.*`) 연산자를 쓰지 않으므로 model SKILL.md ④-A 의 함정(마커 modal·body_temp
poll 실패·AI 파일 누락)은 이 경로에 해당하지 않는다. background 로 완주한다.

다리 검출은 추정하지 않고 **메시에서 잰다** — 지면 근처 정점을 몸통 중심 기준 방위각으로
히스토그램 내어 봉우리 N 개를 찾고, 각 봉우리 방향의 정점만 모아 그 다리의 축(뿌리→발끝)을
구한다. 다리 개수·좌우 배분은 인자로 받는다.

사용:
    blender --background --python rig_spider_arp.py -- <입력.fbx|.glb> <출력.blend> [--legs 8]
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
    print("usage: rig_spider_arp.py -- <입력모델> <출력.blend> [--legs N] [--body-ratio R]")
    sys.exit(1)

SRC = os.path.abspath(argv[0])
DST = os.path.abspath(argv[1])
LEGS = 0                   # 0 = 발끝 클러스터에서 자동 검출(권장). 양수면 그 개수를 강제.
BODY_RATIO = 0.42          # 몸통 반경 = 최대 반경 × 이 값. 이 밖을 '다리' 로 본다.
FOOT_Z = 0.10              # 발끝으로 볼 높이 상한(전체 높이 대비)
FOOT_SEP = 0.22            # 발끝 클러스터 반경(최대 반경 대비) — 두 발을 가르는 최소 간격
FOOT_MIN = 0                # >0 이면 절대 최소 정점 수를 추가로 강제(기본 0 = 상대 임계만)

for i, a in enumerate(argv):
    if a == "--legs" and i + 1 < len(argv):
        LEGS = 0 if argv[i + 1] == "auto" else int(argv[i + 1])
    elif a == "--body-ratio" and i + 1 < len(argv):
        BODY_RATIO = float(argv[i + 1])
    elif a == "--foot-z" and i + 1 < len(argv):
        FOOT_Z = float(argv[i + 1])
    elif a == "--foot-sep" and i + 1 < len(argv):
        FOOT_SEP = float(argv[i + 1])
    elif a == "--foot-min" and i + 1 < len(argv):
        FOOT_MIN = int(argv[i + 1])

LOG = {"src": SRC, "dst": DST, "legs_requested": LEGS, "steps": [], "errors": []}


def step(name, **kw):
    LOG["steps"].append({"step": name, **kw})
    print(f"[STEP] {name} " + " ".join(f"{k}={v}" for k, v in kw.items()))


def fail(msg):
    LOG["errors"].append(msg)
    print(f"[FAIL] {msg}")
    _write_log()
    sys.exit(1)


def _write_log():
    try:
        with open(DST + ".log.json", "w", encoding="utf-8") as f:
            json.dump(LOG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("로그 기록 실패:", e)


# ── ARP 를 창 없이(background) 돌리기 위한 최소 패치 ─────────────────────────
# 🛑 ARP 는 3D 뷰를 전제한다 — `--background` 에서는 `bpy.context.space_data` 가 None 이라
# `'NoneType' object has no attribute 'overlay'` 로 죽는다. 그런데 실제로 3D 뷰를 만지는
# 곳은 **표시 설정 한 줄씩, 두 함수뿐**이다(실측, auto_rig.py):
#     _add_limb    :10031   overlay.show_relationship_lines = False
#     _append_arp  :12348   overlay.show_relationship_lines = False
# 리깅 결과와 무관한 뷰포트 장식이므로, 그 문장만 no-op 으로 바꿔 모듈에 다시 심는다.
# 🛑 GUI 를 띄우지 않는다 — 사람이 다른 작업 중일 때 Blender 창이 화면을 가로채면 안 된다.
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
            src = inspect.cleandoc("\n".join(src.splitlines()[:1])) and src
            # 최상위 def 로 맞추기 위해 공통 들여쓰기 제거
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
    print(f"[STEP] arp_background_patch applied={_PATCHED}")


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
if _CTX is None:
    print("[WARN] VIEW_3D 컨텍스트 없음(background 실행?) — ARP 연산자가 실패할 수 있다")


def arp_op(fn, *a, **kw):
    """ARP 연산자를 3D 뷰 컨텍스트로 감싸 실행."""
    if _CTX:
        with bpy.context.temp_override(**_CTX):
            return fn(*a, **kw)
    return fn(*a, **kw)


def deselect_all():
    """background 에서도 되는 선택 해제.
    🛑 `bpy.ops.object.select_all` 은 area 컨텍스트를 요구해 `--background` 에서
    `poll() failed, context is incorrect` 로 죽는다(실측). 데이터 API 로 직접 끈다."""
    for o in bpy.context.view_layer.objects:
        try:
            o.select_set(False)
        except Exception:
            pass


def select_only(*objs, active=None):
    deselect_all()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


# ────────────────────────── 0) 씬 비우기 · 임포트 ──────────────────────────
# 🛑 `read_factory_settings()` 를 쓰지 않는다 — preferences 를 초기화하면서 **ARP 확장까지
# 꺼버려** 뒤에서 `bpy.ops.arp.append_arp` 가 "could not be found" 로 죽는다(실측).
# 기본 씬의 오브젝트만 지운다.
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

# 임포트된 armature 는 버린다(리깅 전 원본이어야 한다)
for o in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
    bpy.data.objects.remove(o, do_unlink=True)

step("import", meshes=len(meshes), polys=sum(len(m.data.polygons) for m in meshes))


# ────────────────────── 1) 메시 정리: 합치기 · 변환 적용 ──────────────────────
deselect_all()
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
mesh = bpy.context.view_layer.objects.active
mesh.name = "spider_body"

# 부모·변환을 모두 굳힌다 — 스케일이 1 이 아니면 ARP 가 어긋난다
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Z-up · 발이 원점 · 중심을 XY 원점으로
verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
minz = min(v.z for v in verts)
cx = (min(v.x for v in verts) + max(v.x for v in verts)) / 2.0
cy = (min(v.y for v in verts) + max(v.y for v in verts)) / 2.0
mesh.location.x -= cx
mesh.location.y -= cy
mesh.location.z -= minz
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

# 크기 정규화 — 거미는 '키' 가 아니라 '폭' 이 지배적이라 최대 수평 지름을 기준으로 맞춘다
verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
w = max(v.x for v in verts) - min(v.x for v in verts)
d = max(v.y for v in verts) - min(v.y for v in verts)
h = max(v.z for v in verts) - min(v.z for v in verts)
span = max(w, d)
TARGET_SPAN = 2.0                     # 다리 끝~끝 2m 급 개체로 통일(스프라이트는 bbox 프레이밍이라 무해)
if span > 1e-6:
    s = TARGET_SPAN / span
    mesh.scale = (s, s, s)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
step("normalize", span_before=round(span, 4), scale=round(TARGET_SPAN / span, 4) if span > 1e-6 else 1)

# 폴리곤 감축 — 뷰포트·렌더 속도용(스프라이트라 예산이 헐겁다)
npoly = len(mesh.data.polygons)
if npoly > 60000:
    dec = mesh.modifiers.new("dec", "DECIMATE")
    dec.ratio = max(0.02, 40000.0 / npoly)
    bpy.ops.object.modifier_apply(modifier=dec.name)
step("decimate", polys_before=npoly, polys_after=len(mesh.data.polygons))

verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
H = max(v.z for v in verts)
R = max(math.hypot(v.x, v.y) for v in verts)
step("bbox", height=round(H, 4), radius=round(R, 4))


# ─────────────────── 2) 다리 검출 — 추정하지 않고 메시에서 잰다 ───────────────────
# 🛑 방위각 히스토그램은 쓰지 않는다(실측 실패: 다리 간격이 균등하지 않아 6/8 만 잡혔다).
# 지면에 닿는 **발끝을 XY 로 클러스터링** 하는 편이 훨씬 안정적이다 — 발은 서로 떨어져
# 있고, 다리 개수 자체를 데이터가 알려 준다.
rlim = R * BODY_RATIO
foot_pts = [v for v in verts if v.z < H * FOOT_Z]
clusters = []
sep = R * FOOT_SEP
for v in sorted(foot_pts, key=lambda p: -math.hypot(p.x, p.y)):
    hit = None
    for c in clusters:
        if math.hypot(v.x - c["x"], v.y - c["y"]) < sep:
            hit = c
            break
    if hit:
        hit["n"] += 1
        hit["x"] += (v.x - hit["x"]) / hit["n"]
        hit["y"] += (v.y - hit["y"]) / hit["n"]
        hit["z"] = min(hit["z"], v.z)
    else:
        clusters.append({"x": v.x, "y": v.y, "z": v.z, "n": 1})

# 🛑 절대 개수로 거르지 않는다 — Decimate 로 정점이 줄면 같은 임계가 전멸시킨다(실측:
# 원본 93만 정점에서 4440 이던 발끝 클러스터가 4만 폴리 감축 후 300 미만이 되어 0개가 됐다).
# 가장 큰 클러스터 대비 상대 크기로 판정한다.
outer = [c for c in clusters if math.hypot(c["x"], c["y"]) > rlim]
nmax = max((c["n"] for c in outer), default=0)
thr = max(FOOT_MIN if FOOT_MIN > 0 else 0, int(nmax * 0.18), 8)
feet = [c for c in outer if c["n"] >= thr]
feet.sort(key=lambda c: math.atan2(c["y"], c["x"]))
step("feet_detected", n=len(feet), threshold=thr, nmax=nmax, outer=len(outer),
     pos=[(round(c["x"], 3), round(c["y"], 3), c["n"]) for c in feet])

if LEGS and len(feet) != LEGS:
    print(f"[WARN] 발끝 {len(feet)}개 검출(요청 {LEGS}) → 검출값을 따른다")
if len(feet) < 4:
    fail(f"발끝을 {len(feet)}개만 찾았습니다 — --foot-z/--foot-sep/--foot-min 을 조정하세요")
LEGS = len(feet)
LOG["legs_detected"] = LEGS


def leg_axis(foot):
    """발끝 하나를 기준으로 그 다리의 뿌리·무릎·발끝 좌표를 메시에서 만든다."""
    ang = math.degrees(math.atan2(foot["y"], foot["x"])) % 360.0
    sector = min(34.0, 360.0 / LEGS * 0.5)      # 이웃 다리를 삼키지 않을 만큼만
    sel = []
    for v in verts:
        r = math.hypot(v.x, v.y)
        if r < rlim * 0.75:
            continue
        a = math.degrees(math.atan2(v.y, v.x)) % 360.0
        dd = min(abs(a - ang), 360 - abs(a - ang))
        if dd <= sector:
            sel.append((r, v))
    if not sel:
        return None
    sel.sort(key=lambda t: t[0])
    reach = sel[-1][0]
    tip = Vector((foot["x"], foot["y"], max(foot["z"], 0.0)))

    # 뿌리: 몸통 경계 부근(그 방향) 정점 평균 — 다리가 몸통에 붙는 지점
    root_pool = [v for r, v in sel if r <= rlim * 1.3]
    if root_pool:
        root = Vector((sum(v.x for v in root_pool) / len(root_pool),
                       sum(v.y for v in root_pool) / len(root_pool),
                       sum(v.z for v in root_pool) / len(root_pool)))
    else:
        root = Vector((sel[0][1].x, sel[0][1].y, sel[0][1].z))

    # 무릎: 거미 다리는 몸통에서 **위로 솟았다가** 내려온다 → 중간 반경대의 최고점
    mid = [v for r, v in sel if rlim * 1.15 < r < reach * 0.72]
    knee = max(mid, key=lambda v: v.z) if mid else (root + tip) * 0.5
    return {"root": root, "knee": knee, "tip": tip, "ang": ang, "reach": reach}


legs = []
for f in feet:
    ax = leg_axis(f)
    if ax:
        legs.append(ax)
if len(legs) != LEGS:
    fail(f"다리 축을 {len(legs)}개만 만들었습니다(발끝 {LEGS}개)")

step("leg_axes", n=len(legs),
     ang=[round(l["ang"], 1) for l in legs],
     reach=[round(l["reach"], 3) for l in legs],
     knee_z=[round(l["knee"].z, 3) for l in legs])


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
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
step("append_arp", rig=rig.name)

deselect_all()
bpy.context.view_layer.objects.active = rig
rig.select_set(True)

# 몸통(spine) — 거미는 머리·배가 수평으로 놓이므로 spine 1개로 충분하다
for _pn, _pv in (("arp_spine_master", False), ("arp_spine_count", 1)):
    try:
        setattr(bpy.context.scene, _pn, _pv)   # 버전마다 없을 수 있는 옵션 — 있으면 쓴다
    except Exception:
        pass
arp_op(bpy.ops.arp.add_limb, limbs_presets="spine")
step("add_limb", limb="spine")

# 다리: 좌우 번갈아 배분(ARP 는 side 로 .l/.r 을 구분하고 같은 side 는 dupli 인덱스가 붙는다)
#   ARP 규약: 첫 leg.l → thigh_ref.l · 두번째 → thigh_ref_dupli_001.l …
lefts = [l for l in legs if math.sin(math.radians(l["ang"])) >= 0]
rights = [l for l in legs if math.sin(math.radians(l["ang"])) < 0]
# 좌우 개수를 맞춘다(홀수면 각도 기준으로 넘긴다)
while len(lefts) > LEGS // 2:
    rights.append(lefts.pop())
while len(rights) > LEGS // 2:
    lefts.append(rights.pop())
lefts.sort(key=lambda l: l["ang"])
rights.sort(key=lambda l: l["ang"])
step("leg_sides", left=len(lefts), right=len(rights))

for _ in lefts:
    arp_op(bpy.ops.arp.add_limb, limbs_presets="leg.l")
for _ in rights:
    arp_op(bpy.ops.arp.add_limb, limbs_presets="leg.r")
step("add_limb", limb="leg", left=len(lefts), right=len(rights))


# ──────────────── 4) reference bone 을 실측 다리 축으로 이동 ────────────────
def ref_names(side, idx):
    """ARP dupli 규약: 0번은 접미사 없음, 1번부터 _dupli_00N."""
    suf = side if idx == 0 else f"_dupli_{idx:03d}{side}"
    return {
        "thigh": ("thigh_ref" + suf),
        "calf": ("leg_ref" + suf),
        "foot": ("foot_ref" + suf),
        "toes": ("toes_ref" + suf),
        "toes_end": ("toes_end_ref" + suf),
        "heel": ("foot_heel_ref" + suf),
        "bank1": ("foot_bank_01_ref" + suf),
        "bank2": ("foot_bank_02_ref" + suf),
    }


deselect_all()
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = rig.data.edit_bones
rig.data.use_mirror_x = False

placed, missing = [], []

# 몸통 spine — 앞(−Y)이 정면이 되게 배치. 거미 몸통은 낮고 길다.
body_top = max(v.z for v in verts if math.hypot(v.x, v.y) < rlim) if any(
    math.hypot(v.x, v.y) < rlim for v in verts) else H * 0.6
body_z = body_top * 0.62
for nm, head, tail in (
    ("root_ref.x", Vector((0, 0.06 * R, body_z)), Vector((0, -0.02 * R, body_z))),
    ("spine_01_ref.x", Vector((0, 0.06 * R, body_z)), Vector((0, -0.10 * R, body_z * 1.05))),
):
    b = eb.get(nm)
    if b:
        b.head, b.tail = head, tail
        placed.append(nm)
    else:
        missing.append(nm)


def place_leg(ax, side, idx):
    n = ref_names(side, idx)
    root, knee, tip = ax["root"], ax["knee"], ax["tip"]
    # 거미 다리: 뿌리(몸통) → 무릎(높은 관절) → 발목(지면 근처) → 발끝
    ankle = Vector((tip.x * 0.82, tip.y * 0.82, max(tip.z, H * 0.06)))
    toe_end = Vector((tip.x, tip.y, max(tip.z * 0.5, 0.0)))
    layout = {
        n["thigh"]: (root, knee),
        n["calf"]: (knee, ankle),
        n["foot"]: (ankle, Vector((tip.x * 0.94, tip.y * 0.94, max(tip.z * 0.55, 0.0)))),
        n["toes"]: (Vector((tip.x * 0.94, tip.y * 0.94, max(tip.z * 0.55, 0.0))), toe_end),
    }
    ok = 0
    for bn, (hd, tl) in layout.items():
        b = eb.get(bn)
        if not b:
            missing.append(bn)
            continue
        if (tl - hd).length < 1e-4:
            tl = hd + Vector((0, 0, 0.01))
        b.head, b.tail = hd, tl
        placed.append(bn)
        ok += 1
    # 발 보조 본(heel·bank)은 발 주변으로 모아 둔다 — 없으면 match 가 튄다
    dirv = Vector((math.cos(math.radians(ax["ang"])), math.sin(math.radians(ax["ang"])), 0))
    perp = Vector((-dirv.y, dirv.x, 0))
    for bn, off in ((n["heel"], -dirv * 0.05), (n["bank1"], -perp * 0.05), (n["bank2"], perp * 0.05)):
        b = eb.get(bn)
        if b:
            base = Vector((ankle.x, ankle.y, 0.0)) + off
            b.head = base
            b.tail = base + dirv * 0.04
            placed.append(bn)
    return ok


for i, ax in enumerate(lefts):
    place_leg(ax, ".l", i)
for i, ax in enumerate(rights):
    place_leg(ax, ".r", i)

bpy.ops.object.mode_set(mode="OBJECT")
step("place_refs", placed=len(placed), missing=len(missing),
     missing_sample=sorted(set(missing))[:12])


# ──────────────────────── 5) Match to Rig → Bind ────────────────────────
deselect_all()
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
try:
    arp_op(bpy.ops.arp.match_to_rig)
    step("match_to_rig", ok=True, has_match=bool(rig.data.get("has_match_to_rig", True)))
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

os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=DST)
LOG["ok"] = True
LOG["rig"] = rig.name
LOG["mesh"] = mesh.name
_write_log()
print(f"[DONE] {DST}")

if _CTX:            # GUI 로 띄운 경우 스크립트 종료 후 Blender 를 닫는다
    bpy.ops.wm.quit_blender()
