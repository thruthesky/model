"""
verify_mixamo_rig.py 의 판정 로직 테스트 — **Blender 없이** 돈다.

    python3 .claude/skills/model/scripts/test_verify_mixamo_rig.py

검사 대상은 `sheet.py` 의 동작을 재현하는 세 함수다. 이것들이 어긋나면 검증이
거짓 통과를 내고, 896장을 다 렌더한 뒤에야 정적 아틀라스를 발견하게 된다.

  - anim_threshold()    : `_sheet_render.py:451` 의 `max(8, int(len(anim)*0.5))`
  - normalize_prefix()  : `_sheet_render.py:430-445` 의 `mixamorig\\d*:` 정규화
  - matched_roles()     : `_sheet_render.py:283-321` 의 역할 매칭

`bpy` 를 스텁으로 갈아 끼워 import 한다 — 판정 함수는 Blender 에 의존하지 않는다.
"""
import os
import sys
import types

sys.modules.setdefault("bpy", types.ModuleType("bpy"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import verify_mixamo_rig as V  # noqa: E402

_fails = []


def check(label, got, want):
    if got == want:
        print(f"  [OK  ] {label}")
    else:
        print(f"  [FAIL] {label}\n         기대={want!r}\n         실제={got!r}")
        _fails.append(label)


# ── 픽스처 — 실제 자산에서 뽑은 값 ────────────────────────────────────────
# game-assets/animations/default/*.fbx 는 5개 전부 65본이다(Blender 실측 2026-07-30).
MIXAMO_ANIM_BONES = 65

BODY = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
        "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
        "RightShoulder", "RightArm", "RightForeArm", "RightHand",
        "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
        "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"]
FINGERS = [f"{s}Hand{f}{i}"
           for s in ("Left", "Right")
           for f in ("Thumb", "Index", "Middle", "Ring", "Pinky")
           for i in (1, 2, 3)]


def mix(names, prefix="mixamorig"):
    return {f"{prefix}:{n}" for n in names}


print("── anim_threshold — sheet.py 의 직접 적용 임계 ──")
check("애니 65본 → 임계 32", V.anim_threshold(MIXAMO_ANIM_BONES), 32)
check("애니 10본이어도 하한 8 이 이긴다", V.anim_threshold(10), 8)
check("애니 0본 → 8", V.anim_threshold(0), 8)
check("애니 100본 → 50", V.anim_threshold(100), 50)

print("\n── 교집합 판정 — 매핑표 전체 vs 손가락 누락 ──")
anim = mix(BODY + FINGERS)          # Mixamo 표준 65본 중 이름이 겹칠 수 있는 52개
thr = V.anim_threshold(MIXAMO_ANIM_BONES)

full = mix(BODY + FINGERS)          # 매핑표 전체를 적용한 캐릭터
check("몸통+손가락 52개 → 임계 통과", len(anim & full) >= thr, True)
check("  교집합이 정확히 52", len(anim & full), 52)

body_only = mix(BODY)               # 손가락을 뺀 캐릭터
check("몸통 22개만 → 임계 미달(정적)", len(anim & body_only) >= thr, False)
check("  교집합이 정확히 22", len(anim & body_only), 22)

# 1번 마디 10개가 rename 되지 않은 상태(1차 매핑표의 버그).
no_first = mix(BODY + [f for f in FINGERS if not f.endswith("1")])
check("손가락 1번 마디 누락(42개) → 임계는 통과", len(anim & no_first) >= thr, True)
check("  교집합이 정확히 42", len(anim & no_first), 42)
check("  22역할은 그대로 채워진다(역할만 보면 못 잡는다)",
      len(V.matched_roles(no_first)), 22)

print("\n── normalize_prefix — mixamorig1: 같은 중복 export 접두사 ──")
dup = mix(BODY, prefix="mixamorig1")
norm, n = V.normalize_prefix(dup, "mixamorig")
check("22본이 정규화된다", n, 22)
check("정규화 후 캐릭터와 완전히 겹친다", len(norm & mix(BODY)), 22)
check("정규화 전에는 하나도 안 겹친다", len(dup & mix(BODY)), 0)

check("캐릭터 접두사를 못 찾으면 그대로 둔다", V.normalize_prefix(dup, None), (dup, 0))
check("이미 같은 접두사면 바꾸지 않는다",
      V.normalize_prefix(mix(BODY), "mixamorig")[1], 0)
check("캐릭터가 mixamorig2 면 그쪽에 맞춘다",
      V.normalize_prefix(mix(["Hips"]), "mixamorig2"), ({"mixamorig2:Hips"}, 1))

print("\n── mixamo_prefix ──")
check("접두사를 찾는다", V.mixamo_prefix(mix(["Hips"])), "mixamorig")
check("숫자 붙은 접두사도 찾는다", V.mixamo_prefix({"mixamorig7:Hips"}), "mixamorig7")
check("ARP 이름뿐이면 None", V.mixamo_prefix({"root.x", "arm_stretch.l"}), None)

print("\n── matched_roles — detect_rig 의 리그 종류 판정 ──")
check("Mixamo 22역할 전부", len(V.matched_roles(mix(BODY))), 22)
check("ARP 이름은 0역할", len(V.matched_roles({"root.x", "spine_01.x", "c_thumb1.l"})), 0)
check("8역할이면 리그로 인정된다(임계값 자체)",
      len(V.matched_roles(mix(BODY[:8]))) >= V.MIN_ROLES, True)
check("7역할이면 인정되지 않는다",
      len(V.matched_roles(mix(BODY[:7]))) >= V.MIN_ROLES, False)

print()
if _fails:
    print(f"##### 실패 {len(_fails)}건")
    for f in _fails:
        print("  -", f)
    sys.exit(1)
print("##### 전부 통과")
