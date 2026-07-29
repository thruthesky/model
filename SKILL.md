---
name: model
description: Tripo3D(tripo3d.ai)로 3D 모델을 생성·다운로드하고 Mixamo 애니메이션(FBX)을 적용한다. 다음 요청에 사용할 것 - "3d 모델 만들어줘", "캐릭터 생성", "tripo 로 모델 뽑아줘", "몬스터/사람/로봇 3D 모델 만들어줘", 생성한 모델에 "애니메이션 붙여줘", "리깅해줘", "auto rig", "mixamo 애니메이션 적용", "걷기/공격 모션 넣어줘", 또는 애니메이션 결과를 "Blender 로 보여줘". 텍스트→3D 생성, 오토 리깅, Mixamo→Tripo 본 리타게팅, Blender 자동 재생 미리보기까지 전 과정을 다룬다.
---

# Tripo3D 모델 생성 + Mixamo 애니메이션

텍스트 프롬프트로 3D 캐릭터를 만들고, 리깅한 뒤, 기존 Mixamo FBX 애니메이션을 입혀 게임에 바로 쓸 수 있는 파일로 내보낸다.

## 준비 확인

```bash
which blender                    # 없으면 사용자에게 설치 요청
ls <애니메이션폴더>/*.fbx          # 기본 위치 ./default/ (idle walk run attack hit death)
```

Chrome DevTools MCP 가 필요하다. 없으면 브라우저 자동화가 불가능하므로 사용자에게 알릴 것.

## 전체 흐름

```
로그인 → 텍스트→3D 생성 → 오토 리깅 → FBX 다운로드
     → 리그 확인 → 리타게팅 → 렌더 검증 → (요청 시) Blender 미리보기
```

각 단계는 앞 단계 산출물에 의존한다. 건너뛰지 말 것. 특히 **리그 확인과 렌더 검증은 생략하면 실패를 놓친다.**

## 1단계 — 로그인

`https://studio.tripo3d.ai/workspace/generate` 접속.

**Google OAuth 는 쓸 수 없다.** MCP 브라우저는 `--enable-automation` 플래그 때문에 Google 이 차단한다. 이메일 인증 코드를 쓴다.

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

셀렉터와 함정은 [references/tripo-studio.md](references/tripo-studio.md) 참조. **UI 조작에서 막히면 반드시 읽을 것.**

## 2단계 — 모델 생성

1. 생성 패널의 **4번째 아이콘(연필)** 을 눌러 텍스트 모드로 전환 (기본은 이미지 업로드 모드)
2. 프롬프트 입력
3. **`T-Pose` 토글 ON** — 리깅 품질이 크게 달라진다
4. `Generate Model` 클릭

**생성에 3~4분 걸린다.** 백그라운드 `sleep` 으로 기다렸다가 스크린샷으로 확인할 것. 비용 55~65 크레딧.

### 프롬프트 규칙

Mixamo 애니메이션은 인간형 리그 전용이다. **인간형 T-포즈를 반드시 강제한다.** 사족보행·다관절·촉수형으로 생성되면 이후 단계가 전부 불가능하다.

```
A menacing humanoid AI robot monster, full body, standing in T-pose with both arms
straight out horizontally, humanoid proportions with two arms and two legs,
heavy mechanical armor plating, glowing red eyes, symmetrical, clean topology, game-ready
```

필수 요소: `humanoid proportions`, `two arms and two legs`, `standing in T-pose with arms straight out horizontally`, `symmetrical`, `game-ready`

사용자가 "거미 몬스터", "용" 처럼 비인간형을 요청하면 애니메이션 적용이 불가능함을 알리고 인간형으로 조정할지 확인할 것.

### 폴리곤 줄이기

기본 `HD Model` 은 약 200만 페이스를 만든다. 게임용이면 다음 중 하나를 쓴다.

- 패널 상단의 **`Smart Mesh`** 탭 — 게임용 저폴리곤 토폴로지를 생성한다
- 생성 후 좌측 **`Retopo`** 탭에서 리토폴로지 (추가 크레딧)
- 또는 Blender Decimate 모디파이어로 후처리

## 3단계 — 오토 리깅

좌측 `Animate` 탭 → `/workspace/rigging/<task-id>`

1. **AI Model 을 `v1.0 - Good for Humanoid` 로 변경** — 기본값이 `v2.5 - Good for Animals` 다. 놓치면 본 이름이 달라져 리타게팅이 전부 실패한다
2. `Auto Rig` (20 크레딧, 1~2분)
3. 완료 확인: 버튼이 `Retry` 로 바뀌고 `Model Type: Humanoid` 표시

드롭다운(`combobox`)은 `evaluate_script` 의 `.click()` 으로 열리지 않는다. `take_snapshot` 으로 uid 를 얻어 `click` 도구를 쓸 것.

## 4단계 — 다운로드

`Export` → 다이얼로그에서:

| 항목 | 값 |
|---|---|
| File Name | **단계마다 다르게** (아래 주의) |
| Format | `FBX` |
| FBX 프리셋 | `Blender` (`Mixamo`/`3dsmax` 는 본 방향이 바뀌어 매핑이 깨진다) |
| Texture Resolution | **`2k`** |
| Export Skeleton | **ON** |

**텍스처는 2k 를 쓴다.** 8k 는 서버에서 ZIP 생성이 지연되거나 아예 다운로드가 오지 않는 일이 잦다(크레딧만 차감된다). 2k 로 낮추면 안정적으로 받아진다.

**File Name 을 단계마다 다르게 지정할 것.** Export 는 비동기라 이전 요청의 ZIP 이 뒤늦게 도착해 리깅 전 파일과 헷갈린다.

다이얼로그 안에도 `Export` 버튼이 있으므로 **마지막 것**을 눌러야 한다.

```js
() => {
  const btns = [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Export');
  const last = btns[btns.length - 1];
  if (last) last.click();
  return { clicked: !!last };
}
```

받은 뒤 정리:

```bash
unzip -o ~/Downloads/"<파일명>.zip" -d output/<이름>_rigged/
cd output/<이름>_rigged
mv tripo_convert_*.fbx <이름>_rigged.fbx
mv tripo_convert_*.fbm <이름>_rigged.fbm    # 텍스처 폴더. FBX 와 같은 이름이어야 로드된다
```

**아마추어가 들어 있는지 반드시 확인한다:**

```bash
blender --background --python .claude/skills/model/scripts/inspect_rig.py -- \
  output/<이름>_rigged/<이름>_rigged.fbx
```

`본 41개` / `루트 본: ['Root']` 가 나와야 정상이다. `아마추어 없음` 이면 리깅 전 파일이므로 다시 받을 것.

## 5단계 — 애니메이션 리타게팅

```bash
blender --background --python .claude/skills/model/scripts/retarget.py -- \
  output/<이름>_rigged/<이름>_rigged.fbx \
  ./default \
  output \
  <이름>_animated
```

`output/<이름>_animated.fbx` 와 `.glb` 가 생성된다. 폴더의 모든 `*.fbx` 를 액션으로 변환하며 `idle walk run attack hit death` 순서를 우선한다.

**성공 판정:** 각 동작마다 `F-커브 91개` (22본 × 쿼터니언 4 + Hip 위치 3). `0개` 면 실패다.

6개 동작 기준 수 분이 걸린다. 원리·본 매핑표·문제 해결은 [references/retargeting.md](references/retargeting.md) 참조. **경고가 뜨거나 결과가 이상하면 반드시 읽을 것.**

Tripo 가 아닌 리그를 쓸 때는 `inspect_rig.py --tree` 로 본 이름을 확인하고 `scripts/retarget.py` 의 `BONE_MAP` 만 고치면 된다.

## 6단계 — 렌더 검증 (생략 금지)

리타게팅은 조용히 실패한다. 키프레임은 들어갔는데 포즈만 뒤틀리는 경우가 있으므로 **눈으로 확인해야 한다.**

```bash
blender --background --python .claude/skills/model/scripts/verify_render.py -- \
  output/<이름>_animated.fbx .preview

cd .preview && python3 -c "
from PIL import Image
import glob
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

`grid.png` 를 Read 로 열어 각 동작이 제대로 나오는지 확인한다.

## 7단계 — Blender 미리보기 (요청 시)

사용자가 "Blender 로 보여줘", "애니메이션 확인하고 싶어" 라고 하면:

```bash
blender --background --python .claude/skills/model/scripts/make_blend.py -- \
  output/<이름>_animated.fbx output/<이름>.blend

nohup blender output/<이름>.blend --python .claude/skills/model/scripts/play.py > /dev/null 2>&1 &
```

`make_blend.py` 는 모든 동작을 NLA 트랙에 순서대로 이어 붙이고 타임라인 마커를 찍는다. `play.py` 는 Blender 가 뜬 직후 카메라 뷰로 맞추고 재생을 시작한다. **사용자는 아무것도 조작할 필요가 없다.**

Blender 를 모르는 사용자에게는 이것만 안내한다: 재생/정지 `Space`, 특정 동작으로 건너뛰려면 하단 타임라인의 마커 클릭.

## 산출물

```
output/
├── <이름>_rigged/            # Tripo 리깅 FBX + .fbm 텍스처
├── <이름>_animated.fbx       # 최종 (액션별 AnimStack, 텍스처 임베드)
├── <이름>_animated.glb       # 최종 (glTF 애니메이션 클립)
└── <이름>.blend              # 미리보기용
```

## 사용자에게 반드시 알릴 것

- **손가락이 움직이지 않는다.** Tripo 리그(41본)에 손가락 본이 없어 Mixamo 의 주먹 쥐기가 손목 회전으로만 남는다. `run`·`hit` 에서 손 모양이 어색하다
- **폴리곤 수** — `HD Model` 은 약 200만 페이스다. 게임 엔진에 넣으려면 `Smart Mesh` / `Retopo` / Decimate 로 줄여야 한다
- **크레딧 소모** — 생성 55~65, 리깅 20, Export 40 정도. 실패해도 돌아오지 않는다

## 자주 겪는 문제

| 증상 | 대처 |
|---|---|
| 다운로드가 오지 않음 | 8k 텍스처가 원인. `2k` 로 낮춰 재시도. 크레딧은 차감되므로 처음부터 2k 로 할 것 |
| 받은 FBX 에 아마추어 없음 | 리깅 전 파일을 받았거나 Export Skeleton 이 꺼짐 |
| `Model count limit exceeded` | 계정 저장 한도 초과. 에셋 삭제는 되돌릴 수 없으므로 **반드시 사용자 확인 후** 진행 |
| `[경고] 타겟에 없는 본` | `v2.5 Good for Animals` 로 리깅함. `v1.0 - Good for Humanoid` 로 다시 리깅 |
| F-커브 0개 | Blender 4.4+ 슬롯 미연결. `retarget.py` 의 `assign_action()` 확인 |
| 팔다리가 뒤틀림 | 생성 시 T-Pose 토글 누락, 또는 Twist 본을 매핑함 |
| 드롭다운이 안 열림 | `evaluate_script` 대신 `click` 도구에 uid 를 넘길 것 |
