"""비행체(드론)의 **후미 엔진 점화 발광**을 3D 씬에 추가한다.

🛑 **왜 런타임이 아니라 3D 인가** — 라리엔의 전투 VFX 채널은 `ground` 와 `foreground` 둘뿐이라
**몹 *뒤* 에 그리는 층이 없다**(`combat_vfx_system.dart`). 런타임으로 불빛을 얹으면 기체 *위* 에
겹쳐 "뒤에서 뿜는 추진 화염" 으로 읽히지 않는다. 3D 에 두면 8방향 위치·가림이 렌더에서
자동으로 맞는다(정면을 볼 땐 엔진이 기체에 가려지고, 뒤를 볼 땐 크게 보인다 — 이게 정답이다).

**뒤쪽을 어떻게 아는가**: 리깅이 기록한 `laryen_front_y` 를 읽는다(`rig_drone_arp.py` 가 무기가
튀어나온 쪽을 정면으로 자동 판정해 리그에 남긴다). 정면이 −Y 면 **후미는 +Y** 다.
🛑 이 값을 여기에 상수로 쓰지 않는다 — 리깅이 정하고 여기서는 읽기만 한다(anim_drone.py 와 동일 규약).

**본에 붙인다**: 발광 오브젝트를 몸통 본에 bone-parent 하므로 기체가 기울고 반동할 때 함께
움직인다. 부수 효과로 `_sheet_render.py` 가 `parent_type == 'BONE'` 메시를 **framing 에서 제외**해
(무기와 같은 취급) 셀 크기가 커지지 않고, `_foot` 마스크에도 들어가지 않아 **발 정렬에 영향이 없다**.

사용:
    blender --background <입력.blend> --python add_engine_glow.py -- <출력.blend>
        [--strength 22] [--radius-ratio 0.055] [--color 1,0.13,0.04] [--pair-gap 0.22]
"""
import bpy
import sys
import os
import json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("usage: blender --background <입력.blend> --python add_engine_glow.py -- <출력.blend>")
    sys.exit(1)

DST = os.path.abspath(argv[0])
# 🛑 emission 세기를 올린다고 잘 보이는 게 아니다 — 너무 높이면 R·G·B 가 전부 클리핑되어
#    **빨강이 흰색으로 타 버린다**(실측: 22 로 굽자 노즐이 흰 타원이 됐다). 색을 살리려면
#    4 안팎에서 시작해 눈으로 조정한다.
STRENGTH = 3.2           # emission 세기
# 🛑 128px 셀로 줄어드는 것을 감안해 크게 잡는다 — 동체 폭의 3% 로 구웠더니 화면에서
#    **2px 짜리 점**이라 사실상 안 보였다(실측).
RADIUS_RATIO = 0.058     # 발광 구 반지름 = **동체** 폭 × 이 값
COLOR = (1.0, 0.06, 0.02)   # 빨강 (세기를 곱해도 G·B 가 안 뜨도록 낮게 잡는다)
PAIR_GAP = 0.34          # 좌우 노즐 간격 = **동체** 폭 × 이 값
BACK_RATIO = 0.96        # 후미 위치 = **동체** 뒤쪽 끝의 이 비율
Z_RATIO = 0.52           # 노즐 높이 = 기체 높이 × 이 값
CORE_RATIO = 0.22        # 동체로 볼 |x| 범위 = 전체 폭 × 이 값 (로터 암 제외)

for i, a in enumerate(argv):
    if a == "--strength" and i + 1 < len(argv):
        STRENGTH = float(argv[i + 1])
    elif a == "--radius-ratio" and i + 1 < len(argv):
        RADIUS_RATIO = float(argv[i + 1])
    elif a == "--color" and i + 1 < len(argv):
        COLOR = tuple(float(x) for x in argv[i + 1].split(","))
    elif a == "--pair-gap" and i + 1 < len(argv):
        PAIR_GAP = float(argv[i + 1])
    elif a == "--back-ratio" and i + 1 < len(argv):
        BACK_RATIO = float(argv[i + 1])
    elif a == "--z-ratio" and i + 1 < len(argv):
        Z_RATIO = float(argv[i + 1])

LOG = {"dst": DST}

rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if rig is None:
    print("[FAIL] 아마추어가 없습니다")
    sys.exit(1)

# 본체 메시 — ARP 컨트롤러 위젯(cs_*)과 이미 붙인 발광은 제외
meshes = [o for o in bpy.data.objects
          if o.type == "MESH"
          and not o.name.lower().startswith("cs_")
          and not o.name.startswith("engine_glow")]
if not meshes:
    print("[FAIL] 본체 메시가 없습니다")
    sys.exit(1)

# 🛑 정면축은 리깅이 정한다 — 여기서는 읽기만 한다(없으면 −Y 폴백).
FRONT_Y = float(rig.get("laryen_front_y", -1.0))
BACK_Y = -FRONT_Y            # 후미 방향 부호
print(f"[INFO] front_y={FRONT_Y:+.0f} → 후미는 {'+Y' if BACK_Y > 0 else '−Y'} 쪽")

pts = [m.matrix_world @ v.co for m in meshes for v in m.data.vertices]
xs = [p.x for p in pts]
ys = [p.y for p in pts]
zs = [p.z for p in pts]
W = max(xs) - min(xs)
D = max(ys) - min(ys)
H = max(zs) - min(zs)

# 🛑 **전체 bbox 의 뒤쪽 끝을 후미로 삼으면 안 된다** — 쿼드콥터는 로터 암이 앞뒤로 뻗어
#    있어 bbox y 끝은 **로터 날 끝**이고, 거기에 노즐을 놓으면 **동체에서 떨어진 허공**에
#    발광이 뜬다(실측: 첫 두 번 다 기체 옆 허공에 찍혔다).
#    중앙(|x| 가 작은) 정점만 모아 **동체의 후미**를 찾는다.
core = [p for p in pts if abs(p.x) < W * CORE_RATIO]
if len(core) < 50:                      # 동체를 못 고르면 전체로 폴백
    core = pts
core_xs = [p.x for p in core]
core_ys = [p.y for p in core]
core_w = max(core_xs) - min(core_xs)
back_y = (max(core_ys) if BACK_Y > 0 else min(core_ys)) * BACK_RATIO
cz = min(zs) + H * Z_RATIO
radius = core_w * RADIUS_RATIO
gap = core_w * PAIR_GAP

print(f"[INFO] bbox W={W:.3f} D={D:.3f} H={H:.3f} · 동체폭={core_w:.3f}(정점 {len(core)}) "
      f"→ 노즐 y={back_y:.3f} z={cz:.3f} r={radius:.3f} gap=±{gap:.3f}")

# ── emission 머티리얼 ────────────────────────────────────────────────
mat = bpy.data.materials.new("engine_glow_mat")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out = nt.nodes.new("ShaderNodeOutputMaterial")
em = nt.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (COLOR[0], COLOR[1], COLOR[2], 1.0)
em.inputs["Strength"].default_value = STRENGTH
nt.links.new(em.outputs["Emission"], out.inputs["Surface"])

# 붙일 본 — 몸통 deform 본(없으면 아무 deform 본)
bone_name = None
for cand in ("spine_01.x", "root.x", "c_spine_01.x", "c_root.x"):
    if cand in rig.data.bones:
        bone_name = cand
        break
if bone_name is None:
    df = [b.name for b in rig.data.bones if b.use_deform]
    bone_name = df[0] if df else rig.data.bones[0].name
print(f"[INFO] parent bone = {bone_name}")

# 🛑 **bone-parent 를 쓰지 않는다.** 그 경로는 자식 원점이 본의 *tail* 기준이 되어
#    `matrix_parent_inverse` 를 정확히 물려야 하는데, rest 와 pose 행렬을 헷갈리면 노즐이
#    **기체 바깥으로 날아간다**(실측: 첫 시도에서 기체 왼쪽 허공에 찍혔다).
#    대신 **본체 메시에 join 하고 몸통 본 vertex group 에 100% 로 넣는다** — 이미 검증된
#    armature modifier 경로를 그대로 타므로 기체가 기울고 반동할 때 정확히 따라온다.
#    머티리얼은 슬롯이 따로 유지되므로 emission 이 살아 있다.
body = max(meshes, key=lambda m: len(m.data.vertices))   # 본체 = 정점이 가장 많은 메시
n_before = len(body.data.vertices)

made = []
for i, sx in enumerate((-gap, +gap)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=12, ring_count=8,
                                         location=(sx, back_y, cz))
    ob = bpy.context.active_object
    ob.name = f"engine_glow_{i}"
    ob.data.materials.append(mat)
    ob.scale = (1.0, 0.65, 1.0)          # 살짝 눌러 구가 아니라 노즐 원반처럼
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    made.append(ob)

# join — active 가 흡수 대상(body)이어야 한다
for o in bpy.context.view_layer.objects:
    try:
        o.select_set(False)
    except Exception:
        pass
for ob in made:
    ob.select_set(True)
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()

n_after = len(body.data.vertices)
new_idx = list(range(n_before, n_after))
if not new_idx:
    print("[FAIL] join 후 새 정점이 없다 — 발광이 합쳐지지 않았다")
    sys.exit(1)

# 몸통 본에 100% 로 매단다(다른 그룹에서는 뺀다)
for g in body.vertex_groups:
    if g.name != bone_name:
        try:
            g.remove(new_idx)
        except Exception:
            pass
vg = body.vertex_groups.get(bone_name) or body.vertex_groups.new(name=bone_name)
vg.add(new_idx, 1.0, "REPLACE")

LOG["glow"] = {"joined_into": body.name, "verts": len(new_idx), "bone": bone_name,
               "front_y": FRONT_Y, "pos_y": round(back_y, 4), "pos_z": round(cz, 4),
               "radius": round(radius, 4), "strength": STRENGTH, "color": list(COLOR)}
print(f"[OK] engine glow 추가 — 정점 {len(new_idx)}개를 '{body.name}' 에 join, "
      f"vertex group='{bone_name}' 100%")

os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=DST)
LOG["ok"] = True
with open(DST + ".log.json", "w", encoding="utf-8") as f:
    json.dump(LOG, f, ensure_ascii=False, indent=2)
print(f"[DONE] {DST}")
