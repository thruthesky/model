# 씬에 3D 모델 표시하기 — 이동·애니메이션·버튼까지

**GLB 를 만든 뒤, Godot 씬에 올려 실제로 움직이는지 확인하는 전 과정.**
[godot-pipeline.md](godot-pipeline.md) 가 만든 `outputs/<NAME>/<NAME>.glb` 를 입력으로 받는다.

## 목차

- [먼저 확인 — GLB 가 준비됐는가](#먼저-확인--glb-가-준비됐는가)
- [씬 구조](#씬-구조)
- [인스펙터 값](#인스펙터-값)
- [🛑 카메라 — 캐릭터 중심을 보게 한다](#-카메라--캐릭터-중심을-보게-한다)
- [🛑 방향키가 반대로 도는 문제](#-방향키가-반대로-도는-문제)
- [스크립트 — player_demo.gd](#스크립트--player_demogd)
- [실행하는 법 (macOS)](#실행하는-법-macos)
- [🛑 자주 겪는 문제](#-자주-겪는-문제)

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
├─ Armature       [Node3D]
│  └─ Skeleton3D  [Skeleton3D]
│     └─ <mesh>   [MeshInstance3D]
└─ AnimationPlayer  ["RESET","attack","death","idle","run","walk"]
```

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
| `CollisionShape3D` | Shape / Position | **CapsuleShape3D** (Height `1.8`, Radius `0.3`) / `(0, 0.9, 0)` |
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


## 같은 애니면 다시 걸지 않는다 — 매 프레임 play() 하면 되감겨 멈춘 것처럼 보인다.
func _play(name: String) -> void:
	if _anim.current_animation == name:
		return
	if not _anim.has_animation(name):
		push_warning("애니메이션 없음: %s (있는 것: %s)" % [name, _anim.get_animation_list()])
		return
	_anim.play(name, blend_time)


## 1회성 애니는 같은 것을 다시 눌러도 처음부터 재생되어야 한다.
func _play_once(name: String) -> void:
	if not _anim.has_animation(name):
		push_warning("애니메이션 없음: %s" % name)
		return
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
