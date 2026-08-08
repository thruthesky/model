"""거미형 메시의 다리 분포를 실측한다(추정 금지 — 배치 전에 반드시 눈으로 확인할 값).

blender --background --python measure_legs.py -- <모델>
"""
import bpy, sys, os, math, json

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC = os.path.abspath(argv[0])

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(SRC)[1].lower()
if ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=SRC, use_image_search=False)
else:
    bpy.ops.import_scene.gltf(filepath=SRC)

ms = [o for o in bpy.data.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for m in ms:
    m.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1:
    bpy.ops.object.join()
mesh = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

V = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
minz = min(v.z for v in V)
cx = (min(v.x for v in V) + max(v.x for v in V)) / 2
cy = (min(v.y for v in V) + max(v.y for v in V)) / 2
V = [(v.x - cx, v.y - cy, v.z - minz) for v in V]
H = max(v[2] for v in V)
R = max(math.hypot(v[0], v[1]) for v in V)
print(f"[MEASURE] verts={len(V)} H={H:.4f} R={R:.4f} "
      f"W={max(v[0] for v in V)-min(v[0] for v in V):.4f} "
      f"D={max(v[1] for v in V)-min(v[1] for v in V):.4f}")

# z 층별 수평 퍼짐 — 어디까지가 다리이고 어디부터가 몸통인지
print("[LAYERS] z%   count   maxR    meanR")
for i in range(20):
    lo, hi = H * i / 20, H * (i + 1) / 20
    sel = [v for v in V if lo <= v[2] < hi]
    if sel:
        rs = [math.hypot(v[0], v[1]) for v in sel]
        print(f"   {i*5:3d}% {len(sel):7d}  {max(rs):.3f}  {sum(rs)/len(rs):.3f}")

# 발끝 클러스터링 — 지면 근처 정점을 XY 로 그리디 묶음
for zr in (0.08, 0.12, 0.18, 0.25):
    foot = [v for v in V if v[2] < H * zr]
    if not foot:
        continue
    clusters = []
    rad = R * 0.22
    for v in sorted(foot, key=lambda p: -math.hypot(p[0], p[1])):
        hit = None
        for c in clusters:
            if math.hypot(v[0] - c["x"], v[1] - c["y"]) < rad:
                hit = c
                break
        if hit:
            hit["n"] += 1
            hit["x"] = (hit["x"] * (hit["n"] - 1) + v[0]) / hit["n"]
            hit["y"] = (hit["y"] * (hit["n"] - 1) + v[1]) / hit["n"]
        else:
            clusters.append({"x": v[0], "y": v[1], "n": 1})
    big = [c for c in clusters if c["n"] >= 12]
    print(f"[FEET] z<{zr:.2f}H pts={len(foot)} clusters={len(clusters)} big={len(big)} "
          + " ".join(f"({c['x']:.2f},{c['y']:.2f},n={c['n']})" for c in sorted(big, key=lambda c: math.atan2(c['y'], c['x']))))
