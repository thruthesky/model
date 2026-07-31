---
name: model
description: Tripo3D(tripo3d.ai)로 3D 캐릭터를 생성해 리깅 없이 곧바로 내려받고, Blender 의 Auto-Rig Pro 애드온으로 Mixamo 규격 리그(mixamorig:* 본)를 입힌 뒤, game-assets/animations/default 의 Mixamo 애니메이션(idle·walk·run·attack·death)을 적용해 texture-packer 의 sheet.py 로 16방향 packed atlas(Flame flame_texturepacker)를 굽는다. 다음 요청에 사용할 것 - "3d 모델 만들어줘", "캐릭터 생성", "tripo 로 모델 뽑아줘", "몬스터/사람/로봇 3D 모델 만들어줘", "우주복/개척자/NPC 모델", 생성한 모델에 "리깅해줘", "auto rig", "Auto-Rig Pro 로 리깅", "Mixamo 본 붙여줘", "mixamo 애니메이션 적용", "걷기/공격 모션 넣어줘", "PC 를 스프라이트로 만들어줘", "16방향 아틀라스 만들어줘", "도형 대신 캐릭터 그림 넣어줘", 또는 리깅 결과를 "Blender 로 보여줘". 텍스트→3D 생성, ARP 오토 리깅, ARP→Mixamo 본 이름 rename, 리그 검증, 16방향 5행동 texture-pack 까지 전 과정을 다룬다.
---

# Tripo3D 캐릭터 → Auto-Rig Pro(Mixamo 리그) → 16방향 스프라이트 아틀라스

텍스트 프롬프트로 3D 캐릭터를 만들고, Blender 에서 리깅하고, Mixamo 애니메이션을 입혀,
**게임에 넣을 수 있는 packed atlas** 로 굽는 전 과정.

⚠️ **Tripo 의 오토 리깅(Animate 탭)을 쓰지 않는다**〔원저자 지시 2026-07-30〕. 생성한 모델을
**리깅하지 않은 채로 내려받아** Blender 의 **Auto-Rig Pro** 로 리깅한다. 크레딧 20 을 아끼는
것보다 중요한 이유가 둘 있다:

- **본 이름을 우리가 정한다.** ARP export 단계에서 `mixamorig:*` 규격으로 rename 하므로
  Mixamo 애니메이션이 **리타게팅 없이** 그대로 붙는다(아래 ⑥ 참조). Tripo 리그(41본,
  `Hip`/`L_Upperarm` 식)는 매번 본 매핑을 거쳐야 했다.
- **손가락이 움직인다.** Tripo v1.0 Humanoid 리그에는 손가락 본이 없어 주먹 쥐기가
  손목 회전으로만 남았다. ARP 는 손가락 3마디를 만든다.

⚠️ **최종 산출물은 GLB 가 아니라 `.png` + `.atlas` 다.** 이 저장소는 `flutter_scene`(3D)을
쓰지 않는다(원저자 확정 2026-07-30 — 루트 `CLAUDE.md`). 런타임은 Flame 2.5D 아이소메트릭이고
캐릭터는 **16방향 프리렌더 스프라이트**다. GLB 를 만드는 옛 경로는 아래
[레거시](#레거시--glb-경로) 절에 축소해 남겨 두었다.

## 준비 확인

```bash
which blender && blender --version | head -1      # 실측: 5.1.2
ls game-assets/animations/default/*.fbx           # idle walk run attack death

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
- 애니메이션 폴더에 **실제로 무엇이 있는지 먼저 확인하고 사용자에게 알린다.**
  5개를 가정하지 말 것.

## 전체 흐름

```
① 로그인 → ② 생성(T-Pose) → ③ 리깅 없이 다운로드
  → ④ ARP 리깅 (Smart → **Match to Rig** → Bind) → ⑤ Mixamo 본 이름으로 export
  → ⑥ 리그 검증 → ⑦ **rest pose 보정(.blend)** → ⑧ texture-pack(16방향 5행동)
  → ⑨ 아틀라스 검증
```

**⑥ 과 ⑨ 를 건너뛰면 실패를 놓친다.** 이 파이프라인의 실패는 대부분 예외가 아니라
"돌기는 했는데 캐릭터가 안 움직인다"·"움직이는데 자세가 틀렸다" 로 나타난다 — 본 이름이
하나 어긋나면 sheet.py 는 경고 없이 **정적 프레임**을 굽고, 이름이 다 맞아도 rest pose 가
다르면 **팔이 만세인 스프라이트**를 굽는다(⑦ 참조).

**완료 조건** — 아래를 다 통과해야 "됐다" 고 말한다:

1. ④ `Match to Rig` 를 눌렀다(안 누르면 Bind·Export 가 거부한다)
2. ⑥ `verify_mixamo_rig.py` 종료 코드 0
3. ⑦ 리타게팅 로그에 `[OK] <행동>` 이 **5줄** → `.blend` 생성
4. ⑧ 렌더 로그에 `애니 소스 : 캐릭터 내장(built-in)` + `####ANIM <행동> ← '<액션>'` 이
   **5줄**, `####WARN … 정적` 이 **0줄**
5. ⑨ `verify_cells` 잘림 경고 없음 + **낱장 프레임 몽타주를 눈으로 확인**
   (행동 5종이 서로 다른 포즈인가 · 팔이 만세가 아닌가 · 16방향이 실제로 도는가)
5. 앱에서 실제로 로드된다 — ⚠️ **로더가 폴더 이름 기반으로 전환되는 중이다**(③ 참조).
   전환이 끝나기 전에는 이 항목이 굽는 쪽의 실패가 아닐 수 있다

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
3. **`T-Pose` 토글 ON** — ARP 의 마커 자동 배치 정확도가 크게 달라진다
4. `Generate Model` 클릭

**생성에 3~5분 걸린다.** 백그라운드 대기 후 스크린샷으로 확인할 것. 55~65 크레딧.

### 프롬프트 규칙

Mixamo 애니메이션은 인간형 리그 전용이고, ARP 의 humanoid 리그도 마찬가지다.
**인간형 T-포즈를 반드시 강제한다.** 사족보행·다관절·촉수형으로 생성되면 이후 단계가
전부 불가능하다.

```
A male astronaut colonist in a white and orange sci-fi spacesuit, full body,
standing in T-pose with both arms straight out horizontally, humanoid proportions
with two arms and two legs, sealed helmet with dark reflective visor, life support
backpack, armored chest plate, gloves and boots, symmetrical, clean topology, game-ready
```

필수 요소: `humanoid proportions`, `two arms and two legs`,
`standing in T-pose with arms straight out horizontally`, `symmetrical`, `game-ready`

사용자가 "거미 몬스터", "용" 처럼 비인간형을 요청하면 Mixamo 애니메이션 적용이 불가능함을
알리고 인간형으로 조정할지 확인할 것.

### 폴리곤은 나중에 줄인다

`HD Model` 은 약 200만 페이스를 만든다. **여기서 `Smart Mesh`·`Retopo` 로 줄이려 하지
말 것** — 크레딧이 더 든다. ④ 의 Decimate 가 리깅 전에 안전하게 줄인다(실측: 191만 → 3만).

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

받은 뒤 **sheet.py 가 기대하는 자리**에 푼다 — 폴더 이름이 곧 자산 이름이다:

```bash
NAME=colonist                     # 자산 이름 = 폴더명 = 화면에 보이는 캐릭터 이름
DST=game-assets/characters/pc/male/$NAME       # pc 는 중간 단계가 하나 더 필요하다(아래)
mkdir -p "$DST"
unzip -o ~/Downloads/"<이름>_raw.zip" -d "$DST"
# 서브셸로 감싼다 — cd 가 남으면 이후 상대 경로 명령이 조용히 엉뚱한 곳을 본다
( cd "$DST" \
  && mv tripo_convert_*.fbx  ${NAME}_raw.fbx \
  && mv tripo_convert_*.fbm  ${NAME}_raw.fbm )   # 텍스처 폴더. FBX 와 같은 이름이어야 로드된다
```

**`<NAME>` 이 곧 자산 이름이자 아틀라스 이름이다** — `assets/pc/<NAME>/<NAME>.atlas` 가 되고,
**그 이름이 캐릭터 선택 화면에 그대로 보인다**〔원저자 지시 2026-07-30〕. 사람이 읽을 이름을
붙일 것(`colonist`·`denis`·`maria`).

⚠️ **성별 구분은 없어졌다.** 예전에는 `male`·`female` 두 가지가 곧 캐릭터였지만, 지금은
**폴더 이름이 캐릭터 종류**다. 성별로 나누지 말고 캐릭터마다 폴더를 하나 만든다.

⚠️ **`pc` 는 중간 폴더가 하나 더 필요하다** — `sheet.py` 가 `pc/<중간>/<NAME>/<파일>` 네
단계를 요구하고 **끝에서 두 번째**를 자산 이름으로 쓴다(`sheet.py:553-557`). 중간 폴더의
이름 자체는 아무 영향이 없다(분류용). 기존 자산이 `pc/male/` 아래 있어 그대로 두는 것뿐이다.

🛑 **런타임 로더는 아직 전환 중이다.** [pc_atlas.dart](../../../lib/engine/actor/pc_atlas.dart)
가 아직 `PcGender`(`male`·`female`) enum 으로 `assets/pc/<gender>/<gender>.atlas` 를 찾는다.
폴더 이름을 그대로 보여주고 고르게 하는 작업이 **다른 팀에서 진행 중**이므로, 그 전까지는
새 이름으로 구운 아틀라스가 앱에서 안 보일 수 있다. **굽는 쪽은 이 문서대로 진행하면 된다** —
이름 규칙이 바뀌는 것이 아니라 로더가 따라오는 중이다.

⚠️ **raw 를 `_raw` 로 남긴다.** ⑤ 의 ARP export 가 `<NAME>.fbx` 를 쓰므로, 같은 이름으로
풀면 원본이 덮여 리깅을 다시 하려면 Tripo 에서 다시 받아야 한다(크레딧 재소모).

⚠️ **이 폴더에 애니메이션 `.fbx` 를 두지 말 것.** `--animations` 를 생략하면 sheet.py 가
모델과 같은 폴더의 `idle/walk/attack/death.fbx` 를 **1순위**로 집는다(`sheet.py:732`).
우리는 `animations/default` 를 쓴다.

## ④ Auto-Rig Pro 리깅 (Blender)

⚠️ **이 단계는 GUI 작업이다.** ARP 의 Smart 는 마커 위치를 **눈으로 확인**해야 하고,
모델마다 실패 양상이 다르다. `--background` 로 완전 자동화하지 않는다 — 자동으로 놓인
마커가 어깨 하나만 어긋나도 팔이 통째로 뒤틀린 채 아틀라스까지 그대로 간다.
Blender MCP(`mcp__blender__*`)가 붙어 있으면 **화면을 보면서** 조작한다.

1. **임포트·정리**
   - `File > Import > FBX` 로 `<NAME>.fbx`
   - 캐릭터가 **Z-up, 발이 원점, 정면이 -Y** 를 보게 회전·이동
   - `Object > Apply > All Transforms` — **스케일이 1 이 아니면 ARP 가 어긋난다**
   - 키가 실제 사람 크기(약 1.7~1.8)인지 확인. cm 단위로 오면 0.01 배
   - 페이스가 많으면 여기서 `Decimate`(COLLAPSE) 로 3만 안팎까지 줄인다

2. **ARP Smart — 마커 배치**
   - `Auto-Rig Pro: Smart` 패널 → `Get Selected Objects` (메시 선택 상태에서)
   - **`Spine Count` 를 `4` 로 둔다** (프로퍼티 기본값이 4 다 — `auto_rig_smart.py:8421`).
     ⚠️ **`3` 으로 낮추지 말 것.** 직관과 반대로, ARP 는 `spine_count == 3` 이면 export
     리그에서 **`spine_03.x` 를 삭제**한다(`auto_rig_ge.py:6322-6329`). `> 3` 일 때만
     추가한다(`6287`). 즉 Mixamo 의 `Spine/Spine1/Spine2` 3분할에 대응하려면 **4** 다.
     (실측: 3 으로 구운 `colonist.fbx` 는 `spine2` 역할이 비어 21/22 였다)
   - `Add Neck` / `Add Chin` / `Add Shoulders` / `Add Wrists` / `Add Spine Root`
     / `Add Ankles` 를 차례로 눌러 마커를 놓는다 (`arp.guess_markers` 로 자동 추정 가능)
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

## ⑤ Mixamo 본 이름으로 export

ARP 의 **Game Engine Export** 가 컨트롤러를 걷어내고 deform 본만 남긴 스켈레톤을 굽는다.
이때 **Rename Bones from File** 로 본 이름을 Mixamo 규격으로 바꾼다.

🛑 **④-3 의 `Match to Rig` 를 안 눌렀으면 여기서도 거부당한다**
(`'Click "Match to Rig" before exporting'` — `auto_rig_ge.py:1648-1652`). 리그를 손본 뒤
Export 하러 왔다면 **`Match to Rig` 를 다시 누르고 온다.**

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
(`auto_rig_ge.py:8587-8589`). `human.blend` 를 열어 `use_deform` 을 실측하면 `thumb1.l` 이
나오는데 **그건 원본 리그다** — 이 값을 매핑표에 적으면 1번 마디 10개가 조용히 rename 되지
않는다(실측: `colonist.fbx` 에 `c_thumb1.l` 등 정확히 10개가 남았다).

내보낼 곳은 **모델과 같은 폴더, 같은 이름**이다 — sheet.py 가 폴더명으로 자산을 식별한다:

```
game-assets/characters/pc/<중간>/<NAME>/<NAME>.fbx     ← ARP export 결과
                                <NAME>_raw.fbx        ← ③ 의 원본. 지우지 않는다
```

## ⑥ 리그 검증 (생략 금지)

```bash
# 프로젝트 루트에서 실행한다(Blender 는 --python 경로를 cwd 기준으로 연다)
blender --background --python .claude/skills/model/scripts/verify_mixamo_rig.py -- \
  game-assets/characters/pc/male/<NAME>/<NAME>.fbx \
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
| rename 이 **통째로** 실패 | `sheet.py` 가 **시작도 못 하고 종료** — `❌ … Mixamo rig 가 아닙니다` | `Rename Bones from File` OFF 또는 파일 경로 오류. ARP 는 파일을 못 찾아도 `Rename Bone File not found! Skip renaming` 만 찍고 **그냥 진행**한다(`auto_rig_ge.py:10406`). 종료시키는 쪽은 `sheet.py:398-411` 의 `assert_mixamo_rig` 다 |
| rename 이 **부분** 실패 | 렌더는 끝나는데 **5행동이 전부 같은 포즈** | 교집합이 임계 미달. 매핑표의 본 이름이 export 리그와 어긋난 것 |

⚠️ **background 실행 시 ARP 가 `arp_debug_mode` AttributeError 를 뱉는다**(실측).
씬 로드 핸들러가 GUI 속성을 찾는 것이라 **무해하다** — 검증 출력은 그 아래에 나온다.

판정 로직 자체의 테스트는 Blender 없이 돈다:

```bash
python3 .claude/skills/model/scripts/test_verify_mixamo_rig.py    # 22개
```

## ⑦ rest pose 보정 — **ARP 리그에는 이 단계가 반드시 필요하다** 🛑

⚠️ **⑥ 이 전부 `OK` 여도 애니메이션을 그대로 쓰면 안 된다.** 검증이 통과시키는
"리타게팅 없이 직접 적용" 은 **본 이름이 맞다**는 뜻이지 **포즈가 맞다**는 뜻이 아니다.

`_sheet_render.py:451` 은 본 이름 교집합이 임계를 넘으면 **rest pose 보정 없이 액션을
그대로 할당**한다. Mixamo 로 리깅된 캐릭터끼리는 rest 가 같아 그래도 맞지만, **ARP 리그는
이름만 Mixamo 이고 rest pose(본 방향·roll)가 다르다** — 실측 결과 **5행동 전부 팔이
만세로 올라간 스프라이트**가 나왔다. 예외도 경고도 없다.

```bash
blender --background --python .claude/skills/model/scripts/retarget_to_arp_rig.py -- \
  game-assets/characters/pc/male/<NAME>/<NAME>.fbx \
  game-assets/animations/default \
  game-assets/characters/pc/male/<NAME>/<NAME>.blend
```

캐릭터 + 보정된 액션 5종을 담은 `.blend` 가 나온다. 이 스크립트가 지키는 것 셋:

| | 왜 |
|---|---|
| **월드 기준** 상대 회전<br>`(src_pose @ src_rest⁻¹) @ tgt_rest` | `_sheet_render.py` 의 `retarget_action` 은 **로컬 기준**이고, 그 식은 두 리그의 **본 로컬 축(roll)이 대응할 때만** 맞다. ARP GE Export 는 본 축을 자체 규약으로 정하므로 로컬 기준으로 옮기면 **다리는 맞고 팔만 틀어진다**(실측) |
| 결과를 **`.blend`** 로 (FBX 아님) | 리타게팅 직후엔 정확한데, Blender 기본 exporter 로 FBX 를 내보내 다시 임포트하면 **rest 가 달라져 또 T-포즈로 벌어진다**(실측). 캐릭터 FBX 는 ARP GE Export 가, 애니 FBX 는 Blender 가 만들어 축 규약이 갈린다 |
| `action_slot` 지정 | Blender 4.4+ 의 slotted action — slot 을 안 잡으면 액션이 **조용히 평가되지 않는다**(정적 T-포즈) |

## ⑧ texture-pack — 16방향 5행동

[texture-packer 스킬](../texture-packer/SKILL.md)의 `sheet.py` 에 **⑦ 이 만든 `.blend`** 를
주고 **`--animations built-in`** 으로 내장 액션을 쓰게 한다. `pc` kind 의 기본 행동이 정확히
**idle · walk · attack · death · run** 이고 방향은 **16** 이다.

```bash
python3 .claude/skills/texture-packer/scripts/sheet.py \
  ./game-assets/characters/pc/male/<NAME>/<NAME>.blend \
  --animations built-in --auto
```

액션 이름이 `idle`/`walk`/`run`/`attack`/`death` 라 `match_embedded` 가 정확 매칭한다
(`_sheet_render.py:489`). 로그에 `애니 소스 : 캐릭터 내장(built-in)` 이 찍히는지 볼 것.

<details>
<summary>⑦ 없이 FBX 를 직접 주는 옛 방식 (Mixamo 로 리깅된 캐릭터에만 유효)</summary>

```bash
python3 .claude/skills/texture-packer/scripts/sheet.py \
  ./game-assets/characters/pc/male/<NAME>/<NAME>.fbx \
  --animations default --auto
```
</details>

경로에서 `--kind pc --name <NAME>` 이 추론되고 `--auto` 가 켜진다(`sheet.py:1730-1732`).
`--animations default` 는 명시하는 편이 안전하다 — **명시하면 자동 탐색 블록 자체가 돌지
않아 `default` 로 고정되기 때문**이다(`sheet.py:732`·`744` 두 블록의 조건이 모두
`not args.animations`). 생략하면 모델 폴더 → `animations/<NAME>/` → `default` 순으로 찾다가
의도치 않은 세트를 집을 수 있다.

⚠️ **이 저장소에는 `scripts/compress_image.py` 가 없어 색 압축이 조용히 건너뛰어진다.**
`sheet.py:1239` 는 프로젝트 루트의 그 파일을 부르는데(texture-packer 스킬 소유가 아니다),
없으면 예외 없이 무압축으로 넘어간다. 실측 — 같은 규격인데 **4배**다:

| | 아틀라스 페이지 | PNG |
|---|---|---|
| `male`(압축됨) | 7921×763 | 1.5 MB |
| `colonist`(압축 안 됨) | 7727×539 (더 작다) | **6.1 MB** |

번들 용량이 중요하면 laryen 의 `scripts/compress_image.py` 를 이 저장소에 두거나
(`numpy`·`Pillow` 필요), 구운 뒤 따로 256색 양자화한다.

| 항목 | 값(pc 기본) |
|---|---|
| 방향 | **16** |
| 셀 | 128px 고정 |
| 행동·프레임 | `idle 8` · `walk 12` · `attack 16` · `death 8` · `run 12` = 56프레임 |
| 총 셀 | 56 × 16 = **896** |
| 산출 | `assets/pc/<NAME>/<NAME>.png` + `.atlas`, `pubspec.yaml` 자동 등록 |

프레임 수를 바꾸려면 `--idle 8 --walk 12 --attack 16 --death 8 --run 12` 처럼 개별 지정한다.
**애니메이션 원본 길이는 idle 180 · walk 31 · run 16 · attack 38 · death 72 프레임**(실측)
이므로, 위 기본값은 그 구간을 균등 샘플링한 것이다.

옵션·발 정렬·색 압축·잘림 검사는 texture-packer 스킬이 소유한다. **거기 문서를 먼저 읽을 것.**

## ⑨ 아틀라스 검증 (생략 금지)

리깅은 조용히 실패한다. 키프레임이 들어갔는데 포즈만 뒤틀리는 경우가 있으므로
**눈으로 확인해야 한다.**

**셀 잘림은 sheet.py 가 이미 검사했다** — `--verify-cells` 기본값이 `true` 라 렌더 직후
낱장 프레임을 훑고, 잘린 행동이 있으면 권장 옵션을 출력한다. 그 줄을 놓치지 말 것:

```
🛑 잘린 행동 2종 — 아래 옵션으로 재생성 권장:
   --scale-attack 0.85 --scale-run 0.9
```

⚠️ **`verify_cells.py --atlas` 로 판정하지 말 것.** packed 아틀라스는 trim 후라 원본
잘림이 보이지 않아 정상 자산도 전부 후보로 찍힌다(스크립트 주석의 실측 경고). 다시 검사할
일이 있으면 **낱장 프레임 폴더**로 돌린다:

```bash
python3 .claude/skills/texture-packer/scripts/verify_cells.py --frames outputs/<NAME>/frames
```

그리고 `assets/pc/<NAME>/<NAME>.png` 을 **Read 로 열어** 확인한다 — 여기부터는 자동화할
수 없다:

- 5행동이 모두 **다른 포즈**인가 (전부 같으면 애니메이션이 안 붙은 것 → ⑥ 재실행)
- 16방향이 실제로 돌아가는가
- 팔다리가 뒤틀리지 않았는가 (뒤틀렸으면 ④ 의 마커 위치 → 재리깅)
- 발 높이가 행동별로 튀지 않는가 (`align_feet` 가 맞추지만 확인은 필요)

## 산출물

```
game-assets/characters/pc/<중간>/<NAME>/        # <중간> 은 분류용 — sheet.py 는 이름을 안 본다
├── <NAME>_raw.fbx      # ③ Tripo 원본(리깅 전) — 지우지 않는다
├── <NAME>_raw.fbm/     # 텍스처
├── <NAME>.fbx          # ⑤ ARP 리깅 + Mixamo 본 이름
├── <NAME>.blend        # ⑦ rest pose 보정 + 액션 5종 ← **sheet.py 의 입력**
└── <NAME>_rig.blend    # ARP 리그 원본(컨트롤러 포함) — 재리깅용으로 반드시 남긴다

assets/pc/<NAME>/
├── <NAME>.png          # packed atlas
└── <NAME>.atlas        # flame_texturepacker 메타 (+ laryen.actionScale.* 헤더)
```

**`<NAME>` 이 캐릭터 이름이고, 그대로 선택 화면에 보인다**〔원저자 지시 2026-07-30〕.
성별 구분은 없다 — 캐릭터마다 폴더를 하나 만든다(`colonist`·`denis`·`maria`).

⚠️ **로더는 전환 중이다.** 현재 코드는 아직
[terraform_game.dart:98-106](../../../lib/engine/terraform_game.dart) 이 `PcGender.values`
(`male`·`female`)만 순회하고 [pc_atlas.dart:94-107](../../../lib/engine/actor/pc_atlas.dart)
이 `assets/pc/<gender>/<gender>.atlas` 를 연다. 폴더 이름을 그대로 보여주고 고르게 하는
작업이 **다른 팀에서 진행 중**이라, 그 전까지 새 이름 아틀라스는 번들에만 들어가고 화면에는
안 나올 수 있다. **이 스킬은 굽는 데까지 책임지며, 이름 규칙은 위가 정본이다.**

런타임 쪽 규약(이미 구현돼 있다 — 이 스킬이 맞춰야 하는 계약):

| 무엇 | 값 | 어디 |
|---|---|---|
| region 이름 | `<action>_<DIR16>` (예: `walk_ESE`) | `pc_atlas.dart:7` |
| 행동 | `idle` `walk` `run` `attack` `death` | `pc_atlas.dart:82-88` |
| 행동별 배율 | `.atlas` 헤더의 `laryen.actionScale.<action>` 을 `1/scale` 로 되돌림 | `pc_atlas.dart:19-23` |
| trim 복원 | `useOriginalSize: true` — 없으면 방향마다 발 위치가 떤다 | `pc_atlas.dart:106` |

## 사용자에게 반드시 알릴 것

- **④ 는 GUI 작업이라 자동으로 끝나지 않는다.** 마커 확인과 웨이트 확인은 사람이 본다.
  MCP 로 자동화하더라도 **마커 위치와 최종 아틀라스는 반드시 이미지로 보여준다**
- **크레딧 소모** — 생성 55~65, Export 40 정도. **리깅 20 은 이제 들지 않는다**
- 애니메이션 폴더에 **실제로 무엇이 있는지** — 없는 행동은 정적 프레임이 된다
- 아틀라스 크기·프레임 수는 조정 가능하다(위 표) — 용량이 문제면 프레임을 줄인다
- **⑦ 이 생기면서 산출물이 하나 늘었다** — `<NAME>.blend` 가 sheet.py 의 입력이다.
  이걸 지우면 아틀라스를 다시 구울 때 리타게팅부터 해야 한다
- 소요 시간 실측(우주복 캐릭터 1종) — 생성 4분 · 리깅 15분 · 리타게팅 2분 ·
  packing 1분 30초(auto-fit 재렌더 포함 시 3분)

## 자주 겪는 문제

| 증상 | 대처 |
|---|---|
| 버튼을 눌렀는데 아무 일도 안 일어남 | `evaluate_script` 대신 **`click` 도구에 uid**. 크레딧 차감으로 실행 확인 |
| 다운로드가 오지 않음 | 8k 텍스처가 원인. `2k` 로 재시도(크레딧은 차감되므로 처음부터 2k) |
| `Model count limit exceeded` | 계정 저장 한도 초과. 에셋 삭제는 되돌릴 수 없으므로 **반드시 사용자 확인 후** |
| ARP `Go!` 에서 실패 | 스케일이 1 이 아니거나(Apply All Transforms) 메시가 여러 개로 쪼개져 있다 |
| **`Click "Match to Rig" before binding/exporting`** | ④-3 을 건너뛴 것이다. reference bones 를 손본 뒤에도 **다시 눌러야** 한다 |
| ARP 리그가 몸에 안 맞음 | 마커 위치 문제. 헬멧·백팩이 있으면 목·어깨를 손으로 옮긴다 |
| `sheet.py` 가 `Mixamo rig 가 아닙니다` 로 즉시 종료 | rename 이 **통째로** 실패했다. `Rename Bones from File` 이 켜져 있었는지·경로가 맞는지 확인(`sheet.py:398-411`) |
| `Mixamo 리그로 감지되지 않는다` | 위와 같은 원인. ARP 는 rename 파일이 없어도 **경고만 찍고 진행**한다 |
| 검증에 `spine2 가 비었다` | Spine Count 가 3 이다. **4** 로 올린다(3 이면 ARP 가 `spine_03.x` 를 지운다) |
| 검증에 `ARP 이름이 남아 있는 본 … c_thumb1.l` | 매핑표가 export 리그 이름과 어긋났다. 손가락 세 마디 전부 `c_` 다 |
| 정점 그룹이 본과 이름이 다름 | rename 이 vgroup 에 반영되지 않았다. ARP GE Export 를 쓰지 않고 손으로 rename 했을 때 발생 |
| 아틀라스의 5행동이 전부 같은 포즈 | 교집합이 임계 미달이다. ⑥ 을 돌려 `교집합 N < 32` 를 확인하고 매핑표를 고친다 |
| **5행동이 움직이긴 하는데 팔이 전부 만세** | ⑦ 을 건너뛰었다. 본 이름이 다 맞아도 **ARP rest pose ≠ Mixamo rest pose** 라 그대로 붙이면 뒤틀린다. `retarget_to_arp_rig.py` 로 `.blend` 를 만들어 `--animations built-in` 으로 굽는다 |
| 리타게팅했는데 **다리는 맞고 팔만 틀어짐** | 로컬 기준으로 보정한 것이다. **월드 기준**(`src_pose @ src_rest⁻¹ @ tgt_rest`)이어야 한다(⑦) |
| 리타게팅 결과를 FBX 로 내보냈더니 **다시 T-포즈** | FBX 왕복에서 rest 가 달라진다. **`.blend` 로 넘긴다**(⑦) |
| 액션을 할당했는데 **정적 T-포즈** | Blender 4.4+ 의 slotted action — `animation_data.action_slot` 을 안 잡았다 |
| `id.go_detect.poll() failed` 가 계속 남 | 컨텍스트가 아니라 **active 오브젝트가 숨겨진 것**이다. `body_temp` 를 active 로 둔다(④-A 4번) |
| `AI files are missing or not up to date` | `guess_markers`·`guess_fingers` 는 ARP AI 리소스가 필요하다. 마커는 `id.add_marker` 로 직접 놓고, 손가락은 `arp_smart_fingers_engine='LEGACY'` 로 우회(④-A 3번) |
| `_append_arp` 가 `space_data … NoneType` 로 죽음 | MCP 실행 컨텍스트에 3D 뷰가 없다. `bpy.app.timers` 안에서 `temp_override(window, area, region)` 로 실행(④-A 5번) |
| 캐릭터가 100배 크기로 export 됨 | `arp_units_x100` 이 **기본 ON** 이다(⑤). 아틀라스만 보면 프레이밍이 bbox 기준이라 안 드러난다 |
| 아틀라스 PNG 가 유난히 크다 | 색 압축이 건너뛰어졌다 — `scripts/compress_image.py` 부재(⑧ 참조) |
| 팔이 뒤틀림 | 생성 시 T-Pose 토글 누락, 또는 Twist 본을 export 했다(`arp_export_twist` 는 **기본 ON**) |
| 구운 아틀라스가 게임에 안 보임 | 로더가 아직 `PcGender`(`male`·`female`) 기반이다 — 폴더 이름 기반 전환이 다른 팀에서 진행 중. **굽는 쪽의 실패가 아니다**(③·산출물 참조) |
| 프레임이 셀 밖으로 잘림 | `verify_cells.py` 가 제안하는 `--scale-<action>` 을 적용해 재굽기 |
| background 에서 `arp_debug_mode` AttributeError | ARP 의 GUI 핸들러. **무해하다** — 그 아래 출력을 본다 |

## 레거시 — GLB 경로

**이 저장소에서는 쓰지 않는다.** `flutter_scene`(3D)을 폐기했기 때문이다(원저자 확정
2026-07-30). 아래 스크립트는 3D 런타임을 쓰는 다른 프로젝트를 위해 남겨 둔 것이고,
Tripo 오토 리깅 리그를 전제한다:

| 스크립트 | 용도 |
|---|---|
| `scripts/retarget.py` | Mixamo → Tripo 본 리타게팅 → [references/retargeting.md](references/retargeting.md) |
| `scripts/postprocess_glb.py` | Decimate · root motion 제거 · 액션명 정규화 → GLB |
| `scripts/inspect_glb.py` | GLB 10개 항목 검사(Blender 없이 순수 Python) |
| `scripts/verify_render.py` | 동작별 프리뷰 PNG 렌더 |
| `scripts/inspect_rig.py` | 리그 구조 덤프(`--tree`) — **새 흐름에서도 디버깅에 유용하다** |
| `references/flutter-scene-integration.md` | flutter_scene 통합 |

⚠️ **새 흐름에 이것들을 섞지 말 것.** 특히 `postprocess_glb.py` 의 root motion 제거는
sheet.py 가 Hips 를 추적해 스스로 처리하므로 불필요하고, 액션명 정규화는 sheet.py 의
행동 인식과 규칙이 다르다.
