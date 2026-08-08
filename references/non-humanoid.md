# 동물형(비인간형) 몬스터 — 거미 · 지네 · 고질라 · 네발 짐승

> **이 문서는 [SKILL.md](../SKILL.md) 의 humanoid 경로를 *대체* 한다.** 사람 모양이 아닌
> 액터는 ④(ARP Smart)·⑤(Mixamo 본 rename)·⑦(Mixamo 리타게팅)을 **탈 수 없다.**
> 제0원칙(AAA 급 · 원시 도형 금지)은 여기서도 그대로 적용된다.

## 왜 별도 경로인가 — 두 개의 벽

| | humanoid 경로 | 동물형에서 무슨 일이 나나 |
|---|---|---|
| ④ ARP **Smart** | 메시에서 사람 몸을 자동 감지해 마커를 놓는다 | **사람 몸이 없다.** 다리 6개·8개, 팔 없음, 척추가 수평 → 감지 자체가 성립하지 않는다 |
| ⑤~⑦ **Mixamo 애니** | `mixamorig:*` 65본에 idle/walk/run/attack/death 를 붙인다 | **거미 걸음이라는 원본이 세상에 없다.** Mixamo 는 2족 인간형만 제공한다. 리타게팅할 소스가 없으니 리타게팅이라는 개념이 성립하지 않는다 |

그래서 동물형은 **리깅을 ARP 의 다른 기능으로 하고, 애니메이션을 계산해서 만든다.**

## 표준 규격 〔원저자 2026-08-08〕

| 항목 | 값 | 왜 |
|---|---|---|
| 방향 | **8방향** | 다족은 실루엣이 방사대칭이라 16방향을 줘도 구분이 잘 안 된다. 절반이면 디스크·RAM 도 절반 |
| 행동 | **idle · walk · attack · death** (4종) | `run` 은 굽지 않는다 — `MOB_ACTIONS` 와 같다 |
| cell | **128px** | pc/mob 과 같은 축. 화면 표시도 128 이라 1:1(축소 렌더 없음) |
| 저장 위치 | **`outputs/mob/<name>/`** | `--output ./outputs` → `sheet.py` 가 `<output>/<kind>/<name>/` 로 넣는다. `/sprite-preview:start` 가 그대로 집어 준다 |

```bash
--kind mob --directions 8 --output ./outputs
```

🛑 **`--kind boss`(cell 256) 로 굽지 말 것** — 표준은 128 이다. 보스급으로 크게 쓸 것이
확실할 때만 `boss` 를 고르고, 그때는 사람에게 먼저 확인한다. 실측: 같은 거미가
boss(256) 는 PNG 2.0MB, mob 8방향(128) 은 **660KB**.

🛑 **게임 번들(`assets/`)로 바로 굽지 않는다.** `--output ./outputs` 를 빼면 `pubspec.yaml`
이 자동 갱신되어 앱에 들어간다. 동물형은 아직 후보 단계이므로 **작업 폴더에만** 둔다.

---

## 전체 흐름

```
① Tripo3D 생성(리깅 없이 다운로드)      ← SKILL.md ①~③ 과 같다. T-Pose 토글은 끈다
② 다리 분포 실측                        measure_legs.py · preview_ortho.py
③ ARP `free` + add_limb 리깅            rig_animal_arp.py
④ 애니메이션 4종 계산 생성              anim_animal.py
⑤ 베이크 + 정리                         bake_actor_actions.py
⑥ 8방향 4행동 아틀라스                  sheet.py --kind mob --directions 8
⑦ 검증(몽타주 + /sprite-preview)
```

### ① Tripo3D 생성 — humanoid 와 다른 점만

- 🛑 **`T-Pose` 토글을 켜지 않는다.** 그것은 *팔을 수평으로 펴라* 는 사람용 지시다.
  동물형에 걸면 형상이 무너진다.
- 🛑 **다리를 모으라고 쓰지 않는다.** SKILL.md ②의 `legs together` 는 2족 전용이다.
  거미·지네는 **다리가 벌어진 것이 정상**이고, 오히려 **다리끼리 붙어 있으면 리깅이 안 된다**
  (다리를 서로 구분할 수 없다).
- **다리가 서로 떨어져 보이게** 쓴다. 이것이 이 경로의 유일한 형상 요구다:

```
A menacing mechanical spider monster, full body, eight long segmented legs spread
evenly and symmetrically around a central armored body, each leg clearly separated
from the others and from the body with visible gaps, standing on the ground in a
neutral wide stance, a missile launcher pod and a cannon barrel mounted on top of
its head, armored carapace, glowing red eyes, sci-fi military robot, symmetrical,
clean topology, game-ready
```

필수 요소: `each leg clearly separated … with visible gaps` · `spread evenly and
symmetrically` · `standing on the ground` · `symmetrical` · `game-ready`.

⚠️ **다리 개수는 프롬프트대로 나오지 않는다.** 실측(2026-08-08): `eight legs` 를 명시했는데
**6다리**가 나왔다. 파이프라인은 다리 개수를 **모델에서 세므로** 그대로 진행해도 되지만,
개수가 중요하면 위에서 본 렌더로 세어 보고 재생성 여부를 사람에게 묻는다(크레딧 55~65).

### ② 다리 분포 실측 — 추정하지 않는다

```bash
blender --background --python .claude/skills/model/scripts/measure_legs.py -- <모델.fbx>
blender --background --python .claude/skills/model/scripts/preview_ortho.py -- <모델.fbx> outputs/<name>/diag
```

`measure_legs.py` 는 z 층별 퍼짐과 **발끝 클러스터**를 출력한다. `preview_ortho.py` 는
위·앞·옆 정사영을 굽는다 — **위에서 본 그림으로 다리 개수를 눈으로 센다.**

### ③ ARP 리깅 — `free` 프리셋 + `add_limb`

```bash
blender --background --python .claude/skills/model/scripts/rig_animal_arp.py -- \
  <모델.fbx> <출력>_rig.blend --legs auto
```

ARP Smart 대신 **빈 아마추어에 다리를 하나씩 붙인다**:

```
arp.append_arp(rig_preset='free')     # 빈 ARP 아마추어(사람 몸 전제가 없다)
arp.add_limb(limbs_presets='spine')   # 몸통
arp.add_limb(limbs_presets='leg.l')   # 좌 N개  → thigh_ref.l · thigh_ref_dupli_001.l …
arp.add_limb(limbs_presets='leg.r')   # 우 N개
→ reference bone 을 실측 다리 축으로 이동 → arp.match_to_rig() → arp.bind_to_rig()
```

**다리 검출은 발끝 XY 클러스터링**이다. 방위각 히스토그램은 쓰지 않는다 — 다리 간격이
균등하지 않아 8개 중 6개만 잡혔다(실측). 발은 서로 떨어져 있으므로 지면 근처 정점을 묶으면
**다리 개수 자체를 데이터가 알려 준다**.

옵션: `--legs auto|N` · `--foot-z 0.10`(발끝으로 볼 높이) · `--foot-sep 0.22`(발 구분 간격)
· `--body-ratio 0.42`(몸통 반경) — 검출이 어긋날 때만 조정한다.

**통과 기준**: `place_refs … missing=0` · `match_to_rig ok=True` · `bind_to_rig ok=True`
· `verify_bind vertex_groups>0 armature_modifier=True`.

### ④ 애니메이션 — Mixamo 가 없으니 계산해서 만든다

```bash
blender --background <_rig.blend> \
  --python .claude/skills/model/scripts/anim_animal.py -- <출력>.blend
```

**삼각보행(tripod gait)** — 다리를 방위각 순으로 정렬해 번갈아 두 조로 나눈다. 어느 순간에도
서로 이웃하지 않는 다리들이 지면을 딛고 있어 몸이 넘어지지 않는다. **다리가 6개든 8개든
같은 규칙으로 성립한다.**

조작 대상은 **IK 발 컨트롤러(`c_foot_ik*`)** 다. 발만 옮기면 무릎·허벅지는 IK 가 접어 주므로
관절 각도를 지어내지 않아도 된다.

| 행동 | 무엇을 하나 |
|---|---|
| `idle` | 몸통이 오르내리고 발이 번갈아 조금씩 들린다(접지 유지) |
| `walk` | 두 조가 반주기 어긋나게 접지/스윙 + 몸통이 걸음에 맞춰 상하·좌우로 흔들린다 |
| `attack` | 웅크렸다가 앞으로 튀어나가며 앞다리를 들어 내려찍는다 |
| `death` | 다리가 바깥으로 풀리며 몸이 주저앉고 옆으로 기운다(끝에 경련) |

🛑 **발 위치는 `pose_bone.location` 이 아니라 `pose_bone.matrix` 로 준다** — 방사형 리그는
본마다 로컬 축이 제각각이라 `location` 에 같은 값을 넣으면 다리마다 엉뚱한 방향으로 간다.

🛑 **진폭은 과장한다.** 128px 셀로 축소되면 사실적인 크기의 움직임은 보이지 않는다.
실측으로 보폭 `SPAN×0.30 → 0.52`, 들어올림 `0.16 → 0.34` 로 올린 뒤에야 걸음이 눈에 띄었다.

### ⑤ 베이크 + 정리 — 굽기 전 반드시

```bash
blender --background <애니.blend> \
  --python .claude/skills/model/scripts/bake_actor_actions.py -- <출력>_baked.blend
```

ARP 리그는 IK·제약·컨트롤러 위젯이 얽힌 **저작용** 리그다. 그대로 `sheet.py` 에 넘기면
렌더가 죽는다. 이 단계가 하는 일 여섯:

1. **액션 베이크**(visual keying) — IK 결과를 본 로컬 변환으로 굳힌다
2. **제약 전부 제거** — 🛑 베이크가 *전부 끝난 뒤* 지운다. 첫 액션에서 지우면 나머지가
   다리 없는 포즈로 구워진다
3. 컨트롤러 위젯 메시(`cs_*`) 제거
4. ARP 씬 커스텀 프로퍼티 제거 — 남으면 ARP 핸들러가 GUI 전용 값을 찾다 죽는다
5. **텍스처 경로 복구** — Tripo ZIP 을 `<NAME>_raw.fbm` 으로 rename 하면 blend 안 경로가
   깨져 **마젠타 스프라이트**가 나온다(실측). 파일명이 같으면 실제 위치를 찾아 다시 연결
6. **`head` 본 추가** — 아래 참조

🛑 **`head` 본이 왜 필요한가**: `_sheet_render.py` 는 head 본이 없으면 mesh bbox 로 폴백해
**"높이 < 폭×0.7 이면 누운 것"** 으로 판정한다. 거미처럼 **넓적한 것이 정상**인 액터는 이
규칙에 걸려 통째로 90° 눕혀진다(실측: hz=1.32 < max(2.00,1.41)×0.7=1.40). `head` 본을
**발 평균 바로 위**에 세우면 발→머리 벡터가 수직이라 `캐릭터 서있음(보정 불필요)` 로 끝난다.
x·y 를 0 으로 두면 발 평균이 치우친 만큼 기운다(실측 15°).

### ⑥ 아틀라스 — 8방향 4행동 128

```bash
python3 .claude/skills/texture-packer/scripts/sheet.py \
  ./game-assets/characters/mob/<name>/<name>_baked.blend \
  --kind mob --directions 8 --name <name> \
  --animations built-in --output ./outputs --auto
```

- `--kind mob` → cell 128 · 표시 128 · 행동 `idle/walk/attack/death`(run 없음)
- `--directions 8` → `KIND_POLICY` 의 16 을 덮어쓴다
- `--animations built-in` → **필수**. 빼면 `animations/default` 의 **사람 애니**를 집어
  거미에 사람 걸음을 씌우려다 정적 프레임이 된다
- `--output ./outputs` → `outputs/mob/<name>/` 에 저장, `pubspec.yaml` 손대지 않음

**리그가 Mixamo 가 아니어도 통과하는 이유**: `sheet.py` 는 입력이 `.blend` 면
`assert_mixamo_rig()` 를 건너뛰고, `built-in` 이면 액션을 **이름으로** 매칭한다. 그래서
액션 이름을 `idle`/`walk`/`attack`/`death` 로 지어 두는 것이 계약의 전부다.

### ⑦ 검증 — 눈으로 본다

```bash
python3 .claude/skills/texture-packer/scripts/verify_cells.py --frames outputs/<name>/frames
/sprite-preview:start        # 8방향이 동시에 같은 프레임으로 움직인다
```

- 렌더 로그에 `####ANIM <행동> ← '<액션>'` **4줄**, `####WARN … 정적` **0줄**
- `INFO 캐릭터 서있음(보정 불필요)` — `누움 감지` 가 나오면 `head` 본이 빠진 것이다
- `cell 잘림 검사 … 잘림 없음`
- **몽타주로 4행동이 서로 다른 포즈인지** · **8방향이 실제로 도는지** · **색이 살아 있는지**

---

## 실측 기준값 — 거미 1체 (2026-08-08)

| | 값 |
|---|---|
| Tripo 생성 | 55 크레딧 · 약 4분 · 186만 페이스(리깅 전 4만으로 Decimate) |
| 검출된 다리 | 6개(프롬프트는 8) · 발끝 클러스터로 자동 검출 |
| 리그 | deform 본 117 · vertex group 117 · 제약 358(베이크 후 제거) |
| 아틀라스 | 8방향 × 44프레임 = **352장** · page 3082×1052 · **660KB**(256색) |
| 소요 | 리깅 40초 · 애니 20초 · 베이크 90초 · 굽기 39초 |

## 자주 겪는 문제

| 증상 | 원인·대처 |
|---|---|
| 스프라이트가 **마젠타·회색** | 텍스처 경로가 깨졌다. ⑤ 가 복구한다. 로그의 `텍스처 복구 fixed=[…] missing=[]` 확인 |
| 액터가 **옆으로 누워** 구워짐 | `head` 본 없음 → bbox 폴백이 "넓적하니 누웠다" 로 오판(⑤-6) |
| 액터가 **몇 도 기울어** 구워짐 | `head` 본의 x·y 가 발 평균과 어긋났다. 발 평균 바로 위에 세운다 |
| 4행동이 **전부 같은 포즈** | `--animations built-in` 을 빠뜨렸거나 액션 이름이 `idle/walk/attack/death` 가 아니다 |
| 움직임이 **거의 안 보인다** | 진폭이 작다. 128 셀로 줄면 사실적 크기는 안 보인다 — ④의 과장 지침 |
| 다리 검출 **0개** | 절대 정점 수로 거르면 Decimate 후 전멸한다. `rig_animal_arp.py` 는 최대 클러스터 대비 상대 임계를 쓴다. 그래도 안 되면 `--foot-z`·`--foot-sep` 조정 |
| 다리를 **6/8 만** 찾음 | 방위각 히스토그램의 한계다(폐기됨). 현재 스크립트는 발끝 클러스터링을 쓴다 |
| `bpy.ops.arp.append_arp … could not be found` | `read_factory_settings()` 가 ARP 확장까지 껐다. 씬 오브젝트만 지울 것 |
| `'NoneType' object has no attribute 'overlay'` | ARP 가 3D 뷰를 만진다. `rig_animal_arp.py` 가 그 두 줄만 no-op 으로 패치해 **창 없이** 돈다 |
| `select_all.poll() failed` | background 에서 area 컨텍스트가 없다. 데이터 API(`select_set`)로 대체 |
| `'Action' object has no attribute 'fcurves'` | Blender 4.4+ slotted action. `layers→strips→channelbags` 로 내려간다 |
| `KeyError: key must be a string … not NoneType` | `sheet.py` 가 Hips 없는 리그에서 죽던 버그. texture-packer `3a4eb14` 에서 수정됨 |

## 다른 동물형으로 확장할 때

스크립트는 **다리 개수·배치에 의존하지 않는다**(발끝을 세고, 방위각으로 정렬해 교대 배정).
지네·네발 짐승도 같은 명령으로 돈다. 다만 형상에 따라 확인할 것:

| 형태 | 주의 |
|---|---|
| **지네**(다리 다수·몸통이 길다) | 다리가 촘촘해 `--foot-sep` 를 낮춰야 붙은 발이 갈라진다. 몸통이 길면 `spine` limb 을 여러 개 붙이는 편이 자연스럽다 |
| **고질라형**(2족 직립·꼬리) | 다리는 2개뿐이라 삼각보행이 성립하지 않는다 — `walk` 를 좌우 교대(2조)로 두고, 꼬리는 `add_limb('tail')` 로 붙인다 |
| **네발 짐승** | 대각선 두 쌍(좌앞+우뒤 / 우앞+좌뒤)이 자연스럽다. 방위각 교대 배정이 우연히 이 짝을 만들어 주지만 **걸음을 눈으로 확인**할 것 |
| **날개·촉수** | 지면 접지가 없어 발끝 클러스터링이 안 먹는다. `--legs` 로 개수를 강제하거나 별도 배치가 필요하다 |

🛑 **새 형태를 처음 굽고 나면 이 문서에 실측값을 남긴다.** 추정으로 쓰면 다음 사람이
그대로 믿고 틀린다.
