# Tripo Studio 브라우저 자동화 상세

Chrome DevTools MCP 로 https://studio.tripo3d.ai 를 조작하는 전 과정. 실제 검증된 절차다.

## 목차

- [핵심 개념](#핵심-개념)
- [로그인 — 이메일 인증 코드](#로그인--이메일-인증-코드)
- [텍스트 → 3D 모델 생성](#텍스트--3d-모델-생성)
- [오토 리깅](#오토-리깅)
- [Export (다운로드)](#export-다운로드)
- [함정 모음](#함정-모음)

## 핵심 개념

Tripo Studio 는 React SPA 다. 세 가지 원칙을 지켜야 자동화가 깨지지 않는다.

1. **uid 는 매 스냅샷마다 바뀐다.** 조작 직전에 `take_snapshot` 을 다시 찍어 uid 를 확보할 것.
2. **스냅샷 출력이 매우 길다**(에셋 목록에 서명된 URL 이 수백 줄). `filePath` 로 파일에 저장한 뒤 `grep` 으로 필요한 uid 만 뽑아 쓸 것. 컨텍스트를 아낀다.
3. **드롭다운(`combobox`)은 `evaluate_script` 의 `.click()` 으로 열리지 않는다.** Radix UI 계열이라 합성 이벤트가 필요하다. 반드시 `click` 도구에 uid 를 넘길 것. 단순 버튼은 `evaluate_script` 로 눌러도 된다.

```js
// 스냅샷 없이 버튼을 찾아 누르는 패턴 (단순 버튼에만 사용)
() => {
  const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === 'Export');
  if (b) b.click();
  return { clicked: !!b };
}
```

## 로그인 — 이메일 인증 코드

**Google OAuth 는 쓸 수 없다.** MCP 가 띄우는 Chrome 은 `--enable-automation` 플래그가 붙어 있어 Google 이 "이 브라우저는 안전하지 않을 수 있습니다"로 차단한다. 사용자의 평소 Chrome 은 원격 디버깅 포트가 꺼져 있어 붙을 수도 없다.

대신 Tripo 의 이메일 코드 로그인을 쓴다.

1. `Sign up/Log in` → `Continue with Email` 클릭
2. 이메일 입력 후 `Send Code`
3. 코드 확보:
   - **Gmail MCP 로 연결된 계정이면** 직접 읽는다:
     ```
     mcp__claude_ai_Gmail__search_threads
       query: "from:notification@tripo3d.ai newer_than:1d"
     ```
     snippet 에 `Your Login code is: 026531` 형태로 들어 있다.
   - **다른 계정이면 읽을 수 없다.** 사용자에게 6자리 코드를 요청할 것. 코드 유효기간은 10분이다.
4. 코드 입력 → `Continue`

로그인 성공 판정: 우상단에 크레딧 숫자와 프로필 아이콘이 나타난다. `Sign up/Log in` 텍스트가 사라지는지로 확인한다.

```js
() => ({ loggedIn: !/Sign up\/Log in/.test(document.body.innerText) })
```

로그인 직후 프로모션 모달(`Special Bonus`, `8K Texture`)이 뜬다. `No Thanks` / `Maybe Later` 로 닫는다.

## 텍스트 → 3D 모델 생성

URL: `https://studio.tripo3d.ai/workspace/generate`

### 1. 텍스트 모드로 전환

Generate Model 패널 상단에 아이콘 버튼 4개가 있다: `[이미지] [3D] [다중이미지] [연필]`. **4번째(연필)** 가 텍스트 입력이다. 기본값은 이미지 업로드 모드라 반드시 전환해야 한다.

스냅샷에서 `heading "Generate Model"` 바로 아래 나오는 이름 없는 `button` 4개 중 마지막을 클릭한다.

### 2. 프롬프트 입력

리깅·애니메이션이 목적이면 **인간형 T-포즈**를 강제해야 한다. 다관절/사족보행/촉수형으로 나오면 Mixamo 리타게팅이 불가능하다.

```
A menacing humanoid AI robot monster, full body, standing in T-pose with both arms
straight out horizontally, humanoid proportions with two arms and two legs,
heavy mechanical armor plating, glowing red eyes, symmetrical, clean topology, game-ready
```

필수 요소: `humanoid proportions`, `two arms and two legs`, `standing in T-pose with arms straight out horizontally`, `symmetrical`, `game-ready`

### 3. T-Pose 토글

프롬프트 입력창 아래 `T-Pose` 버튼을 켠다. 리깅 품질이 눈에 띄게 좋아진다.

### 4. 생성

`Generate Model` 버튼(크레딧 표시 포함). 소요 시간 3~4분, 비용 55~65 크레딧.

진행 상태 확인:
```js
() => ({ url: location.href, generating: /Generating/.test(document.body.innerText) })
```
생성이 시작되면 URL 이 `/workspace/generate/<task-id>` 로 바뀐다.

## 오토 리깅

좌측 사이드바 `Animate` → `https://studio.tripo3d.ai/workspace/rigging/<task-id>`

### AI Model 을 반드시 바꿀 것

기본값이 **`v2.5 - Good for Animals`** 다. 인간형 캐릭터에는 **`v1.0 - Good for Humanoid`** 를 선택해야 한다. 이걸 놓치면 본 구조가 달라져 `retarget.py` 의 `BONE_MAP` 이 전부 어긋난다.

```
1. combobox uid 를 스냅샷에서 확보          → click 도구로 클릭 (evaluate_script 로는 안 열림)
2. 다시 스냅샷 → option "v1.0 - Good for Humanoid" 의 uid 확보
3. click 도구로 선택
4. 검증: (t.match(/AI Model\s*\n\s*([^\n]+)/) || [])[1] === "v1.0 - Good for Humanoid"
```

### Auto Rig 실행

`Auto Rig` 버튼 (20 크레딧). 1~2분 소요.

완료 판정: 버튼이 `Retry` 로 바뀌고, `Skeleton` 토글과 `Model Type: Humanoid` 가 나타난다.

```js
() => {
  const t = document.body.innerText;
  return { done: /Retry/.test(t), modelType: (t.match(/Model Type\s*\n\s*([^\n]+)/) || [])[1] };
}
```

## Export (다운로드)

`Export` 버튼 → 다이얼로그가 열린다. 다이얼로그 안에도 `Export` 버튼이 있으므로 **마지막 것**을 눌러야 한다.

```js
() => {
  const btns = [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Export');
  const last = btns[btns.length - 1];
  if (last) last.click();
  return { count: btns.length, clicked: !!last };
}
```

### 설정

| 항목 | 값 | 이유 |
|---|---|---|
| File Name | 단계마다 다르게 | 아래 "함정" 참고 |
| Format | `FBX` | Mixamo 애니메이션도 FBX 라 파이프라인이 단순해진다 |
| FBX 프리셋 | `Blender` | `Mixamo`/`3dsmax` 를 고르면 본 방향이 바뀌어 `BONE_MAP` 이 안 맞는다 |
| Texture Resolution | `8k` (기본) | 낮춰도 무방. 파일 크기와 처리 시간에 직결된다 |
| Export Skeleton | **ON** | 꺼져 있으면 메시만 나와서 리타게팅이 불가능하다 |

FBX 는 **ZIP 으로** 다운로드된다. `~/Downloads/<파일명>.zip` 안에 `tripo_convert_<uuid>.fbx` 와 텍스처가 든 `.fbm` 폴더가 들어 있다.

```bash
unzip -o ~/Downloads/"<파일명>.zip" -d output/robot_rigged/
mv output/robot_rigged/tripo_convert_*.fbx output/robot_rigged/robot_rigged.fbx
mv output/robot_rigged/tripo_convert_*.fbm output/robot_rigged/robot_rigged.fbm
```

`.fbm` 폴더는 FBX 와 같은 위치에 같은 이름(확장자만 다름)으로 둬야 Blender 가 텍스처를 찾는다.

### 다운로드 완료 확인

Export 는 비동기다. 크레딧이 먼저 차감되고 ZIP 은 서버에서 만들어진다. 8K + 200만 폴리곤은 **1분 이상** 걸린다.

```bash
ls -lt ~/Downloads | head -3
```

## 함정 모음

**1. Export 결과가 뒤바뀐다**
Export 를 여러 번 누르면 이전 요청의 ZIP 이 나중에 도착한다. 리깅 전 모델을 받아놓고 "리깅된 파일"로 착각하기 쉽다.
→ **단계마다 File Name 을 다르게 지정할 것**(`robot_raw`, `robot_rigged_skeleton`).
→ 받은 뒤 반드시 `inspect_rig.py` 로 아마추어 유무를 확인할 것. 아마추어가 없으면 리깅 전 파일이다.

**2. "Model count limit exceeded"**
계정 저장 한도(무료 20개)를 넘으면 생성이 거부된다. 우측 `Memory Usage` 에 `84/20` 처럼 표시된다.
→ 기존 에셋 삭제 또는 플랜 업그레이드가 필요하다. **에셋 삭제는 되돌릴 수 없으므로 반드시 사용자에게 확인받을 것.**

**3. 강제 로그인 모달**
로그인하지 않으면 워크스페이스 진입 직후 모달이 뜨고 Escape·X 로 닫히지 않는다. 로그인이 유일한 통과 방법이다.

**4. 페이지 전환 시 프롬프트가 날아간다**
로그아웃되거나 페이지가 리로드되면 입력한 프롬프트가 사라진다. 생성 직전에 값이 남아 있는지 확인할 것.

**5. Guide / 프로모션 팝업**
`Guide`, `View Your Model`, `8K Texture`, `Special Bonus` 등이 수시로 뜬다. 클릭을 가로막으므로 `OK` / `No Thanks` / `Maybe Later` 로 닫는다.
