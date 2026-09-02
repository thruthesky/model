# Godot 경로 — Tripo3D → 정규화 → 리깅 → 애니 → 본 감축 → GLB

**라리엔 3D(Godot)용 3D 캐릭터를 만드는 전 과정.** 2.5D 아틀라스(Phase B)를 굽지 않고
**`.glb` 를 Godot 에 바로 넣는다.**

## 목차

- [명령 사용법](#명령-사용법)
- [🛑 출력 위치 — `./outputs` 가 기본이다](#-출력-위치--outputs-가-기본이다)
- [🛑 정규화 규약 — 이 문서의 핵심](#-정규화-규약--이-문서의-핵심)
- [전체 흐름](#전체-흐름)
- [① Tripo3D 생성 설정](#-tripo3d-생성-설정)
- [② 정규화 — normalize_for_godot.py](#-정규화--normalize_for_godotpy)
- [③ 리깅](#-리깅)
- [④ 애니 적용 + 본 감축 + GLB — export_godot_glb.py](#-애니-적용--본-감축--glb--export_godot_glbpy)
- [⑤ 검증 — verify_godot_glb.py](#-검증--verify_godot_glbpy)
- [⑥ Godot 임포트 설정](#-godot-임포트-설정)
- [본 예산 — 16 과 25](#본-예산--16-과-25)
- [삼각형 예산](#삼각형-예산)
- [🛑 진단 — "Godot 에 안 보인다"](#-진단--godot-에-안-보인다)
- [실측 사례 — male.glb](#실측-사례--maleglb)
- [스크립트의 핵심 로직](#스크립트의-핵심-로직)

---

## 명령 사용법

```
/model --bones 16 --kind human --triangles 4800 --animations <폴더> "<프롬프트>"
```

| 옵션 | 값 | 기본 | 뜻 |
|---|---|---|---|
| `--bones` | **16** · 25 | **16** | 본 예산. 저사양 우선이므로 **최저 16 이 기본** |
| `--kind` | **human** · animal · drone · prop | `human` | 형태. 리깅 경로를 정한다 |
| `--triangles` | 1600 · 3200 · **4800** · 6400 · 7200 | **4800** | 삼각형 예산. 0 이면 줄이지 않는다 |
| `--animations` | 폴더 경로 | **없음** | Mixamo `.fbx` 폴더. **없으면 애니 없이 진행** |
| `--height` | 미터 | 1.8 | 목표 키 |
| `--texture` | 픽셀 | 1024 | 텍스처 최대 변 |
| `--name` | 문자열 | 프롬프트에서 추론 | 자산 이름 = 폴더명 |
| **`--output`** | 폴더 경로 | **`./outputs`** | 🛑 산출물 저장 폴더. **`assets/` 에 쓰지 않는다** |

### 🛑 출력 위치 — `./outputs` 가 기본이다

**모든 산출물은 `./outputs/<NAME>/` 에 저장한다. `assets/` 에 직접 쓰지 않는다.**
근거와 예외는 [SKILL.md](../SKILL.md) 의 「출력 위치」 절 —
요약하면 **`assets/` 는 게임 번들이고 무엇을 넣을지는 사람이 고른다.**

```
outputs/
├── tripo3d.ai/<NAME>_raw.glb      # ① Tripo 다운로드 원본
└── <NAME>/
    ├── <NAME>_norm.blend          # ② 정규화
    ├── <NAME>_rig.blend           # ③ 리깅
    ├── <NAME>.glb                 # ④ 최종 산출물 ← Godot 에 넣는 것
    └── textures/
```

**`--output` 을 명시하면 그 폴더 아래 `<NAME>/` 로 들어간다** — `--output assets/actor/pc`
면 `assets/actor/pc/<NAME>/<NAME>.glb`. 🛑 **사람이 지정했을 때만 그렇게 한다.**

> ⚠️ **`--output` 은 `/model` 명령의 옵션이지 스크립트의 플래그가 아니다.**
> `normalize_for_godot.py` · `export_godot_glb.py` 는 출력 경로를 **두 번째 위치 인자**로
> 받으므로, `--output` 값은 아래 예시들의 그 자리에 그대로 들어간다. 스크립트를
> 고칠 일은 없다.

> ℹ️ 프로젝트 루트가 곧 `res://` 라서 `outputs/<NAME>/<NAME>.glb` 도 Godot 이 그대로
> 임포트한다. **`assets/` 로 옮겨야 쓸 수 있는 것이 아니다.**

### `--animations` 를 생략하면

**작업을 멈추지 않는다.** 정적 모델로 끝까지 진행하되 사용자에게 반드시 알린다:

```
🛑 애니메이션을 적용하지 않습니다.
   --animations 옵션이 없어 정적 모델로 내보냅니다.
   캐릭터는 Godot 에서 움직이지 않습니다(T-포즈로 서 있습니다).

   나중에 애니메이션을 붙이려면 폴더를 지정해 이 단계만 다시 돌립니다:
     blender --background --python export_godot_glb.py -- \
       <입력.blend> <출력.glb> --animations <폴더> --kind human
```

**작업이 끝난 뒤에도 한 번 더 알린다** — "애니메이션은 아직 없습니다. `--animations`
로 폴더를 지정해 주세요." 조용히 넘어가면 나중에 "왜 안 움직이지" 로 되돌아온다.

### `--kind` 는 두 종류가 있다 — 혼동 금지

| | 값 | 무엇을 정하나 |
|---|---|---|
| **이 문서(Godot)** | `human` `animal` `drone` `prop` | **형태** → 리깅 경로·검증 항목 |
| 2.5D 아틀라스([SKILL.md](../SKILL.md) ⑧) | `pc` `mob` `npc` `boss` `minion` | **게임 역할** → 방향 수·셀 크기 |

Godot 경로는 아틀라스를 굽지 않으므로 두 값이 충돌할 일은 없다. 다만 **같은 이름의
옵션이 다른 뜻**이라는 것을 기억한다.

---

## 🛑 정규화 규약 — 이 문서의 핵심

> **Tripo3D 다운로드 직후, 리깅 전에, Blender 에서 키 1.8m · 발바닥 원점 ·
> Z-up · scale 1 · rot 0 으로 정규화한다.**

**이 한 줄이 캐릭터 5종·몬스터 30종에서 같은 사고가 반복되는 것을 막는다.**

### 왜 — 두 좌표계가 섞이기 때문이다

| | 축 | 단위 |
|---|---|---|
| **Tripo3D 메시** | **Y-up** | 1.0 정규화 |
| **Mixamo 리그** | **Z-up** | **cm** (Hips 63.49) |

이 둘을 정규화 없이 붙이면 **같은 회전을 걸어도 하나만 맞는다.** 실측(`male.blend`):

```
human 메시  : 데이터 Y-up + 오브젝트 rot X +90°  → 월드에서 똑바로 섬 ✅
Armature    : 데이터 Z-up + 오브젝트 rot X +90°  → 90° 더 돌아 누움 ❌
              게다가 scale 0.01 이 살아 있어 단위계까지 섞임
```

그 결과가 GLB 에서 **메시가 원점 아래로 매달림**(Y −2.17 ~ 0)이었다.

### 🛑 그리고 그것을 Godot 에서 덮으면 더 크게 터진다

```
GLB 가 1.2cm 로 나옴
   ↓
.import 에 root_scale=150 을 넣어 화면에 맞춤        ← 🛑 땜질
   ↓
GLB 를 고쳐 1.8m 로 만듦 (근본 해결)
   ↓
그런데 root_scale=150 이 남아 있음 → 1.8 × 150 = 270m 거인
   ↓
카메라 직교 size=22.5 기준 화면의 12배 → **또 안 보임**
```

**증상을 덮은 값은 근본을 고친 뒤에 반드시 되돌려야 하고, 되돌리는 것을 잊는다.**
그래서 애초에 덮지 않는다 → CLAUDE.md "근본 원인을 고친다".

### 규약 5줄

| # | 보장 | 검사 |
|---|---|---|
| 1 | Blender 월드 **Z-up · 정면 −Y** | Godot 이 Y-up · 정면 −Z 로 변환 |
| 2 | **키 1.8 m** | bbox 높이 |
| 3 | **발바닥이 원점** (bbox Z_min = 0) | 좌우·앞뒤 중심도 원점 |
| 4 | **loc 0 · rot 0 · scale 1** — 전부 Apply | glTF 루트에 변환이 실리지 않는다 |
| 5 | **메시 1개 · 머티리얼 1개** | 드로우콜 |

---

## 전체 흐름

```
① Tripo3D 생성 (Ultra Mesh OFF · Texture 2K · 최대 100만 tri)
        ↓ 리깅 없이 **GLB** 다운로드 (Godot 옵션은 없다 — GLB 가 곧 Godot 용)
② normalize_for_godot.py     ← 🛑 리깅 **전에**. 규약 5줄 + Decimate
        ↓ <NAME>_norm.blend
③ 리깅 (ARP Smart → Match to Rig → Bind)   ← 유일한 GUI 단계
        ↓ <NAME>_rig.blend
④ export_godot_glb.py --animations --bones
        ↓ 애니 적용 → 본 감축(베이크) → 텍스처 리사이즈 → GLB
        ↓ outputs/<NAME>/<NAME>.glb   ← 🛑 기본 출력. assets/ 에 쓰지 않는다
⑤ verify_godot_glb.py        ← 🛑 완료 게이트. 종료 0 이 아니면 넣지 않는다
        ↓
⑥ Godot 임포트 설정 (root_scale=1.0)
```

### 🛑 순서를 바꾸면 안 되는 두 곳

| 순서 | 바꾸면 |
|---|---|
| **정규화 → 리깅** | 리깅 후 스케일을 바꾸면 본 길이와 액션 위치 키가 어긋난다 |
| **애니 적용 → 본 감축** | 감축을 먼저 하면 Mixamo 의 어깨·목 트랙이 갈 곳을 잃어 **그 회전이 사라진다.** 뒤에 하면 베이크가 팔·머리로 흡수한다 |

---

## ① Tripo3D 생성 설정

[SKILL.md ①②③](../SKILL.md) 의 로그인·프롬프트·다운로드 절차를 그대로 따르되,
**Godot 경로는 아래 설정을 쓴다.**

| 항목 | 값 | 왜 |
|---|---|---|
| **Ultra Mesh Quality** | 🛑 **끈다** | 폴리곤만 늘고 크레딧을 더 쓴다. 어차피 ② 에서 4,800 으로 깎는다 |
| **Texture Quality** | **2K** | 8K 는 ZIP 이 지연되거나 오지 않는다(크레딧만 차감). 로컬에서 1024 로 다시 줄인다 |
| 삼각형 | **최대 100만까지 허용** | 생성 단계에서 줄이려 하지 않는다 — 크레딧이 더 든다. Decimate 가 안전하게 줄인다 |
| T-Pose 토글 | **ON** | ARP 마커 정확도 |
| Export Skeleton | **OFF** | 리깅은 ARP 가 한다 |
| **Format** | 🛑 **`GLB`** | 아래 절 참조 |

### 🛑 Export 포맷은 GLB 가 기본이다 — Godot 옵션은 없다

**Tripo3D 의 Export 목록에 "Godot" 항목은 없다.** 찾지 말 것. 목록은 GLB · FBX · OBJ ·
STL 뿐이고, **Godot 은 glTF(`.glb`)를 네이티브 1급으로 지원**하므로 **GLB 가 곧 Godot 용**이다.

| 우선순위 | 포맷 | 언제 |
|---|---|---|
| **1순위** | **`GLB`** | **기본값. 가능하면 항상** |
| 2순위 | `FBX` + 프리셋 **`Blender`** | GLB 를 못 고르거나 결과가 깨질 때만 |

| | GLB | FBX |
|---|---|---|
| 텍스처 | **파일 안에 임베드** — 경로가 깨질 수 없다 | `.fbm` **별도 폴더**. 어긋나면 **회색 모델** |
| 축 규약 | glTF 표준 **Y-up 고정** | 프리셋마다 다르다 |
| `normalize_for_godot.py` | 그대로 받는다 | 받지만 `.fbm` 을 함께 옮겨야 한다 |

🛑 **실측** — `male` 을 FBX 로 받았을 때 `.fbm` 경로가 어긋나 `embedding file … failed` 가
났고 **텍스처 없는 회색 결과**가 나왔다. GLB 에서는 구조적으로 불가능한 사고다.

⚠️ **GLB 라고 정규화를 건너뛰지 않는다.** Tripo 는 GLB 도 **1.0 단위 정규화 메시**로 주므로
키 1.8m·발바닥 원점은 여전히 ② 에서 맞춘다.

> **폴리곤을 Tripo 에서 줄이지 않는 이유** — `Smart Mesh`·`Retopo` 는 크레딧을 더
> 쓰는데, Decimate(COLLAPSE)가 리깅 전에 무료로 같은 일을 한다.
> 실측: 1,020,514 → 4,798 (0.47%), 형상 손실 없음.

---

## ② 정규화 — `normalize_for_godot.py`

```bash
blender --background --python .claude/skills/model/scripts/normalize_for_godot.py -- \
  outputs/tripo3d.ai/<NAME>_raw.fbx \
  outputs/<NAME>/<NAME>_norm.blend \
  --kind human --height 1.8 --triangles 4800
echo "종료코드=$?"    # 0 = 통과
```

| 옵션 | 기본 | |
|---|---|---|
| `--height` | 1.8 | 목표 키(m) |
| `--triangles` | 4800 | 0 이면 줄이지 않는다 |
| `--kind` | human | `prop` 은 `--height` 를 **명시했을 때만** 크기를 맞춘다 |
| `--rigged` | off | **이미 리깅된 파일을 고칠 때만.** 아래 참조 |
| **`--exclude`** | 없음 | **제외할 메시(쉼표 구분). 🛑 무기는 반드시 제외한다** |
| **`--only`** | 없음 | 이 메시만 남긴다(무기만 따로 뽑을 때) |
| `--no-join` | off | 메시를 합치지 않는다 |
| `--dry-run` | off | 측정만 |

**원본을 건드리지 않는다** — 입력은 읽기만 하고 출력 경로에만 쓴다. `.blend` 를
입력으로 줘도 그 파일에 저장하지 않는다.

### 🛑 이미 리깅된 파일 — `--rigged`

아마추어가 있으면 스크립트가 **거부**한다. 정규화는 리깅 전이 원칙이기 때문이다.
기존 자산을 구제해야 하면 `--rigged` 를 준다 — 리그·메시·액션 location 키를
함께 변환한다. 실측으로 동작하지만 **새로 만드는 캐릭터는 반드시 리깅 전에** 한다.

---

### 🛑 무기·장비는 반드시 분리한다 — `--exclude`

**Tripo 는 "검을 든 캐릭터" 를 요청하면 검을 캐릭터 메시에 붙여서 준다.**
그대로 두면 **두 가지가 동시에 깨진다.**

| | 무슨 일이 | 실측(2026-09-02 `male`) |
|---|---|---|
| **① 삼각형 예산 독식** | 원본에서 폴리곤이 많은 쪽이 예산을 가져간다 | 검이 원본 970,514(95%) → 예산 4,800 중 **4,564 를 검이 먹고 캐릭터가 234 삼각형**으로 뭉개짐 |
| **② 무기 교체 불가** | 캐릭터 메시에 구워져 분리할 수 없다 | MMORPG 인데 무기를 못 바꾼다. 무기 없는 상태도 표현 못 한다 |

②가 더 근본적이다. 라리엔은 장비를 교체하는 게임이고,
**무기는 `BoneAttachment3D` 로 손 본에 붙이는 별도 에셋**이다(assets-3d.md §4
"BoneAttachment3D 파츠 부착 — 무기·이펙트 등 소수만").

```bash
# 캐릭터 — 무기를 빼고 예산 전부를 몸에 쓴다
blender --background --python .../normalize_for_godot.py -- \
  <입력> outputs/<NAME>/<NAME>_norm.blend --kind human --triangles 4800 --exclude weapon

# 무기 — 따로 뽑는다. prop 은 --height 를 줘야 크기가 맞는다
blender --background --python .../normalize_for_godot.py -- \
  <입력> outputs/sword/sword_norm.blend --kind prop --triangles 1600 \
  --only weapon --height 1.0 --no-center
```

⚠️ **`prop` 에 `--height` 를 빼먹으면 4cm 짜리 검이 나온다.** 캐릭터에서 분리하는
순간 크기 기준을 잃기 때문이다. 한손검은 1.0m, 양손검·창은 1.6~2.0m 를 준다.

⚠️ **`--no-center` 를 준다.** 무기는 좌우 중심을 원점에 맞추면 손잡이가 아니라
날 한가운데가 기준이 된다. 부착점은 Godot 에서 `BoneAttachment3D` 의 오프셋으로 잡는다.

> **더 나은 방법은 애초에 따로 만드는 것이다.** Tripo 프롬프트에서 무기를 빼고
> 캐릭터만 생성한 뒤, 무기는 **별도 프롬프트로 생성**한다. 무기 종류가 여러 개인
> 게임에서는 어차피 그래야 한다.

## ③ 리깅

[SKILL.md ④](../SKILL.md) 의 ARP 절차와 **완전히 같다.** Godot 경로라고 달라지는 것이 없다.

- `Auto-Rig Pro: Smart` → `Get Selected Objects` → 마커 → `Go!`
- 🛑 **`Match to Rig`** 를 반드시 누른다 (안 누르면 Bind·Export 가 거부)
- `Bind to Rig`
- `<NAME>_rig.blend` 로 저장

**손가락은 리깅해도 된다.** ④ 의 본 감축이 어차피 제거하고, ARP 의 `LEGACY` 손가락
엔진을 끄는 것보다 켜 두는 편이 마커 감지가 안정적이다.

### 🛑 ARP 는 `--background` 에서 **구조적으로 불가능**하다 (2026-09-02 실측)

시도하지 말 것. 첫 연산자에서 바로 죽는다:

```
bpy.ops.id.get_selected_objects()
  → _get_selected_objects() → set_selection_filters()
  → space_view3d = [i for i in current_area.spaces if i.type == "VIEW_3D"]
AttributeError: 'NoneType' object has no attribute 'spaces'
```

**ARP 가 3D 뷰 `area` 를 직접 참조**하는데 `--background` 에는 area 자체가 없다.
`temp_override` 로도 만들어 줄 수 없다(window·screen이 없으므로). 즉 **리깅에는
GUI Blender 가 반드시 필요하다** — 이것이 ④ 가 "유일한 GUI 단계" 인 진짜 이유다.

**두 경로 중 하나를 쓴다:**

| 경로 | 방법 |
|---|---|
| **Blender MCP** | GUI Blender 실행 + MCP 애드온 → `bpy.app.timers` 안에서 `temp_override(window, area, region)` ([SKILL.md](../SKILL.md) ④-A 5번) |
| **사람이 직접** | ARP 패널에서 Smart → Match to Rig → Bind → `<NAME>_rig.blend` 저장 |

⚠️ **리깅 전까지의 단계(② 정규화)와 이후 단계(④ 애니·본 감축·GLB·검증)는 전부
`--background` 로 자동화된다.** 사람이 개입하는 것은 리깅 하나뿐이다.

**입력은 ② 가 만든 `<NAME>_norm.blend`** 다. Tripo 원본을 바로 리깅하지 않는다.

---

## ④ 애니 적용 + 본 감축 + GLB — `export_godot_glb.py`

```bash
blender --background --python .claude/skills/model/scripts/export_godot_glb.py -- \
  outputs/<NAME>/<NAME>_rig.blend \
  outputs/<NAME>/<NAME>.glb \
  --animations game-assets/animations/default \
  --kind human --bones 16 --texture 1024
echo "종료코드=$?"
```

**한 스크립트가 네 가지를 순서대로 한다** — 순서 자체가 규범이라 분리하지 않았다:

| 순서 | 하는 일 | 순서를 지키는 이유 |
|---|---|---|
| 1 | 정규화 확인 | scale·rot 이 남아 있으면 **여기서 멈춘다**. GLB 에 실리기 전에 잡는다 |
| 2 | 애니메이션 임포트 | 파일 이름이 액션 이름이 된다 (`idle.fbx` → `idle`) |
| 3 | **본 감축** | 🛑 애니 **뒤**여야 어깨 회전이 팔에 흡수된다 |
| 4 | RESET 생성 · NLA 분리 · 텍스처 리사이즈 · GLB | |

### NLA 트랙으로 분리하는 이유

glTF exporter 는 **NLA 트랙 하나당 애니메이션 하나**를 만든다. 액션을 그냥 데이터에
두면 현재 할당된 하나만 나간다(assets-3d.md §5 "한 타임라인에 붙여 두면 하나로 합쳐진다").
스크립트가 `export_animation_mode="NLA_TRACKS"` 로 내보낸다.

### RESET 을 반드시 만든다

Godot 의 애니메이션 블렌딩은 **RESET 을 기준 포즈로 전제**한다. 없으면 블렌드가
이상하게 섞인다. 스크립트가 rest pose 한 프레임짜리로 만든다(`--no-reset` 로 끌 수 있다).

---

## ⑤ 검증 — `verify_godot_glb.py`

```bash
python3 .claude/skills/model/scripts/verify_godot_glb.py \
  outputs/<NAME>/<NAME>.glb --bones 16 --kind human
echo "종료코드=$?"    # 🛑 0 이 아니면 Godot 에 넣지 않는다
```

**Blender 없이 돈다**(순수 Python). GLB 앞부분이 JSON 청크라 표준 라이브러리로 읽힌다.
Blender 를 띄우면 20~40초가 드는데 이 검사는 즉시 끝난다.

검사 9항목 — **전부 실패 이력이 있다**:

| # | 검사 | 실패하면 |
|---|---|---|
| 1 | 루트 노드에 scale·translation 이 없는가 | Godot 이 한 번 더 곱한다 |
| 2 | 발바닥이 원점인가 (bbox Y_min ≈ 0) | 지면 아래로 매달린다 |
| 3 | 키 1.6~2.0 m | |
| 4 | 본 ≤ 예산 · **손가락 본 0개** | GPU 대역폭 |
| 5 | 삼각형 ≤ 예산 **+ 프리미티브 분포** | 한 부속이 70% 를 넘으면 나머지가 뭉개진 것이다 |
| 6 | 텍스처 ≤ 1024 | VRAM |
| 7 | 머티리얼 1개 | 드로우콜 |
| 8 | 애니 이름이 `idle/walk/run/attack/death` | AnimationTree 가 이름으로 찾는다 |
| 9 | 애니가 0.2초 이상 | `mixamo.com` 2프레임짜리 빈 껍데기가 실제로 있었다 |

> `RESET` 은 1프레임이 정상이므로 9번에서 제외된다.

---

## ⑥ Godot 임포트 설정

`.import` 파일은 **사람이 Godot 에디터에서** 설정한다(CLAUDE.md — Claude 는 문서만 쓴다).

**Godot 에디터 경로**: FileSystem 에서 `.glb` 선택 → **Import** 탭 → 값 변경 → **Reimport**

| 항목 | 값 | 🛑 왜 |
|---|---|---|
| **`nodes/root_scale`** | **`1.0`** | 🛑 **가장 중요하다.** 1.0 이 아니면 모델이 이미 맞는데 또 곱한다. `150` 같은 값은 과거 땜질의 잔재이며 **반드시 되돌린다** |
| `nodes/apply_root_scale` | `true` | |
| `meshes/generate_lods` | `true` | 카메라 거리가 고정이라 LOD 가 안전하다 |
| `meshes/create_shadow_meshes` | **`false`** | SSOT §2 — 동적 그림자를 쓰지 않는다 |
| `meshes/light_baking` | **`0`**(Disabled) | SSOT §2 — 캐릭터는 라이트맵에 굽지 않는다 |
| `animation/import_rest_as_RESET` | `true` | RESET 이 없을 때의 보험 |
| `animation/fps` | `30` | |

---

## 본 예산 — 16 과 25

Mixamo 는 **65본**이고 그중 **40본이 손가락**이다. 고정 −45° 피치·직교 투영인
라리엔 카메라에서 손가락은 **한 픽셀도 구분되지 않는다**.

본 행렬은 매 프레임 GPU 로 업로드된다. 캐릭터 90개가 보이는 AOI 예산에서
65본과 16본은 대역폭이 **4배** 차이 난다.

### 16본 (최저 · 기본)

```
Hips, Spine, Spine1, Head,
LeftArm, LeftForeArm, LeftHand,
RightArm, RightForeArm, RightHand,
LeftUpLeg, LeftLeg, LeftFoot,
RightUpLeg, RightLeg, RightFoot
```

**없는 것** — 어깨(Shoulder) · 목(Neck) · 발가락(ToeBase) · 손가락 · Spine2

### 25본

```
Hips, Spine, Spine1, Spine2, Neck, Head,          (6)
L/R Shoulder, Arm, ForeArm, Hand,                 (8) → 14
L/R UpLeg, Leg, Foot, ToeBase,                    (8) → 22
```

**22본이 표준 구성**이고 나머지 **3본은 모델 고유 요소**(무기 그립·망토·꼬리)에 쓴다.
`--keep-bones` 로 지정한다.

### 무엇을 잃는가 — 판단 기준

| | 16본 | 25본 |
|---|---|---|
| 어깨 흔들림 | ❌ 없음 | ✅ |
| 발가락 굴림 | ❌ 없음 | ✅ |
| 목 독립 회전 | ❌ 머리에 흡수 | ✅ |
| 걷기 자연스러움 | 보통 | 좋음 |
| **권장 대상** | **멀리서 다수가 보이는 몹** | **근거리에 오래 보이는 PC** |

> 🛑 **본을 지우면 그 회전이 사라진다** — 그래서 감축은 **애니메이션을 붙인 뒤**
> 아마추어 공간으로 **베이크**하며 한다. 순서를 뒤집으면 어깨 회전이 통째로 없어진다.

### 🛑 기존 규범과의 차이 — 사람 결정으로 확정

`game` 스킬 [assets-3d.md §4](../../game/references/assets-3d.md) 는 본 수를
**30~40** 으로 적고 있다. 이 문서의 **16/25 는 그보다 엄격하며, 원저자 지시(2026-09-02)로
확정**됐다. 예산을 넘기는 방향이 아니라 더 아끼는 방향이라 충돌이 아니다.
**두 문서가 어긋나 보이면 16/25 가 최신이다.**

---

## 삼각형 예산

| 값 | 쓰는 곳 |
|---|---|
| 1600 | 원거리 전용 · 군중 몹 |
| 3200 | 일반 몹 |
| **4800** | **기본 — PC·주요 몹** (assets-3d.md LOD0 3,000~6,000 의 중앙) |
| 6400 | 보스 |
| 7200 | 근접 컷신용 |

**Decimate 는 리깅 전에 한다.** 리깅 후에 줄이면 정점 그룹 웨이트가 재분배되며
관절이 뭉개진다.

---

## 🛑 진단 — "Godot 에 안 보인다"

**순서대로 본다. 위에서 걸리면 아래는 볼 필요가 없다.**

| # | 확인 | 명령·위치 | 증상 |
|---|---|---|---|
| 1 | **`.import` 의 `root_scale`** | `grep root_scale <파일>.glb.import` | **1.0 이 아니면 여기가 원인이다.** 150 이면 1.8m × 150 = 270m 거인 |
| 2 | GLB 자체 검증 | `verify_godot_glb.py` | 원점·키·본·삼각형을 한 번에 판정 |
| 3 | 원점 | 검증의 `bbox Y_min` | 음수면 지면 **아래로** 매달림 |
| 4 | 씬 배치 | `.tscn` 의 노드 `transform` | 씬에서 또 스케일을 걸지 않았는가 |
| 5 | 카메라 | 직교 `size` 와 캐릭터 크기 비 | `size=22.5` 면 화면 세로 22.5m |

### 실제로 겪은 것들

| 증상 | 원인 | 고치는 곳 |
|---|---|---|
| **화면이 텍스처 한 조각으로 가득 참** | `root_scale=150` 잔재 → 270m | `.import` 를 `1.0` 로 |
| **아무것도 안 보이는데 로그는 정상** | 원점이 정수리 → 캐릭터가 지면 아래 | ② 정규화 |
| **깨알같이 작음** | GLB 가 1.0 단위(1m 아님) 또는 cm | ② 정규화 |
| **T-포즈로 서서 안 움직임** | 애니 이름이 `mixamo.com` | ④ `--animations` |
| **애니가 하나만 나감** | NLA 로 분리하지 않았다 | ④ (스크립트가 처리) |
| **블렌딩이 이상하게 섞임** | RESET 없음 | ④ 또는 `.import` |
| **손가락 끝 정점만 공중에 뜸** | 본을 지우며 웨이트를 병합하지 않았다 | ④ (스크립트가 처리) |
| **어깨가 안 움직이고 팔이 몸통에 붙어 돎** | 본 감축을 애니 **전에** 했다 | 순서를 되돌린다 |
| **삼각형 예산은 통과했는데 캐릭터가 뭉개져 보임** | 무기·부속이 예산을 독식했다 | ② `--exclude` 로 분리 |
| **분리한 무기가 4cm 로 나옴** | `prop` 에 `--height` 를 안 줬다 | `--height 1.0` |

---

## 실측 사례 — `male.glb`

**2026-09-02, laryen3d.** 이 파이프라인이 만들어진 계기다.

### 문제 상태

| 항목 | 규격 | 실측 | 배율 |
|---|---|---|---|
| 삼각형 | 3,000~6,000 | **1,020,514** | **170배** |
| 본 | 30~40 | **65**(손가락 40) | 1.6배 |
| 텍스처 | 1024 | **4096** (17.7MB) | 16배 픽셀 |
| 머티리얼 | 1 | 2 | 2배 |
| 키 | 1.8 m | **2.171 m** | |
| 원점 | 발바닥 | **정수리**(bbox Y −2.171 ~ 0) | |
| 애니 | idle/walk/run/attack/death | `mixamo.com`×3, **각 0.083초** | 빈 껍데기 |
| 파일 | — | **59.6 MB** | |
| `.import` | `root_scale=1.0` | **`150.0`** | → 270m |

`weapon` 메시 하나가 **970,514 폴리곤**으로 전체의 95% 였다(검 한 자루).

### 파이프라인 통과 후

```
[OK  ] 루트 노드 1개에 스케일 이중 적용 없음
[OK  ] 발바닥이 원점에 있다 (bbox Y_min = +0.0000 m)
[OK  ] 키 1.800 m (예산 1.6~2.0)
[OK  ] 본 16개 ≤ 예산 16
[OK  ] 삼각형 4,798 ≤ 예산 6,000
[OK  ] image[0] 1024x1024 ≤ 1024
[OK  ] 규격 애니 5종 전부 있다

파일 3.7 MB · 정점 3,711 · 삼각형 4,798 · 본 16 · 애니 6
```

| | 전 | 후 |
|---|---|---|
| 파일 | 59.6 MB | **3.7 MB** (−94%) |
| 삼각형 | 1,020,514 | **4,798** |
| 본 | 65 | **16** |
| 애니 | 0.083초 × 3 | idle 2.00 · walk 1.07 · run 0.90 · attack 2.30 · death 2.43 초 |

### 🛑 그리고 총합만 보면 놓치는 것 — 이번에 실제로 놓쳤다

위 결과는 **삼각형 4,798 로 예산을 통과했지만** 그 안의 분포가 이랬다:

| 프리미티브 | 대상 | 삼각형 | 비중 |
|---|---|---|---|
| prim0 | **캐릭터 본체** | **234** | 4.9% |
| prim1 | **검** | **4,564** | **95.1%** |

**검 한 자루가 예산의 95% 를 먹고 캐릭터가 234 삼각형으로 뭉개졌다** — 규격
LOD0 3,000~6,000 의 **1/20** 이라 사람 형체가 나오지 않는다. 원인은 Decimate 의
**비례 배분**이었다. 원본에서 검이 970,514 폴리곤(95%)이라 비례 배분이 예산의
95% 를 검에 준 것이다 — **가장 조잡한 메시가 예산을 독식**하는 구조였다.

두 가지를 고쳤다:

1. **배분을 균등 상한으로 바꿨다** — 예산을 메시 수로 나눈 몫을 상한으로 두고,
   그보다 작은 메시는 건드리지 않은 뒤 남는 예산을 큰 메시에 되돌린다.
2. **검증에 프리미티브 분포 검사를 넣었다** — 하나가 70% 를 넘으면 실패시킨다.
3. **정규화 로그가 메시별 삼각형을 찍는다** — 눈으로 즉시 잡힌다.

### 무기를 분리한 최종 결과

```
[OK  ] 루트 노드 1개에 스케일 이중 적용 없음
[OK  ] 발바닥이 원점에 있다 (bbox Y_min = +0.0000 m)
[OK  ] 키 1.800 m · 본 16개 · 삼각형 4,800 · 머티리얼 1개
[OK  ] 규격 애니 5종 전부 있다
✅ 전부 통과
```

| | 검 포함 | **검 분리 후** |
|---|---|---|
| 캐릭터 삼각형 | **234** 🛑 | **4,800** ✅ |
| 머티리얼 | 2 | **1** |
| 파일 | 3.7 MB | **2.0 MB** |

검은 따로 뽑는다 — `--only weapon --kind prop --triangles 1600 --height 1.0`.

---

## 스크립트의 핵심 로직

**SSOT 는 `scripts/` 의 실제 파일이다.** 아래는 왜 그렇게 짜였는지의 요약이다.

| 스크립트 | 역할 | Blender |
|---|---|---|
| [`normalize_for_godot.py`](../scripts/normalize_for_godot.py) | 규약 5줄 + Decimate | 필요 |
| [`export_godot_glb.py`](../scripts/export_godot_glb.py) | 애니 → 본 감축 → 텍스처 → GLB | 필요 |
| [`reduce_bones.py`](../scripts/reduce_bones.py) | 본 감축(단독 실행도 가능) | 필요 |
| [`verify_godot_glb.py`](../scripts/verify_godot_glb.py) | 완료 게이트 | **불필요** |

### 🛑 정규화가 조용히 실패하는 다섯 가지 — 전부 2026-09-02 실측

**다섯 다 오류를 내지 않고 잘못된 결과만 남긴다.** 직접 구현할 때 반드시 알아야 한다.

| # | 함정 | 증상 | 대응 |
|---|---|---|---|
| 1 | **숨겨진 오브젝트는 `select_set(True)` 가 무시된다** | `transform_apply` 가 `{'FINISHED'}` 를 반환하고도 아마추어에 적용 안 됨 → scale 0.01 · rot 90° 잔존 | `select_only()` 가 `hide_set(False)` 를 먼저 부른다 |
| 2 | **애니메이션이 붙으면 `transform_apply` 가 거부**한다 | 위와 같은 잔존 | 액션을 떼고 굽고 되돌린다 |
| 3 | **`data.transform()` 은 rest 만 바꾸고 pose 는 안 바꾼다** | armature modifier 가 그 차이만큼 폭발 — 키 1.0 → **89.3** | 데이터 직접 변환 대신 연산자에 맡긴다 |
| 4 | **부모·자식을 함께 변환하면 이중 적용된다** | 키 1.8 을 노렸는데 **10.03** | 부모를 끊고 작업 후 복원 |
| 5 | **`evaluated_get()` 으로 bbox 를 재면 흔들린다** | 스케일을 맞춘 직후에 재도 다른 값 | 원본 메시(`o.bound_box`)로 잰다 |

같은 부류의 함정이 ARP `go_detect` 의 `poll() failed` 에도 있다([SKILL.md](../SKILL.md) ④-A 4번).

```python
# scripts/normalize_for_godot.py — 함정 1 의 대응
def select_only(objs: list) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        if o.hide_get():
            o.hide_set(False)      # 🛑 이 줄이 없으면 select_set 이 무시된다
        o.hide_viewport = False
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]
```

### 텍스처 리사이즈가 GLB 에 반영되지 않는 함정

`img.scale()` 만으로는 안 된다. packed 이미지는 **원본 PNG 바이트를 `packed_file` 에
그대로 들고 있고**, glTF exporter 가 픽셀 버퍼가 아니라 그 바이트를 복사한다.
실측: 4096→1024 로 줄였는데 GLB 안에는 4096 이 그대로 들어가 파일이 20MB 였다.

또 하나 — **`has_data` 로 거르면 안 된다.** `open_mainfile()` 직후에는 픽셀이 아직
메모리에 없어 packed 이미지도 `False` 다. 그 조건 때문에 리사이즈가 통째로
건너뛰어졌다(커맨드라인으로 연 씬에서는 `True` 라 재현이 안 됐다).

```python
# scripts/export_godot_glb.py
for img in bpy.data.images:
    if img.type != "IMAGE":      # 🛑 has_data 로 거르지 않는다
        continue
    w, h = img.size              # size 는 지연 로드 상태에서도 유효하다
    if w <= 0 or h <= 0 or max(w, h) <= limit:
        continue
    ratio = limit / max(w, h)
    img.scale(max(int(w * ratio), 1), max(int(h * ratio), 1))
    img.pack()                   # 🛑 이 줄이 없으면 GLB 에 원본 4096 이 들어간다
```

### 본 감축이 궤적을 보존하는 원리

`pose_bone.matrix` 는 **아마추어 오브젝트 공간**의 행렬이라 **계층이 바뀌어도 화면상
위치가 같다.** 이것이 본을 지워도 궤적이 보존되는 근거다.

```python
# scripts/reduce_bones.py — 4단계
# 1. 지우기 전에 각 액션 × 각 프레임에서 남길 본의 pose matrix 를 기록
frames[f] = {n: arm.pose.bones[n].matrix.copy() for n in keep}

# 2. 지울 본의 정점 그룹 웨이트를 가장 가까운 남은 조상으로 합산
#    (안 하면 그 정점들이 아무 본에도 묶이지 않아 공중에 남는다)

# 3. 본 제거 — 자식은 자동으로 남은 조상에 연결된다

# 4. 기록한 matrix 를 **부모 → 자식 순서로** 되적용하며 키 삽입
#    🛑 순서가 중요하다. pose_bone.matrix 설정은 부모의 현재 상태를 기준으로
#       로컬 변환을 역산하므로, 자식을 먼저 넣으면 부모가 나중에 움직이며 어긋난다
order = sorted(keep, key=depth)
for name in order:
    arm.pose.bones[name].matrix = mats[name]
    bpy.context.view_layer.update()
```

### slotted action (Blender 4.4+)

액션 구조가 `layers → strips → channelbags → fcurves` 로 바뀌었다. `action.fcurves`
는 **없다**(`AttributeError`). 그리고 **`action_slot` 을 잡지 않으면 액션이 조용히
평가되지 않는다** — 정적 T-포즈가 나온다.

```python
def action_fcurves(act):
    try:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        if out:
            return out
    except AttributeError:
        pass
    return list(getattr(act, "fcurves", []))   # 옛 구조 폴백
```
