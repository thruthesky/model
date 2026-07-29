---
name: model
description: Tripo3D(tripo3d.ai)로 3D 캐릭터를 생성·리깅하고 Mixamo 애니메이션(FBX)을 리타게팅해 게임 엔진에 넣을 수 있는 GLB 로 만든다. Flutter(flutter_scene) 게임 화면에 움직이는 캐릭터로 표시하는 통합까지 다룬다. 다음 요청에 사용할 것 - "3d 모델 만들어줘", "캐릭터 생성", "tripo 로 모델 뽑아줘", "몬스터/사람/로봇 3D 모델 만들어줘", "우주복/병사/NPC 모델", 생성한 모델에 "애니메이션 붙여줘", "리깅해줘", "auto rig", "mixamo 애니메이션 적용", "걷기/공격 모션 넣어줘", "게임에 캐릭터로 표시해줘", "PC 를 3D 모델로 바꿔줘", "glb 를 flutter 에 띄워줘", "flutter_scene 에 스킨드 메시 붙여줘", 또는 애니메이션 결과를 "Blender 로 보여줘". 텍스트→3D 생성, 오토 리깅, Mixamo→Tripo 본 리타게팅, 폴리곤 감축, GLB 검증, flutter_scene 통합, Blender 자동 재생 미리보기까지 전 과정을 다룬다.
---

# Tripo3D 캐릭터 → Mixamo 애니메이션 → 게임 엔진

텍스트 프롬프트로 3D 캐릭터를 만들고, 리깅하고, 애니메이션을 입혀, **게임 화면에서
실제로 움직이게** 하는 전 과정.

## 준비 확인

```bash
which blender                    # 없으면 사용자에게 설치 요청
ls <애니메이션폴더>/*.fbx          # 예: game-assets/animations/default/
```

Chrome DevTools MCP 가 필요하다. 없으면 브라우저 자동화가 불가능하므로 사용자에게 알릴 것.

애니메이션 폴더에 실제로 무엇이 있는지 **먼저 확인하고 사용자에게 알린다.** `idle walk
run attack hit death` 를 가정하지 말 것 — 3개만 있는 경우가 흔하다.

## 전체 흐름

```
① 로그인 → ② 생성 → ③ 리깅 → ④ FBX 다운로드 → ⑤ 리그 확인
  → ⑥ 리타게팅 → ⑦ 후처리(감축·root motion 제거·이름 정규화) → ⑧ GLB 검증
  → ⑨ 렌더 검증 → ⑩ 게임 엔진 통합
```

각 단계는 앞 단계 산출물에 의존한다. **⑤·⑧·⑨ 를 건너뛰면 실패를 놓친다** — 이
파이프라인의 실패는 대부분 예외가 아니라 "로드는 됐는데 이상하다" 로 나타난다.

⑩ 은 사용자가 "게임에 표시해줘" 라고 했을 때만. 에셋만 원하면 ⑨ 에서 끝낸다.

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
3. **`T-Pose` 토글 ON** — 리깅 품질이 크게 달라진다
4. `Generate Model` 클릭

**생성에 3~5분 걸린다.** 백그라운드 대기 후 스크린샷으로 확인할 것. 55~65 크레딧.

### 프롬프트 규칙

Mixamo 애니메이션은 인간형 리그 전용이다. **인간형 T-포즈를 반드시 강제한다.**
사족보행·다관절·촉수형으로 생성되면 이후 단계가 전부 불가능하다.

```
A male astronaut colonist in a white and orange sci-fi spacesuit, full body,
standing in T-pose with both arms straight out horizontally, humanoid proportions
with two arms and two legs, sealed helmet with dark reflective visor, life support
backpack, armored chest plate, gloves and boots, symmetrical, clean topology, game-ready
```

필수 요소: `humanoid proportions`, `two arms and two legs`,
`standing in T-pose with arms straight out horizontally`, `symmetrical`, `game-ready`

사용자가 "거미 몬스터", "용" 처럼 비인간형을 요청하면 애니메이션 적용이 불가능함을
알리고 인간형으로 조정할지 확인할 것.

### 폴리곤은 나중에 줄인다

`HD Model` 은 약 200만 페이스를 만든다. **여기서 `Smart Mesh`·`Retopo` 로 줄이려 하지
말 것** — 리깅 품질이 달라지고 크레딧이 더 든다. ⑦ 단계의 Decimate 가 스킨 웨이트를
보존하면서 안전하게 줄인다(실측: 191만 → 3만, 리깅 유지됨).

## ③ 오토 리깅

좌측 `Animate` 탭 → `/workspace/rigging/<task-id>`

1. **AI Model 을 `v1.0 - Good for Humanoid` 로 변경** — 기본값이
   `v2.5 - Good for Animals` 다. 놓치면 본 이름이 달라져 리타게팅이 전부 실패한다
2. `Auto Rig` (20 크레딧, 1~2분)
3. 완료 확인

⚠️ **드롭다운과 `Auto Rig` 버튼은 `click` 도구로 눌러야 한다.** `evaluate_script` 로는
**아무 일도 일어나지 않는다**(오류도 없다). 눌린 것은 **크레딧 차감**으로 확인한다.

⚠️ **완료 판정에 `/Retry/` 정규식을 쓰지 말 것.** 화면에 `Free Retry` 버튼이 처음부터
있어 항상 참이 된다(실측 오판 사례). `Model Type: Humanoid` + `Skeleton` 표시 +
버튼이 `Retry 20` 인지를 함께 본다 → [references/tripo-studio.md](references/tripo-studio.md)

## ④ 다운로드

하단 `Export` 를 **`click` 도구로** 눌러 다이얼로그를 연 뒤:

| 항목 | 값 |
|---|---|
| File Name | **단계마다 다르게** (아래 주의) |
| Format | `FBX` |
| FBX 프리셋 | `Blender` (`Mixamo`/`3dsmax` 는 본 방향이 바뀌어 매핑이 깨진다) |
| Texture Resolution | **`2k`** |
| Export Skeleton | **ON** |

**텍스처는 2k 를 쓴다.** 8k 는 ZIP 생성이 지연되거나 아예 오지 않는다(크레딧만 차감).

**File Name 을 단계마다 다르게 지정할 것.** Export 는 비동기라 이전 요청의 ZIP 이
뒤늦게 도착해 리깅 전 파일과 헷갈린다.

다이얼로그 **안**의 `Export` 는 `evaluate_script` 로 눌러도 된다(마지막 버튼 패턴).

받은 뒤 정리:

```bash
unzip -o ~/Downloads/"<이름>_rigged.zip" -d <출력>/<이름>_rigged/
cd <출력>/<이름>_rigged
mv tripo_convert_*.fbx <이름>_rigged.fbx
mv tripo_convert_*.fbm <이름>_rigged.fbm    # 텍스처 폴더. FBX 와 같은 이름이어야 로드된다
```

## ⑤ 리그 확인 (생략 금지)

```bash
blender --background --python .claude/skills/model/scripts/inspect_rig.py -- \
  <출력>/<이름>_rigged/<이름>_rigged.fbx
```

**`본 41개` / `루트 본: ['Root']`** 가 나와야 정상이다. `아마추어 없음` 이면 리깅 전
파일이므로 다시 받는다.

## ⑥ 애니메이션 리타게팅

```bash
blender --background --python .claude/skills/model/scripts/retarget.py -- \
  <출력>/<이름>_rigged/<이름>_rigged.fbx \
  <애니메이션폴더> \
  <출력> \
  <이름>_animated
```

**성공 판정:** 각 동작마다 **`F-커브 91개`** (22본 × 쿼터니언 4 + Hip 위치 3). `0개` 면 실패다.

⚠️ **이 단계의 `.glb` 출력을 쓰지 말 것.** Mixamo 소스 아마추어의 액션까지 섞여 들어간다
(실측: `Armature.001|mixamo.com|Layer0` 3개가 추가로 포함됨). **`.fbx` 를 ⑦ 의 입력으로
쓴다** — FBX 는 깨끗하다.

원리·본 매핑표·문제 해결은 [references/retargeting.md](references/retargeting.md).
Tripo 가 아닌 리그를 쓸 때는 `inspect_rig.py --tree` 로 본 이름을 확인하고
`scripts/retarget.py` 의 `BONE_MAP` 만 고치면 된다.

## ⑦ 후처리 — 게임에 넣을 수 있게 다듬는다

```bash
blender --background --python .claude/skills/model/scripts/postprocess_glb.py -- \
  <출력>/<이름>_animated.fbx \
  assets/models/<이름>.glb \
  30000 1.7
```

인자: `<입력FBX> <출력GLB> [목표페이스수] [목표키]`

이 스크립트가 하는 네 가지는 **전부 없으면 조용히 실패하는 것들**이다:

| 하는 일 | 없으면 |
|---|---|
| **Decimate**(COLLAPSE, 웨이트 보존) | 200만 페이스가 모바일에서 무너진다 |
| **root motion 제거**(루트 본 location 키 삭제) | 클립의 이동 + 게임의 이동 = **두 배로 걷는다** |
| **액션명 정규화**(`Armature\|Armature\|idle` → `idle`) | 엔진의 이름 조회가 실패해 **클립이 0개**가 된다 |
| **명시적 export 옵션**(`export_skins`·`export_yup`) | Blender 기본값에 의존 → 스킨 누락 가능 |

⚠️ **root motion 은 `walk` 에 특히 흔하다**(실측: Hip 이 1.4초에 0.712 단조 이동 =
초당 0.51m). Mixamo 의 "in place" 가 아닌 버전을 받으면 이렇게 된다.

⚠️ **높이 정규화는 GLB 에 반영되지 않을 수 있다**(아마추어 스케일이 exporter 를 통과하지
못함 — 실측). 문제가 아니다. **최종 배율은 게임 코드의 보정 노드에서 주는 편이 유연하다.**

## ⑧ GLB 검증 (생략 금지)

```bash
python3 .claude/skills/model/scripts/inspect_glb.py assets/models/<이름>.glb
```

Blender 없이 순수 Python 으로 돈다. **전부 `OK` 여야 한다:**

```
[OK  ] 애니메이션 이름에 접두사 없음
[OK  ] 스킨 존재 (1개)
[OK  ] 단일 buffer
[OK  ] 필수 확장 없음               ← Draco 압축이면 로드 실패
[OK  ] JOINTS_1 없음(정점당 영향 ≤4)  ← 넘으면 메시가 찌그러진다
[OK  ] 전부 삼각형                   ← 아니면 프리미티브째 스킵된다
[OK  ] NORMAL 포함
[OK  ] 텍스처 임베드
[OK  ] 발이 원점 근처                ← 아니면 캐릭터가 공중에 뜨거나 파묻힌다
[OK  ] root motion 없음
```

`FAIL` 이 있으면 **⑦ 로 돌아간다.** 이 검사를 통과하지 못한 GLB 를 게임에 넣으면
원인 파악에 몇 배의 시간이 든다.

## ⑨ 렌더 검증 (생략 금지)

리타게팅은 조용히 실패한다. 키프레임은 들어갔는데 포즈만 뒤틀리는 경우가 있으므로
**눈으로 확인해야 한다.**

```bash
blender --background --python .claude/skills/model/scripts/verify_render.py -- \
  <출력>/<이름>_animated.fbx .preview

cd .preview && python3 -c "
from PIL import Image
import glob, sys
order = ['idle','walk','run','attack','hit','death']
files = []
for n in order:
    m = sorted(glob.glob(f'{n}_1_*.png')) or sorted(glob.glob(f'{n}_0_*.png'))
    if m: files.append(m[0])
ims = [Image.open(f) for f in files]
w,h = ims[0].size
g = Image.new('RGB',(w*len(ims),h),'white')
[g.paste(im,(i*w,0)) for i,im in enumerate(ims)]
g.save('grid.png'); print('OK', files)"
```

`grid.png` 를 **Read 로 열어** 각 동작이 제대로 나오는지 확인한다.

## ⑩ 게임 엔진 통합 (Flutter / flutter_scene)

사용자가 "게임에 표시해줘", "PC 를 3D 모델로 바꿔줘" 라고 하면 진행한다.

**작업 전에 [references/flutter-scene-integration.md](references/flutter-scene-integration.md)
를 읽을 것.** 검증된 API 사실·조용한 실패 5가지·재사용 소스코드 전문이 거기 있다.

요약하면:

1. **`pubspec.yaml` 에 `assets:` 등록** — 최종 GLB 만. 원본·중간 산출물은 넣지 않는다
2. **`Node.fromGlbAsset()` 런타임 로딩** — 빌드 훅(`.fsceneb`)은 쓰지 않는다.
   `Node.fromAsset` 과 `.model` 은 **존재하지 않는 API** 다
3. **PC 노드를 3단 계층으로** — `앵커(이동만)` → `보정(배율·방향)` → `모델 root(건드리지 않음)`.
   임포트 root 에는 **Z-flip 이 들어 있어** 덮어쓰면 캐릭터가 좌우 반전된다
4. **재사용 코드는 GPU 여부로 배럴을 나눈다** — 순수 로직(속도→상태, 가중치 전환)과
   GPU 인접(로더·클립)을 같은 배럴에 두면 위젯 테스트가 깨진다
5. **클립 이름·에셋 경로·배율은 게임이 주입** — 엔진 코드에 `'idle'` 문자열이 있으면 안 된다

### 검증은 3층으로

| 층 | 무엇을 | 어디서 |
|---|---|---|
| 순수 | 상태 판정(히스테리시스), 전환 가중치, 실패 경로 | `flutter test` |
| 결선 | GLB 임포트·클립 재생 | `integration_test` (Impeller) |
| 체감 | 반전·크기·발 높이 | 실기 + 스크린샷 |

⚠️ **스크린샷 전에 카메라를 캐릭터 가까이 당긴다.** 기본 거리에서는 캐릭터가 수십
픽셀짜리 점이라 아무것도 판별할 수 없다(실측 — 첫 검증 스크린샷이 통째로 쓸모없었다).

## 산출물

```
<출력>/
├── <이름>_rigged/            # Tripo 리깅 FBX + .fbm 텍스처
├── <이름>_animated.fbx       # 리타게팅 결과 (⑦ 의 입력)
└── <이름>_animated.glb       # ⚠️ 소스 액션이 섞여 있다. 쓰지 말 것

assets/models/
└── <이름>.glb                # 최종 — 게임에 넣는 것은 이것뿐
```

## 사용자에게 반드시 알릴 것

- **손가락이 움직이지 않는다.** Tripo 리그(41본)에 손가락 본이 없어 Mixamo 의 주먹
  쥐기가 손목 회전으로만 남는다. `run`·`hit` 에서 손 모양이 어색하다
- **크레딧 소모** — 생성 55~65, 리깅 20, Export 40 정도. 실패해도 돌아오지 않는다
- **배율은 스크린샷을 보고 정한 값**이라 플레이하며 조정할 여지가 있다
- 애니메이션 폴더에 **실제로 무엇이 있는지** (`attack`·`death` 가 없는 경우가 흔하다)

## 자주 겪는 문제

| 증상 | 대처 |
|---|---|
| 버튼을 눌렀는데 아무 일도 안 일어남 | `evaluate_script` 대신 **`click` 도구에 uid**. 크레딧 차감으로 실행 확인 |
| 리깅이 끝난 줄 알았는데 아님 | `/Retry/` 는 `Free Retry` 때문에 항상 참. `Model Type` + `Skeleton` 으로 판정 |
| 다운로드가 오지 않음 | 8k 텍스처가 원인. `2k` 로 재시도(크레딧은 차감되므로 처음부터 2k) |
| 받은 FBX 에 아마추어 없음 | 리깅 전 파일을 받았거나 Export Skeleton 이 꺼짐 |
| `Model count limit exceeded` | 계정 저장 한도 초과. 에셋 삭제는 되돌릴 수 없으므로 **반드시 사용자 확인 후** |
| `[경고] 타겟에 없는 본` | `v2.5 Good for Animals` 로 리깅함. `v1.0 - Good for Humanoid` 로 다시 |
| F-커브 0개 | Blender 4.4+ 슬롯 미연결. `retarget.py` 의 `assign_action()` 확인 |
| 팔다리가 뒤틀림 | 생성 시 T-Pose 토글 누락, 또는 Twist 본을 매핑함 |
| 게임에서 클립이 0개 | 애니메이션 이름 불일치. `inspect_glb.py` 로 확인 → ⑦ 재실행 |
| 게임에서 캐릭터가 좌우 반전 | 임포트 root 의 `localTransform` 을 덮어씀. 3단 계층으로 |
| 게임에서 두 배로 이동 | 클립에 root motion 잔존. `inspect_glb.py` 로 확인 → ⑦ 재실행 |
| 게임에서 캐릭터가 공중에 뜸 | 이전 표현(구체 등)의 높이 보정값이 남음. 캐릭터는 발이 원점이다 |
