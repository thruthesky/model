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

✅ **정면축 불일치는 2026-08-09 에 해소됐다**(라몬 작업 중 수정). 종전에는 리깅이 정면을
−Y 로 잡는데 애니메이션만 +Y 로 전진시켜 **몸이 향한 반대로 걷고 뒷다리로 내려찍었다.**
거미는 방사대칭이라 안 보였을 뿐, 앞뒤가 분명한 액터에서는 그대로 드러나는 결함이었다.

지금은 **리깅이 정하고 애니메이션이 읽는 단방향**이라 어긋날 수 없다:

| 파일 | 역할 |
|---|---|
| `rig_animal_arp.py` | `FRONT_Y = -1.0` 상수로 spine 을 배치하고, **같은 값을 리그 오브젝트의 `laryen_front_y` 커스텀 프로퍼티에 기록**한다(이 값의 유일한 출처) |
| `anim_animal.py` | `rig.get("laryen_front_y")` 로 **읽기만** 한다. walk 전진·attack 앞다리 선택·돌진·숙임이 모두 이 값을 따른다 |

- 🛑 **`anim_animal.py` 에 축을 직접 써넣지 말 것** — 그 순간 두 파일이 다시 갈릴 수 있다.
- 구 리그(이 프로퍼티가 없는 `.blend`)는 **+Y 로 폴백**해 종전 동작을 유지한다. 그래서
  기존 거미(`spider_cannon`)를 재생성해도 결과가 달라지지 않는다 — 다만 **리깅부터 다시
  하면** 새 규칙(−Y)이 적용되므로, 이미 승인된 액터는 굳이 재리깅하지 않는다.
- 검증: 리깅 로그의 `[STEP] front_axis front_y=-1.0` 과 애니 로그의 `[INFO] front_y=-1` 이
  같은지 본다(라몬 실측에서 둘 다 −1 로 일치).

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

## ⑧ 게임에 실제로 등록하기 — 🛑 **아틀라스를 구웠다고 끝이 아니다**

⑦까지는 *스프라이트를 만든 것* 이고, 게임에 몬스터로 나오게 하려면 **7곳을 더 고쳐야 한다.**
이 목록이 없어서 "구웠는데 왜 안 나오죠?" 가 반복된다(cowork animal-model-perf-sfx 지적).

| # | 파일 | 무엇을 |
|---|---|---|
| 1 | `game-assets/characters/mob/<name>/` | 3D 원본·아틀라스를 여기 두고, 아틀라스를 `assets/mob/<name>/` 로 복사 |
| 2 | `pubspec.yaml` | `assets/mob/<name>/` 2줄(`.png`·`.atlas`) — 빠지면 **번들에 안 들어가 투명** |
| 3 | 서버 `monster/archetype.go` | `ArchXxx = <다음번호>` + `String()` case + **`ArchLast` 갱신** |
| 4 | 서버 `config/config.go` | `ArchetypeOrder` 배열 **크기와 항목** 둘 다 |
| 5 | 서버 `config/monsters.config.yaml` | archetype 스탯 + `zoneSpawns` 배치(🛑 zone 이름은 `*_sub_zone`) |
| 6 | 클라 `render/data/archetype.dart` | `ArchetypeKind` 에 추가 → **컴파일러가 exhaustive switch 를 전부 잡아준다**(사거리·색·wireName·짧은이름) |
| 7 | 클라 `render/iso_hunt_world.dart` · `audio/audio_manifest.dart` | sprite loader 2곳(보스/일반) + **오디오 폴더 매핑** |

🛑 **번호는 서버와 클라가 1:1 이어야 한다** — SNAP 은 archetype 을 1바이트로 보내고 클라는
enum 인덱스로 되돌린다. 순서가 어긋나면 **엉뚱한 몬스터로 그려진다**.

✅ **다행히 대부분은 컴파일러가 잡아준다** — 6번 enum 에 하나 추가하면 클라의 exhaustive
switch 가 전부 에러를 내므로 빠뜨릴 수 없다(실측: 7곳이 한 번에 잡혔다).

🔊 **오디오는 컴파일러가 못 잡는 것이 하나 있다** — 폴더 매핑(`_mobFolder`)은 exhaustive 라
잡히지만, **그 폴더에 파일이 실제로 있는지**는 `audio_manifest_paths_test` 가 잡는다.
신규 자산은 **`.ogg`(Vorbis)** 여야 하고(`_mobExt` 에 case 추가), 🚫 **OGG/Opus 는 SoLoud 가
못 읽어 무음**이다. 파일이 없으면 `attack`/`hit`/`death` 4개가 전부 무음이 된다.

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

| 형태 | 지금 되나 | 주의 |
|---|---|---|
| **지네**(다리 다수·몸통이 길다) | ✅ 된다 | 다리가 촘촘해 `--foot-sep` 를 낮춰야 붙은 발이 갈라진다. 몸통이 길면 `spine` limb 을 여러 개 붙이는 편이 자연스럽다 |
| **네발 짐승** | ✅ 된다 | 대각선 두 쌍(좌앞+우뒤 / 우앞+좌뒤)이 자연스럽다. 방위각 교대 배정이 우연히 이 짝을 만들어 주지만 **걸음을 눈으로 확인**할 것 |
| **고질라형**(2족 직립·꼬리) | 🛑 **아직 안 된다** | 아래 참조 |
| **비행체**(드론·호버 유닛) | ✅ **된다 — 단 전용 경로다** | 다리가 없어 이 문서의 ③④ 를 쓸 수 없다. **아래 §비행체 참조** |
| **날개·촉수**(지면에 안 닿는 다족) | 🛑 **아직 안 된다** | 지면 접지가 없어 발끝 클러스터링이 안 먹는다. `--legs` 로 개수를 강제해도 IK 발 컨트롤러가 없어 `anim_animal.py` 가 멈춘다. 비행체처럼 몸통만 리깅하는 쪽이 현실적이다 |

### 🛑 2족(고질라)·꼬리는 현재 **미지원** 이다 — 문서만 믿고 시도하지 말 것

이 표는 원래 "고질라는 walk 를 좌우 교대로 두고 꼬리는 `add_limb('tail')` 로 붙인다" 고
적혀 있었다. **그 두 가지 모두 스크립트에 없다**(cowork animal-model-perf-sfx 에서 3개 AI 가
지적, 코드로 확정):

```python
anim_animal.py:64
if len(legs) < 4:
    print(f"[FAIL] IK 발 컨트롤러를 {len(legs)}개만 찾았습니다")
    sys.exit(1)          # ← 2족은 여기서 즉시 종료된다
```

- **2족**: 위 가드가 `sys.exit(1)` 로 막는다. 삼각보행이 3개 이상 접지를 전제하기 때문이다.
- **꼬리**: `rig_animal_arp.py` 는 `spine`·`leg.l`·`leg.r` 만 추가한다. ARP 자체는
  `add_limb('tail')` 을 지원하지만 **스크립트가 부르지 않는다.**

**하려면 무엇이 필요한가**(다음 사람이 착수할 때의 실제 작업 목록):

1. `anim_animal.py` — 다리 2개용 **좌우 교대 보행** 분기 추가(삼각보행은 ≥4 유지)
2. `rig_animal_arp.py` — `arp.add_limb(limbs_presets='tail')` + 꼬리 축 실측 배치
3. 꼬리 흔들림을 `idle`/`walk` 에 넣기(2족은 꼬리로 균형을 잡는 실루엣이 핵심이다)

**지금은 2족을 인간형 경로**([SKILL.md](../SKILL.md))로 보내는 편이 낫다 — Mixamo 애니가
붙는다면 그쪽이 훨씬 빠르다. 다만 고질라처럼 사람 모션이 어울리지 않는 괴수는 위 3개를
구현하기 전까지 **만들 수 없다**고 사람에게 알린다.

🛑 **새 형태를 처음 굽고 나면 이 문서에 실측값을 남긴다.** 추정으로 쓰면 다음 사람이
그대로 믿고 틀린다.

---

# 비행체(드론·호버 유닛) — 다리가 없는 액터 〔2026-08-10 신설〕

**다족형(위 ①~⑦)도 탈 수 없다.** 이 문서의 리깅·애니메이션이 전부 *발* 을 전제하기 때문이다:

| 단계 | 무엇을 전제하나 | 드론에서 |
|---|---|---|
| ② `measure_legs.py` · ③ `rig_animal_arp.py` | **지면에 닿는 발끝**을 클러스터링해 다리를 센다 | 떠 있어 접지점이 없다 → 발끝 0개로 `fail()` |
| ④ `anim_animal.py` | IK 발 컨트롤러 **4개 이상**(삼각보행) | `len(legs) < 4` 가드에 걸려 `sys.exit(1)` |

## 전용 경로 — 몸통 하나 + 무기 본 하나

```
① Tripo3D 생성(T-Pose 끔)  → ② rig_drone_arp.py  → ③ anim_drone.py
   → ④ bake_actor_actions.py → ⑤ sheet.py --kind mob --directions 8
```

```bash
D=game-assets/characters/mob/<name>
blender --background --python .claude/skills/model/scripts/rig_drone_arp.py -- $D/<name>_raw.fbx $D/<name>_rig.blend
blender --background $D/<name>_rig.blend  --python .claude/skills/model/scripts/anim_drone.py       -- $D/<name>_anim.blend
blender --background $D/<name>_anim.blend --python .claude/skills/model/scripts/bake_actor_actions.py -- $D/<name>_baked.blend
python3 .claude/skills/texture-packer/scripts/sheet.py $D/<name>_baked.blend \
  --kind mob --directions 8 --name <name> --animations built-in --output ./outputs --auto
```

- **리깅**: ARP `free` + `add_limb('spine')` **하나뿐**이다. 실제 비행체는 관절이 없는
  **강체** 라 이것이 물리적으로도 옳다. 다리 검출 코드가 통째로 없다.
- **무기 본**: `bind_to_rig()` **뒤에** `weapon` deform 본과 vertex group 을 직접 만든다.
  🛑 bind 전에 넣으면 `match_to_rig` 가 ARP 관리 본만 남기며 지운다. 무기 정점은 "정면 쪽
  깊이 30% × 높이 하위 55%" 로 실측 검출한다(`--weapon-front`·`--weapon-z` 로 조정).
  이 본이 없으면 발사가 "기체가 흔들리는 것" 으로만 보이고 **쏘는 것으로 읽히지 않는다.**
- **정면축 자동 판정**: 하부에서 y 로 더 튀어나온 쪽(=무기가 달린 쪽)을 앞으로 본다.
  값은 `laryen_front_y` 로 리그에 기록되고 `anim_drone.py` 가 **읽기만** 한다(다족과 같은 규칙).

## 🛑 넓적한 액터가 90° 눕는 함정 — `foot_ground` 본

`_sheet_render.py` 의 `_upright_by_bones` 는 head 와 **foot 본을 둘 다** 찾지 못하면 곧바로
mesh bbox 폴백으로 떨어지고, 그 폴백은 **"높이 < 폭×0.7 이면 누운 것"** 으로 판정한다.
드론처럼 **넓적한 것이 정상**인 기체는 여기 그대로 걸린다(실측: 높이 0.80 <
max(1.60, 1.43)×0.7 = 1.12 → 눕혀짐).

그래서 `bake_actor_actions.py` 가 **발 본이 하나도 없을 때만** 지면에 `foot_ground` 더미
본을 세운다(이름에 `foot` 이 들어가야 `FOOT_KEYWORDS` 에 잡힌다). 발이 이미 있는 액터
(사람·거미)는 이 분기를 타지 않으므로 기존 결과가 달라지지 않는다.
통과 신호는 렌더 로그의 **`INFO 캐릭터 서있음(보정 불필요)`** 이다.

## 애니메이션 4종 — 보행이 아니라 비행의 문법

| 행동 | 무엇을 하나 |
|---|---|
| `idle` | 제자리 부양. **가만히 있어도 계속 흔들리는 것**이 비행체의 '정지' 다(어긋난 두 주기로 기계적 반복감 제거) |
| `walk` | 기수를 숙여(`lean`) 그 방향으로 떠간다 + 상하 부유·좌우 롤 |
| `attack` | 조준(기수 들기) → **연사 반동**(발마다 `exp(-t)` 감쇠로 기체가 젖혀지고 포신이 후퇴) → 복귀 |
| `death` | 양력 상실 → 기울며 스핀 하강 → 지면 충돌 튕김 → 처박힘 |

🛑 **진폭은 크게 과장한다.** 실측(2026-08-10 `drone`): 처음 잡은 값
(호버 `SPAN×0.055`, 반동 `0.085`)은 128px 셀에서 **완전한 정지 화면**으로 보였다.
호버 `0.14`·반동 `0.17`·walk 롤 `0.24` 로 **약 2.5배** 올린 뒤에야 움직임이 읽혔다.
거미가 보폭을 0.30→0.52 로 올린 것과 같은 이유이며, 비행체는 접지 변화가 없어 **더 크게**
줘야 한다.

🛑 **`anim_drone.py` 의 크기 계산에서 ARP 컨트롤러 위젯(`cs_*`)을 반드시 뺀다** — 위젯은
리그를 감싸도록 크게 퍼져 있어, 섞어 재면 실제 1.60 인 기체가 **5.24** 로 나와 모든 진폭이
3.3배 과장된다(실측). 판정은 이름이 아니라 **armature modifier 유무**가 우선이다.

## 실측 기준값 — 드론 1체 (2026-08-10)

| | 값 |
|---|---|
| Tripo 생성 | 55 크레딧 · 약 4분 · 198만 페이스(리깅 전 4만으로 Decimate) |
| 리깅 | 24초 · deform 본 3 + `weapon` · 무기 정점 7,262 |
| 애니 · 베이크 | 각 1초 남짓(다족과 달리 IK 가 없어 훨씬 가볍다) |
| 아틀라스 | 8방향 × 44프레임 = **352장** · page 2100×1044 · **598KB**(256색) |
| 굽기 | 32~47초(auto-fit 재렌더 포함) · action scale `walk 0.92 · death 0.74` |
