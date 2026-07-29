"""
GLB 를 게임 엔진에 넣기 전에 **조용한 실패 요인을 전부 실측**한다.

왜 필요한가 — glTF 로더는 잘못된 입력에 대해 예외를 던지지 않는다. 정점당 본
영향이 5개면 다섯 번째부터 무시하고, 삼각형이 아닌 프리미티브는 통째로 건너뛰고,
애니메이션 이름이 다르면 클립이 0개가 된다. **전부 "로드는 됐는데 이상하다" 로
나타나므로**, 화면을 보기 전에 파일을 직접 뜯어보는 것이 유일한 방어다.

Blender 없이 순수 Python 으로 돈다(GLB 컨테이너 + JSON 청크만 읽는다).

사용법:
  python3 inspect_glb.py <파일.glb> [--verbose]

종료 코드: 0 = 전부 통과, 1 = 하나 이상 실패
"""
import json
import struct
import sys

# 정점당 본 영향 한도. glTF 는 JOINTS_1 로 8개까지 허용하지만 대부분의 경량
# 런타임(flutter_scene 포함)은 JOINTS_0 한 세트만 읽는다.
MAX_INFLUENCE_SET = "JOINTS_1"

# 삼각형 이외의 토폴로지는 스킵되는 일이 많다. glTF 의 mode 4 = TRIANGLES.
TRIANGLES = 4

# 이 값보다 크게 움직이는 translation 채널이 있으면 root motion 으로 본다.
# 게임에서 캐릭터를 이동시키는 것은 보통 부모 노드이므로, 클립에도 이동이 있으면
# 두 배로 움직인다.
ROOT_MOTION_EPS = 0.001


def read_glb(path):
    """GLB 컨테이너에서 JSON 청크와 BIN 청크를 꺼낸다."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        raise ValueError(f"{path} 는 GLB 가 아니다(매직 불일치)")

    doc = None
    binary = None
    offset = 12
    while offset < len(data):
        length, ctype = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8: offset + 8 + length]
        if ctype == 0x4E4F534A:      # 'JSON'
            doc = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:    # 'BIN'
            binary = chunk
        offset += 8 + length + ((4 - length % 4) % 4)

    if doc is None:
        raise ValueError("JSON 청크가 없다")
    return doc, binary


def read_accessor(doc, binary, index):
    """accessor 를 float 튜플 리스트로 읽는다(애니메이션 샘플러 전용)."""
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    values = struct.unpack_from("<" + "f" * (count * ncomp), binary, start)
    return [values[i * ncomp:(i + 1) * ncomp] for i in range(count)]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    verbose = "--verbose" in sys.argv
    if not args:
        print("사용법: python3 inspect_glb.py <파일.glb> [--verbose]")
        sys.exit(2)

    path = args[0]
    doc, binary = read_glb(path)
    failures = []

    def check(name, ok, detail=""):
        mark = "OK  " if ok else "FAIL"
        print(f"[{mark}] {name} {detail}")
        if not ok:
            failures.append(name)

    print(f"=== {path} ===")

    # ── 애니메이션 이름 ──
    # 엔진의 "이름으로 찾기" API 는 대부분 **정확히 일치**해야 한다. Blender 를
    # 거치면 `Armature|Armature|walk` 처럼 오브젝트 접두사가 붙어 나온다(실측).
    names = [a.get("name", "") for a in doc.get("animations", [])]
    print(f"  애니메이션: {names}")
    check("애니메이션 존재", len(names) > 0)
    dirty = [n for n in names if "|" in n]
    check("애니메이션 이름에 접두사 없음", not dirty, f"({dirty})" if dirty else "")

    # ── 스킨 ──
    check("스킨 존재", len(doc.get("skins", [])) > 0,
          f"({len(doc.get('skins', []))}개)")

    # ── 버퍼 ──
    # 런타임 임포터는 다중 버퍼를 거부하는 일이 많다. GLB 는 보통 1개다.
    check("단일 buffer", len(doc.get("buffers", [])) == 1,
          f"({len(doc.get('buffers', []))}개)")

    # ── 확장 ──
    # Draco 압축은 디코더가 없는 런타임에서 로드 실패로 이어진다.
    required = doc.get("extensionsRequired", [])
    check("필수 확장 없음", not required, f"({required})" if required else "")

    # ── 정점 속성·토폴로지 ──
    has_joints1 = False
    bad_mode = []
    missing_normal = []
    for mi, mesh in enumerate(doc.get("meshes", [])):
        for pi, prim in enumerate(mesh.get("primitives", [])):
            attrs = prim.get("attributes", {})
            if MAX_INFLUENCE_SET in attrs:
                has_joints1 = True
            if prim.get("mode", TRIANGLES) != TRIANGLES:
                bad_mode.append(f"mesh{mi}/prim{pi}")
            if "NORMAL" not in attrs:
                missing_normal.append(f"mesh{mi}/prim{pi}")
            if verbose:
                print(f"    mesh{mi}/prim{pi} attrs={sorted(attrs)} "
                      f"mode={prim.get('mode', TRIANGLES)}")

    check(f"{MAX_INFLUENCE_SET} 없음(정점당 영향 ≤4)", not has_joints1)
    check("전부 삼각형", not bad_mode, f"({bad_mode})" if bad_mode else "")
    check("NORMAL 포함", not missing_normal,
          f"({missing_normal})" if missing_normal else "")

    # ── 텍스처 임베드 ──
    external = [im.get("uri") for im in doc.get("images", [])
                if im.get("uri") and not im["uri"].startswith("data:")]
    check("텍스처 임베드", not external, f"({external})" if external else "")

    # ── 메시 bounds — 발이 원점인가 ──
    # 캐릭터는 발이 로컬 원점에 있어야 지면에 그대로 놓을 수 있다.
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            pos = doc["accessors"][prim["attributes"]["POSITION"]]
            lo = [round(v, 3) for v in pos["min"]]
            hi = [round(v, 3) for v in pos["max"]]
            print(f"  bounds: min={lo} max={hi}  (키 {round(hi[1] - lo[1], 3)})")
            check("발이 원점 근처", abs(lo[1]) < 0.02, f"(min.y={lo[1]})")
            break
        break

    # ── root motion ──
    if binary:
        nodes = doc.get("nodes", [])
        moving = []
        for anim in doc.get("animations", []):
            for ch in anim.get("channels", []):
                if ch["target"].get("path") != "translation":
                    continue
                out = read_accessor(
                    doc, binary, anim["samplers"][ch["sampler"]]["output"])
                if not out:
                    continue
                span = max(
                    max(v[k] for v in out) - min(v[k] for v in out)
                    for k in range(3)
                )
                if span > ROOT_MOTION_EPS:
                    node = nodes[ch["target"]["node"]].get("name", "?")
                    moving.append(f"{anim.get('name')}/{node}={span:.4f}")
        check("root motion 없음", not moving, f"({moving})" if moving else "")

    print(f"\n=== {'전부 통과' if not failures else f'실패 {len(failures)}건: {failures}'} ===")
    sys.exit(0 if not failures else 1)


main()
