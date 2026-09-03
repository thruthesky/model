# 씬에 3D 모델 표시하기 — 이동·애니메이션·버튼까지

**GLB 를 만든 뒤, Godot 씬에 올려 실제로 움직이는지 확인하는 전 과정.**
[godot-pipeline.md](godot-pipeline.md) 가 만든 `outputs/<NAME>/<NAME>.glb` 를 입력으로 받는다.

## 목차

- [**❓ 질문으로 찾기 — 실제로 막힌 순서 그대로**](#-질문으로-찾기--실제로-막힌-순서-그대로)
- [먼저 확인 — GLB 가 준비됐는가](#먼저-확인--glb-가-준비됐는가)
- [**GLB 는 Godot 안에서 무엇이 되는가 — 임포트 해부**](#glb-는-godot-안에서-무엇이-되는가--임포트-해부)
- [**🛑 씬 트리에 AnimationPlayer 가 보이지 않는다 — 정상이다**](#-씬-트리에-animationplayer-가-보이지-않는다--정상이다)
- [**애니메이션이 도는 원리 — 🛑 자동이 아니다**](#애니메이션이-도는-원리---자동이-아니다)
- [**🛑🛑 실측으로 드러난 함정 — play() 는 되감지 않는다**](#-실측으로-드러난-함정--play-는-되감지-않는다)
- [씬 구조](#씬-구조)
- [인스펙터 값](#인스펙터-값)
- [🛑 카메라 — 캐릭터 중심을 보게 한다](#-카메라--캐릭터-중심을-보게-한다)
- [🛑 방향키가 반대로 도는 문제](#-방향키가-반대로-도는-문제)
- [스크립트 — player_demo.gd](#스크립트--player_demogd)
- [실행하는 법 (macOS)](#실행하는-법-macos)
- [🛑 자주 겪는 문제](#-자주-겪는-문제)

---

## ❓ 질문으로 찾기 — 실제로 막힌 순서 그대로

**GLB 를 씬에 올린 사람이 실제로 던진 질문들이다.** 순서까지 그대로 두었다 —
같은 곳에서 같은 순서로 막히기 때문이다. 답의 요지만 적고, 근거는 각 절로 보낸다.

| # | 질문 | 짧은 답 |
|---|---|---|
| 1 | **캐릭터 애니메이션은 어디서 오나? 3D 모델 안에 들어 있나?** | ✅ **`.glb` 안에 들어 있다.** `idle`·`walk`·`run`·`attack`·`death` 가 파일 안의 `animations` 배열이고, Godot 이 이것을 **`AnimationPlayer` 노드 하나**로 바꾼다 → [임포트 해부](#glb-는-godot-안에서-무엇이-되는가--임포트-해부) |
| 2 | **3D 안에 있는 애니메이션이 어떻게 움직이나?** | 애니메이션은 **그림이 아니라 "뼈의 시간별 자세표"** 다. 엔진이 매 프레임 그 표를 읽어 뼈 23개에 써 넣고, **GPU 스키닝**이 피부를 뼈에 딸려 보낸다 → [같은 절](#실측--remove_immutable_tracks-가-트랙을-65-줄인다) |
| 3 | **프로그램은 화살표 키로 움직이기만 하는데 어떻게 애니가 자동으로 동작하나?** | 🛑 **자동이 아니다.** `_physics_process` 안의 `if dir.length_squared() > 0.001` 한 줄이 매 프레임 직접 고른다. 그 줄을 지우면 **차렷 자세로 미끄러져 다닌다** → [애니가 도는 원리](#애니메이션이-도는-원리---자동이-아니다) |
| 4 | **애니메이션을 플레이하면 자동으로 움직이게 되나?** | 🛑 **반대다.** 애니는 **제자리에서** 걷고, 이동은 `move_and_slide()` 가 시킨다. 실측 — `walk` 1.4초 동안 루트는 (0,0,0) 고정 → [같은 절](#-애니메이션은-캐릭터를-이동시키지-않는다--실측) |
| 5 | **씬 트리에 `AnimationPlayer`·`Skeleton3D` 가 안 보인다. Inspector 에 나와야 하는 것 아닌가?** | ✅ **정상이다.** 인스턴스된 씬은 내부가 접힌다(🎬 아이콘). **Inspector 는 자식 목록을 보여주는 곳이 아니다.** `Editable Children` 으로 편다 → [안 보이는 이유](#-씬-트리에-animationplayer-가-보이지-않는다--정상이다) |
| 6 | **펼쳤는데 애니메이션을 눈으로 어떻게 확인하나? 본은 찾았는데 애니를 못 찾겠다** | 하단 **Animation 패널**이 닫혀 있는 것이다. 가장 빠른 길은 **Inspector 첫 줄의 `Current Animation` 드롭다운** → [확인하는 5가지 경로](#애니메이션-목록을-확인하는-5가지-경로) |
| 7 | **`["RESET","attack","death","idle","run","walk"]` 이 목록은 어디서 보나?** | 화면에서 볼 수 있는 곳이 **네 군데**, 코드·터미널까지 하면 **다섯 군데**다 → [같은 절](#애니메이션-목록을-확인하는-5가지-경로) |
| 8 | **애니 패널을 열었는데 편집이 안 되고 루프도 못 켠다** | 🛑 **임포트된 애니는 에디터에서 읽기 전용이다.** 엔진이 직접 그렇게 말한다 → [읽기 전용](#-임포트된-애니는-에디터에서-읽기-전용이다) |
| 9 | **캐릭터가 지면에서 떠 있다** | GLB 원점은 **발바닥**, 캡슐 원점은 **중심**이다. GLB 인스턴스 Position 은 `(0,0,0)` → [원점 규칙](#-캐릭터가-지면에서-떠-있다--원점-규칙이-노드마다-다르다) |
| 10 | **공격 버튼 연타가 무시된다** | 🛑 **`play()` 는 같은 애니를 되감지 않는다**(4.7.2 실측). `stop()` 이나 `seek(0.0, true)` 가 필요하다 → [실측 함정](#-실측으로-드러난-함정--play-는-되감지-않는다) |

---

## 먼저 확인 — GLB 가 준비됐는가

```bash
python3 .claude/skills/model/scripts/verify_godot_glb.py \
  outputs/<NAME>/<NAME>.glb --bones 25 --kind human
```

**종료 0 이 아니면 씬을 만들지 않는다.** 특히 아래 둘이면 애니메이션이 아예 없다:

```
[FAIL] human 인데 스킨이 없다 — 리깅되지 않았다
[FAIL] 규격 애니가 없다: idle, walk, run, attack, death
```

Godot 이 임포트한 구조는 이렇게 된다 — `AnimationPlayer` 가 **루트의 직계 자식**이다:

```
<NAME>            [Node3D]
├─ Armature       [Node3D]        ⚠️ 이 중간 노드의 이름은 GLB 마다 다르다
│  └─ Skeleton3D  [Skeleton3D]       (root · Armature … Blender 오브젝트 이름이 온다)
│     └─ <mesh>   [MeshInstance3D]
└─ AnimationPlayer  ["RESET","attack","death","idle","run","walk"]
```

**왜 이런 모양이 되는지, 그리고 본 이름·트랙이 임포트되며 어떻게 바뀌는지는
아래 [임포트 해부](#glb-는-godot-안에서-무엇이-되는가--임포트-해부) 에서 실측으로 확인한다.**

---

## GLB 는 Godot 안에서 무엇이 되는가 — 임포트 해부

**"애니메이션은 어디서 오는가"** 의 답이 여기 있다.
아래 값은 전부 `outputs/exosuit.glb` 를 **Godot 4.7.2 로 실제 임포트해 찍은 것**이다.

### `.glb` 는 이미지가 아니라 **씬**이다

`.glb` 옆에 자동 생성되는 `.import` 파일의 두 줄이 전부를 설명한다.

```ini
importer="scene"                 ← 🔑 "씬 임포터" 로 처리한다
type="PackedScene"               ← 🔑 결과물이 PackedScene, 즉 씬이다
path="res://.godot/imported/exosuit.glb-<해시>.scn"

[params]
nodes/apply_root_scale=true
nodes/root_scale=1.0             ← 🛑 정규화를 했다면 반드시 1.0 (godot-pipeline.md)
animation/import=true            ← 애니메이션도 함께 가져온다
animation/fps=30                 ← 키프레임을 초당 몇 개로 굽는가
animation/remove_immutable_tracks=true   ← 아래에서 이것의 실제 효과를 잰다
meshes/generate_lods=true
skins/use_named_skins=true
```

**`type="PackedScene"` 이므로 `.glb` 는 `.tscn` 과 똑같이 인스턴싱해서 쓴다.**
씬에 드래그해 넣으면 `.tscn` 인스턴스와 완전히 같은 취급을 받는다 — 이 사실이
바로 아래 "AnimationPlayer 가 안 보인다" 문제의 원인이기도 하다.

### 실측 — 임포트되면 이런 노드 트리가 된다

```
exosuit  [Node3D]                                  ← 씬 루트 (인스턴스 이름)
├─ root  [Node3D]                                  ← ⚠️ 이름은 GLB 마다 다르다
│  └─ Skeleton3D  [Skeleton3D]  [본 23개]
│     └─ tripo_node_ddb4bdd0-…  [MeshInstance3D]
└─ AnimationPlayer  ["RESET","attack","death","idle","run","walk"]
```

| `.glb` 안의 것 | Godot 노드 |
|---|---|
| `animations` 배열 | **`AnimationPlayer` 하나** + 이름별 `Animation` 리소스 |
| `skins` 의 joints | **`Skeleton3D`** 하나 |
| `meshes` | **`MeshInstance3D`** (`Skeleton3D` 의 자식이 된다) |
| 머티리얼·텍스처 | `StandardMaterial3D` 등 |

> 🛑 **`AnimationPlayer` 는 `Skeleton3D` 의 형제가 아니다.**
> **씬 루트의 직계 자식**이고, 중간 `Node3D` 의 **형제**다.

> 🛑🛑 **중간 노드 이름이 GLB 마다 다르다.** 이 파일은 `root` 지만 다른 파일은
> `Armature` 다. Blender 의 오브젝트 이름이 그대로 넘어오기 때문이다.
> **그래서 `$exosuit/AnimationPlayer` 같은 고정 경로를 절대 쓰지 않는다** —
> 캐릭터를 교체하는 순간 경로가 조용히 깨진다.
> `player_demo.gd` 가 `_find_animation_player()` 로 **타입을 재귀 탐색**하는 이유다.

### 🛑 실측 — 본 이름의 `:` 가 `_` 로 바뀐다

**리타게팅·본 참조 코드에서 반드시 걸리는 함정이다.**

| | 이름 |
|---|---|
| `.glb` 안 (glTF 노드명) | `mixamorig:Hips` · `mixamorig:LeftUpLeg` |
| **Godot 임포트 후** (`Skeleton3D` 의 본 이름) | **`mixamorig_Hips`** · **`mixamorig_LeftUpLeg`** |

**왜 바뀌는가** — 애니메이션 트랙의 경로 형식이 이렇기 때문이다(실측).

```
root/Skeleton3D:mixamorig_Hips
└──── 노드 경로 ────┘│└─ 본 이름 ─┘
                    콜론이 구분자다
```

**`:` 는 Godot `NodePath` 에서 "여기부터는 속성 이름" 을 뜻하는 예약 문자**라
본 이름에 그대로 두면 경로가 깨진다. 그래서 임포터가 `_` 로 치환한다.

```gdscript
# 🛑 이렇게 찾으면 -1 이 나온다
var b := skel.find_bone("mixamorig:Hips")
# ✅ 임포트 후 이름으로 찾는다
var b := skel.find_bone("mixamorig_Hips")
```

### 실측 — `remove_immutable_tracks` 가 트랙을 65% 줄인다

`.import` 의 기본값이 `true` 라 **모르는 사이에 적용되고 있다.**
같은 파일을 두 설정으로 재임포트해 `idle` 의 트랙을 세어 봤다.

| `animation/remove_immutable_tracks` | `idle` 의 트랙 수 | 내역 |
|---|---|---|
| `false` | **66개** | Position 22 + Rotation 22 + Scale 22 — **glTF 채널 수 그대로** |
| **`true`** (기본값) | **23개** | **Position 1 + Rotation 22** — Scale 은 전부 사라졌다 |

**왜 이렇게 줄어드는가** — 트랙별 키 개수를 보면 답이 나온다.

```
root/Skeleton3D:mixamorig_Hips        Position  키 30개   ← 변한다 → 남는다
root/Skeleton3D:mixamorig_Hips        Rotation  키 20개   ← 변한다 → 남는다
root/Skeleton3D:mixamorig_Hips        Scale     키  1개   ← 안 변한다 → 제거
root/Skeleton3D:mixamorig_LeftUpLeg   Position  키  1개   ← 안 변한다 → 제거
root/Skeleton3D:mixamorig_LeftUpLeg   Rotation  키 28개   ← 변한다 → 남는다
```

🔑 **뼈는 회전만 한다.** 관절은 길이가 변하지 않으므로 위치·크기가 고정이고,
**골반(`Hips`) 하나만 위치가 변한다**(걸을 때의 체중 이동·상하 진동).
이 성질 덕에 트랙이 **66 → 23 으로 65% 줄어든다** — 저사양에서 그대로 이득이다.

### 실측 — 임포트 직후의 기본값들

**이 표가 `player_demo.gd` 의 `_ready()` 가 왜 그 세 줄을 쓰는지를 설명한다.**

| 항목 | 임포트 직후 값 | 뜻 |
|---|---|---|
| `Animation.loop_mode` | **`0` (`LOOP_NONE`)** — 6개 전부 | 🛑 **켜지 않으면 idle 이 2.03초 만에 얼어붙는다** |
| `AnimationPlayer.callback_mode_process` | **`1` (`..._IDLE`)** | 렌더 프레임에서 갱신 → 이동과 어긋난다 |
| `Animation.step` | **`0.0333`** (= 1/30) | `.import` 의 `animation/fps=30` 이 여기 온다 |
| `AnimationPlayer.root_node` | `..` | 트랙 경로가 이 노드 기준으로 해석된다 |

```
상수 실측값 — AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_
   PHYSICS = 0     IDLE = 1     MANUAL = 2
Animation.LOOP_NONE = 0    LOOP_LINEAR = 1    LOOP_PINGPONG = 2
```

### 실측 — 이 GLB 의 실제 수치

| 항목 | 값 |
|---|---|
| 애니메이션 길이 | `idle` 2.03초 · `walk` 1.40초 · `run` 0.63초 · `attack` 1.30초 · `death` 2.43초 · `RESET` 0.07초 |
| 본 | **23개** (`mixamorig_Hips` 부터 · `neutral_bone` 포함) |
| 정점 | 24,945 |
| 삼각형 | 20,000 |
| **정점당 참조 본 수** | **4** (GPU 스키닝의 가중치 슬롯) |
| skin 바인드 수 | 23 |
| `walk` 의 Hips Position 키 | **42개** = 1.40초 × 30fps — `animation/fps` 와 정확히 맞는다 |
| **AABB 높이** | **1.800m** — 🔑 정규화 규약(키 1.8m)이 지켜졌음의 증거 |

---

## 🛑 씬 트리에 `AnimationPlayer` 가 보이지 않는다 — 정상이다

**가장 자주 나오는 질문이다. 버그가 아니다.**

씬에 GLB 를 넣으면 Scene 독에는 이것만 보인다.

```
Player  (CharacterBody3D)
├─ CollisionShape3D
└─ exosuit          🎬   ← 펼침 화살표(▶)조차 없다
```

### 왜 접혀 있는가

이름 오른쪽의 **영화 슬레이트 아이콘(🎬)** 이 **"이 노드는 별도 씬 파일의 인스턴스"**
라는 표시다. 위에서 본 대로 `.glb` 는 `PackedScene` 이므로 **씬 인스턴스**이고,
**Godot 은 인스턴스된 씬의 내부를 기본적으로 감춘다.**

**`.glb` 만의 특성이 아니다** — 직접 만든 `.tscn` 을 인스턴싱해도 똑같이 접힌다.
내부 노드는 **그 씬 파일의 소유**이므로, 이쪽 씬에서 함부로 건드리지 못하게 막는 것이다.

> 🛑 **Inspector 에는 원래 나오지 않는다.** Inspector 는 **선택한 노드 하나의 속성**을
> 보여주는 곳이지 자식 목록을 보여주는 곳이 아니다. `exosuit` 를 고르면
> `Node3D` 의 속성(Transform · Visibility · Process …)만 나오는 것이 맞다.

### 펼쳐 보는 법 — Editable Children

```
Scene 독에서 exosuit 우클릭 → "Editable Children" (자식 편집 가능) 체크
```

```
└─ exosuit
   ├─ root
   │  └─ Skeleton3D
   │     └─ tripo_node_…       ← 여기서 머티리얼·메시를 확인할 수 있다
   └─ AnimationPlayer          ← 선택하면 하단에 애니메이션 패널이 열린다
```

### 🛑 펼쳤는데도 애니메이션이 안 보인다

**펼치는 데까지 성공한 사람이 그다음에 반드시 막히는 곳이다.**
`AnimationPlayer` 를 선택하면 Inspector 에는 `Current Animation`·`Speed Scale`·
`Root Node` 같은 **속성만** 나오고, 정작 **애니메이션 목록이 어디에도 없어 보인다.**

### 애니메이션 목록을 확인하는 5가지 경로

**`["RESET","attack","death","idle","run","walk"]` 를 실제로 보는 방법이다.**
①②③ 은 에디터, ④⑤ 는 화면에서 못 찾겠을 때의 확실한 우회로다.

#### ① 하단 **Animation** 패널 — 재생·트랙까지 본다

**"애니메이션이 없다" 는 오해의 대부분이 이 패널이 닫혀 있어서 생긴다.**
Godot 의 화면 맨 아래에는 탭 줄이 있다.

```
Output   ● Debugger   Audio   ▸ Animation ◂   Shader Editor
                              └─ 네 번째. 이것을 클릭한다
```

```
1. Scene 독에서 AnimationPlayer 를 클릭해 선택 상태로 둔다
2. 화면 맨 아래 "Animation" 탭을 클릭한다
3. 패널 왼쪽 위 드롭다운에 애니메이션 6개가 들어 있다
```

```
┌──────────────────────────────────────────────────────────┐
│ [idle ∨]  ⏮ ▶ ⏭  🔁     0.0 ──────────────── 2.03       │ ← 이 드롭다운
├──────────────────────────────────────────────────────────┤
│ root/Skeleton3D:mixamorig_Hips       ◆──◆──◆──◆──◆       │
│ root/Skeleton3D:mixamorig_LeftUpLeg  ◆────◆────◆         │ ← 트랙 23개
│ root/Skeleton3D:mixamorig_Spine      ◆──◆────◆──◆        │
└──────────────────────────────────────────────────────────┘
```

| 상황 | 대처 |
|---|---|
| 탭 줄이 안 보인다 | 뷰포트와 화면 아래 **경계선을 위로 드래그**해 패널 높이를 늘린다 |
| `Animation` 탭이 없다 | `AnimationPlayer` 를 **먼저 선택**해야 생긴다 |
| 눌렀는데 비어 있다 | 고른 것이 `Skeleton3D` 가 아니라 **`AnimationPlayer`** 가 맞는지 |

**여기 보이는 트랙 목록이 곧 "뼈의 시간별 자세표" 다.**

#### ② Inspector 맨 첫 줄 — `Current Animation` 드롭다운 (가장 빠르다)

```
Inspector
  ▣ AnimationPlayer
     Current Animation    [             ∨ ]   ← 이 빈 칸의 ∨
```

누르면 6개가 그대로 나오고, 고르면 **뷰포트의 캐릭터가 즉시 그 자세로 바뀐다.**
T-포즈가 풀리면 GLB 가 정상이라는 뜻이다. **재생은 되지 않고 정지 자세만 보인다.**

#### ③ 씬을 거치지 않고 — **Advanced Import Settings**

**GLB 파일 자체를 들여다본다.** 씬에 올리기 전에도 쓸 수 있다.

```
1. FileSystem 독에서 <NAME>.glb 를 한 번 클릭
2. Scene 독 위의 탭 중 "Import" 를 클릭
3. 패널 아래쪽 "Advanced..." 버튼      ← 엔진 확인된 라벨
4. "Advanced Import Settings for '<NAME>.glb'" 창이 열린다
5. 왼쪽 트리에서 애니메이션을 선택하면 오른쪽에 그 애니의 설정이 나온다
```

**여기서는 애니를 미리보기로 재생할 수 있고, `Loop Mode` 도 바꿀 수 있다.**
그 이유는 바로 아래 절에 있다.

#### ④ 코드로 찍는다 — 가장 확실하다

**화면에서 못 찾겠을 때 이걸 쓴다.** `_ready()` 끝에 한 줄이면 된다.

```gdscript
print("애니 목록: ", _anim.get_animation_list())
# → 애니 목록: ["RESET", "attack", "death", "idle", "run", "walk"]
```

길이·트랙 수까지 보고 싶으면:

```gdscript
for n in _anim.get_animation_list():
    var a := _anim.get_animation(n)
    print("  %-8s 길이 %.2f초  트랙 %d개  루프 %d" % [n, a.length, a.get_track_count(), a.loop_mode])
# →   RESET    길이 0.07초  트랙 23개  루프 0
#     attack   길이 1.30초  트랙 23개  루프 0
#     death    길이 2.43초  트랙 23개  루프 0
#     idle     길이 2.03초  트랙 23개  루프 0
#     run      길이 0.63초  트랙 23개  루프 0
#     walk     길이 1.40초  트랙 23개  루프 0
```

**목록이 비어 있으면 코드 문제가 아니라 GLB 문제다.** ⑤ 로 간다.

#### ⑤ 에디터 없이 — 터미널에서 파일을 연다

**Godot 을 켜지 않고 `.glb` 안을 직접 본다.** 별도 라이브러리가 필요 없다.

```bash
python3 -c "
import json,struct
f=open('outputs/<NAME>/<NAME>.glb','rb'); f.read(12)
n=struct.unpack('<I4s',f.read(8))[0]
print([a['name'] for a in json.loads(f.read(n))['animations']])"
```

```
['idle', 'walk', 'run', 'attack', 'death', 'RESET']
```

**여기에도 없으면 굽기 단계로 돌아간다** — `verify_godot_glb.py` 를 다시 돌리고,
`export_godot_glb.py` 의 NLA 분리를 확인한다. Godot 쪽에서 할 수 있는 일이 없다.

---

### 🛑 임포트된 애니는 에디터에서 읽기 전용이다

**애니 패널을 열고 트랙을 고쳐 보려다 막히는 지점이다.**
Godot 바이너리에 들어 있는 안내 문구가 그대로 설명해 준다(엔진 확인).

```
Animation is read-only.
Can't change loop mode on animation instanced from an imported scene.
To change this animation's loop mode, navigate to the scene's
Advanced Import settings and select the animation.
To modify this animation, navigate to the scene's
Advanced Import settings and select the animation.
```

**임포트로 만들어진 애니메이션은 `.glb` 에 속한 자원이라 에디터가 편집을 막는다.**
`.glb` 를 다시 구우면 덮어써질 것이므로, 에디터에서 고쳐 봐야 남지 않기 때문이다.

#### 루프를 켜는 두 가지 길 — 어느 쪽을 쓸 것인가

| | ⓐ Advanced Import Settings | ⓑ 코드 (`_ready()`) |
|---|---|---|
| 어디서 | 에디터 → Import 탭 → `Advanced...` | `player_demo.gd` |
| 저장되는가 | ✅ **`.import` 에 남는다** | 🛑 **남지 않는다.** 실행할 때마다 다시 켠다 |
| GLB 를 다시 구우면 | `.import` 는 유지된다 | 코드라 영향 없다 |
| 캐릭터가 늘어나면 | **파일마다 손으로** 해야 한다 | **코드 한 벌로 전부** 처리된다 |

**`player_demo.gd` 는 ⓑ 를 쓴다.** model 스킬이 캐릭터를 계속 구워 내는 구조라
**파일마다 에디터에서 손으로 켜는 방식은 유지되지 않기 때문**이다.

```gdscript
# ⓑ — 실행할 때마다 켠다. 임포트 설정을 건드리지 않는다.
for name in [ANIM_IDLE, ANIM_WALK, ANIM_RUN]:
    if _anim.has_animation(name):
        _anim.get_animation(name).loop_mode = Animation.LOOP_LINEAR
```

**실측 — 코드로는 정말 바뀐다.**

```
Animation 리소스 경로 : res://exosuit.glb::Animation_2o1u4
변경 전 loop_mode = 0  →  변경 후 loop_mode = 1        ✅
walk(1.40초) 를 3초간 재생 → 재생위치 0.200초, is_playing = true
                             animation_finished 신호 = []   ← 두 바퀴를 돌았다
```

🔑 **리소스 경로에 `::` 가 들어 있는 것을 눈여겨본다.** `.glb` **안에 들어 있는**
내장 리소스라는 표시이며, 그래서 **바꿔도 파일에 저장되지 않는다.**
매번 `_ready()` 에서 다시 켜야 하는 이유가 이것이다.

---

#### 그리고 — 실제 동작은 실행해야 보인다

**에디터는 `_ready()` 를 실행하지 않는다.** 위 ①②③ 은 어디까지나 **에디터가
미리보기로 자세를 씌워 주는 것**이고, `play("idle")` 이 진짜로 걸리는 것은 실행할 때다.
"에디터에서는 되는데 실행하면 T-포즈" 라면 그때는 코드 문제다(`_ready()` 의 이름 상수).

| ⚠️ Editable Children 주의 | |
|---|---|
| 켜 두면 하위 노드의 변경이 **`player_demo.tscn` 에 저장된다** | 구경만 할 거면 확인 후 **다시 끈다** |
| GLB 를 다시 구우면 저장해 둔 변경과 **충돌할 수 있다** | 에셋 수정은 Blender 로 돌아가 한다 |

### 🛑 캐릭터가 지면에서 떠 있다 — 원점 규칙이 노드마다 다르다

**실제로 나온 증상이다.** 그림자는 바닥에 있는데 발이 공중에 있다면 이것이다.

```
[node name="exosuit" parent="Player" instance=ExtResource(...)]
transform = Transform3D(1,0,0, 0,1,0, 0,0,1, 0, 0.9, 0)   ← 🛑 이 0.9 가 원인
```

**`CollisionShape3D` 를 `y=0.9` 로 올린 것을 보고 GLB 도 같이 올린 것인데, 둘은
원점 규칙이 정반대다.**

| 노드 | 원점이 어디인가 | 올바른 Position |
|---|---|---|
| `CollisionShape3D` (`CapsuleShape3D`) | **캡슐의 중심** | `(0, 0.9, 0)` — 높이 1.8 의 절반 |
| **`<NAME>` (GLB 인스턴스)** | **발바닥** (정규화 규약) | **`(0, 0, 0)`** |

**실측으로 확인할 수 있다** — 임포트된 메시의 AABB 는 `P:(x, 0.0, z)` 에서 시작해
높이가 정확히 `1.800` 이다. 즉 **원점이 발바닥이고 머리끝이 1.8m**다.

```gdscript
# 확인용 — MeshInstance3D 를 골라 인스펙터가 아니라 코드로 잰다
print(mesh_instance.get_aabb())
# → [P: (-0.800113, 0.0, -0.168727), S: (1.600226, 1.8, 0.337455)]
#                    ↑ 0 에서 시작            ↑ 높이 1.8
```

> 🔑 **실행하면 중력으로 떨어져 결국 바닥에 붙기 때문에 놓치기 쉽다.**
> 하지만 에디터에서 떠 보이고, 실행 첫 순간 0.9m 를 낙하한다.
> **`<NAME>` 의 Position 은 `(0, 0, 0)` 그대로 둔다.**

### 에디터에서 캐릭터가 T-포즈인 것도 정상이다

**에디터는 게임을 실행하지 않는다.** `_ready()` 가 돌지 않으니 `play("idle")` 도
걸리지 않고, 캐릭터는 **리깅된 기본 자세(rest pose)** 로 서 있다.
⌘R 로 실행하면 그때 idle 이 걸린다.

---

## 애니메이션이 도는 원리 — 🛑 자동이 아니다

**화살표 키를 눌렀다고 Godot 이 알아서 걷기 애니를 트는 것이 아니다.**
`player_demo.gd` 의 `_physics_process` 안에서 **이동과 애니는 완전히 분리되어 있고**,
`if` 한 줄이 둘을 잇는다.

```gdscript
func _physics_process(delta: float) -> void:
    # ── ⓐ 이동 — 애니메이션의 존재를 모른다 ────────────────────
    var input := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
    var dir := Vector3(input.x, 0.0, input.y)
    velocity.x = dir.x * speed
    velocity.z = dir.z * speed
    move_and_slide()                  # ← 캐릭터가 실제로 이동하는 것은 이 줄이다

    # ── ⓑ 애니 선택 ★ 이동과 애니를 잇는 유일한 지점 ──────────
    if _busy:
        return
    if dir.length_squared() > 0.001:
        _play(ANIM_RUN if _running else ANIM_WALK)
    else:
        _play(ANIM_IDLE)
```

> 🛑 **ⓑ 를 지우면** 캐릭터는 여전히 화살표 키로 잘 이동하지만
> **차렷 자세 그대로 미끄러져 다닌다.**
> **ⓐ 를 지우면** 제자리에서 열심히 걷기만 한다.

### 🛑 애니메이션은 캐릭터를 이동시키지 않는다 — 실측

`walk` 를 1.4초(한 바퀴) 재생하며 루트와 본을 함께 찍었다.

```
 t=0.0초   루트 (0,0,0)   Hips 본 Z = -0.0074
 t=0.2초   루트 (0,0,0)   Hips 본 Z = +0.0211
 t=0.4초   루트 (0,0,0)   Hips 본 Z = -0.0126
 t=0.8초   루트 (0,0,0)   Hips 본 Z = +0.0217
 t=1.2초   루트 (0,0,0)   Hips 본 Z = -0.0263
```

**루트는 단 1mm 도 움직이지 않고, 골반만 ±2.6cm 안에서 앞뒤로 흔들린다.**
`export_godot_glb.py` 가 walk·run 에서 root motion 을 제거해 **제자리(in-place)** 로
굽기 때문이다. 전진은 전적으로 `velocity` + `move_and_slide()` 의 몫이다.

| 무엇이 | 누가 |
|---|---|
| 공간에서 **이동** | `velocity` + `move_and_slide()` — 물리 |
| 몸을 **돌린다** | `rotation.y` — 코드 |
| **팔다리가 움직인다** | `AnimationPlayer` — 뼈만 |

### 실측 — `blend_time` 은 두 자세를 선형으로 섞는다

`blend_time = 0.6` 으로 idle → run 전환하며, 같은 시각의 **순수 idle 자세**와
**순수 run 자세** 사이 어디에 있는지 쟀다(`LeftUpLeg` 기준).

```
 t=0.00초  → run 쪽으로   0%
 t=0.15초  → run 쪽으로  18%
 t=0.30초  → run 쪽으로  45%      ← 절반 지점에서 거의 정확히 절반
 t=0.45초  → run 쪽으로  73%
 t=0.60초  → run 쪽으로 100%      ← blend_time 에 정확히 도달
```

**`blend_time` 동안 가중치가 0 → 1 로 선형 이동한다.**

| 값 | 느낌 |
|---|---|
| `0.0` | 자세가 순간이동하듯 툭 바뀐다 |
| **`0.1 ~ 0.2`** | **캐릭터 이동 전환에 적당하다** (`player_demo.gd` 기본값 0.15) |
| `0.5` 이상 | 흐물거리고 반응이 느리게 느껴진다 |

---

## 🛑🛑 실측으로 드러난 함정 — `play()` 는 되감지 않는다

**Godot 4.7.2 에서 직접 확인한 것이며, 통설과 반대다.**

### ① 같은 애니를 매 프레임 `play()` 해도 아무 문제가 없다

```
가드 없이 매 프레임 play("walk", 0.15) × 30프레임 → 재생위치 0.5000초
가드 두고 같은 0.5초 진행                          → 재생위치 0.5000초
LeftUpLeg 자세 — 두 경우가 소수점까지 완전히 동일
```

**이미 재생 중인 애니와 같은 이름이면 `play()` 는 아무 일도 하지 않는다.**
Godot 3 에서 "매 프레임 play 하면 되감겨 얼어붙는다" 던 이야기는 **4 에서는 성립하지 않는다.**

```gdscript
func _play(name: String) -> void:
    if _anim.current_animation == name:
        return                  # 재생 위치·자세에는 영향이 없다.
                                # 남겨 두는 이유는 성능과 의도의 명확성이다
    _anim.play(name, blend_time)
```

**가드는 여전히 남겨 둔다** — 매 프레임 문자열 비교와 블렌드 준비를 건너뛰고,
"같은 애니면 손대지 않는다" 는 의도가 코드에 드러나기 때문이다.
다만 **없다고 화면이 깨지지는 않는다.**

### ② 🛑 진짜 함정은 반대다 — 연타가 무시된다

```
attack 을 0.6초까지 재생한 뒤 play("attack") 다시 호출
   → 재생위치 0.600초   🛑 처음부터 다시 재생되지 않는다
```

**`player_demo.gd` 의 `_play_once()` 는 이름대로 동작하지 않는다.**
공격 버튼을 연타해도 **진행 중인 재생이 그대로 이어진다.**

**되감는 방법은 둘이고, 실측으로 확인했다.**

```gdscript
## 1회성 애니를 확실히 처음부터 재생한다.
## 🛑 play() 만으로는 되감기지 않는다 (Godot 4.7.2 실측)
func _play_once(name: String) -> void:
    if not _anim.has_animation(name):
        push_warning("애니메이션 없음: %s" % name)
        return
    _anim.stop()                       # ← 이 한 줄이 있어야 연타가 먹는다
    _anim.play(name, blend_time)
```

| 방법 | 결과 |
|---|---|
| `play()` 만 | **0.600초 — 되감기지 않음** |
| `stop()` → `play()` | **0.000초** ✅ |
| `seek(0.0, true)` | **0.000초** ✅ |

> ⚠️ `stop()` 은 블렌드의 출발 자세도 함께 지우므로 전환이 조금 더 딱딱해진다.
> 부드러움이 필요하면 `seek(0.0, true)` 쪽을 쓴다.

### ③ `animation_finished` 는 루프 애니에서 영영 오지 않는다

```
attack (루프 없음) 1.5초 진행 → 받은 신호: ["attack"]   ✅
walk   (루프)      3.0초 진행 → 받은 신호: []           🛑 두 바퀴를 돌아도 안 온다
```

**그래서 `_ready()` 에서 `attack`·`death` 를 루프 목록에 넣지 않는 것은 취향이 아니라 필수다.**
루프를 걸면 `_busy` 가 영원히 `true` 로 남아 **캐릭터가 공격 자세로 굳는다.**

### ④ 루프 없는 애니가 끝나면 마지막 자세로 멈춘다

```
death (2.43초) 를 3.3초까지 진행
   → is_playing() = false,  current_animation = ""   (빈 문자열)
   → 마지막 프레임 자세, 즉 쓰러진 채로 유지된다
```

🔑 **`current_animation` 이 빈 문자열이 되므로** `_play(ANIM_IDLE)` 의 가드가
정상적으로 통과한다 — 부활 처리가 별도 초기화 없이 동작하는 이유다.

---

## 씬 구조

```
PlayerDemo (Node3D)                    ← 루트. 🛑 여기에 스크립트를 붙이지 않는다
├─ WorldEnvironment
├─ Ground (CSGBox3D)
├─ Player (CharacterBody3D)            ← 🛑 player_demo.gd 는 **여기**
│  ├─ CollisionShape3D
│  └─ <NAME>                           ← outputs/<NAME>/<NAME>.glb 를 드래그
├─ CameraRig (Node3D)                  ← camera_rig.gd
│  └─ Camera3D
└─ UI (CanvasLayer)
   └─ Buttons (HBoxContainer)
      ├─ RunButton · AttackButton · DeathButton
```

🛑 **스크립트를 루트에 붙이면 이 오류가 난다:**

```
Script inherits from native type 'CharacterBody3D',
so it can't be assigned to an object of type: 'Node3D'
```

`player_demo.gd` 는 `extends CharacterBody3D` 라서 **`Player` 노드에만** 붙는다.

---

## 인스펙터 값

| 노드 | 속성 | 값 |
|---|---|---|
| `Ground` | Size / Position / **Use Collision** | `(20,1,20)` / `(0,-0.5,0)` / **ON** |

> 🛑 **`Ground` 의 `CSGBox3D` 는 데모 전용이다.** CSG 는 불리언 연산을 CPU 에서 하고,
> 라리엔의 **조명 굽기(SSOT §2)·드로우콜 병합(§3)** 이 둘 다 성립하지 않는다.
> 데모 씬은 빌드에 넣지 않으므로 그대로 둬도 된다.
>
> ✅ **다만 CSG 를 버릴 필요는 없다** — `bake_static_mesh()` 로 구우면 평범한
> `MeshInstance3D` 가 되어 **런타임 불리언 연산이 사라지고 오히려 빨라진다.**
> 형상은 그대로 유지된다. 출시 맵에 남기면 안 되는 것은 **CSG 노드 그대로**이지
> 그 형상이 아니다(SSOT §3.0).
| `CollisionShape3D` | Shape / Position | **CapsuleShape3D** (Height `1.8`, Radius `0.3`) / `(0, 0.9, 0)` |
| **`<NAME>` (GLB 인스턴스)** | **Position** | 🛑 **`(0, 0, 0)`** — 원점이 **발바닥**이라 올리면 뜬다 |
| `Camera3D` | **Projection** | **Orthogonal** 🛑 SSOT §1 |
| `Camera3D` | **Rotation** | `(-45, 0, 0)` 🛑 SSOT §1 |
| `Camera3D` | **Position** | **`(0, 6.9, 6)`** ← 아래 절 참조 |
| `Camera3D` | Size | `4.0` (캐릭터가 화면의 약 45%) |
| `CameraRig` | Target | **`Player`** 를 드래그 |
| `RunButton` | **Toggle Mode** | **ON** |
| `Buttons` | Anchors Preset | **Bottom Wide** |
| `Player` | Run/Attack/Death Button | 각 버튼을 드래그 |

**스크립트 붙이는 법** (Magic Mouse 는 보조 클릭이 꺼져 있을 수 있어 드래그를 권한다):
FileSystem 독에서 `.gd` 파일을 **씬 독의 노드 위로 끌어다 놓는다.**

---

## 🛑 카메라 — 캐릭터 중심을 보게 한다

`camera_rig.gd` 는 **대상의 원점**(`global_position`)을 따라간다. 그런데 정규화 규약상
캐릭터의 원점은 **발바닥**이라, 카메라를 원점에 맞추면 캐릭터가 **화면 위쪽에 치우쳐**
보인다. "카메라 위치가 이상하다" 는 대부분 이것이다.

**해결 — 카메라를 캐릭터 중심 높이만큼 올린다.**

−45° 로 캐릭터 중심 `(0, h/2, 0)` 을 보려면:

```
카메라 위치 = (0, h/2, 0) + d × (0, 0.707, 0.707)
```

키 1.8 m · 거리 8.5 기준 → `(0, 0.9 + 6, 6)` = **`(0, 6.9, 6)`**

| 캐릭터 키 | Camera3D Position | Size |
|---|---|---|
| 1.8 m (기본) | **`(0, 6.9, 6)`** | 4.0 |
| 2.16 m (`--scale 1.2`) | `(0, 7.08, 6)` | 4.8 |

🛑 **`Camera3D` 를 `Player` 의 자식으로 넣지 않는다.** 캐릭터가 회전하면 카메라도 함께
돌아 **yaw 고정(SSOT §1)이 깨진다.** 반드시 별도 `CameraRig` 로 둔다 —
`camera_rig.gd` 는 위치만 옮기고 회전은 건드리지 않도록 이미 작성돼 있다.

---

## 🛑 방향키가 반대로 도는 문제

**위 화살표를 눌렀는데 캐릭터가 뒷걸음질한다면, 코드가 아니라 모델이 원인이다.**

| | |
|---|---|
| 증상 | 이동 방향은 맞는데 **얼굴이 반대**를 향한다 |
| 원인 | 캐릭터 정면이 glTF **+Z** (Godot 표준은 **−Z**) |
| 뿌리 | Tripo3D 원본이 Blender **−Y** 정면이고, glTF 변환이 −Y → **+Z** 로 보낸다 |

**고치는 곳은 에셋이다** — [godot-pipeline.md 의 정면 규약](godot-pipeline.md) 참조.
`export_godot_glb.py` 가 **리깅·애니가 끝난 뒤** 자동으로 180° 돌린다.

🛑 **정규화(리깅 전) 단계에서 돌리면 안 된다.** ARP 가 −Y 정면을 전제하므로
뒤통수를 얼굴로 착각해 **몸통·머리 본만 반대로** 심는다 — 다리는 정상이라
"발은 맞는데 몸통이 거꾸로" 인 상태가 된다.

```bash
python3 .claude/skills/model/scripts/verify_godot_glb.py outputs/<NAME>/<NAME>.glb --bones 25 --kind human
# 통과해도 정면은 별도 확인 — 발가락 방향으로 판별한다
```

🛑 **`rotation.y += PI` 로 덮지 않는다.** 캐릭터마다 반복되고, `BoneAttachment3D` 로
붙이는 무기까지 따라 틀어진다.

### 입력 축은 이 조합이 맞다

```gdscript
var input := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
var dir := Vector3(input.x, 0.0, input.y)
```

`ui_up` 은 `input.y = -1` 이라 `dir = (0,0,-1)` = 월드 −Z = **화면 위쪽**이다.
카메라가 +Z 쪽에서 −45° 로 내려다보므로 화면 위가 −Z 다. **부호를 뒤집지 말 것** —
뒤집으면 모델의 정면 문제를 입력으로 덮는 꼴이 된다.

### 캐릭터가 이동 방향을 보게 하는 식

```gdscript
var target_yaw := atan2(-dir.x, -dir.z)
rotation.y = rotate_toward(rotation.y, target_yaw, turn_speed * delta)
```

Godot 의 정면은 −Z 다. yaw 회전 시 forward = `(-sin(yaw), 0, -cos(yaw))` 이므로
이것이 `dir` 과 같아지려면 `yaw = atan2(-dir.x, -dir.z)` 다.
검산: `dir=(0,0,-1)` → `atan2(0,1)=0` → forward `(0,0,-1)` ✅

---

## 스크립트 — `player_demo.gd`

🛑 **`Player`(CharacterBody3D)에 붙인다.**

```gdscript
## 플레이어 데모 — GLB 캐릭터의 애니메이션·이동을 한 씬에서 확인한다.
##
## 조작
##   화살표 키   — 이동. Run 이 켜져 있으면 달리기
##   Run 버튼    — 걷기/달리기 토글
##   Attack 버튼 — 공격 1회 재생 후 자동 복귀
##   Death 버튼  — 사망 재생 후 쓰러진 채 정지. 다시 누르면 부활
extends CharacterBody3D

@export var walk_speed: float = 2.0
@export var run_speed: float = 5.0

## 방향 전환 속도(rad/s). 크면 즉시 돌아 딱딱해 보인다.
@export var turn_speed: float = 12.0

## 애니메이션 전환 블렌드(초). 0 이면 툭 끊긴다.
@export var blend_time: float = 0.15

## UI 버튼 — 인스펙터에서 드래그해 연결한다.
## 🔑 get_node("../UI/...") 로 잡지 않는 이유 — 노드를 옮기면 조용히 깨진다.
@export var run_button: Button
@export var attack_button: Button
@export var death_button: Button

## 🛑 model 스킬이 굽는 규격 이름과 같아야 한다. 어긋나면 T-포즈로 서 있기만 한다.
const ANIM_IDLE := "idle"
const ANIM_WALK := "walk"
const ANIM_RUN := "run"
const ANIM_ATTACK := "attack"
const ANIM_DEATH := "death"

const GRAVITY := 9.8

var _anim: AnimationPlayer
var _running := false
var _busy := false      # attack 재생 중 — 이동 애니가 덮어쓰지 않게
var _dead := false


func _ready() -> void:
	_anim = _find_animation_player(self)
	if _anim == null:
		push_error("AnimationPlayer 를 찾지 못했다 — GLB 가 리깅되지 않았을 수 있다")
		set_physics_process(false)
		return

	# 🛑 GLB 애니메이션은 기본이 '루프 없음' 이다.
	#    이 세 줄을 빼면 idle 이 2초 재생하고 그대로 멈춰 "애니가 안 된다" 로 보인다.
	for n in [ANIM_IDLE, ANIM_WALK, ANIM_RUN]:
		if _anim.has_animation(n):
			_anim.get_animation(n).loop_mode = Animation.LOOP_LINEAR

	# 캐릭터 애니는 물리 프레임에 맞춘다 — 렌더 프레임이면 발이 미끄러진다.
	_anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	_anim.animation_finished.connect(_on_animation_finished)

	if run_button:
		run_button.toggled.connect(_on_run_toggled)
	if attack_button:
		attack_button.pressed.connect(_on_attack_pressed)
	if death_button:
		death_button.pressed.connect(_on_death_pressed)

	_play(ANIM_IDLE)


## GLB 안 어디에 있든 AnimationPlayer 를 찾는다.
## 🔑 $<NAME>/AnimationPlayer 같은 고정 경로를 쓰지 않는 이유 —
##    GLB 를 다른 캐릭터로 바꾸면 노드 이름이 달라져 코드가 깨진다.
func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for child in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null


func _physics_process(delta: float) -> void:
	if _dead:
		velocity = Vector3.ZERO
		move_and_slide()
		return

	# get_vector 는 대각선에서 속도가 √2 배가 되지 않는다.
	# ui_up 은 y = -1 이라 그대로 월드 -Z(화면 위쪽)가 된다.
	var input := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var dir := Vector3(input.x, 0.0, input.y)

	var speed := run_speed if _running else walk_speed
	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	velocity.y = 0.0 if is_on_floor() else velocity.y - GRAVITY * delta
	move_and_slide()

	# Godot 의 정면은 -Z 이므로 yaw = atan2(-x, -z).
	if dir.length_squared() > 0.001:
		var target_yaw := atan2(-dir.x, -dir.z)
		rotation.y = rotate_toward(rotation.y, target_yaw, turn_speed * delta)

	if _busy:
		return
	if dir.length_squared() > 0.001:
		_play(ANIM_RUN if _running else ANIM_WALK)
	else:
		_play(ANIM_IDLE)


## 같은 애니면 다시 걸지 않는다.
##
## 🔑 Godot 4.7.2 실측 — 이 가드가 없어도 재생 위치·자세는 달라지지 않는다.
##    (같은 이름으로 play() 를 다시 부르면 엔진이 아무 일도 하지 않는다)
##    남겨 두는 이유는 매 프레임의 낭비를 줄이고 의도를 코드에 드러내기 위해서다.
func _play(name: String) -> void:
	if _anim.current_animation == name:
		return
	if not _anim.has_animation(name):
		push_warning("애니메이션 없음: %s (있는 것: %s)" % [name, _anim.get_animation_list()])
		return
	_anim.play(name, blend_time)


## 1회성 애니 — 같은 것을 다시 눌러도 처음부터 재생되어야 한다.
##
## 🛑 play() 만으로는 되감기지 않는다 (Godot 4.7.2 실측).
##    stop() 이 없으면 공격 버튼 연타가 통째로 무시된다.
##    블렌드를 살리고 싶으면 stop() 대신 _anim.seek(0.0, true) 를 쓴다.
func _play_once(name: String) -> void:
	if not _anim.has_animation(name):
		push_warning("애니메이션 없음: %s" % name)
		return
	_anim.stop()
	_anim.play(name, blend_time)


func _on_run_toggled(pressed: bool) -> void:
	_running = pressed


func _on_attack_pressed() -> void:
	if _dead:
		return
	_busy = true
	_play_once(ANIM_ATTACK)


func _on_death_pressed() -> void:
	if _dead:
		_dead = false
		_busy = false
		_play(ANIM_IDLE)
		if death_button:
			death_button.text = "Death"
		return
	_dead = true
	_busy = true
	_play_once(ANIM_DEATH)
	if death_button:
		death_button.text = "Revive"


func _on_animation_finished(anim_name: StringName) -> void:
	if anim_name == ANIM_DEATH:
		return          # 쓰러진 채로 둔다
	if anim_name == ANIM_ATTACK:
		_busy = false
```

작성 후 검증:

```bash
python3 .claude/skills/godot/scripts/gdscript_lsp.py diagnose scenes/demo/player_demo.gd
```

---

## 실행하는 법 (macOS)

**F5·F6 이 아니다.** Godot 은 macOS 에서 실행 단축키를 재정의한다.

| 동작 | Windows·Linux | **macOS** |
|---|---|---|
| Run Project | F5 | **⌘B** |
| **Run Current Scene** | F6 | **⌘R** |
| Stop | F8 | **⌘.** |

- **마우스만으로** — 에디터 오른쪽 위 **필름 슬레이트 아이콘(🎬)** 이 "현재 씬 실행" 이다(▶ 는 메인 씬).
- **터미널에서** — 단축키·에디터와 무관하게 가장 확실하다:

```bash
godot --path . scenes/demo/player_demo.tscn
```

⚠️ **Magic Keyboard 는 F1~F12 가 기본이 미디어 키다.** F 키를 쓰려면 `fn` 을 함께 눌러야
하므로(`fn`+`F6`), Mac 에서는 위 표의 ⌘ 조합이나 터미널을 쓰는 편이 낫다.

---

## 🛑 자주 겪는 문제

| 증상 | 원인 | 고치는 곳 |
|---|---|---|
| `Script inherits from native type 'CharacterBody3D'…` | 스크립트를 **루트(Node3D)** 에 붙였다 | `Player`(CharacterBody3D)에 붙인다 |
| 인스펙터에 **`Target` 이 없다** | `CameraRig` 에 `camera_rig.gd` 를 **안 붙였다** | `@export` 는 스크립트가 만드는 속성이다 |
| **idle 이 2초 만에 멈춘다** | GLB 애니는 기본이 루프 없음 | `_ready()` 의 `loop_mode = LOOP_LINEAR` |
| **T-포즈로 서 있기만 한다** | 애니 이름이 규격이 아니거나 리깅 안 됨 | `verify_godot_glb.py` 로 확인 |
| **통째로** 뒤를 보고 걷는다 | 정면 교정을 안 했다 | `export_godot_glb.py` 가 처리(기본 켜짐) |
| **몸통만** 뒤집혔다(다리는 정상) | 정면 교정을 **리깅 전에** 했다 | 🛑 리깅부터 다시 — 순서는 리깅·애니 **후** |
| **캐릭터가 화면 위에 치우친다** | 카메라가 발바닥(원점)을 본다 | `Camera3D` Position `(0, 6.9, 6)` |
| **캐릭터가 화면 가득 / 안 보인다** | `.import` 의 `root_scale` 이 1.0 이 아니다 | Import 탭 → `Root Scale` = `1.0` → Reimport |
| **캐릭터가 돌면 카메라도 돈다** | `Camera3D` 를 `Player` 자식으로 넣었다 | 별도 `CameraRig` 로 분리(SSOT §1) |
| **버튼을 눌러도 반응 없다** | 인스펙터에 버튼을 안 넣었다 | `Player` 의 Run/Attack/Death Button 칸 |
| **애니가 하나만 나온다** | NLA 분리 안 됨 | `export_godot_glb.py` 가 처리한다 |
| **걸을 때 캐릭터가 떠오른다** | 애니에 root motion 이 남았다 | `export_godot_glb.py` 가 walk/run 에서 제거 |
| **씬 트리에 `AnimationPlayer` 가 없다** | 인스턴스된 씬은 내부가 접힌다 (정상) | `<NAME>` 우클릭 → **Editable Children** |
| **`AnimationPlayer` 를 눌러도 애니가 안 보인다** | 하단 **Animation 패널**이 닫혀 있다 | 아래 탭의 `Animation` 클릭 · Inspector 의 `Current Animation` 드롭다운 |
| **캐릭터가 지면에서 0.9m 떠 있다** | GLB 인스턴스 Position 을 `0.9` 로 올렸다 | 🛑 GLB 원점은 **발바닥** — `(0, 0, 0)` 으로 되돌린다 |
| **공격 버튼 연타가 무시된다** | `play()` 는 **같은 애니를 되감지 않는다**(4.7.2 실측) | `_play_once()` 에 `stop()` 또는 `seek(0.0, true)` |
| **공격 자세로 굳는다** | `attack` 에 루프가 걸려 `animation_finished` 가 오지 않는다 | 루프는 `idle`·`walk`·`run` 에만 건다 |
| **`find_bone("mixamorig:Hips")` 가 −1** | 임포트하며 `:` 가 `_` 로 치환된다 | `mixamorig_Hips` 로 찾는다 |
