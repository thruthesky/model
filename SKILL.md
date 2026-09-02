---
name: model
description: 🛑 제0원칙 — 사람 개발자가 원하는 것은 **오직 AAA 급 모델 디자인**이다(원저자 2026-08-07). 원시 도형(box·sphere·cylinder·cone)을 조합해 캐릭터·몬스터·무기의 형상을 흉내내지 않는다 — 2026-08-07 에 몬스터가 "구슬+막대기", 무기가 "ㄱ 자 조각" 으로 나와 실패로 판명됐고, 같은 화면의 GLB 캐릭터만 AAA 급이었다. "임시로 도형으로 대신하자" 는 제안 자체를 하지 않는다. 형상이 필요하면 반드시 이 파이프라인을 탄다. **🛑 Godot 3D 프로젝트면 references/godot-pipeline.md 로 간다** — `/model --bones 16 --kind human --triangles 4800 --animations <폴더> "<프롬프트>"` 형식으로 Tripo3D 생성 → **리깅 전 정규화(키 1.8m·발바닥 원점·Z-up·scale 1)** → ARP 리깅 → Mixamo 애니 적용 → **본 감축(16 또는 25, 기본 16)** → 텍스처 1024 → `.glb` 로 내보내 Godot 에 바로 넣는다. 【Godot 관련 요청】"godot 용 모델 만들어줘", "glb 로 내보내줘", "본 16개로 줄여줘", "삼각형 줄여줘", "저사양용 캐릭터", **"모델이 Godot 에디터에 안 보여요"**, "캐릭터가 화면에 없어요", "모델이 너무 크다/작다", "원점이 머리 위에 있다", "발이 지면에 안 닿는다", "root_scale", "스케일이 이중 적용", "캐릭터가 누워 있다", "T-포즈로 안 움직인다", "애니메이션이 하나만 나온다" — 원인은 대부분 **Tripo 메시(Y-up·1.0)와 Mixamo 리그(Z-up·cm)의 좌표계 혼재**이고, 그것을 `.import` 의 root_scale 로 덮으면 더 크게 터진다. 3D 캐릭터를 만들어 **두 단계로 나눠** 쓴다 — **Phase A(3D)**: Tripo3D(tripo3d.ai) 텍스트→3D 생성 → 리깅 없이 다운로드 → Blender Auto-Rig Pro 리깅(mixamorig:* 규격 본) → Mixamo 애니메이션(idle·walk·run·attack·death) 적용 → 애니가 들어간 `<NAME>.blend` 완성. **Phase B(2.5D)**: 그 `.blend` 를 texture-packer 의 sheet.py 로 16방향 5행동 packed atlas(`.png`+`.atlas`, Flame flame_texturepacker)로 굽는다. **A 만 돌리고 멈춰도 되고, 이미 있는 `.blend` 로 B 만 돌려도 된다.** 다음 요청에 사용할 것 — 【전체】"3d 모델 만들어줘", "캐릭터 생성", "tripo 로 모델 뽑아줘", "몬스터/사람/로봇 3D 모델 만들어줘", "우주복/개척자/NPC 모델", "도형 대신 캐릭터 그림 넣어줘". 【Phase A 만】"3D 모델만 만들어줘", "스프라이트 말고 3d 모델로", "리깅해줘", "auto rig", "Auto-Rig Pro 로 리깅", "Mixamo 본 붙여줘", "mixamo 애니메이션 적용", "걷기/공격 모션 넣어줘", "리깅 결과를 Blender 로 보여줘", "무기 붙일 3d 원본 만들어줘". 【다리 모으기】"다리 모아줘", "다리가 벌어졌어", "양다리·무릎·발 붙여줘", "다리 벌어진 것 고쳐줘", "close legs", "차렷 자세로", "팔자 다리 고쳐줘" — pc/mob 의 다리가 벌어져 있으면 재생성하지 않고 Blender 에서 rest pose 를 고쳐 모은다(⑤-L, 벌어진 모델은 지시 없이도 자동 적용). 【동물형(비인간형)】"거미 몬스터 만들어줘", "지네/고질라/네발 짐승 만들어줘", "동물형 몬스터", "다족 몬스터", "사람 모양이 아닌 몬스터", "비인간형 리깅", "거미처럼 기어다니는 애니메이션" — Mixamo 에 해당 애니가 없고 ARP Smart 도 humanoid 전용이라 경로가 완전히 다르다(8방향·idle/walk/attack/death 4행동·128 cell, `outputs/` 저장). 상세는 references/non-humanoid.md. 【Phase B 만】"이 blend 를 스프라이트로 구워줘", "16방향 아틀라스 만들어줘", "texture pack 해줘", "2.5d 로 구워줘", "프레임 수 바꿔서 다시 구워줘". 텍스트→3D 생성, ARP 오토 리깅, ARP→Mixamo 본 이름 rename, 리그 검증, rest pose 보정, 16방향 5행동 texture-pack 전 과정과 두 단계 사이의 인계 계약을 다룬다.
---

# 🛑 제0원칙 — 사람 개발자가 원하는 것은 **오직 AAA 급 모델 디자인이다**

> **"제가 원하는 것은 오직 AAA 급 모델 디자인입니다."** — 원저자 2026-08-07

**이것이 이 스킬의 존재 이유이고, 다른 모든 지침보다 우선한다.** 아래를 어기면 그 작업은
실패다 — 돌아가든, 테스트를 통과하든, 시간 안에 끝나든 상관없다.

## 🛑 절대 금지 — 원시 도형 조합으로 캐릭터·몬스터·무기를 만들지 않는다

**`box`·`sphere`·`cylinder`·`cone`·`capsule` 을 조합해 생물이나 물건의 형상을 흉내내지
말라.** 파라미터를 아무리 정교하게 다듬어도 AAA 급이 되지 않는다. **이것은 취향 문제가
아니라 이미 실패로 판명된 사실이다.**

### 실패 기록 — 2026-08-07, terraform 프로젝트 〔반드시 읽을 것〕

| 무엇을 | 어떻게 만들었나 | 화면에 무엇으로 보였나 |
|---|---|---|
| 외계 몬스터 20계열 | 구 + 원기둥 + 원뿔을 부품으로 조립(`monster_body.dart`) | **"보라색 구슬에 막대기 네 개"** |
| PC 의 무기 | 박스 두 개를 직각으로(`weapon_spec.dart`) | **"기역(ㄱ) 자 회색 조각"** |
| PC 캐릭터 | **Tripo3D → ARP 리깅 → GLB**(이 스킬의 파이프라인) | ✅ **AAA 급** |

**같은 화면 안에서 GLB 캐릭터는 훌륭했고 프리미티브 조합은 형편없었다.** 즉 렌더러의
한계도, 조명의 문제도, 파라미터 튜닝 부족도 아니다 — **접근 자체가 틀린 것이다.**

원저자의 반응: *"너무 형편없습니다. 당신이 추천/권장하는 대로 했지만 결국 너무 형편없습니다.
앞으로 도대체 당신의 권유/추천을 어떻게 믿겠습니까?"*

🛑 **그러므로 다음을 절대 제안하지 말라:**

- ❌ "우선 임시로 도형으로 표시하고 나중에 모델로 교체하자"
  → 그 "나중" 이 오기 전에 사람이 그 화면을 보고 실망한다. **임시가 곧 결과물이 된다.**
- ❌ "절차적 생성이 크레딧을 아끼고 성능에도 유리하다"
  → 사람이 요구한 것은 **품질**이다. 비용·성능은 그 다음에 푸는 문제이고,
    품질을 깎아서 푸는 것이 아니다.
- ❌ "프리미티브를 더 정교하게 조합하면 괜찮아질 것이다"
  → 위 표가 반증이다. **부품을 늘리면 조잡함이 늘어날 뿐이다.**

### ✅ 그래서 무엇을 하는가

**형상이 필요하면 이 스킬의 파이프라인을 탄다. 예외 없다.**

| 대상 | 경로 |
|---|---|
| 캐릭터 · 몬스터(인간형) | Phase A 전체 — 생성 → ARP 리깅 → Mixamo 애니 → GLB |
| **무기 · 장비 · 소품**(정적) | ② 생성 → ③ 다운로드 → **리깅 없이 GLB 로 변환**(④~⑦ 불필요) |
| 몬스터(비인간형 — 비행체·차량형) | ② 생성 → ③ 다운로드 → 리깅 없이 GLB. 움직임은 **노드 변환**으로 준다 |
| 지형 · 건물 · 배경 구조물 | 원시 도형을 **써도 된다** — 아래 예외 참조 |

### 원시 도형을 써도 되는 곳 (예외)

**"사람이 그것을 무엇이라고 알아보는가" 가 기준이다.**

- ✅ **지면·바닥·벽·기둥·슬래브** — 실제로 상자 모양인 것들
- ✅ **디버그 표식·충돌 시각화·개발 도구** — 개발자만 본다
- ✅ **에셋이 로드되기 전의 폴백** — 화면이 죽지 않게 하는 용도이며, **정상 경로가 아니다**
- ❌ **생물·기계 유닛·무기·탈것** — 사람이 "저게 뭐지" 하고 형태를 읽는 것 전부

### 품질 게이트 — "됐다" 고 말하기 전에

1. **스크린샷을 찍어 눈으로 본다.** 로그가 통과했다고 품질이 확보되는 것이 아니다.
2. 그 스크린샷을 보고 스스로 묻는다 — **"이것이 상용 게임에 나와도 되는 수준인가?"**
   아니면 완료라고 보고하지 않는다.
3. 품질이 미달인데 시간·크레딧이 부족하면, **품질을 낮추지 말고 사람에게 상황을 보고**하고
   판단을 받는다. **말없이 조잡한 결과를 내놓는 것이 가장 나쁘다.**

---

# 🛑 첫 번째 분기 — **Godot 인가, 2.5D 인가**

**출력 대상이 무엇인지부터 정한다.** 두 경로는 ③ 이후가 완전히 다르다.

| 대상 | 산출물 | 문서 |
|---|---|---|
| **Godot 3D** (라리엔 3D) | **`<NAME>.glb`** — Godot 에 바로 넣는다 | 🛑 **[references/godot-pipeline.md](references/godot-pipeline.md)** |
| Flutter/Flame 2.5D (구 라리엔) | `<NAME>.png` + `.atlas` — 16방향 스프라이트 | **이 문서** 아래 전체 |

**프로젝트가 Godot 이면 지금 [godot-pipeline.md](references/godot-pipeline.md) 로 간다.**
아래 ①~⑨ 는 2.5D 아틀라스를 굽는 경로이고, Godot 에서는 ⑧⑨ 를 쓰지 않는다.

## `/model` 명령 사용법 (Godot 경로)

```
/model --bones 16 --kind human --triangles 4800 --animations <폴더> "<프롬프트>"
```

| 옵션 | 값 | 기본 | 뜻 |
|---|---|---|---|
| `--bones` | **16** · 25 | **16** | 본 예산. 저사양 우선이라 **최저 16 이 기본** |
| `--kind` | **human** · animal · drone · prop | `human` | 형태 → 리깅 경로 |
| `--triangles` | 1600 · 3200 · **4800** · 6400 · 7200 | **4800** | 삼각형 예산 |
| `--animations` | 폴더 경로 | **없음** | Mixamo `.fbx` 폴더 |
| `--height` | 미터 | 1.8 | 목표 키 |
| `--texture` | 픽셀 | 1024 | 텍스처 최대 변 |

🛑 **`--animations` 가 없으면 "애니메이션을 적용하지 않습니다" 를 알리고 정적 모델로
진행한다.** 작업을 멈추지 않되, **끝난 뒤 한 번 더** 폴더를 지정해 달라고 말한다.

> ⚠️ **`--kind` 는 두 종류가 있다.** Godot 경로는 **형태**(`human`/`animal`/`drone`/`prop`),
> 2.5D 아틀라스(⑧)는 **게임 역할**(`pc`/`mob`/`npc`/`boss`/`minion`) 이다.

### 🛑 Godot 경로의 절대 규약 — 리깅 전에 정규화한다

> **Tripo3D 다운로드 직후, 리깅 전에, 키 1.8m · 발바닥 원점 · Z-up ·
> scale 1 · rot 0 으로 정규화한다.**

Tripo 메시는 **Y-up · 1.0 단위**, Mixamo 리그는 **Z-up · cm** 라서, 정규화 없이 붙이면
두 좌표계가 섞이고 리깅·익스포트를 거치며 증폭된다. 실측(`male.blend` 2026-09-02):
**메시는 똑바로 서고 아마추어만 90° 누웠으며**, GLB 에서 캐릭터가 원점 아래로
매달려 Godot 에 보이지 않았다.

🛑 **그리고 그것을 `.import` 의 `root_scale=150` 으로 덮은 것이 두 번째 사고를 만들었다** —
GLB 를 근본 해결한 뒤에도 150 이 남아 **270m 거인**이 됐다.
근거·수치·진단 절차는 [godot-pipeline.md](references/godot-pipeline.md).

---

# Tripo3D 캐릭터 → Auto-Rig Pro(Mixamo 리그) → 16방향 스프라이트 아틀라스

**⚠️ 여기부터는 Flutter/Flame 2.5D 경로다.** Godot 이면 위 분기로 돌아간다.
(①~⑦ 의 생성·리깅·Mixamo 애니는 두 경로가 공유한다 — 갈라지는 것은 ⑧ 부터다.)

텍스트 프롬프트로 3D 캐릭터를 만들고, 리깅하고, Mixamo 애니메이션을 입혀,
**게임에 넣을 수 있는 packed atlas** 로 굽는 전 과정. **두 단계로 나뉜다.**

## 🛑 시작 전 분기 — 사람 모양인가, 아닌가

**이 문서(아래 ①~⑨)는 humanoid 전용이다.** 만들 대상이 사람 형태가 아니면
**지금 [references/non-humanoid.md](references/non-humanoid.md) 로 간다.**

| 대상 | 경로 | 규격 |
|---|---|---|
| 사람·인간형 로봇·2족 직립 NPC | **이 문서** ①~⑨ | 16방향 · 5행동(idle walk run attack death) · 128 |
| **거미 · 지네 · 고질라 · 네발 짐승 등 동물형** | **[non-humanoid.md](references/non-humanoid.md)** | **8방향 · 4행동(idle walk attack death) · 128 · `outputs/` 저장** |
| **드론 · 호버 유닛 등 비행체**(다리 없음) | **[non-humanoid.md §비행체](references/non-humanoid.md)** | 8방향 · 4행동 · 128. 🛑 동물형 경로도 **탈 수 없다** — 발끝 클러스터링(지면 접지)과 삼각보행(IK 발 4개)이 둘 다 성립하지 않아 `rig_drone_arp.py`·`anim_drone.py` 전용 |

동물형이 이 문서를 타면 **두 곳에서 반드시 막힌다**(우회로 없음):

- **④ ARP Smart** 는 메시에서 *사람 몸* 을 찾아 마커를 놓는다 → 다리 6·8개짜리에는 감지가
  성립하지 않는다. 동물형은 `free` 프리셋 + `add_limb` 로 다리를 직접 붙인다.
- **⑤~⑦ Mixamo 애니** 는 2족 인간형 모션만 있다 → **거미 걸음이라는 원본이 세상에 없다.**
  리타게팅할 소스가 없으므로 동물형은 애니메이션을 **계산해서 만든다**(삼각보행).

⚠️ 형태가 애매하면(예: 2족인데 꼬리가 길고 팔이 짧은 괴수) **다리 개수로 판정한다** —
2개면 이 문서, 3개 이상이면 non-humanoid.md. 2족이라도 Mixamo 사람 모션이 어울리지 않으면
non-humanoid.md 의 "다른 동물형으로 확장할 때" 절을 본다.

## 🔀 두 단계 — 어디까지 필요한가

```
Phase A ── 3D 자산 ─────────────────────────┐
① 로그인 → ② 생성(T-Pose) → ③ 리깅 없이 다운로드
  → ④ ARP 리깅 (Smart → Match to Rig → Bind)
  → ⑤ Mixamo 본 이름으로 export
  → ⑤-L 🦵 다리 벌어졌으면 **자동으로 모으기** → ⑥ 리그 검증
  → ⑦ rest pose 보정  ➜ **<NAME>.blend** (애니 5종 포함)
                                            │
             ← 3D 만 필요하면 여기서 끝 ───┘
                                            ↓
Phase B ── 2.5D 아틀라스 ───────────────────
⑧ texture-pack(16방향 5행동) → ⑨ 아틀라스 검증
                     ➜ **<NAME>.png + <NAME>.atlas**
```

| | **Phase A — 3D** | **Phase B — 2.5D** |
|---|---|---|
| 하는 일 | 생성·리깅·애니 적용 | 스프라이트 렌더·패킹 |
| 산출물 | **`<NAME>.blend`**(애니 5종 내장) | `<NAME>.png` + `<NAME>.atlas` |
| 소유 코드 | 이 스킬의 `scripts/` | **[texture-packer 스킬](../texture-packer/SKILL.md)** 의 `sheet.py` |
| 자동화 | ④ 만 GUI, 나머지 전부 명령 | 전부 명령 |
| 대략 소요 | 생성 4분 · 리깅 15분 · 보정 2분 | 1분 30초~3분 |

🛑 **경계는 ⑦ 뒤다. ⑤ 의 `<NAME>.fbx` 를 "3D 완성" 으로 착각하지 말 것** — 그것은
`arp_bake_anim=False`(`scripts/arp_export_mixamo.py` `run()`)로 내보낸 **뼈대만 있는 파일**이라
애니메이션이 하나도 들어 있지 않다. "Mixamo 애니메이션 적용까지" 를 만족하는 산출물은
⑦ 이 만드는 **`<NAME>.blend`** 하나뿐이다.

⚠️ **Tripo 의 오토 리깅(Animate 탭)을 쓰지 않는다**〔원저자 지시 2026-07-30〕. 생성한 모델을
**리깅하지 않은 채로 내려받아** Blender 의 **Auto-Rig Pro** 로 리깅한다. 크레딧 20 을 아끼는
것보다 중요한 이유가 둘 있다:

- **본 이름을 우리가 정한다.** ARP export 단계에서 `mixamorig:*` 규격으로 rename 하므로
  Mixamo 애니메이션이 **리타게팅 없이** 그대로 붙는다(⑤ 참조). Tripo 리그(41본,
  `Hip`/`L_Upperarm` 식)는 매번 본 매핑을 거쳐야 했다.
- **손가락이 움직인다.** Tripo v1.0 Humanoid 리그에는 손가락 본이 없어 주먹 쥐기가
  손목 회전으로만 남았다. ARP 는 손가락 3마디를 만든다.

## 준비 확인

```bash
which blender && blender --version | head -1      # 실측: 5.1.2
ls game-assets/animations/default/*.fbx           # 실제로 무엇이 있는지 눈으로 볼 것

# ARP 는 여러 벌 설치될 수 있다(실측: user_default 3.78.18 + superhivemarket_com 3.78.34).
# 버전을 문서에 고정하지 말고 **활성본을 실행 전에 확인**한다 — 같은 함수가 버전마다
# 다른 줄에 있어, 비활성본을 근거로 삼으면 인용이 통째로 어긋난다.
blender --background --python-expr "
import addon_utils
for m in addon_utils.modules():
    if 'auto_rig' in m.__name__:
        print('ARP', m.__name__, addon_utils.check(m.__name__))" 2>/dev/null | grep ARP
```

- **Auto-Rig Pro 는 유료 애드온이다.** 없으면 사용자에게 설치를 요청한다.
  이 문서의 ARP 인용 줄 번호는 **활성본 3.78.18**(`extensions/user_default/`) 기준이다.
- **Chrome DevTools MCP** 가 있어야 Tripo 를 조작할 수 있다. 없으면 사용자에게 알린다.
- 🛑 **애니메이션 폴더에 실제로 무엇이 있는지 먼저 확인하고 사용자에게 알린다.**
  실측: 폴더에는 `idle walk run attack death` + **`hit` 까지 6개**가 있지만,
  **`hit` 은 2026-07-20 규격에서 제외됐고 쓰는 것은 5개**다
  (`sheet.py` `DEFAULT_ACTIONS`). **존재 ≠ 사용** — `hit` 을 되살리면 캐릭터마다
  8프레임 × 16방향 = **128셀**이 더 붙어 디스크·RAM 만 커진다(런타임은 hit 상태를
  같은 방향 idle 로 폴백해 그린다).

---

# Phase A — 3D 자산 만들기 (①~⑦)

🛑 **⑥ 과 ⑦ 을 건너뛰면 실패를 놓친다.** 이 파이프라인의 실패는 대부분 예외가 아니라
"돌기는 했는데 캐릭터가 안 움직인다"·"움직이는데 자세가 틀렸다" 로 나타난다 — 본 이름이
하나 어긋나면 경고 없이 **정적 프레임**이 나오고, 이름이 다 맞아도 rest pose 가 다르면
**팔이 만세인 결과**가 나온다(⑦ 참조).

## ① 로그인

`https://studio.tripo3d.ai/workspace/generate` 접속.

**Google OAuth 는 쓸 수 없다.** MCP 브라우저는 `--enable-automation` 플래그 때문에
Google 이 차단한다. 이메일 인증 코드를 쓴다.

1. `Sign up/Log in` → `Continue with Email`
2. 이메일 입력 (기본 계정: **`withcenter.dev3@gmail.com`**) → `Send Code`
3. 코드 확보:
   - Gmail MCP 로 읽을 수 있는 계정이면 직접 조회
     ```
     mcp__claude_ai_Gmail__search_threads  query: "from:notification@tripo3d.ai newer_than:1d"
     ```
   - **읽을 수 없는 계정이면 사용자에게 요청한다.** "메일함을 열어 6자리 코드를 알려주세요" (유효 10분)
4. 코드 입력 → `Continue`

로그인 직후 프로모션 모달(`Special Bonus`, `8K Texture`)이 뜬다. `No Thanks` / `Maybe Later` 로 닫는다.

셀렉터·이벤트 처리·함정은 [references/tripo-studio.md](references/tripo-studio.md).
**UI 조작에서 한 번이라도 막히면 반드시 읽을 것.**

## ② 모델 생성

1. 생성 패널의 **4번째 아이콘(연필)** 을 눌러 텍스트 모드로 전환 (기본은 이미지 업로드 모드)
2. 프롬프트 입력 — textarea 는 native setter + `input` 이벤트로 채운다(참조 문서)
3. **`T-Pose` 토글 ON** — ARP 의 마커 자동 배치 정확도가 크게 달라진다.
   ⚠️ **이 토글은 팔만 수평으로 편다. 다리 간격은 보장하지 않는다** — 아래 절 참조
4. `Generate Model` 클릭
5. **생성 결과의 다리를 확인한다** — 벌어졌으면 ③ 으로 넘어가지 않고 **재생성**한다

**생성에 3~5분 걸린다.** 백그라운드 대기 후 스크린샷으로 확인할 것. 55~65 크레딧.

### 프롬프트 규칙

Mixamo 애니메이션은 인간형 리그 전용이고, ARP 의 humanoid 리그도 마찬가지다.
**인간형 T-포즈를 반드시 강제한다.** 사족보행·다관절·촉수형으로 생성되면 이후 단계가
전부 불가능하다.

```
A male astronaut colonist in a white and orange sci-fi spacesuit, full body,
standing in T-pose with both arms straight out horizontally,
legs together and straight with both feet touching side by side, ankles together,
humanoid proportions with two arms and two legs, sealed helmet with dark reflective
visor, life support backpack, armored chest plate, gloves and boots, symmetrical,
clean topology, game-ready
```

필수 요소: `humanoid proportions`, `two arms and two legs`,
`standing in T-pose with arms straight out horizontally`,
**`legs together and straight with both feet touching side by side, ankles together`**,
`symmetrical`, `game-ready`

사용자가 "거미 몬스터", "용" 처럼 비인간형을 요청하면 Mixamo 애니메이션 적용이 불가능함을
알리고 인간형으로 조정할지 확인할 것.

### 🛑 ②-V 다리와 발은 반드시 모은다 (완료 조건 0번)

🛑 〔원저자 지시 2026-07-31〕 **T-포즈는 팔에 대한 규격이지 다리에 대한 규격이 아니다.**
표준 T-포즈 참고 이미지는 다리를 어깨너비로 벌리고 있고, `T-Pose` 토글도 팔만 수평으로
편다. 그래서 **다리를 모으라고 프롬프트에 직접 쓰지 않으면 벌어진 채 생성된다.**

**리깅은 모델의 자세를 그대로 rest pose 로 굳힌다.** ARP 는 메시 형상에서 본 위치를 잡으므로
다리가 벌어진 모델에서는 **다리가 벌어진 리그**가 나오고, 그 벌어짐이 이후 전부에 남는다:

| 어디서 | 무슨 일이 | 왜 |
|---|---|---|
| ⑦ 리타게팅 | 걷기·달리기가 **다리를 벌린 채** 재생된다 | 보정식이 `(src_pose @ src_rest⁻¹) @ tgt_rest` 다. Mixamo 에서 가져오는 것은 **rest 대비 회전차**뿐이고 기준 자세는 **우리 리그의 rest**(=벌어진 다리)다. 벌어짐은 상쇄 대상이 아니라 **기준값**이라 그대로 더해진다 |
| ⑧ 렌더 | 캐릭터가 **작게** 그려진다 | 실루엣이 옆으로 넓어지는데 셀 프레이밍은 bbox 기준이다 |
| 게임 화면 | 걸을 때 **어기적거린다** | 위 둘의 합 |

🛑 **③ 이후에는 못 고친다.** 리그만 모으면 메시가 안 따라와 웨이트가 어긋나고, 메시까지
같이 고치는 것은 재생성보다 비싸다. **다리를 벌린 결과가 나오면 그 자리에서 재생성한다** —
크레딧 55~65 가 다시 들므로 **사용자에게 먼저 알리고 진행**한다.

확인 방법 — 생성 결과 미리보기를 **정면에서** 보고:

- 양발 안쪽 면이 **닿아 있거나 주먹 하나 폭 이내**인가
- 무릎이 곧게 펴져 있는가(굽혀 있으면 rest 가 어중간해져 같은 문제가 난다)
- 발끝이 **정면(−Y)** 을 보는가 — 바깥으로 벌어진 발은 걸을 때 팔자로 보인다
### ②-V 다리가 벌어졌는지 판정한다 (완료 조건 0번)

다리·무릎·발이 벌어진 채로 두면 걷기 모션에서 뒤뚱거리고, 그 결함은 **⑧ 에서 셀에
맞춰 축소된 뒤에야** 눈에 띈다. **생성 직후에 판정한다.**

- 눈으로: 정면 렌더에서 두 발 사이가 붙어 있는가. 무릎이 벌어지지 않았는가.
- 수치로: 같은 저장소에 `actor` 스킬이 있으면 그 판정 스크립트를 **경로로 호출**한다
  (파일을 이 스킬로 복사하지 말 것 — 사본이 갈라진다):
  ```bash
  # 있을 때만. 없으면 위의 눈 확인으로 대신한다(이 스킬은 독립 저장소라 없을 수 있다).
  ls .claude/skills/actor/scripts/check_leg_gap.py && \
    blender --background --python .claude/skills/actor/scripts/check_leg_gap.py -- <모델.fbx>
  ```

🛑 **벌어졌다고 바로 재생성하지 않는다**(2026-08-07 변경). 리깅이 끝난 뒤 **⑤-L 에서
Blender 로 다리를 모은다** — 크레딧 55~65 와 4분을 아끼고, 다시 벌어져 나오는 재생성
무한 반복도 없앤다. 재생성은 ⑤-L 로도 안 될 때의 **최후 수단**이다.
(여기서 판정만 해 두고, 교정은 리그가 생긴 ⑤ 뒤에 한다 — 본이 있어야 다리를 돌릴 수 있다.)

🛑 **동물형에는 이 판정을 적용하지 않는다** — 거미·지네처럼 다리가 방사형으로 벌어진 것이
정상인 액터에 "다리를 모으라" 고 하면 형상이 무너진다. 동물형은
[references/non-humanoid.md](references/non-humanoid.md) 로 간다.

### 🛑 생성 품질 설정 — Ultra Mesh 는 끄고 텍스처는 2K

| 항목 | 값 | 왜 |
|---|---|---|
| **Ultra Mesh Quality** | 🛑 **끈다** | 폴리곤만 늘고 크레딧을 더 쓴다. 어차피 Decimate 로 깎는다 |
| **Texture Quality** | **2K** | 8K 는 ZIP 이 지연되거나 아예 오지 않는다(크레딧만 차감). Godot 경로는 로컬에서 다시 1024 로 줄인다 |
| 삼각형 | **최대 100만까지 허용** | 생성 단계에서 줄이지 않는다 — 로컬 Decimate 가 무료로 같은 일을 한다 |

### 폴리곤은 나중에 줄인다

`HD Model` 은 약 200만 페이스를 만든다. **여기서 `Smart Mesh`·`Retopo` 로 줄이려 하지
말 것** — 크레딧이 더 든다. ④ 의 Decimate 가 리깅 전에 안전하게 줄인다(실측: 191만 → 3만).

**Godot 경로는 `--triangles` 로 예산을 지정한다**(1600·3200·**4800**·6400·7200).
실측: 1,020,514 → 4,798 (형상 손실 없음) →
[godot-pipeline.md](references/godot-pipeline.md).

⚠️ **스프라이트로 구울 것이므로 폴리곤 예산이 3D 런타임보다 훨씬 헐겁다.** 128px 셀에
렌더할 뿐이라 페이스 수는 렌더 시간에만 영향을 준다. 그래도 Blender 뷰포트 조작이 느려지므로
줄이는 편이 낫다.

## ③ 다운로드 — 리깅하지 않는다

**좌측 `Animate` 탭에 들어가지 않는다.** 생성이 끝난 모델에서 바로 하단 `Export` 를
**`click` 도구로** 눌러 다이얼로그를 연다.

| 항목 | 값 |
|---|---|
| File Name | **단계마다 다르게** (아래 주의) |
| Format | `FBX` |
| FBX 프리셋 | `Blender` (`Mixamo`/`3dsmax` 는 축이 바뀐다) |
| Texture Resolution | **`2k`** |
| Export Skeleton | **OFF** ← 리깅하지 않았으므로 켤 스켈레톤이 없다 |

**텍스처는 2k 를 쓴다.** 8k 는 ZIP 생성이 지연되거나 아예 오지 않는다(크레딧만 차감).

**File Name 을 단계마다 다르게 지정할 것.** Export 는 비동기라 이전 요청의 ZIP 이
뒤늦게 도착해 헷갈린다.

다이얼로그 **안**의 `Export` 는 `evaluate_script` 로 눌러도 된다(마지막 버튼 패턴).

🛑 **내려받은 Tripo ZIP 원본은 `outputs/tripo3d.ai/` 에 보관한다**〔원저자 지시 2026-08-06〕.
`outputs/` 는 `.gitignore` 에 있어 저장소를 오염시키지 않는다. ZIP 을 남겨 두면 **리깅을
다시 할 때 Tripo 크레딧을 다시 쓰지 않아도 된다** — 생성 55~65 + Export 40 이 그냥 날아가는
것을 막는 유일한 보험이다.

```bash
mkdir -p outputs/tripo3d.ai
mv ~/Downloads/"<이름>_raw.zip" outputs/tripo3d.ai/    # 원본 ZIP 보관(재사용·재리깅용)
```

그 다음 **sheet.py 가 기대하는 자리**에 푼다 — 폴더 이름이 곧 자산 이름이다:

```bash
NAME=colonist                     # 자산 이름 = 폴더명 = 아틀라스 이름
DST=game-assets/characters/pc/male/$NAME       # pc 는 중간 단계가 하나 더 필요하다(아래)
mkdir -p "$DST"
unzip -o outputs/tripo3d.ai/"<이름>_raw.zip" -d "$DST"
# 서브셸로 감싼다 — cd 가 남으면 이후 상대 경로 명령이 조용히 엉뚱한 곳을 본다
( cd "$DST" \
  && mv tripo_convert_*.fbx  ${NAME}_raw.fbx \
  && mv tripo_convert_*.fbm  ${NAME}_raw.fbm )   # 텍스처 폴더. FBX 와 같은 이름이어야 로드된다
```

**`<NAME>` 이 곧 자산 이름이자 아틀라스 이름이다** — `assets/pc/<NAME>/<NAME>.atlas` 가 된다.
사람이 읽을 이름을 붙일 것(`colonist`·`denis`·`maria`).

⚠️ **성별로 나누지 않는다.** 폴더 이름이 캐릭터 종류다 — 캐릭터마다 폴더를 하나 만든다
〔원저자 지시 2026-07-30〕. (기존 자산이 `male_*`/`female_*` 로 되어 있는 것은 과거 명명일 뿐이다.)
🛑 **다만 "이름을 지으면 게임 화면에 그대로 나온다" 는 뜻은 아니다** — 굽는 것과 게임에
노출되는 것은 별개다. [§게임에 실제로 보이게 하려면](#게임에-실제로-보이게-하려면--노출은-4층이다) 참조.

⚠️ **`pc` 는 중간 폴더가 하나 더 필요하다** — `sheet.py` 가 `pc/<중간>/<NAME>/<파일>` 네
단계를 요구하고 **끝에서 두 번째**를 자산 이름으로 쓴다
(`sheet.py` `infer_kind_name_from_path()` — 실측 위치 `:540-580`, 이름 추출 `:572-578`).
중간 폴더의 이름 자체는 아무 영향이 없다(분류용).

⚠️ **raw 를 `_raw` 로 남긴다.** ⑤ 의 ARP export 가 `<NAME>.fbx` 를 쓰므로, 같은 이름으로
풀면 원본이 덮여 리깅을 다시 하려면 Tripo 에서 다시 받아야 한다(크레딧 재소모).

⚠️ **이 폴더에 애니메이션 `.fbx` 를 두지 말 것.** `--animations` 를 생략하면 sheet.py 가
모델과 같은 폴더의 `idle/walk/attack/death.fbx` 를 **1순위**로 집는다(`sheet.py:751-781`).
우리는 `animations/default` 를 쓴다.

## ④ Auto-Rig Pro 리깅 (Blender) — **이 단계만 GUI 다**

⚠️ **ARP 의 Smart 는 마커 위치를 눈으로 확인**해야 하고, 모델마다 실패 양상이 다르다.
`--background` 로 완전 자동화하지 않는다 — 자동으로 놓인 마커가 어깨 하나만 어긋나도 팔이
통째로 뒤틀린 채 아틀라스까지 그대로 간다. Blender MCP(`mcp__blender__*`)가 붙어 있으면
**화면을 보면서** 조작한다.

🛑 **이 "GUI 작업" 단서를 ⑤ 이후로 확대 해석하지 말 것.** ⑤~⑨ 는 전부 명령 한 줄이다.

1. **임포트·정리**
   - `File > Import > FBX` 로 `<NAME>_raw.fbx`
   - 캐릭터가 **Z-up, 발이 원점, 정면이 -Y** 를 보게 회전·이동
   - `Object > Apply > All Transforms` — **스케일이 1 이 아니면 ARP 가 어긋난다**
   - 키가 실제 사람 크기(약 1.7~1.8)인지 확인. cm 단위로 오면 0.01 배
   - 페이스가 많으면 여기서 `Decimate`(COLLAPSE) 로 3만 안팎까지 줄인다
   - 🛑 **다리가 벌어져 있지 않은지 정면에서 확인한다 — 여기가 마지막 관문이다.**
     벌어진 채 리깅하면 rest pose 가 벌어진 리그가 되어 **걷기·달리기가 다리를 벌린 채**
     재생된다. 되돌리려면 ② 부터 다시다([다리 절](#다리와-발은-반드시-모은다) 참조)

2. **ARP Smart — 마커 배치**
   - `Auto-Rig Pro: Smart` 패널 → `Get Selected Objects` (메시 선택 상태에서)
   - **`Spine Count` 를 `4` 로 둔다** (프로퍼티 기본값이 4 다 — `auto_rig_smart.py:8421`).
     ⚠️ **`3` 으로 낮추지 말 것.** 직관과 반대로, ARP 는 `spine_count == 3` 이면 export
     리그에서 **`spine_03.x` 를 삭제**한다(`auto_rig_ge.py:6322-6329`). `> 3` 일 때만
     추가한다(`6287`). 즉 Mixamo 의 `Spine/Spine1/Spine2` 3분할에 대응하려면 **4** 다.
     (실측: 3 으로 구운 `colonist.fbx` 는 `spine2` 역할이 비어 21/22 였다)
   - `Add Neck` / `Add Chin` / `Add Shoulders` / `Add Wrists` / `Add Spine Root`
     / `Add Ankles` 를 차례로 눌러 마커를 놓는다
   - **놓인 마커를 반드시 눈으로 확인한다.** 헬멧·백팩이 있는 우주복은 목·어깨 추정이
     자주 빗나간다
   - `Go!` (= `id.go_detect`) → **reference bones** 생성

3. **`Match to Rig` — 건너뛰면 이후가 전부 막힌다** 🛑
   - `Go!` 는 reference bones 만 만들고 `has_match_to_rig = False` 로 둔다
     (`auto_rig_smart.py:651`). **`Match to Rig`(`arp.match_to_rig`) 를 눌러야** 실제
     리그가 만들어지고 이 값이 `True` 가 된다(`auto_rig.py:6621`).
   - 누르지 않으면 **Bind 와 Export 가 둘 다 거부**한다:
     - `'Click "Match to Rig" before binding'` (`auto_rig.py:5352-5356`)
     - `'Click "Match to Rig" before exporting'` (`auto_rig_ge.py:1648-1652`)
   - reference bones 를 손으로 옮겼다면 **다시 `Match to Rig`** 를 눌러야 반영된다.

4. **Bind** — 메시 + 리그 선택 → `Bind to Rig` (`arp.bind_to_rig`)
   - "Select first the meshes, then the armature" — **메시를 먼저 선택하고 리그를 active** 로
   - 포즈를 돌려 보며 웨이트가 튀는 곳이 없는지 확인
     (빠른 확인: `c_hand_ik.l` 의 `ik_fk_switch` 를 1 로 두고 `c_arm_fk.l`·`c_forearm_fk.l`
     을 Z 로 60°·35° 돌려 렌더 — 팔이 매끄럽게 접히면 통과)

5. **`.blend` 로 저장** — `<DST>/<NAME>_rig.blend`. 리깅은 다시 하기 비싸다.

### ④-A MCP·스크립트로 리깅할 때 — 실측 함정 5가지 〔2026-07-30〕

GUI 버튼이 아니라 `bpy.ops` 로 돌릴 때만 부딪히는 것들이다. 이걸 모르면
"연산자가 조용히 아무 일도 안 하거나 `poll() failed` 만 반복"한다.

**1. Smart 연산자는 `arp.*` 가 아니라 `bpy.ops.id.*` 다.**

| 패널 버튼 | 연산자 |
|---|---|
| Get Selected Objects | `id.get_selected_objects()` |
| Add Neck / Chin / Shoulders / Wrists / Spine Root / Ankles | `id.add_marker(body_part=…)` |
| Go! | `id.go_detect()` |
| Match to Rig | **`arp.match_to_rig()`** ← 이것만 `arp.*` |
| Bind to Rig | **`arp.bind_to_rig()`** ← 이것도 `arp.*` |

`body_part` 값(`auto_rig_smart.py:8038-8053`): `neck` · `chin` · `shoulder`(=Shoulders) ·
`hand`(=**Wrists**) · `root`(=**Spine Root**) · `foot`(=**Ankles**).
선택: `hand_tip` · `thigh` · `knee` · `elbow` · `head_tip`.

**2. `add_marker` 는 modal 이라 위치를 마우스로 받는다.** `execute()` 는 마커 오브젝트
`<part>_loc` 를 만들 뿐이다(`auto_rig_smart.py:1394-1405`). 그래서 **`'EXEC_DEFAULT'` 로
불러 modal 을 건너뛰고 좌표를 직접 대입**한다. `arp_smart_sym=True` 면 `_sym` 짝이 자동 생성된다.

```python
bpy.ops.id.add_marker('EXEC_DEFAULT', body_part='neck')
bpy.data.objects['neck_loc'].location = (0.0, -0.06, 1.45)   # world = arp_markers 로컬
bpy.context.view_layer.objects.active = mesh                 # poll 조건 복구(아래 4번)
```

**3. `arp.guess_markers`(딥러닝 자동 배치)는 대개 못 쓴다.**
`RuntimeError: AI files are missing or not up to date` — ARP 의 AI 리소스를 따로 받아야 한다.
**`arp.guess_fingers` 도 같다.** 손가락은 엔진을 바꿔 피한다:

```python
scn.arp_smart_fingers_engine = 'LEGACY'   # Voxel Centroids. AI 파일 불필요
scn.arp_fingers_enable = True             # 실측: 손가락 deform 38본이 그대로 생겼다
```

`invoke` 는 AI 감지가 실패하면 `arp_fingers_enable=False` 로 폴백하지만
(`auto_rig_smart.py:522-530`), `guess_fingers` 가 **예외를 던지면** invoke 째로 죽는다.
그래서 **미리 `LEGACY` 로 두는 편이 안전하다.**

**4. 🛑 `poll() failed` 의 진짜 원인은 컨텍스트가 아니라 *숨겨진 오브젝트* 다.**
`id.go_detect.poll` 은 `context.active_object != None` 뿐인데(`auto_rig_smart.py:342`),
**`get_selected_objects()` 가 원본 메시를 숨기고 `body_temp` 복제본을 만든다.**
숨겨진(`hide_get()==True`) 오브젝트는 컨텍스트의 active 로 잡히지 않는다.

```python
bpy.context.view_layer.objects.active = bpy.data.objects['body_temp']   # ← 이것으로 통과
```

MCP 실행 컨텍스트에서 `temp_override` 로는 해결되지 않는다 — **실측:
`area` 를 넘기면 `active_object` 가 `None` 이 되고, 빼면 `space_data` 가 `None` 이라
`_append_arp` 가 `bpy.context.space_data.overlay` 에서 죽는다.** 둘을 동시에 만족시키는
override 조합은 없었다(`window`/`screen`/`scene`/`view_layer` 조합 5가지 전부 실패).

**5. 연산자는 `bpy.app.timers` 안에서 돌린다.** MCP 의 코드 실행 컨텍스트에는
3D 뷰가 없다. 타이머 콜백에서 `temp_override(window, area, region)` 을 잡으면
`space_data` 가 살아 있어 `_append_arp` 가 통과한다. 결과는 **파일로 기록**해 뒤에 읽는다
(콜백은 반환값을 돌려줄 수 없다).

```python
def run():
    for w in bpy.context.window_manager.windows:
        a = next((x for x in w.screen.areas if x.type == 'VIEW_3D'), None)
        rg = next(r for r in a.regions if r.type == 'WINDOW')
        with bpy.context.temp_override(window=w, area=a, region=rg):
            bpy.ops.id.go_detect('INVOKE_DEFAULT')     # invoke 에 필수 준비가 들어 있다
        break
    json.dump(result, open(LOG, 'w'))
    return None
bpy.app.timers.register(run, first_interval=0.2)
```

⚠️ `go_detect` 는 **`INVOKE_DEFAULT`** 로 부른다. `invoke` 가 마커 존재 검사·
`arp_bind_chin` 설정·손가락 감지를 하고 나서 `execute` 를 부른다(`auto_rig_smart.py:531`).
`EXEC_DEFAULT` 로 부르면 그 준비가 통째로 빠진다.

### ④-B 마커를 눈으로 확인하는 법 — 그냥 렌더하면 안 보인다

관절 마커는 **몸 안에 있어야 정상**이라 솔리드 렌더에서 메시에 가려 보이지 않는다.
와이어프레임 렌더는 `BLENDER_WORKBENCH` 에서 **빈 화면**이 나온다(실측).

되는 방법: **표식 구를 마커의 두 축만 남기고 카메라 쪽으로 띄워 실루엣에 겹쳐 본다.**

```python
# 정면(-Y) 확인 — x·z 는 그대로, y 만 캐릭터 앞으로
probe.location = (m.x, -0.7, m.z)
# 측면(+X) 확인 — y·z 는 그대로, x 만 캐릭터 옆으로
probe.location = (1.1, m.y, m.z)
```

마커 좌표 자체는 **메시에서 재서** 정한다(눈대중 금지). z 를 40구간으로 나눠 `|x|` 최대를
훑으면 팔이 시작·끝나는 높이가 그대로 드러나고, 팔 구간에서 x 를 따라가며 단면 두께(`dz`)를
보면 **가장 잘록한 곳이 손목**이다. 실측(키 1.75 우주복):

| 마커 | 좌표 | 어떻게 쟀나 |
|---|---|---|
| `neck` | (0, −0.06, 1.45) | 팔 상단(1.44)과 헬멧 하단(1.48) 사이 |
| `chin` | (0, −0.19, 1.52) | 헬멧 앞면 y=−0.21 보다 살짝 안쪽 |
| `shoulder` | (0.21, −0.06, 1.38) | 몸통 폭 0.23 의 안쪽, 팔 중심 높이 |
| `hand` | (0.70, −0.05, 1.375) | 단면 `dz` 가 0.103→0.084 로 꺾이는 x |
| `root` | (0, −0.08, 1.00) | 가랑이(z=0.95) 바로 위 |
| `foot` | (0.17, −0.02, 0.10) | 발 x 범위 0.10~0.27 의 중앙 |

⚠️ **이 `foot` 값은 다리를 벌린 옛 모델에서 잰 것이다**(양발 중심 간격 0.34m). ② 대로
다리를 모아 생성했다면 **훨씬 작은 x** 가 나온다 — 표를 베끼지 말고 **매번 메시에서 다시
잰다.** 모은 모델에 벌어진 좌표를 쓰면 다리 본이 몸 밖으로 나가 웨이트가 무너진다.

## ⑤ Mixamo 본 이름으로 export — **명령 한 줄, GUI 불필요** 🛑

```bash
blender --background --python .claude/skills/model/scripts/arp_export_mixamo.py -- \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>_rig.blend \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.fbx
echo "종료코드=$?"        # 0 = 통과, 1 = 실패
```

🛑 **④ 와 달리 이 단계는 `--background` 로 완주한다. GUI 를 띄우지 말 것.**
`ARP_OT_GE_export_fbx_panel.execute()` 가 `ARP_OT_export.execute()` 를 그대로 부르므로
(`auto_rig_ge.py:11842-11843`), `'EXEC_DEFAULT'` 로 호출하면 파일 브라우저 `invoke` 를
건너뛰고 바로 실행된다. 실측(2026-08-06 `suit_bot`) — `{'FINISHED'}` · 4.2MB FBX ·
⑥ 검증 **22/22 역할 · 교집합 52 · 경고 0줄** · ⑦ 리타게팅 `[OK]` 5줄.

⚠️ **"ARP 로는 Mixamo 호환 리그를 만들 수 없다" 고 판단하고 mixamo.com 웹 업로드로 우회한
이력이 있다(2026-08-03 `suit_bot`).** 그것은 사실이 아니었다 — ④ 리깅은 이미 성공해 있었고
(`suit_bot_rig.blend.log.json` 의 `match_to_rig`·`bind_to_rig` 모두 ok), **없던 것은 이
export 를 실행하는 코드뿐**이었다.

스크립트가 대신 해 주는 것 셋(전부 실측으로 필요했던 것):

| | 무엇 | 안 하면 |
|---|---|---|
| **텍스처 경로 복구** | Tripo ZIP 을 `<NAME>_raw.*` 로 rename 하면 blend 안 이미지가 옛 `tripo_convert_*.fbm` 을 가리킨 채 남는다 | `embedding file … failed` → **텍스처 없는 회색 스프라이트** |
| **spine 4분할 보정** | `spine_count=3` 이면 ARP 가 export 에서 `spine_03.x` 를 지운다(`auto_rig_ge.py:6322`). `set_spine(4)` + `match_to_rig()` 로 되살린다 | `mixamorig:Spine2` 가 비어 **21/22** · 상체 굽힘 한 마디 손실 |
| **export 후 자가 검증** | 결과 FBX 를 다시 열어 `mixamorig:*` 본이 실제로 들어갔는지 확인 | rename 실패를 ⑧ 렌더까지 가서야 발견 |

옵션 — `--rename-fp <표>` · `--keep-twist` · `--units-x100` · `--no-spine-fix`.
결과·경고는 `<NAME>.fbx.log.json` 에도 남는다.

🛑 **④-3 의 `Match to Rig` 를 안 눌렀으면 여기서도 거부당한다**
(`'Click "Match to Rig" before exporting'` — `auto_rig_ge.py:1651`). 스크립트가
`has_match_to_rig` 를 먼저 확인해 **ARP 가 거부하기 전에** 알려 준다.

<details>
<summary>GUI 로 직접 할 때의 설정표 (스크립트가 그대로 적용한다)</summary>

| ARP 설정 | 값 | 기본값 | 왜 |
|---|---|---|---|
| Rig Type | **`Humanoid`** | Humanoid | 매핑표가 이 타입의 본 이름을 전제한다 |
| **Rename Bones from File** (`arp_export_renaming`) | **ON** | OFF | 이 스킬의 핵심 |
| **Rename file** (`arp_rename_fp`) | `.claude/skills/model/scripts/arp_to_mixamo.txt` — GUI 에는 **절대경로** | — | 아래 |
| Export Twist (`arp_export_twist`) | **OFF** | ⚠️ **ON** | Mixamo 에 대응 본이 없다. **끄는 것이 수동 작업**이다(`auto_rig_ge.py:11945` `default=True`) |
| Full Facial (`arp_full_facial`) | OFF | OFF | 128px 셀에서 보이지 않는다 |
| Units x100 (`arp_units_x100`) | **OFF** | ⚠️ **ON** | **끄는 것이 수동 작업이다**(실측: 새 씬에서 `True`). 켜진 채 내보내면 **100배 크기**로 나가고, sheet.py 는 프레이밍을 bbox 로 맞추므로 **아틀라스는 멀쩡해 보인다** — 나중에 다른 자산과 섞일 때 드러난다 |
| Metacarpal Fingers (`arp_ge_export_metacarp`) | OFF | OFF | Mixamo 손 계층에 대응 마디가 없다 |
| Engine Type (`arp_engine_type`) | `OTHERS` 권장 | `UNITY` | 본 이름은 매핑표가 정하므로 대개 그대로 둬도 되지만, 엔진별 추가 rename 규칙을 타지 않게 `OTHERS` 가 안전하다 |
| Bake Animation (`arp_bake_anim`) | **OFF** | ON | 이 단계에서는 **리그만** 내보낸다. 애니메이션은 ⑦ 이 별도로 붙인다 |

</details>

[scripts/arp_to_mixamo.txt](scripts/arp_to_mixamo.txt) 가 `root.x = mixamorig:Hips` 형태로
**몸통 6 · 팔 8 · 다리 8 · 손가락 30** 을 매핑한다. ARP 의 `rename_custom()` 이 `=` 로
분리해 읽으며 **없는 본은 조용히 건너뛴다**.

⚠️ **export 로그에 `Invalid renaming syntax, skip:` 이 30여 줄 찍힌다.** 매핑표의 주석·빈
줄마다 나오는 것이라 **정상이다**(`auto_rig_ge.py:10411-10415`). 다만 그 노이즈에 진짜
실패가 묻히므로, 매핑표 주석에 **본 이름과 `=` 를 함께 쓰지 말 것** — 매핑 줄로 해석된다.

⚠️ **본 이름을 직접 고칠 때 빠지기 쉬운 함정 둘** — 둘 다 실제로 겪었다:

| | 원본 ARP 리그 | **HUMANOID export 리그**(rename 대상) |
|---|---|---|
| 팔다리 | `arm.l`(IK/FK 중간) · `arm_stretch.l`(deform) | **`arm_stretch.l`** — `_stretch` 만 나온다 |
| 손가락 1번 | `thumb1.l` (`c_` 없음) | **`c_thumb1.l`** — 세 마디 전부 `c_` |

`rename_custom()` 이 적용되는 대상은 원본이 아니라 GE Export 가 만드는 **임시 리그
(`_arpexp`)** 다. ARP 는 원본 이름에서 `c_` 를 뗐다가 Humanoid 면 전부 다시 붙인다
(`auto_rig_ge.py:8587-8589`).

내보낼 곳은 **모델과 같은 폴더, 같은 이름**이다:

```
game-assets/characters/pc/<중간>/<NAME>/<NAME>.fbx     ← ARP export 결과(리그만·애니 없음)
                                <NAME>_raw.fbx        ← ③ 의 원본. 지우지 않는다
```

## ⑤-L 다리 모으기 — 벌어졌으면 **자동으로 모은다** 🦵

🛑 **`pc`·`mob` 은 다리가 벌어져 있으면(발 폭의 50% 초과) 사용자가 시키지 않아도 여기서
자동으로 모은다**〔원저자 지시 2026-08-07〕. 예전에는 "벌어졌으면 재생성" 이 유일한 답이라
크레딧 55~65 와 4분을 다시 쓰고도 또 벌어져 나오기 일쑤였다.

```bash
# 자동 — 벌어졌을 때만 동작하고, 이미 모여 있으면 아무것도 하지 않는다(SKIP)
blender --background --python .claude/skills/model/scripts/close_legs.py -- \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.fbx \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.legs.blend
```

| 언제 | 무엇을 한다 |
|---|---|
| 발 폭의 **50% 초과**(check_leg_gap 의 FAIL/WARN) | **자동으로 모은다** — 사용자 지시 불필요 |
| 이미 모여 있다(50% 이하) | **손대지 않는다**(SKIP). 멀쩡한 자산을 건드리지 않기 위해서다 |
| 사용자가 "다리 모아줘" 라고 **따로 요청** | `--force` 로 모여 있어도 목표까지 모은다 |
| 더 바짝/느슨하게 | `--gap-ratio 0.15`(바짝) · `0.45`(느슨). 기본 0.30 |

무엇을 하는가 — 좌우 다리마다 **엉덩이를 고정한 채 다리 전체를 안쪽으로 회전**하고
(무릎은 다리에 매달려 함께 들어온다), **발은 회전 전 방향으로 복원**해 까치발을 막고,
그 포즈를 **rest pose 로 굳힌다**. 회전으로 발이 지면을 뚫으면 전체를 z 이동해 다시 세운다.

실측(2026-08-07 `suit_bot` 을 20° 벌린 테스트 케이스):

| | 다리 간격 | 판정 |
|---|---|---|
| 교정 전 | 66.5 cm = 발 폭의 **132%** | 🛑 FAIL |
| 교정 후 | 5.8 cm = 발 폭의 **34%** | ✅ PASS |

🛑 **반드시 ⑦ 앞에서 돌린다.** ⑦ 은 캐릭터의 rest pose 를 기준으로 애니메이션을 다시
굽는다. ⑦ **뒤에** 다리를 모으면 이미 구워진 액션과 rest 가 어긋나 전신이 뒤틀린다.

🛑 **출력은 `.blend` 다(FBX 아님).** 교정한 리그를 FBX 로 다시 내보내면 rest 가 달라질
위험이 있어 모은 의미가 사라진다(⑦ 머리말의 실측 경고와 같은 이유). **`retarget_to_arp_rig.py`
는 `.blend` 캐릭터 입력을 받으므로**, ⑤-L 을 돌렸다면 ⑦ 에 `.fbx` 대신 이 `.blend` 를 넘긴다.

⚠️ **결과가 여전히 50% 를 넘으면**(`[WARN]`) 다리가 아니라 **골반이 넓거나 발 자체가
바깥으로 퍼진** 모델이다. `--gap-ratio` 를 낮춰 다시 시도하고, 그래도 안 되면 그때 ② 재생성으로
간다. 다리를 완전 수직 이상으로 모으면 X 자가 되므로 스크립트가 상한을 둔다.

## ⑥ 리그 검증 (생략 금지)

```bash
# 프로젝트 루트에서 실행한다(Blender 는 --python 경로를 cwd 기준으로 연다)
blender --background --python .claude/skills/model/scripts/verify_mixamo_rig.py -- \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.fbx \
  game-assets/animations/default
echo "종료코드=$?"        # 0 = 통과, 1 = 실패
```

sheet.py 의 판정을 **그대로** 옮겨 아틀라스를 굽기 전에 같은 검사를 돌린다. 전부 `OK` 여야
한다:

```
[OK  ] Mixamo 리그로 감지됨 (22/22 역할)
[OK  ] 스킨 연결됨 (메시 1개)
[OK  ] 메시 '…' 의 정점 그룹이 전부 본과 일치     ← rename 후 vgroup 이 안 따라오면 스킨이 끊긴다
[OK  ] 발이 원점 근처
[OK  ] idle: 애니본 65 · 180프레임 · 교집합 52 ≥ 32 → 리타게팅 없이 직접 적용
[OK  ] walk / run / attack / death …
```

⚠️ **판정 기준이 둘이고, 엄격한 쪽은 역할이 아니라 본 이름 교집합이다.**

| | 기준 | 어디 |
|---|---|---|
| 리그 종류 인정 | Mixamo 22역할 중 **8개** 이상 | `_sheet_render.py:321` |
| **애니 직접 적용** | **본 이름 교집합 ≥ `max(8, 애니본×0.5)`** | `_sheet_render.py:451` |

Mixamo 애니는 65본이라 **임계가 32** 다. 22역할을 다 채워도 손가락이 빠지면 교집합이 22 라
**미달 → 정적**이 된다. 그리고 이때 **구제 경로가 없다** — `_sheet_render.py:457` 은 두 리그가
*다를* 때만 retarget 하는데, 캐릭터·애니가 둘 다 mixamorig 이면 그 조건이 거짓이라 곧바로
`####WARN … → 정적` 으로 떨어진다. 그래서 매핑표에서 **손가락 30줄을 빼면 안 된다.**

**`FAIL` 이면 ⑤ 로 돌아간다.** 실패 양상은 **둘이고 증상이 전혀 다르다**:

| 무엇이 잘못됐나 | 증상 | 원인 |
|---|---|---|
| rename 이 **통째로** 실패 | `sheet.py` 가 **시작도 못 하고 종료** — `❌ … Mixamo rig 가 아닙니다` | `Rename Bones from File` OFF 또는 파일 경로 오류. ARP 는 파일을 못 찾아도 `Rename Bone File not found! Skip renaming` 만 찍고 **그냥 진행**한다(`auto_rig_ge.py:10406`). 종료시키는 쪽은 `sheet.py` `assert_mixamo_rig()`(실측 `:417-430`) 다 |
| rename 이 **부분** 실패 | 렌더는 끝나는데 **5행동이 전부 같은 포즈** | 교집합이 임계 미달. 매핑표의 본 이름이 export 리그와 어긋난 것 |

⚠️ **background 실행 시 ARP 가 `arp_debug_mode` AttributeError 를 뱉는다**(실측).
씬 로드 핸들러가 GUI 속성을 찾는 것이라 **무해하다** — 검증 출력은 그 아래에 나온다.

판정 로직 자체의 테스트는 Blender 없이 돈다:

```bash
python3 .claude/skills/model/scripts/test_verify_mixamo_rig.py    # 22개
```

## ⑦ rest pose 보정 — **Phase A 의 마지막이자 계약물** 🛑

⚠️ **⑥ 이 전부 `OK` 여도 애니메이션을 그대로 쓰면 안 된다.** 검증이 통과시키는
"리타게팅 없이 직접 적용" 은 **본 이름이 맞다**는 뜻이지 **포즈가 맞다**는 뜻이 아니다.

`_sheet_render.py:451` 은 본 이름 교집합이 임계를 넘으면 **rest pose 보정 없이 액션을
그대로 할당**한다. Mixamo 로 리깅된 캐릭터끼리는 rest 가 같아 그래도 맞지만, **ARP 리그는
이름만 Mixamo 이고 rest pose(본 방향·roll)가 다르다** — 실측 결과 **5행동 전부 팔이
만세로 올라간 스프라이트**가 나왔다. 예외도 경고도 없다.

```bash
blender --background --python .claude/skills/model/scripts/retarget_to_arp_rig.py -- \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.fbx \
  game-assets/animations/default \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.blend
```

🦵 **⑤-L 로 다리를 모았다면 첫 인자를 `<NAME>.legs.blend` 로 바꾼다** — 그러지 않으면
교정 전 리그를 쓰게 되어 **다리가 다시 벌어진다**:

```bash
blender --background --python .claude/skills/model/scripts/retarget_to_arp_rig.py -- \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.legs.blend \
  game-assets/animations/default \
  game-assets/characters/pc/<중간>/<NAME>/<NAME>.blend
```

캐릭터 + 보정된 액션 5종을 담은 **`<NAME>.blend`** 가 나온다. 이 스크립트가 지키는 것 셋:

| | 왜 |
|---|---|
| **월드 기준** 상대 회전<br>`(src_pose @ src_rest⁻¹) @ tgt_rest` | `_sheet_render.py` 의 `retarget_action` 은 **로컬 기준**이고, 그 식은 두 리그의 **본 로컬 축(roll)이 대응할 때만** 맞다. ARP GE Export 는 본 축을 자체 규약으로 정하므로 로컬 기준으로 옮기면 **다리는 맞고 팔만 틀어진다**(실측) |
| 결과를 **`.blend`** 로 (FBX 아님) | 리타게팅 직후엔 정확한데, Blender 기본 exporter 로 FBX 를 내보내 다시 임포트하면 **rest 가 달라져 또 T-포즈로 벌어진다**(실측). 캐릭터 FBX 는 ARP GE Export 가, 애니 FBX 는 Blender 가 만들어 축 규약이 갈린다 |
| `action_slot` 지정 | Blender 4.4+ 의 slotted action — slot 을 안 잡으면 액션이 **조용히 평가되지 않는다**(정적 T-포즈) |

## ✅ Phase A 완료 조건

여기까지 통과하면 **3D 자산이 완성된 것**이고, 2.5D 가 필요 없으면 **여기서 끝내도 된다.**

0. 🦵 **다리·무릎·발이 모여 있다** — `check_leg_gap.py` 가 **PASS**(발 폭의 50% 이하).
   벌어졌으면 ⑤-L `close_legs.py` 로 모으고, 그래도 `[WARN]` 이면 그때 ② 재생성
1. ④ `Match to Rig` 를 눌렀다 — `<NAME>_rig.blend.log.json` 에 `match_to_rig`·`bind_to_rig`
2. ⑤ `arp_export_mixamo.py` 종료 0 — 로그에 `verify … leftover_count: 0`,
   `texture_paths … missing` 이 **빈 배열**
3. ⑥ `verify_mixamo_rig.py` 종료 0 (22/22 역할 · 교집합 ≥ 32)
4. ⑦ 리타게팅 로그에 `[OK] <행동>` 이 **5줄** → `<NAME>.blend` 생성
   (⑤-L 을 돌렸다면 **입력이 `.legs.blend` 였는지** 확인 — `.fbx` 를 넣으면 다리가 도로 벌어진다)
5. 계약 파일이 한 폴더에 다 있다 → 다음 절의 표
6. (3D 로 바로 쓸 것이면) Blender 로 열어 액션 5종이 실제로 재생되는지 눈으로 확인

🛑 **아틀라스는 Phase A 의 완료 조건이 아니다.**

---

# 🤝 Phase 경계 계약 (A → B 인계)

**두 단계를 다른 세션·다른 날에 나눠 하면 여기서 사고가 난다.** Phase B 만 따로 돌릴 때는
아래 셋을 반드시 확인하고 시작한다.

## (1) 파일 — 한 폴더에 같이 있어야 한다

| 파일 | 필수 | 없으면 |
|---|---|---|
| **`<NAME>.blend`** (⑦) | ✅ | Phase B 입력 자체가 없다 |
| **`<NAME>_raw.fbm/`** (텍스처 폴더) | ✅ | 🛑 `.blend` 는 텍스처를 **품고 있지 않고 외부 파일로 참조**한다(`retarget_to_arp_rig.py` 는 `save_as_mainfile` 만 하고 `pack_all` 을 하지 않는다). `.blend` 만 복사해 굽으면 **회색·무채색 스프라이트**가 나온다 — 분리 후 가장 흔할 오용이다 |
| `<NAME>.fbx` (⑤) | ⭕ | 재보정·디버깅용 보관물 |
| `<NAME>.legs.blend` (⑤-L) | ⭕ | 다리를 모은 경우에만 생긴다. ⑦ 의 입력이 **이것**이었어야 한다 |
| `<NAME>_rig.blend` (④) | ⭕ | 재리깅 원본. 지우면 ④ GUI 부터 다시 |
| `<NAME>_raw.fbx` (③) | ⭕ | 재리깅용 원본. 지우면 Tripo 크레딧 재소모 |

## (2) 게이트 — Phase A 를 통과했다는 증거

1. ⑤ 종료 0 + `<NAME>.fbx.log.json` 의 `verify.leftover_count == 0`
2. ⑥ `verify_mixamo_rig.py` 종료 0
3. ⑦ 로그에 `[OK] <행동>` **5줄**

## (3) 인자 — `.blend` 안에 없어서 반드시 넘겨야 하는 것

| 인자 | 실제 동작 | 위험도 |
|---|---|---|
| **`--animations built-in`** | 생략하면 모델 폴더 → `animations/<NAME>/` → `default` 순으로 자동 탐색해 **원본 Mixamo fbx** 를 집는다 → ⑦ 의 보정이 무시돼 **팔 만세 재현** | 🛑 **진짜 조용한 실패.** Phase B 단독 실행 시 반드시 명시 |
| **`--kind`** | 비대화형에서 누락하면 **명시적으로 종료**하고, 대화형이면 물어본다. 위험은 *누락* 이 아니라 **틀린 값** — kind 하나가 방향·셀·표시크기·행동을 전부 정한다(`sheet.py` `KIND_POLICY`) | 🛑 `boss`/`minion`(8방향)을 16방향으로 굽는 것은 **명시된 회귀** |
| `--name` | 생략하면 **모델 파일 이름**으로 기본화된다. 폴더명 = 아틀라스 이름 = 런타임 조회 키 | ⚠️ 파일명과 자산 이름이 같으면 안전 |
| `--output` | 생략 = 프로젝트 `assets/` + `pubspec.yaml` 자동 등록 / 지정 = 그 폴더에만 저장(pubspec 손대지 않음) | ⚠️ 실패가 아니라 **정책 선택** — "후보만 굽기" 인지 "게임에 넣기" 인지 고른다 |

🛑 **경로 추론은 프로젝트 트리 안에서만 된다.** `sheet.py` 의 `infer_kind_name_from_path()` 는
`characters/<kind>/…` 형태에서만 kind·name 을 뽑고 **프로젝트 루트 밖 경로는 추론을 거부**한다.
`outputs/` 같은 작업 폴더에서 구우면 `--kind`·`--name` 을 **직접 줘야 한다.**

---

# Phase B — 2.5D 아틀라스 굽기 (⑧~⑨)

**입력은 ⑦ 이 만든 `<NAME>.blend`** 이고, 코드 소유자는 이 스킬이 아니라
[texture-packer 스킬](../texture-packer/SKILL.md)이다. **옵션·발 정렬·색 압축·잘림 검사의
SSOT 는 거기이며, 이 절은 호출 방법과 함정만 적는다.**

## ⑧ texture-pack — 16방향 5행동

```bash
python3 .claude/skills/texture-packer/scripts/sheet.py \
  ./game-assets/characters/pc/<중간>/<NAME>/<NAME>.blend \
  --animations built-in --auto
```

액션 이름이 `idle`/`walk`/`run`/`attack`/`death` 라 `match_embedded` 가 정확 매칭한다
(`_sheet_render.py:489`). 로그에 **`애니 소스 : 캐릭터 내장(built-in)`** 이 찍히는지 볼 것.

<details>
<summary>⑦ 없이 FBX 를 직접 주는 옛 방식 (Mixamo 로 *리깅된* 캐릭터에만 유효)</summary>

```bash
python3 .claude/skills/texture-packer/scripts/sheet.py \
  ./game-assets/characters/pc/<중간>/<NAME>/<NAME>.fbx \
  --animations default --auto
```
ARP 리그에는 쓸 수 없다 — 팔이 만세로 나온다(⑦ 참조).
</details>

### kind 가 규격을 통째로 정한다 — SSOT 는 `sheet.py` 의 `KIND_POLICY`

| kind | 방향 | 셀 | 화면 표시 | 기본 행동 |
|---|---|---|---|---|
| `pc` | 16 | 128 | 128 | idle · walk · attack · death · run |
| `mob` | 16 | 128 | 128 | idle · walk · attack · death (run 제외) |
| `npc` | **1** | 128 | 128 | idle (24프레임) |
| `boss` | **8** | **256** | **256** | idle · walk · attack · death |
| `minion` | **8** | **64** | **64** | idle · walk · attack · death |

🛑 **`boss`(8방향) · `minion`(8방향·64셀) 을 "16방향으로 고쳐" 재생성하지 말 것 — 그것이 회귀다.**
이 표는 편의용 사본이므로, 어긋나면 **`KIND_POLICY` 가 맞다.**

### 옵션에서 실제로 자주 틀리는 것

| | 사실 | 왜 중요한가 |
|---|---|---|
| `--auto` 와 `--scale-<action>` | **배타적이다.** `--auto` 는 `--auto-fit-scale` 을 켜고, 그러면 모든 행동 scale 이 **1.0 고정**이 되어 `--scale-*`·전역 `--scale` 이 **전부 무시**된다 | ⑨ 가 제안하는 `--scale-attack 0.85` 를 `--auto` 와 함께 주면 **아무 일도 안 일어난다**. 둘 중 하나만 쓴다 |
| 회전 packing | 캐릭터 계열(`pc/mob/npc/boss/minion`)은 **`--auto` 만 줘도 자동으로 `rotation=false`** 다(`ACTOR_KINDS` 판정). 비대화형 기본도 false | `--rotation false` 를 굳이 병기할 필요가 없다. 반대로 **`--rotation true` 를 억지로 켜면** 발 위치가 어긋나고 16방향 패킹이 20분 넘게 걸린다 |
| `--vivid` | 기본 **9**(최대). `--auto` 도 9 | "5" 로 적힌 문서가 있으면 그 문서가 틀린 것이다 |
| 행동별 생성 scale 기본값 | **전부 1.0**. 과거의 walk 0.9 / attack 0.8 일괄 축소 프리셋은 **폐기됐다** | 셀 확대는 RAM(iOS OOM)과 page 폭(8192 한계)을 키운다. 잘리는 행동만 auto-fit 이 낮춘다 |
| 색 압축 | 프로젝트 루트에 `scripts/compress_image.py` 가 있으면 **자동으로 동작**한다(import → `uv run` 폴백). 판정은 로그에 **`⚠️ 압축 실패` 가 없는지**로 한다 | 이 스킬을 **단독 clone** 한 환경에는 그 파일이 없어 압축이 조용히 건너뛰어질 수 있다. 그때만 PNG 가 몇 배로 커진다 |

### 프레임 수와 메모리는 한 몸이다

| 항목 | 값(pc 기본) |
|---|---|
| 방향 | **16** |
| 셀 | 128px |
| 행동·프레임 | **pc** `idle 8` · `walk 12` · `attack 16` · `death 8` · `run 12` = 56프레임<br>**몬스터(mob·boss·minion)** `idle 8` · `walk 12` · `attack 10` · `death 6` = **36프레임**(2026-08-12 `MONSTER_FRAMES`) |
| 총 셀 | pc 56 × 16 = **896** · mob 36 × 16 = **576** · boss/minion 36 × 8 = **288** |
| 산출 | `assets/pc/<NAME>/<NAME>.png` + `.atlas` (+ `--output` 미지정 시 `pubspec.yaml` 자동 등록) |

> 🛑 **몬스터는 pc 보다 적게 굽는다** — atlas RAM ≈ page W×H×4 라 셀 수 감축이 그대로 RAM 감축이고
> (65종 실측 1112→899MB, −19.2%), **화질 손실은 0**. 재생 속도는 클라가 흡수한다
> (`_atlasActions` = 한 바퀴 목표 시간). SSOT 는 `sheet.py`·`sheet-win.py` 의 `MONSTER_FRAMES`
> — **두 파일을 반드시 함께** 고친다.

프레임 수를 바꾸려면 `--idle 8 --walk 12 --attack 10 --death 6` 처럼 개별 지정한다.
**애니메이션 원본 길이는 idle 180 · walk 31 · run 16 · attack 38 · death 72 프레임**(실측)
이므로, 기본값은 그 구간을 균등 샘플링한 것이다.

🛑 **프레임을 늘리면 부드러워지지만 RAM 이 그대로 늘어난다.** 게임의 메모리 공식은
**`RAM ≈ 원본 PNG 가로 × 세로 × 4`** 이고, 프레임 수는 page 픽셀을 직접 키운다.
**색 압축(256색)은 디스크·번들만 줄이고 RAM 은 1바이트도 줄이지 못한다** — 둘을 혼동하면
"압축했으니 괜찮다" 며 OOM 으로 되돌아간다. 근거 없이 프레임을 늘리지 말 것.

## ⑨ 아틀라스 검증 (생략 금지)

리깅은 조용히 실패한다. 키프레임이 들어갔는데 포즈만 뒤틀리는 경우가 있으므로
**눈으로 확인해야 한다.**

**셀 잘림은 sheet.py 가 이미 검사했다** — `--verify-cells` 기본값이 `true` 라 렌더 직후
낱장 프레임을 훑고, 잘린 행동이 있으면 권장 옵션을 출력한다. 그 줄을 놓치지 말 것:

```
🛑 잘린 행동 2종 — 아래 옵션으로 재생성 권장:
   --scale-attack 0.85 --scale-run 0.9
```

⚠️ **이 제안을 `--auto` 와 함께 주면 무시된다**(위 옵션표). `--auto` 없이 `--scale-*` 만
주거나, `--auto` 에 맡겨 auto-fit 이 수렴할 때까지 두거나 **둘 중 하나**를 고른다.

⚠️ **`verify_cells.py --atlas` 로 판정하지 말 것.** packed 아틀라스는 trim 후라 원본
잘림이 보이지 않아 정상 자산도 전부 후보로 찍힌다. **자동 게이트는 `--frames` 모드뿐**이다
(종료 코드 0=정상 / 2=잘림 / 1=오류):

```bash
python3 .claude/skills/texture-packer/scripts/verify_cells.py --frames outputs/<NAME>/frames
```

그리고 `assets/pc/<NAME>/<NAME>.png` 을 **Read 로 열어** 확인한다 — 여기부터는 자동화할
수 없다:

- 5행동이 모두 **다른 포즈**인가 (전부 같으면 애니메이션이 안 붙은 것 → ⑥⑦ 재실행)
- 16방향이 실제로 돌아가는가
- 팔다리가 뒤틀리지 않았는가 (뒤틀렸으면 ④ 의 마커 위치 → 재리깅)
- **`walk`·`run` 에서 다리를 벌린 채 걷지 않는가** — 정면(`S`)·후면(`N`) 프레임에서
  두 다리 사이가 계속 벌어져 있으면 **모델 자체가 다리를 벌리고 생성된 것**이다.
  리깅·리타게팅의 실패가 아니므로 ⑥·⑦ 을 다시 돌려도 바뀌지 않는다 → ② 부터 재생성
- 색이 살아 있는가 (회색·무채색이면 텍스처 폴더 누락 → 경계 계약 (1))
- 발 높이가 행동별로 튀지 않는가 (`align_feet` 가 셀의 **0.85** 지점에 발을 고정한다)

🛑 **정지 이미지만으로는 방향 전환과 발 튐을 못 잡는다.** 움직임을 반드시 한 번 본다 —
같은 저장소에 스프라이트 뷰어가 있으면 그것으로, 없으면 앱을 **재빌드**해서(아틀라스 교체는
hot reload 로 안 잡힌다) 확인한다.

## ✅ Phase B 완료 조건

1. **진입 검사 통과** — 경계 계약 (1)(2)(3) 을 확인하고 시작했다
2. 렌더 로그에 `애니 소스 : 캐릭터 내장(built-in)` + `####ANIM <행동> ← '<액션>'` **5줄**,
   `####WARN … 정적` **0줄**
3. `verify_cells --frames` 종료 코드 0 (또는 auto-fit 수렴 로그로 잘림 0)
4. 압축 로그에 `⚠️ 압축 실패` 없음
5. 산출 위치와 `pubspec.yaml` 등록 여부가 의도와 일치한다
6. 낱장 프레임 몽타주를 **눈으로** 확인했다(위 5항목)
7. **움직임을 봤다** — 뷰어 또는 앱 재빌드 후 로드
8. 🛑 여기까지 통과해도 **게임 화면에 새 캐릭터로 등장하는 것은 별개**다 → 다음 절

---

# 게임에 실제로 보이게 하려면 — 노출은 4층이다

🛑 **아틀라스를 구웠다고 게임에 새 캐릭터가 나타나지 않는다.** 이것이 이 파이프라인에서
가장 오해가 잦은 지점이고, **"안 보인다" 를 정상으로 넘기면 진짜 실패까지 묻힌다.**

**안 보이면 순서를 지켜 판정한다 — 먼저 굽는 쪽부터 의심한다:**

1. **굽는 쪽 게이트(⑤⑥⑦⑨)가 전부 통과했는가?** 하나라도 실패면 그것이 원인이다
   (본 이름 어긋남 → 정적 프레임 / 텍스처 누락 → 회색 / 잘림).
2. 게이트가 다 통과했다면, **아래 4층 중 연결되지 않은 층**이 원인이다:

| 층 | 폴더 이름만으로 되는가 | 확인할 곳(라리엔 기준) |
|---|---|---|
| ① 월드 아틀라스 로드 | ✅ **된다** — 번들 매니페스트를 훑어 폴더명으로 연다 | `actor_animation_set.dart` `availablePcKinds()` |
| ② 번들 등록 | ❌ `pubspec.yaml`(또는 원격 자산 목록)에 들어가고 **앱 재빌드** 필요 | `pubspec.yaml` 의 `AUTO(sheet.py packed actors)` 블록 |
| ③ 캐릭터 **미리보기**(생성·목록 화면) | ❌ **아니다** — `assets/pc/<gender>/<gender>.atlas` 로 **`male`/`female` 고정** | `character_preview_atlas.dart` |
| ④ 다른 플레이어에게 보이는 **외형** | ❌ **아니다** — 서버가 `외형코드 = 세트번호×2 + 성별` 로 만들고 클라가 번호표로 되돌린다 | 서버 `equip.go` `effectiveAppearance()` · 클라 `kindForAppearanceCode()` |

즉 **①②만 하면 내 화면의 월드에는 뜨지만, 캐릭터 만들기 화면과 남의 화면에는 안 뜬다.**
③④ 는 코드·서버 매핑을 추가해야 하며 **이 스킬의 범위 밖**이다.

---

# 3D 모델을 그대로 쓰기 (Phase A 만 필요한 경우)

**Phase A 의 `<NAME>.blend` 는 다음 용도로 그대로 쓸 수 있다:**

| 용도 | 쓰는 파일 | 비고 |
|---|---|---|
| **Blender 후속 편집** — 무기 손 장착, 홀로그램 재질, 밝기·색 보정, 스크린샷 | `<NAME>.blend` | 관련 스킬들이 `.blend`/`.fbx` 를 그대로 입력으로 받는다 |
| **재렌더 원본** — 프레임 수·scale·kind 를 바꿔 아틀라스를 다시 굽기 | `<NAME>.blend` | 이것을 지우면 ⑦ 부터 다시 |
| **재리깅 원본** | `<NAME>_raw.fbx` + `<NAME>_rig.blend` | Tripo 크레딧을 다시 쓰지 않는다 |

🛑 **외부 3D 엔진(Unity/Unreal 등)에 납품하는 baked GLB/FBX 는 Phase A 의 계약물이 아니다.**
별도 export + 재임포트 검증이 필요하고, **rest pose 가 보존되는지 아직 실측되지 않았다** —
FBX 왕복에서 rest 가 무너지는 것은 실측으로 확인됐고(⑦), glTF/GLB 는 시도 기록이 없다.
필요해지면 **⑦ 의 `.blend` 를 입력으로 하는 새 절차**를 만들고 "실험" 으로 표기해 검증부터 한다.

🛑 **아래 레거시 GLB 스크립트를 여기에 끌어다 쓰지 말 것** — Tripo 오토리깅 41본
(`Hip`/`L_Upperarm`) 전제라 ARP 의 `mixamorig:*` 65본에는 매핑이 통째로 어긋난다.

---

## 산출물

```
game-assets/characters/pc/<중간>/<NAME>/        # <중간> 은 분류용 — sheet.py 는 이름을 안 본다
├── <NAME>_raw.fbx      # ③ Tripo 원본(리깅 전) — 지우지 않는다
├── <NAME>_raw.fbm/     # 텍스처 — 🛑 Phase B 에 반드시 동반돼야 한다
├── <NAME>.fbx          # ⑤ ARP 리깅 + Mixamo 본 이름 (리그만·애니 없음)
├── <NAME>.legs.blend   # ⑤-L 다리를 모은 리그(벌어졌을 때만 생긴다) ← ⑦ 의 입력
├── <NAME>.blend        # ⑦ rest pose 보정 + 액션 5종 ← **Phase A 계약물 · Phase B 입력**
└── <NAME>_rig.blend    # ARP 리그 원본(컨트롤러 포함) — 재리깅용으로 반드시 남긴다

assets/pc/<NAME>/
├── <NAME>.png          # ⑧ packed atlas
└── <NAME>.atlas        # flame_texturepacker 메타 (+ laryen.actionScale.* 헤더)
```

런타임 쪽 규약(이미 구현돼 있다 — 이 스킬이 맞춰야 하는 계약):

| 무엇 | 값 |
|---|---|
| region 이름 | `<action>_<DIR16>` (예: `walk_ESE`). 8방향 kind 는 짝수 라벨만 |
| 행동 | `idle` `walk` `run` `attack` `death` (`hit` 는 굽지 않고 런타임이 idle 로 폴백) |
| 행동별 배율 | `.atlas` 헤더의 `laryen.actionScale.<action>` 을 `1/scale` 로 되돌림 |
| 표시 크기 | `.atlas` 헤더의 `laryen.displaySize`(boss 256 · minion 64, 기본 128 은 생략) |
| trim 복원 | `useOriginalSize: true` — 없으면 방향마다 발 위치가 떤다 |

구현 위치는 프로젝트마다 다르다(라리엔 기준 `lib/features/game/render/actor_animation_set.dart`).
**이 스킬은 독립 저장소이므로 특정 프로젝트의 파일 경로를 단정하지 않는다** — 실제 파일을
찾아서 확인할 것.

## 스크립트의 SSOT

**이 스킬의 `scripts/` 가 원본이다.** 같은 스크립트가 다른 스킬(예: `actor`)에도 복사돼
있으면 **그쪽이 사본**이고, 고칠 때는 여기를 고친 뒤 사본을 맞춘다. 사본을 먼저 고치면
조용히 갈라진다(실측: 5개 파일이 바이트 단위로 같았다).

⚠️ **이 스킬은 독립 저장소(submodule)로 배포된다.** 그래서 상위 프로젝트의 경로
(`.claude/skills/actor/scripts/…` 등)를 **필수 의존으로 삼지 않는다** — 있으면 쓰고
없으면 대체 수단을 안내하는 식으로만 참조한다(②-V 가 그 예다).

## 사용자에게 반드시 알릴 것

- **④ 는 GUI 작업이라 자동으로 끝나지 않는다.** 마커 확인과 웨이트 확인은 사람이 본다.
  MCP 로 자동화하더라도 **마커 위치와 최종 아틀라스는 반드시 이미지로 보여준다**
- **⑤ 부터는 전부 명령 한 줄이다** — 여기서 막혔다고 mixamo.com 으로 우회하지 말 것
- 🦵 **다리가 벌어져 있었으면 ⑤-L 에서 자동으로 모았다는 사실을 알린다** — 교정 전후
  간격(%)과 회전각을 함께. 사용자가 원래 자세를 원했을 수도 있으므로 되돌리는 법
  (⑦ 에 `.fbx` 를 넘기면 원래대로)도 한 줄 덧붙인다
- **크레딧 소모** — 생성 55~65, Export 40 정도. **리깅 20 은 이제 들지 않는다.**
  다리가 벌어져도 이제 재생성하지 않으므로 그만큼 더 아낀다
- 🕷️ **동물형(비인간형)이면 이 문서가 아니라
  [references/non-humanoid.md](references/non-humanoid.md) 를 탔다는 사실을 알린다** —
  규격이 다르다(8방향·4행동·128). 어느 경로로 구웠는지 밝히지 않으면 사람이 16방향
  기준으로 검수하다 "방향이 절반뿐" 이라고 오해한다
- 애니메이션 폴더에 **실제로 무엇이 있는지**(6개 중 5개 사용) — 없는 행동은 정적 프레임이 된다
- **Phase A 만 필요한지 B 까지 필요한지 먼저 확인**한다. A 만이면 ⑦ 에서 끝난다
- 아틀라스 크기·프레임 수는 조정 가능하다(위 표) — 용량이 문제면 프레임을 줄인다
- **`<NAME>.blend` 를 지우면** 아틀라스를 다시 구울 때 리타게팅부터 해야 한다
- **아틀라스를 구웠다고 게임에 나오는 것이 아니다**(노출 4층). 어디까지 됐는지 명확히 보고할 것
- 소요 시간 실측(우주복 캐릭터 1종) — 생성 4분 · 리깅 15분 · 리타게팅 2분 ·
  packing 1분 30초(auto-fit 재렌더 포함 시 3분)

## 자주 겪는 문제

| 증상 | 대처 |
|---|---|
| **Phase B 만 돌렸더니 5행동이 전부 같은 포즈** | `--animations built-in` 을 빠뜨렸다. 자동 탐색이 원본 Mixamo fbx 를 집은 것이다(경계 계약 (3)) |
| **Phase B 만 돌렸더니 회색·무채색** | `.blend` 만 복사했다. `<NAME>_raw.fbm/` 텍스처 폴더가 같은 폴더에 있어야 한다(경계 계약 (1)) |
| **⑤ 의 FBX 를 "3D 완성" 으로 넘겼는데 애니가 없다** | 정상이다. `arp_bake_anim=False` 라 리그만 들어 있다. 애니가 필요하면 ⑦ 까지 |
| 버튼을 눌렀는데 아무 일도 안 일어남 | `evaluate_script` 대신 **`click` 도구에 uid**. 크레딧 차감으로 실행 확인 |
| 다운로드가 오지 않음 | 8k 텍스처가 원인. `2k` 로 재시도(크레딧은 차감되므로 처음부터 2k) |
| `Model count limit exceeded` | 계정 저장 한도 초과. 에셋 삭제는 되돌릴 수 없으므로 **반드시 사용자 확인 후** |
| **"ARP 로는 Mixamo 리그를 못 만든다" 는 판단에 도달** | 🛑 **거의 항상 오진이다.** ④ 로그(`<NAME>_rig.blend.log.json`)에 `match_to_rig`·`bind_to_rig` 가 있으면 리깅은 성공한 것이고, 남은 것은 ⑤ 를 **실행하지 않은 것**뿐이다 |
| ARP `Go!` 에서 실패 | 스케일이 1 이 아니거나(Apply All Transforms) 메시가 여러 개로 쪼개져 있다 |
| **`Click "Match to Rig" before binding/exporting`** | ④-3 을 건너뛴 것이다. reference bones 를 손본 뒤에도 **다시 눌러야** 한다 |
| ARP 리그가 몸에 안 맞음 | 마커 위치 문제. 헬멧·백팩이 있으면 목·어깨를 손으로 옮긴다 |
| `sheet.py` 가 `Mixamo rig 가 아닙니다` 로 즉시 종료 | rename 이 **통째로** 실패했다. `Rename Bones from File` 이 켜져 있었는지·경로가 맞는지 확인 |
| 검증에 `spine2 가 비었다`(21/22) | Spine Count 가 3 이다. `arp_export_mixamo.py` 가 `set_spine(4)`+`match_to_rig()` 로 자동 보정한다(`--no-spine-fix` 로 끌 수 있다) |
| 검증에 `ARP 이름이 남아 있는 본 … c_thumb1.l` | 매핑표가 export 리그 이름과 어긋났다. 손가락 세 마디 전부 `c_` 다 |
| 정점 그룹이 본과 이름이 다름 | rename 이 vgroup 에 반영되지 않았다. ARP GE Export 를 쓰지 않고 손으로 rename 했을 때 발생 |
| **5행동이 움직이긴 하는데 팔이 전부 만세** | ⑦ 을 건너뛰었다. 본 이름이 다 맞아도 **ARP rest pose ≠ Mixamo rest pose** 다 |
| 리타게팅했는데 **다리는 맞고 팔만 틀어짐** | 로컬 기준으로 보정한 것이다. **월드 기준**이어야 한다(⑦) |
| 리타게팅 결과를 FBX 로 내보냈더니 **다시 T-포즈** | FBX 왕복에서 rest 가 달라진다. **`.blend` 로 넘긴다**(⑦) |
| 액션을 할당했는데 **정적 T-포즈** | Blender 4.4+ 의 slotted action — `animation_data.action_slot` 을 안 잡았다 |
| `id.go_detect.poll() failed` 가 계속 남 | 컨텍스트가 아니라 **active 오브젝트가 숨겨진 것**이다. `body_temp` 를 active 로(④-A 4번) |
| `AI files are missing or not up to date` | `guess_markers`·`guess_fingers` 는 ARP AI 리소스가 필요하다. 마커는 `id.add_marker` 로, 손가락은 `arp_smart_fingers_engine='LEGACY'` 로 우회(④-A 3번) |
| `_append_arp` 가 `space_data … NoneType` 로 죽음 | MCP 에 3D 뷰가 없다. `bpy.app.timers` 안에서 `temp_override` 로 실행(④-A 5번) |
| 캐릭터가 100배 크기로 export 됨 | `arp_units_x100` 이 **기본 ON** 이다(⑤). 아틀라스만 보면 프레이밍이 bbox 기준이라 안 드러난다 |
| **`--scale-attack 0.85` 를 줬는데 그대로다** | `--auto` 와 같이 준 것이다. `--auto` 는 auto-fit 을 켜 scale 을 1.0 으로 고정한다(⑧ 옵션표) |
| 아틀라스 PNG 가 유난히 크다 | 색 압축이 건너뛰어졌다 — 프로젝트 루트에 `scripts/compress_image.py` 가 있는지, 로그에 `⚠️ 압축 실패` 가 없는지 확인 |
| 팔이 뒤틀림 | 생성 시 T-Pose 토글 누락, 또는 Twist 본을 export 했다(`arp_export_twist` 는 **기본 ON**) |
| **걷기·달리기에서 다리를 벌리고 어기적거림** | 모델이 **다리를 벌린 채 생성**돼 그 자세가 rest pose 로 굳은 것이다. 리타게팅은 rest 대비 **회전차**만 옮기므로 벌어짐은 기준값으로 남는다 — ⑥·⑦ 을 다시 돌려도 안 바뀐다. **② 부터 재생성**(크레딧 재소모, 사용자 확인 후) |
| 다리 본이 몸 밖으로 나감 | ④-B 표의 `foot` 좌표(벌린 모델 실측값)를 그대로 베꼈다. **매번 메시에서 다시 잰다** |
| **걷기가 뒤뚱거린다 · 다리가 벌어져 있다** | ⑤-L `close_legs.py` 로 모은다(자동). 재생성은 그것으로도 `[WARN]` 일 때의 **최후 수단**이다 |
| **다리를 모았는데 결과물은 그대로 벌어져 있다** | ⑦ 에 `.fbx` 를 넣었다. ⑤-L 을 돌렸으면 **`.legs.blend`** 를 넘겨야 한다(⑦ 참조) |
| **다리를 모았더니 까치발이 됐다** | 발 방향 복원이 안 먹은 것이다. `Foot`·`ToeBase` 본이 Mixamo 규격인지 확인할 것(⑥ 통과 후 실행) |
| `close_legs.py` 가 `[SKIP] 이미 모여 있다` | 판정상 PASS 다. 그래도 더 모으려면 `--force`, 더 바짝은 `--gap-ratio 0.15` |
| `close_legs.py` 가 `[WARN] 아직 …%` | 다리가 아니라 **골반이 넓거나 발이 바깥으로 퍼진** 모델이다. `--gap-ratio` 를 낮추고, 그래도 안 되면 ② 재생성 |
| **다리가 4개 이상인데 ARP Smart 가 안 먹는다** | 동물형이다 — humanoid 경로(④ Smart)를 쓰지 말고 [references/non-humanoid.md](references/non-humanoid.md) 로 간다 |
| **구운 아틀라스가 게임에 안 보임** | 먼저 ⑤⑥⑦⑨ 게이트를 확인하고, 다 통과했으면 [노출 4층](#게임에-실제로-보이게-하려면--노출은-4층이다) 중 미연결 층을 찾는다 |
| 프레임이 셀 밖으로 잘림 | `verify_cells` 가 제안하는 `--scale-<action>` 을 **`--auto` 없이** 적용해 재굽기 |
| background 에서 `arp_debug_mode` AttributeError | ARP 의 GUI 핸들러. **무해하다** — 그 아래 출력을 본다 |

## 레거시 — GLB 경로 (쓰지 않는다)

**현 파이프라인에서는 쓰지 않는다.** 아래 스크립트는 **Tripo 오토 리깅 리그(41본)** 를
전제하므로 ARP → `mixamorig:*` 흐름에 섞으면 매핑이 어긋난다. 3D 런타임을 쓰는 다른
프로젝트를 위해 남겨 둔 것이다:

| 스크립트 | 용도 |
|---|---|
| `scripts/retarget.py` | Mixamo → **Tripo** 본 리타게팅 → [references/retargeting.md](references/retargeting.md) |
| `scripts/postprocess_glb.py` | Decimate · root motion 제거 · 액션명 정규화 → GLB |
| `scripts/inspect_glb.py` | GLB 10개 항목 검사(Blender 없이 순수 Python) |
| `scripts/verify_render.py` | 동작별 프리뷰 PNG 렌더 |
| `scripts/inspect_rig.py` | 리그 구조 덤프(`--tree`) — **새 흐름에서도 디버깅에 유용하다** |
| `references/flutter-scene-integration.md` | flutter_scene 통합 |

⚠️ **새 흐름에 이것들을 섞지 말 것.** 특히 `postprocess_glb.py` 의 root motion 제거는
sheet.py 가 Hips 를 추적해 스스로 처리하므로 불필요하고, 액션명 정규화는 sheet.py 의
행동 인식과 규칙이 다르다.
</content>
