#!/usr/bin/env python3
"""Godot 용 GLB 규격 검증 — Blender 없이 순수 Python 으로 돈다.

이 스크립트가 이 파이프라인의 **완료 게이트**다. 종료 코드 0 이 아니면
Godot 에 넣지 않는다.

왜 Blender 없이 만드는가 — Blender 를 띄우면 20~40초가 들고, CI 나 반복 검사에서
그 비용이 그대로 쌓인다. GLB 는 앞부분이 JSON 청크라 표준 라이브러리만으로 읽힌다.

검사하는 것(전부 실패 이력이 있는 항목이다):

  1. 루트 노드에 scale·translation 이 실려 있지 않은가
     → Godot 이 한 번 더 곱해 "1.8m 인데 화면에는 1.2cm" 가 된다
  2. 발바닥이 원점에 있는가 (bbox Y_min ≈ 0)
     → 머리 위가 원점이면 캐릭터가 지면 아래로 매달린다
  3. 키가 사람 크기인가 (bbox 높이 1.6~2.0m)
  4. 본 수가 예산 안인가 (--bones)
  5. 삼각형 수가 예산 안인가
  6. 텍스처 해상도가 예산 안인가
  7. 머티리얼 슬롯이 1개인가 (드로우콜)
  8. 애니메이션 이름이 규격 이름인가 (idle/walk/run/attack/death)
  9. 애니메이션이 실제로 프레임을 갖는가
     → mixamo.com 2프레임짜리 빈 껍데기가 실제로 들어간 적이 있다

사용법:
    python3 verify_godot_glb.py <파일.glb> [--bones 16] [--kind human] [--json]
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

# ── 예산 (SSOT: .claude/skills/game/references/assets-3d.md §4 · SSOT.md §3) ──
BUDGET = {
    # 캐릭터 키. 라리엔은 인간형이므로 1.8m 안팎이어야 한다.
    "height_min": 1.6,
    "height_max": 2.0,
    # 발바닥 원점 허용 오차(미터). 5cm 넘게 뜨거나 잠기면 실패로 본다.
    "origin_tol": 0.05,
    # LOD0 삼각형. 근거리 15개 기준 예산.
    "tris_max": 6000,
    # 캐릭터 albedo 해상도.
    "tex_max": 1024,
    # 머티리얼 슬롯. 늘면 드로우콜이 그만큼 늘어난다.
    "materials_max": 1,
}

# 규격 애니메이션 이름. 이 이름이어야 Godot AnimationTree 가 문자열 경로로 찾는다.
ACTIONS_HUMAN = ("idle", "walk", "run", "attack", "death")
ACTIONS_MOB = ("idle", "walk", "attack", "death")

# RESET 은 Godot 블렌딩의 기준 포즈다(assets-3d.md §5). 있어야 정상.
RESET_NAME = "RESET"


def load_gltf_json(path: Path) -> dict:
    """GLB 의 JSON 청크만 읽는다. 바이너리 청크는 건드리지 않는다."""
    with path.open("rb") as f:
        head = f.read(12)
        if len(head) < 12:
            raise ValueError("파일이 너무 짧다 — GLB 가 아니다")
        magic, _version, _length = struct.unpack("<III", head)
        if magic != 0x46546C67:  # 'glTF'
            raise ValueError("magic 이 glTF 가 아니다 — .gltf(텍스트)이거나 다른 포맷이다")
        chunk_len, chunk_type = struct.unpack("<II", f.read(8))
        if chunk_type != 0x4E4F534A:  # 'JSON'
            raise ValueError("첫 청크가 JSON 이 아니다")
        return json.loads(f.read(chunk_len).decode("utf-8"))


def quat_to_matrix(q: list[float]) -> list[list[float]]:
    """glTF 쿼터니언 [x,y,z,w] → 3x3 회전 행렬."""
    x, y, z, w = q
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def node_matrix(node: dict) -> list[list[float]]:
    """노드의 TRS 를 4x4 행렬로. matrix 가 직접 있으면 그것을 쓴다."""
    if "matrix" in node:
        m = node["matrix"]  # glTF 는 column-major
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = node.get("translation", [0.0, 0.0, 0.0])
    r = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    s = node.get("scale", [1.0, 1.0, 1.0])
    rot = quat_to_matrix(r)
    return [
        [rot[0][0] * s[0], rot[0][1] * s[1], rot[0][2] * s[2], t[0]],
        [rot[1][0] * s[0], rot[1][1] * s[1], rot[1][2] * s[2], t[1]],
        [rot[2][0] * s[0], rot[2][1] * s[1], rot[2][2] * s[2], t[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transform_point(m: list[list[float]], p: list[float]) -> list[float]:
    return [
        m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3],
        m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3],
        m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3],
    ]


IDENTITY = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def world_bbox(g: dict) -> tuple[list[float], list[float], int, int]:
    """씬 전체의 월드 bbox 와 정점·삼각형 합계.

    accessor 의 min/max(8꼭짓점)를 노드 변환으로 옮겨 감싼다. 정점을 전부 읽지
    않으므로 빠르고, 회전이 섞여도 실제 bbox 를 넘지언정 놓치지는 않는다.
    """
    nodes = g.get("nodes", [])
    meshes = g.get("meshes", [])
    accessors = g.get("accessors", [])
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    tot_v = tot_t = 0

    def walk(idx: int, parent: list[list[float]]) -> None:
        nonlocal tot_v, tot_t
        node = nodes[idx]
        world = mat_mul(parent, node_matrix(node))
        mi = node.get("mesh")
        if mi is not None:
            for prim in meshes[mi].get("primitives", []):
                acc = accessors[prim["attributes"]["POSITION"]]
                tot_v += acc["count"]
                if "indices" in prim:
                    tot_t += accessors[prim["indices"]]["count"] // 3
                else:
                    tot_t += acc["count"] // 3
                amin, amax = acc.get("min"), acc.get("max")
                if not amin or not amax:
                    continue
                for bit in range(8):
                    corner = [amax[k] if (bit >> k) & 1 else amin[k] for k in range(3)]
                    w = transform_point(world, corner)
                    for k in range(3):
                        lo[k] = min(lo[k], w[k])
                        hi[k] = max(hi[k], w[k])
        for c in node.get("children", []):
            walk(c, world)

    scene = g.get("scenes", [{}])[g.get("scene", 0)]
    for root in scene.get("nodes", []):
        walk(root, IDENTITY)
    return lo, hi, tot_v, tot_t


def image_size(g: dict, blob: bytes, img: dict) -> tuple[int, int]:
    """PNG/JPEG 헤더에서 해상도를 읽는다. 못 읽으면 (0,0)."""
    bv_idx = img.get("bufferView")
    if bv_idx is None:
        return (0, 0)
    bv = g["bufferViews"][bv_idx]
    off = bv.get("byteOffset", 0)
    data = blob[off : off + min(bv["byteLength"], 4096)]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return (w, h)
    if data[:2] == b"\xff\xd8":  # JPEG — SOF 마커를 찾는다
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return (w, h)
            i += 2 + struct.unpack(">H", data[i + 2 : i + 4])[0]
    return (0, 0)


def read_bin_chunk(path: Path) -> bytes:
    """GLB 의 BIN 청크. 이미지 헤더를 읽기 위해서만 쓴다."""
    with path.open("rb") as f:
        f.seek(12)
        while True:
            head = f.read(8)
            if len(head) < 8:
                return b""
            clen, ctype = struct.unpack("<II", head)
            if ctype == 0x004E4942:  # 'BIN'
                return f.read(clen)
            f.seek(clen, 1)


def anim_frame_span(g: dict, anim: dict) -> float:
    """애니메이션의 시간 길이(초). 샘플러 입력 accessor 의 max 를 본다."""
    span = 0.0
    for s in anim.get("samplers", []):
        acc = g["accessors"][s["input"]]
        if acc.get("max"):
            span = max(span, float(acc["max"][0]))
    return span


def main() -> int:
    ap = argparse.ArgumentParser(description="Godot 용 GLB 규격 검증")
    ap.add_argument("glb", type=Path)
    ap.add_argument("--bones", type=int, default=16, choices=(16, 25),
                    help="본 예산. 기본 16(최저)")
    ap.add_argument("--kind", default="human",
                    choices=("human", "animal", "drone", "prop"),
                    help="형태. prop 은 리그·애니 검사를 건너뛴다")
    ap.add_argument("--tris", type=int, default=BUDGET["tris_max"])
    ap.add_argument("--tex", type=int, default=BUDGET["tex_max"])
    ap.add_argument("--json", action="store_true", help="결과를 JSON 으로도 출력")
    args = ap.parse_args()

    if not args.glb.exists():
        print(f"[FAIL] 파일이 없다: {args.glb}")
        return 1

    try:
        g = load_gltf_json(args.glb)
    except Exception as exc:  # noqa: BLE001 — 어떤 파손이든 사람이 읽을 메시지로
        print(f"[FAIL] GLB 를 읽지 못했다: {exc}")
        return 1

    fails: list[str] = []
    warns: list[str] = []
    report: dict = {"file": str(args.glb), "bones_budget": args.bones, "kind": args.kind}

    def ok(msg: str) -> None:
        print(f"[OK  ] {msg}")

    def fail(msg: str) -> None:
        print(f"[FAIL] {msg}")
        fails.append(msg)

    def warn(msg: str) -> None:
        print(f"[WARN] {msg}")
        warns.append(msg)

    # ── 1. 루트 노드에 변환이 실려 있지 않은가 ───────────────────────────────
    # 여기가 "Godot 이 한 번 더 곱한다" 사고의 진원지다.
    nodes = g.get("nodes", [])
    scene = g.get("scenes", [{}])[g.get("scene", 0)]
    roots = scene.get("nodes", [])
    report["roots"] = []
    for ri in roots:
        n = nodes[ri]
        s = n.get("scale")
        t = n.get("translation")
        report["roots"].append({"name": n.get("name"), "scale": s, "translation": t,
                                "rotation": n.get("rotation")})
        if s and any(abs(v - 1.0) > 1e-4 for v in s):
            fail(f"루트 '{n.get('name')}' 에 scale {s} 이 실려 있다 "
                 f"— Blender 에서 Apply Scale 하고 다시 내보낸다")
        if t and any(abs(v) > 1e-4 for v in t):
            warn(f"루트 '{n.get('name')}' 에 translation {t} 이 실려 있다 "
                 f"— 의도한 것이 아니면 Apply 한다")
    if not fails:
        ok(f"루트 노드 {len(roots)}개에 스케일 이중 적용 없음")

    # ── 2·3. 발바닥 원점과 키 ──────────────────────────────────────────────
    lo, hi, verts, tris = world_bbox(g)
    if math.isinf(lo[0]):
        fail("메시가 하나도 없다")
    else:
        height = hi[1] - lo[1]  # glTF 는 Y-up
        report["bbox"] = {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]}
        report["height"] = round(height, 4)
        if abs(lo[1]) <= BUDGET["origin_tol"]:
            ok(f"발바닥이 원점에 있다 (bbox Y_min = {lo[1]:+.4f} m)")
        else:
            where = "지면 아래로 매달려" if lo[1] < 0 else "공중에 떠"
            fail(f"원점이 발바닥이 아니다 — bbox Y_min = {lo[1]:+.4f} m ({where} 있다). "
                 f"Blender 에서 Y 로 {-lo[1]:+.4f} m 옮기고 Apply All Transforms")
        if args.kind in ("human", "animal"):
            if BUDGET["height_min"] <= height <= BUDGET["height_max"]:
                ok(f"키 {height:.3f} m (예산 {BUDGET['height_min']}~{BUDGET['height_max']})")
            else:
                fail(f"키 {height:.3f} m 가 예산 밖이다 "
                     f"({BUDGET['height_min']}~{BUDGET['height_max']}). "
                     f"Blender 에서 {1.8 / height:.4f} 배 스케일 후 Apply")

    # ── 4. 본 수 ──────────────────────────────────────────────────────────
    skins = g.get("skins", [])
    report["skins"] = [{"name": s.get("name"), "joints": len(s["joints"])} for s in skins]
    if args.kind == "prop":
        if skins:
            warn(f"prop 인데 스킨이 {len(skins)}개 있다 — 정적 프롭은 리그가 필요 없다")
        else:
            ok("prop — 리그 없음(정상)")
    elif not skins:
        fail(f"{args.kind} 인데 스킨이 없다 — 리깅되지 않았다")
    else:
        for s in skins:
            n = len(s["joints"])
            if n <= args.bones:
                ok(f"본 {n}개 ≤ 예산 {args.bones}")
            else:
                fail(f"본 {n}개 > 예산 {args.bones} — reduce_bones.py --bones {args.bones} 로 줄인다")
        # 손가락 본은 고정 카메라 거리에서 보이지 않는다(assets-3d.md §4).
        finger = [j for s in skins for j in s["joints"]
                  if any(k in (nodes[j].get("name") or "").lower()
                         for k in ("thumb", "index", "middle", "ring", "pinky"))]
        if finger:
            fail(f"손가락 본이 {len(finger)}개 남아 있다 — 카메라 거리에서 보이지 않는다. 제거한다")

    # ── 5. 삼각형 ─────────────────────────────────────────────────────────
    report["verts"] = verts
    report["tris"] = tris
    if tris <= args.tris:
        ok(f"삼각형 {tris:,} ≤ 예산 {args.tris:,}")
    else:
        fail(f"삼각형 {tris:,} > 예산 {args.tris:,} ({tris / args.tris:.0f}배) "
             f"— Blender Decimate 로 줄인다")

    # ── 6. 텍스처 ─────────────────────────────────────────────────────────
    images = g.get("images", [])
    report["images"] = []
    if images:
        blob = read_bin_chunk(args.glb)
        for i, img in enumerate(images):
            w, h = image_size(g, blob, img)
            report["images"].append({"name": img.get("name"), "size": [w, h]})
            if w == 0:
                warn(f"image[{i}] '{img.get('name')}' 해상도를 읽지 못했다")
            elif max(w, h) > args.tex:
                fail(f"image[{i}] '{img.get('name')}' {w}x{h} > 예산 {args.tex} "
                     f"— {(w * h) / (args.tex ** 2):.0f}배 픽셀. 리사이즈한다")
            else:
                ok(f"image[{i}] {w}x{h} ≤ {args.tex}")

    # ── 7. 머티리얼 슬롯 ──────────────────────────────────────────────────
    mats = g.get("materials", [])
    report["materials"] = len(mats)
    if len(mats) <= BUDGET["materials_max"]:
        ok(f"머티리얼 {len(mats)}개 ≤ {BUDGET['materials_max']}")
    else:
        fail(f"머티리얼 {len(mats)}개 > {BUDGET['materials_max']} "
             f"— 드로우콜이 그만큼 늘어난다. 아틀라스로 합친다")

    # ── 8·9. 애니메이션 ───────────────────────────────────────────────────
    anims = g.get("animations", [])
    names = [a.get("name", "") for a in anims]
    report["animations"] = []
    if args.kind == "prop":
        ok("prop — 애니메이션 검사 생략")
    else:
        want = ACTIONS_HUMAN if args.kind == "human" else ACTIONS_MOB
        for a in anims:
            span = anim_frame_span(g, a)
            name = a.get("name", "")
            report["animations"].append({"name": name, "seconds": round(span, 3)})
            # RESET 은 rest pose 한 프레임짜리가 정상이다 — 길이 검사에서 뺀다.
            if name == RESET_NAME:
                continue
            # 0.2초 미만은 사실상 빈 껍데기다. mixamo.com 2프레임짜리가 실제로 있었다.
            if span < 0.2:
                fail(f"애니 '{name}' 이 {span:.3f}초뿐이다 — 빈 껍데기다. "
                     f"Mixamo 원본이 제대로 임포트됐는지 확인한다")
        missing = [w for w in want if w not in names]
        if missing:
            fail(f"규격 애니가 없다: {', '.join(missing)} "
                 f"(현재: {', '.join(names) if names else '없음'})")
        else:
            ok(f"규격 애니 {len(want)}종 전부 있다")
        junk = [n for n in names if n.startswith("mixamo.com") or n.startswith("Armature")]
        if junk:
            fail(f"애니 이름이 규격이 아니다: {', '.join(junk)} "
                 f"— Godot AnimationTree 가 이름으로 찾으므로 idle/walk/… 로 바꾼다")
        if RESET_NAME not in names:
            warn(f"'{RESET_NAME}' 애니가 없다 — Godot 블렌딩의 기준 포즈다. "
                 f".import 에서 animation/import_rest_as_RESET=true 로도 만들 수 있다")

    # ── 결과 ─────────────────────────────────────────────────────────────
    print()
    size_mb = args.glb.stat().st_size / 1e6
    print(f"파일 {size_mb:.1f} MB · 정점 {verts:,} · 삼각형 {tris:,} · "
          f"본 {report['skins'][0]['joints'] if report['skins'] else 0} · "
          f"머티리얼 {len(mats)} · 애니 {len(anims)}")
    report["size_mb"] = round(size_mb, 2)
    report["fails"] = fails
    report["warns"] = warns

    if args.json:
        out = args.glb.with_suffix(args.glb.suffix + ".verify.json")
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON: {out}")

    if fails:
        print(f"\n🛑 실패 {len(fails)}건 — Godot 에 넣지 않는다")
        return 1
    if warns:
        print(f"\n✅ 통과 (경고 {len(warns)}건)")
        return 0
    print("\n✅ 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
