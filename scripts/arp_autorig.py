#!/usr/bin/env python3
"""ARP Smart 자동 리깅 — 마커 실측부터 Bind 까지 사람 개입 없이 끝낸다.

    🛑 --background 를 **붙이지 않는다**:

    blender <NAME>_norm.blend --python arp_autorig.py -- <출력_rig.blend>

창이 잠깐 뜨지만 스크립트가 알아서 끝내고 닫는다. **완전 자동화다.**

## 🛑🛑 "ARP 는 자동화할 수 없다" 는 오판이다 (2026-09-02 기록)

`blender --background` 에서 첫 연산자가 죽는 것을 보고 **"ARP 는 구조적으로 자동화
불가, 사람이 GUI 에서 해야 한다"** 고 결론낸 적이 있다. **틀렸다.**

    --background 에서:
      bpy.ops.id.get_selected_objects()
        → set_selection_filters() → current_area.spaces
        AttributeError: 'NoneType' object has no attribute 'spaces'

이것은 **`--background` 하나의 제약**이다. ARP 가 3D 뷰 `area` 를 직접 참조하는데
background 에는 area 자체가 없어서다. **GUI 모드로 띄우면 area 가 살아 있어 전부
정상 동작한다** — 이 스크립트가 그 증거다.

**교훈**: 한 실행 모드가 막힌 것과 그 도구가 불가능한 것은 다르다.
"불가능" 이라고 쓰기 전에 **실행 모드를 바꿔 본다.**

## 넘어야 하는 관문 4가지 — 전부 오류 없이 조용히 실패한다

| # | 걸림돌 | 대응 |
|---|---|---|
| 1 | `--background` 에서 `current_area.spaces` → None | **GUI 모드 + `temp_override(window, area, region)`** |
| 2 | `arp.guess_markers` → `AI files are missing` | 마커를 **메시에서 실측**해 `add_marker('EXEC_DEFAULT')` 로 직접 배치 |
| 3 | `go_detect.poll() failed` | `get_selected_objects()` 가 원본을 숨기므로 **`body_temp` 를 active** 로 |
| 4 | `match_to_rig` 후 **EDIT_ARMATURE** 모드로 남아 Bind 가 거부 | **Object 모드 복귀** 후 Bind |

## 🛑 입력은 -Y 정면이어야 한다

ARP Smart 는 **캐릭터가 -Y 를 향한다고 전제**한다. 리깅 전에 +Y 로 돌려 놓으면
뒤통수를 얼굴로 착각해 **몸통·머리 본만 반대로** 심는다(다리는 좌우 대칭이라
정상으로 보여 원인을 찾기 어렵다). Godot 용 180° 회전은 `export_godot_glb.py` 가
리깅·애니가 **끝난 뒤에** 한다.
"""

from __future__ import annotations

import json
import statistics as st
import sys
import traceback

import bpy  # type: ignore


# 마커 이름 → ARP body_part 값 (auto_rig_smart.py:8038-8053)
PARTS = ("neck", "chin", "shoulder", "hand", "root", "foot")


def measure_markers(mesh) -> dict:
    """메시에서 ARP 마커 6개의 좌표를 실측한다.

    🛑 표를 베끼지 말고 **모델마다 다시 잰다.** 헬멧·아머가 있으면 비율이 달라진다.

    재는 법:
      neck     — 어깨 위에서 |x|max 가 **최소**인 z (목이 가장 가늘다)
      chin     — neck 한 단 위, 얼굴 **정면(-Y)** 표면
      shoulder — 몸통 폭 × 0.85, 팔 중심 높이
      hand     — 팔 구간에서 단면 두께가 **꺾이는** x (손목)
      root     — 가랑이. 다리 모은 모델은 탐지가 빗나가므로 **키의 57%** 로 폴백
      foot     — 발 영역의 x 중앙, z 는 키의 5.5%
    """
    vs = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    zs = [v.z for v in vs]
    zmin, zmax = min(zs), max(zs)
    height = zmax - zmin

    n = 100
    bands: list[list] = [[] for _ in range(n)]
    for v in vs:
        bands[min(int((v.z - zmin) / height * n), n - 1)].append(v)

    def xmax(i: int) -> float:
        return max((abs(v.x) for v in bands[i]), default=0.0)

    def ycenter(i: int) -> float:
        b = bands[i]
        return (min(v.y for v in b) + max(v.y for v in b)) / 2 if b else 0.0

    def zcenter(i: int) -> float:
        return zmin + (i + 0.5) * height / n

    # 몸통 폭 — 허리~가슴(45~70%) 구간의 |x|max 중앙값
    torso = st.median([xmax(i) for i in range(int(n * 0.45), int(n * 0.70))])

    # 팔 구간 — 상체에서 몸통의 1.8배를 넘는 밴드
    arm = [i for i in range(int(n * 0.55), n) if xmax(i) > torso * 1.8]
    arm_hi = max(arm) if arm else int(n * 0.78)
    arm_z = st.median([zcenter(i) for i in arm]) if arm else zcenter(int(n * 0.75))
    arm_y = st.median([ycenter(i) for i in arm]) if arm else 0.0
    tip = max((xmax(i) for i in arm), default=torso * 3)

    # 손목 — 팔 정점을 x 로 잘라 단면 두께(dz)가 꺾이는 지점
    av = [v for v in vs
          if arm_z - height * 0.06 < v.z < arm_z + height * 0.06 and abs(v.x) > torso]
    m = 24
    seg: list[list] = [[] for _ in range(m)]
    for v in av:
        t = (abs(v.x) - torso) / max(tip - torso, 1e-6)
        seg[min(int(t * m), m - 1)].append(v)
    thick = [(max(p.z for p in s) - min(p.z for p in s)) if len(s) > 4 else 0.0
             for s in seg]
    wrist_i = m - 1
    for i in range(int(m * 0.55), m - 1):
        if thick[i] > 0 and thick[i + 1] > 0 and thick[i + 1] < thick[i] * 0.86:
            wrist_i = i
            break
    wrist_x = torso + (wrist_i + 0.5) / m * (tip - torso)

    # 목 — 어깨 위에서 |x|max 최소
    cand = [(xmax(i), i) for i in range(arm_hi + 1, int(n * 0.93)) if bands[i]]
    neck_i = min(cand)[1] if cand else int(n * 0.86)

    # 턱 — 목 한 단 위, 정면(-Y) 쪽. 🛑 ARP 규약이 -Y 정면이므로 min(y) 다.
    chin_i = min(neck_i + 2, n - 2)
    chin_b = bands[chin_i] or bands[neck_i]
    chin_y = min(v.y for v in chin_b) * 0.75

    # 가랑이 — 다리 모은 모델에서는 빗나간다. 범위를 벗어나면 비율로 폴백.
    crotch = int(n * 0.52)
    for i in range(int(n * 0.60), int(n * 0.35), -1):
        if len([v for v in bands[i] if abs(v.x) < torso * 0.18]) < 3:
            crotch = i
            break
    root_z = zcenter(crotch)
    if not (height * 0.45 <= root_z <= height * 0.62):
        root_z = height * 0.57

    foot_b = [v for v in vs if v.z < zmin + height * 0.12 and v.x > 0]
    foot_x = st.median([v.x for v in foot_b]) if foot_b else torso * 0.5
    foot_y = st.median([v.y for v in foot_b]) if foot_b else 0.0

    return {
        "height": round(height, 4),
        "torso_w": round(torso, 4),
        "neck": [0.0, round(ycenter(neck_i), 4), round(zcenter(neck_i), 4)],
        "chin": [0.0, round(chin_y, 4), round(zcenter(chin_i), 4)],
        "shoulder": [round(torso * 0.85, 4), round(arm_y, 4), round(arm_z, 4)],
        "hand": [round(wrist_x, 4), round(arm_y, 4), round(arm_z, 4)],
        "root": [0.0, round(ycenter(crotch), 4), round(root_z, 4)],
        "foot": [round(foot_x, 4), round(foot_y, 4), round(zmin + height * 0.055, 4)],
    }


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        print("[autorig] 사용법: blender <입력.blend> --python arp_autorig.py -- <출력_rig.blend>")
        bpy.ops.wm.quit_blender()
        return
    out_path = argv[0]
    log_path = out_path + ".log.json"
    res: dict = {"steps": [], "output": out_path}

    def step(name: str, value) -> None:
        res["steps"].append(f"{name}: {value}")
        print(f"[autorig] {name}: {value}", flush=True)

    def run():
        try:
            # 🛑 GUI 모드라 window/area 가 존재한다. --background 면 여기서 죽는다.
            w = bpy.context.window_manager.windows[0]
            area = next(x for x in w.screen.areas if x.type == "VIEW_3D")
            region = next(r for r in area.regions if r.type == "WINDOW")
            scn = bpy.context.scene

            with bpy.context.temp_override(window=w, area=area, region=region):
                mesh = next(o for o in bpy.data.objects if o.type == "MESH")
                markers = measure_markers(mesh)
                res["markers"] = markers
                step("실측", f"키 {markers['height']} · 몸통폭 {markers['torso_w']}")

                bpy.ops.object.select_all(action="DESELECT")
                mesh.select_set(True)
                bpy.context.view_layer.objects.active = mesh

                # 손가락은 AI 파일 없이 되는 LEGACY 엔진으로(④-A 3번)
                for attr, val in (("arp_smart_fingers_engine", "LEGACY"),
                                  ("arp_fingers_enable", True),
                                  ("arp_smart_sym", True)):
                    try:
                        setattr(scn, attr, val)
                    except Exception:  # noqa: BLE001 — 버전마다 없을 수 있다
                        pass

                step("get_selected_objects", bpy.ops.id.get_selected_objects())

                # 🛑 add_marker 는 modal 이라 EXEC_DEFAULT 로 부르고 좌표를 직접 넣는다
                for part in PARTS:
                    bpy.ops.id.add_marker("EXEC_DEFAULT", body_part=part)
                    obj = bpy.data.objects.get(f"{part}_loc")
                    if obj is None:
                        step(f"marker {part}", "생성 실패")
                        continue
                    obj.location = tuple(markers[part])
                    # 🛑 poll 조건 복구 — get_selected_objects 가 원본을 숨긴다
                    bt = bpy.data.objects.get("body_temp")
                    if bt:
                        bpy.context.view_layer.objects.active = bt
                    step(f"marker {part}", tuple(round(v, 4) for v in obj.location))

                bt = bpy.data.objects.get("body_temp")
                if bt:
                    bpy.context.view_layer.objects.active = bt
                    bt.select_set(True)

                # 🛑 INVOKE_DEFAULT — invoke 에 필수 준비가 들어 있다
                step("go_detect", bpy.ops.id.go_detect("INVOKE_DEFAULT"))
                step("match_to_rig", bpy.ops.arp.match_to_rig())

                # 🛑 match_to_rig 는 EDIT_ARMATURE 로 빠져나온다. 안 되돌리면
                #    다음 object.* 연산자가 전부 poll() failed 로 거부된다.
                if bpy.context.object and bpy.context.object.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")

                rig = next((o for o in bpy.data.objects
                            if o.type == "ARMATURE" and o.name.startswith("rig")), None)
                if rig is None:
                    rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
                res["rig_name"] = rig.name if rig else None

                if rig:
                    # Bind — 메시를 먼저 선택하고 리그를 active 로
                    bpy.ops.object.select_all(action="DESELECT")
                    for o in bpy.data.objects:
                        if o.type == "MESH" and not o.name.startswith("body_temp"):
                            o.hide_set(False)
                            o.select_set(True)
                    rig.hide_set(False)
                    rig.select_set(True)
                    bpy.context.view_layer.objects.active = rig
                    step("bind_to_rig", bpy.ops.arp.bind_to_rig())
                    res["bones"] = len(rig.data.bones)

            bpy.ops.wm.save_as_mainfile(filepath=out_path)
            res["saved"] = True
            step("저장", out_path)
        except Exception as exc:  # noqa: BLE001 — 무엇이든 로그로 남긴다
            res["error"] = f"{type(exc).__name__}: {exc}"
            res["traceback"] = traceback.format_exc()[-1200:]
            print(f"[autorig] [FAIL] {res['error']}", flush=True)

        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=2)
        bpy.ops.wm.quit_blender()
        return None

    # 🛑 타이머로 미룬다 — 스크립트 로드 시점에는 창이 아직 준비되지 않았다.
    bpy.app.timers.register(run, first_interval=2.0)


main()
