# flutter_scene 에 스킨드 캐릭터 붙이기

Blender 파이프라인이 뽑은 `.glb` 를 Flutter 게임 화면에 **움직이는 캐릭터**로 세우는
전 과정. 검증 근거는 `flutter_scene` 0.20.0 소스(`~/.pub-cache/hosted/pub.dev/flutter_scene-0.20.0/`)를
직접 열어 확인한 것이다.

## 목차

- [핵심 개념 — 왜 이런 구조인가](#핵심-개념--왜-이런-구조인가)
- [검증된 API 사실](#검증된-api-사실)
- [조용한 실패 5가지](#조용한-실패-5가지)
- [핵심 소스코드 — 엔진 계층(sengine)](#핵심-소스코드--엔진-계층sengine)
- [핵심 소스코드 — 게임 계층](#핵심-소스코드--게임-계층)
- [검증 방법](#검증-방법)

## 핵심 개념 — 왜 이런 구조인가

### 1. `.glb` 를 런타임에 읽는다 — 빌드 훅은 쓰지 않는다

`flutter_scene` 0.20.0 은 **두 경로**를 준다:

| 경로 | 진입점 | 사전 준비 |
|---|---|---|
| 런타임 GLB | `Node.fromGlbAsset(path)` | `pubspec.yaml` 의 `flutter: assets:` 등록만 |
| 빌드 훅 | `loadScene(path)` → `.fsceneb` | `hook/build.dart` + `hooks`·`data_assets` 의존성 + `flutter config --enable-dart-data-assets` |

**캐릭터가 한둘이면 런타임 경로를 쓴다.** 빌드 훅은 소스가 스스로
*"currently experimental"* 이라고 적어 두었고(`lib/src/importer/build_hooks.dart`), 설정
비용이 크다. 빌드 훅의 유일한 실익은 **스킨드 메시의 컬링 바운드**(`skinned_pose_union_aabb`)인데,
이는 화면 밖 캐릭터가 많을 때만 의미가 있다.

> ⚠️ 구버전 기억에 주의. **`Node.fromAsset` 과 `.model` 포맷은 0.20.0 에 없다.**
> `.model` 은 CHANGELOG 에서 BREAKING 으로 제거됐다. 실제 API 는
> `fromGlbAsset` / `fromGlbBytes` / `fromGltfBytes` 셋이다.

### 2. PC 노드를 3단으로 나눈다 — 이것이 가장 밟기 쉬운 지뢰

임포터가 돌려주는 root 의 `localTransform` 에는 **glTF 우수좌표계를 뒤집는 Z-flip 이
들어 있다**:

```dart
// lib/src/runtime_importer/runtime_importer.dart
final root = Node(
  name: 'root',
  localTransform: Matrix4.identity()..setEntry(2, 2, -1.0),
)..excludeFromWindingParity = true;
```

여기에 이동 행렬을 대입하면 그 보정이 지워져 **캐릭터가 좌우 반전되고 컬 와인딩까지
어긋난다.** 그래서 계층을 셋으로 나눈다:

```text
앵커 노드      ← 매 프레임 이동만 (localTransform = translation)
└ 보정 노드    ← 배율·바라보는 방향·발 높이 (게임이 정한다)
  └ 모델 root  ← 임포터가 만든 것. 절대 건드리지 않는다
```

배율·회전을 앵커에 섞으면 **다음 프레임에 이동 행렬이 통째로 덮어써 지워진다.** 그래서
중간 노드가 따로 필요하다.

### 3. 재사용 코드는 배럴을 둘로 나눈다

게임 엔진 레이어(이 프로젝트에서는 `lib/sengine`)에 캐릭터 코드를 올릴 때, **GPU 를
요구하는 것과 아닌 것을 같은 배럴에 넣으면 안 된다.**

`Scene()` 과 `Node.fromGlbAsset` 은 Flutter GPU 컨텍스트를 요구해 `flutter test` 에서
만들 수 없다. 순수 로직과 같은 배럴에 두면 **순수 경로를 import 하는 것만으로 GPU
타입이 딸려 들어와 위젯 테스트가 깨진다.**

| 배럴 | 내용 | 테스트 |
|---|---|---|
| `sengine.dart` | 속도→상태 판정, 가중치 전환 | `flutter test` |
| `sengine_scene.dart` | GLB 로더, 클립 바인딩, 머티리얼 변환 | `integration_test` |

**게임 고유의 값은 전부 주입받는다** — 클립 이름 문자열(`'idle'`), 에셋 경로, 배율.
엔진 코드에 그 문자열이 하나라도 있으면 다른 게임에 못 가져간다.

## 검증된 API 사실

전부 0.20.0 소스에서 직접 확인한 것이다.

| 사실 | 근거 |
|---|---|
| `Node.fromGlbAsset(String)` / `fromGlbBytes(Uint8List)` 로 런타임 로딩 | `node.dart:554,559` — 주석 *"No offline conversion is required"* |
| `Skin` 은 임포터가 자동 부착 — 직접 만들지 않는다 | `runtime_importer.dart:146-161` — `engineNodes[i].skin = skins[skinIdx]` |
| 애니메이션은 **합성 root** 에 붙는다 | `runtime_importer.dart:190-192` — `root.addParsedAnimation(...)` |
| `AnimationPlayer` 는 `createAnimationClip` 이 지연 생성 | `node.dart:535` — `_animationPlayer ??= AnimationPlayer()` |
| 재생 진행은 **자동** — `clip.advance()` 를 직접 부르면 프레임당 두 번 진행 | `node.dart:936` — `scenePrePass` 안에서 `_animationPlayer?.update(dt)` |
| 클립은 `playing = false` 로 생성 → `play()` 필요 | `animation_clip.dart:55,71` |
| 정점당 본 영향은 **정확히 4개** — `JOINTS_1` 은 읽지 않는다 | `primitive_packer.dart:112-114` |
| **삼각형만** 지원 — 다른 토폴로지는 프리미티브째 스킵 | `runtime_importer.dart:94` — `if (p.mode != 4) null` |
| 총 본 수 상한 없음 — 조인트 텍스처가 `nextPow2(ceil(sqrt(joints*4)))` 로 동적 | `skin.dart:74-81` (41본 → 16×16) |
| 스킨드 지오메트리에는 **컬링 바운드가 없다**(항상 그린다) | `geometry.dart:512-519` 주석 |
| 스킨드는 **인스턴싱·depth-only 변형이 없다** | `geometry.dart` — `UnskinnedGeometry` 만 오버라이드 |
| 광원이 없어도 PBR 이 조명된다 — 기본 `EnvironmentMap.studio()` | `scene.dart:394-400`, `material.dart:148-150` |
| 머티리얼 교체 가능 — `MeshPrimitive.material` 은 non-final | `mesh.dart:25`, `node.dart:411-417`(`meshNodes` 문서가 *"swap materials"* 를 명시) |

### 정확한 호출 순서

```dart
await Scene.initializeStaticResources();          // 셰이더·기본 머티리얼
final root = await Node.fromGlbAsset(assetPath);  // 합성 root (Z-flip 포함)
final anim = root.findAnimationByName('walk');    // ⚠️ 정확히 일치해야 찾는다
final clip = root.createAnimationClip(anim!)
  ..loop = true
  ..weight = 0
  ..play();
anchorNode.add(root);                             // root 를 자식으로만 붙인다
```

`Scene()` 생성자도 `initializeStaticResources()` 를 시작하지만 **기다려 주지 않는다**
(`scene.dart:118`). 로드 전에 명시적으로 await 하는 편이 안전하다.

## 조용한 실패 5가지

전부 예외를 던지지 않는다. "로드는 됐는데 이상하다" 로만 나타난다.

| # | 증상 | 원인 | 방어 |
|---|---|---|---|
| 1 | 캐릭터가 **좌우 반전** | 임포트 root 의 `localTransform` 을 덮어씀 | 3단 계층 (앵커에만 이동) |
| 2 | **클립이 0개** | 애니메이션 이름 불일치 (`Armature\|Armature\|idle`) | `postprocess_glb.py` 가 접두사 제거 · `inspect_glb.py` 로 검증 |
| 3 | 캐릭터가 **두 배로 이동** | 클립에 root motion 잔존 | `postprocess_glb.py` 의 `strip_root_motion` |
| 4 | 메시가 **미묘하게 찌그러짐** | 정점당 본 영향 5개 이상 → `JOINTS_1` 무시 | Blender `export_influence_nb=4`, `export_all_influences=False` · `inspect_glb.py` |
| 5 | 정지 포즈가 **계속 섞임** | `stop()` 만 하고 `weight` 를 안 내림 | 비활성 클립은 `weight = 0` |

> **#5 를 오해하지 말 것.** `weight = 0` 이면 블렌드에서 완전히 빠진다
> (`animation_player.dart:99-109` 의 `totalWeight` 합산에 0 은 기여하지 않는다). 그리고
> `playing = false` 면 시간도 흐르지 않는다(`animation_clip.dart:117` — `if (!playing …) return`).
> 진짜 함정은 반대다 — **블렌드 루프는 `playing` 을 보지 않으므로**, 멈춘 클립이라도
> `weight > 0` 이면 그 정지 포즈가 계속 섞인다.

## 핵심 소스코드 — 엔진 계층(sengine)

아래 네 파일이 재사용 단위다. 게임 고유의 문자열이 하나도 없다.

### `character/locomotion.dart` — 속도 → 상태 (순수)

**핵심 로직**: 임계값 하나로 판정하면 속도가 그 근처에서 떨릴 때 상태가 초당 수십 번
뒤집힌다(애니메이션이 덜덜 떤다). **올라갈 때와 내려올 때의 문턱을 다르게** 둔다.

```dart
enum LocomotionState { idle, walk, run }

class LocomotionThresholds {
  const LocomotionThresholds({
    this.walk = 0.2,
    this.run = 2.5,
    this.hysteresis = 0.6,
  }) : assert(walk > 0),
       assert(run > walk),
       assert(hysteresis > 0 && hysteresis <= 1);

  final double walk;        // 이 속도를 넘으면 걷기
  final double run;         // 이 속도를 넘으면 달리기
  final double hysteresis;  // 내려올 때의 문턱 비율(0.6 = 진입 문턱의 60%)
}

LocomotionState locomotionFor(
  double speed, {
  required LocomotionState previous,
  LocomotionThresholds thresholds = const LocomotionThresholds(),
}) {
  final v = speed.abs();
  final walkExit = thresholds.walk * thresholds.hysteresis;
  final runExit = thresholds.run * thresholds.hysteresis;

  return switch (previous) {
    LocomotionState.run =>
      v < walkExit
          ? LocomotionState.idle
          : (v < runExit ? LocomotionState.walk : LocomotionState.run),
    LocomotionState.walk =>
      v >= thresholds.run
          ? LocomotionState.run
          : (v < walkExit ? LocomotionState.idle : LocomotionState.walk),
    LocomotionState.idle =>
      v >= thresholds.run
          ? LocomotionState.run
          : (v >= thresholds.walk ? LocomotionState.walk : LocomotionState.idle),
  };
}
```

### `character/cross_fade.dart` — 가중치 교차 전환 (순수)

**핵심 로직**: 동작 전환은 클립을 갈아 끼우는 것이 아니라 **한쪽 가중치를 내리면서
다른 쪽을 올리는** 일이다. 전환 중 두 상태의 합이 **정확히 1** 이어야 엔진의 정규화가
개입하지 않는다(합이 1 을 넘으면 두 동작이 함께 옅어져 캐릭터가 흐물거린다).

```dart
class CrossFade<S> {
  CrossFade(S initial, {this.duration = 0.18})
    : assert(duration > 0),
      _current = initial,
      _previous = initial,
      _progress = 1.0;

  final double duration;
  S _current;
  S _previous;
  double _progress;

  S get current => _current;
  bool get isSettled => _progress >= 1.0;

  /// 전환 도중에 또 바뀌면 그 시점의 [current] 가 새 출발점이 된다.
  /// 중간 가중치는 버려지므로 세 클립이 동시에 섞이지 않는다.
  void to(S next) {
    if (next == _current) return;
    _previous = _current;
    _current = next;
    _progress = 0.0;
  }

  void advance(double dt) {
    if (dt <= 0 || _progress >= 1.0) return;
    _progress = (_progress + dt / duration).clamp(0.0, 1.0);
  }

  double weightOf(S state) {
    if (isSettled) return state == _current ? 1.0 : 0.0;
    if (state == _current) return _progress;
    if (state == _previous) return 1.0 - _progress;
    return 0.0;
  }

  /// 보간을 생략하고 즉시 확정(검증 스크린샷·순간이동용).
  void snapTo(S state) {
    _current = state;
    _previous = state;
    _progress = 1.0;
  }
}
```

### `scene/animated_model.dart` — GLB 로딩 + 클립 (GPU)

**핵심 로직**: 클립을 **전부 `weight = 0` 으로 재생 중** 상태로 만들어 둔다. 가중치가
0 이면 화면에 영향이 없고, 올리는 즉시 이어서 움직인다.

```dart
import 'package:flutter_scene/scene.dart';

class AnimatedModel<S> {
  AnimatedModel._(this.root, this._clips, this._missing);

  /// ⚠️ `localTransform` 을 대입하지 말 것 — Z-flip 보정이 들어 있다.
  final Node root;
  final Map<S, AnimationClip> _clips;
  final List<S> _missing;

  /// GLB 에 없어서 만들지 못한 상태들. 비어 있지 않으면 에셋과 코드가 어긋난 것.
  List<S> get missingStates => List.unmodifiable(_missing);

  /// GLB 가 실제로 갖고 있는 애니메이션 이름들(진단용).
  final List<String> availableAnimations = [];

  static Future<AnimatedModel<S>> load<S>({
    required String assetPath,
    required Map<S, String> clipNames,
    bool loop = true,
  }) async {
    await Scene.initializeStaticResources();
    final root = await Node.fromGlbAsset(assetPath);

    final clips = <S, AnimationClip>{};
    final missing = <S>[];
    for (final entry in clipNames.entries) {
      final animation = root.findAnimationByName(entry.value);
      if (animation == null) {
        missing.add(entry.key);
        continue;
      }
      clips[entry.key] = root.createAnimationClip(animation)
        ..loop = loop
        ..weight = 0
        ..play();
    }

    final model = AnimatedModel<S>._(root, clips, missing);
    model.availableAnimations.addAll(root.parsedAnimations.map((a) => a.name));
    return model;
  }

  /// 매 프레임 부른다. **재생 진행은 여기서 하지 않는다** — Scene 이 한다.
  void applyWeights(double Function(S state) weightOf) {
    for (final entry in _clips.entries) {
      entry.value.weight = weightOf(entry.key);
    }
  }

  AnimationClip? clipFor(S state) => _clips[state];
  int get clipCount => _clips.length;
}
```

### `scene/unlit_conversion.dart` — PBR → Unlit (GPU, 선택)

**언제 쓰나**: glTF 머티리얼은 `KHR_materials_unlit` 확장이 없으면
`PhysicallyBasedMaterial` 로 들어온다. 광원이 없어도 기본 IBL 로 조명되므로 **검게
보이지는 않는다.** 이 함수가 필요한 경우는 **씬의 나머지가 `UnlitMaterial` 일 때
셰이딩을 통일**하려는 것이다(캐릭터에만 음영이 지면 따로 논다).

```dart
int convertToUnlit(Node root) {
  var converted = 0;
  for (final node in root.meshNodes) {
    final mesh = node.mesh;
    if (mesh == null) continue;
    for (final primitive in mesh.primitives) {
      final source = primitive.material;
      if (source is UnlitMaterial) continue;

      final unlit = UnlitMaterial();
      if (source is PhysicallyBasedMaterial) {
        unlit
          ..baseColorFactor = source.baseColorFactor
          ..baseColorTexture = source.baseColorTexture
          ..doubleSided = source.doubleSided;
      }
      primitive.material = unlit;
      converted++;
    }
  }
  return converted;
}
```

노멀맵·거칠기·금속성·오클루전은 unlit 에 대응이 없으므로 **버린다.** 되돌리려면 모델을
다시 불러온다.

## 핵심 소스코드 — 게임 계층

### 노드 계층 구성 (동기 생성자 + 비동기 로딩)

씬 생성자는 보통 동기인데 `fromGlbAsset` 은 `Future` 다. **앵커와 임시 표시를 먼저
세우고, 모델이 도착하면 자식만 교체한다.** 실패해도 임시 표시를 지우지 않는다 — 에셋이
없다고 캐릭터가 사라지면 조작이 불가능해지고 원인도 화면만 보고는 알 수 없다.

```dart
// ── 생성자에서 (동기) ──
_pcAnchor = Node(name: 'pc', localTransform: Matrix4.translation(_renderPos));
_pcPresentation = Node(name: 'pc_presentation');
_pcPlaceholder = Node(
  name: 'pc_placeholder',
  localTransform: Matrix4.translation(Vector3(0, 0.26, 0)),  // 구체는 중심이 원점
  mesh: Mesh(IcosphereGeometry(radius: 0.26), UnlitMaterial()),
);
_pcPresentation.add(_pcPlaceholder!);
_pcAnchor.add(_pcPresentation);
scene.add(_pcAnchor);

// ── 배율·방향은 보정 노드에만 (앵커에 섞으면 다음 프레임에 지워진다) ──
void _applyPresentation() {
  _pcPresentation.localTransform = Matrix4.rotationY(_facing)
    ..scaleByDouble(modelScale, modelScale, modelScale, 1);
}

// ── 비동기 로딩 ──
Future<bool> loadPcModel() async {
  if (_pcModel != null) return true;
  try {
    final model = await AnimatedModel.load<LocomotionState>(
      assetPath: pcModelAsset,
      clipNames: pcClipNames,       // { idle: 'idle', walk: 'walk', run: 'run' }
    );
    convertToUnlit(model.root);     // 씬이 unlit 이면
    _pcModel = model;
    _pcPlaceholder?.visible = false;
    _pcPresentation.add(model.root);
    _motion.snapTo(LocomotionState.idle);
    model.applyWeights(_motion.weightOf);
    return true;
  } catch (error, stack) {
    _pcModelError = '$error';       // 진단용으로 남긴다
    _pcModelErrorStack = stack;
    return false;                   // 임시 표시는 그대로 둔다
  }
}
```

### 매 프레임 — 속도로 동작을 고르고 이동 방향으로 몸을 돌린다

**핵심 로직**: 속도는 논리 좌표가 아니라 **렌더 위치의 변화량**에서 얻는다. 격자 좌표는
칸 단위로 순간이동하므로 "지금 얼마나 빨리 가고 있나" 를 말해주지 않는다. 화면 위치의
변화율이 곧 눈에 보이는 속도이고, 애니메이션은 눈에 보이는 것과 맞아야 한다.

이 구조는 **서버 권위로 바뀌어도 그대로다** — 그때는 목표점이 서버가 확정한 위치가 되고,
여기서는 여전히 그 위치를 향한 보간의 변화율만 본다. 동작 선택은 판정이 아니라 **연출**이다.

```dart
void advance(double dt) {
  final previous = _renderPos;
  _renderPos = Vector3(
    expDamp(_renderPos.x, goal.x, followLambda, dt),
    expDamp(_renderPos.y, goal.y, followLambda, dt),
    expDamp(_renderPos.z, goal.z, followLambda, dt),
  );
  _pcAnchor.localTransform = Matrix4.translation(_renderPos);

  final delta = _renderPos - previous;
  final planar = math.sqrt(delta.x * delta.x + delta.z * delta.z);
  final speed = dt > 0 ? planar / dt : 0.0;

  _motion.to(locomotionFor(speed, previous: _motion.current));
  _motion.advance(dt);
  _pcModel?.applyWeights(_motion.weightOf);

  // 임계값이 없으면 멈춰 있을 때 부동소수점 찌꺼기로 몸이 미세하게 떤다.
  if (planar > 1e-4) {
    final goalFacing = math.atan2(delta.x, delta.z);
    _facing = expDampAngle(_facing, goalFacing, turnLambda, dt);
  }
  _applyPresentation();
}
```

### 게임이 정하는 상수 — 엔진에 넣지 않는다

```dart
static const String pcModelAsset = 'assets/models/pc_astronaut.glb';

/// ⚠️ **정확히 일치해야 한다** — findAnimationByName 은 부분 일치를 하지 않는다.
static const Map<LocomotionState, String> pcClipNames = {
  LocomotionState.idle: 'idle',
  LocomotionState.walk: 'walk',
  LocomotionState.run: 'run',
};

/// 모델 원본 키(GLB bounds 로 실측) 대비 배율. 스크린샷을 보고 정한다.
static const double pcModelScale = 0.8;

/// 발이 놓이는 높이. 캐릭터는 발이 로컬 원점이므로 **지면 높이 그대로**다.
/// ⚠️ 구체를 쓰던 시절의 반지름 보정값을 그대로 두면 캐릭터가 공중에 뜬다.
static const double _pcHeight = 0.04;   // 타일 두께 0.08 의 윗면
```

### `pubspec.yaml`

```yaml
flutter:
  assets:
    - assets/models/
```

원본(리깅 FBX·애니메이션·중간 산출물)은 앱 번들에 넣지 않는다. 등록하는 것은
**파이프라인의 최종 산출물뿐**이다.

## 검증 방법

### 3층으로 나눈다

| 층 | 무엇을 | 어디서 |
|---|---|---|
| 순수 | 속도→상태 판정(히스테리시스), 전환 가중치 합, 실패 경로 | `flutter test` |
| 결선 | GLB 가 실제로 임포트되고 클립이 재생되는가 | `integration_test` (Impeller 필요) |
| 체감 | 반전 여부·크기·발 높이 | 실기 + 스크린샷 — **사람이 본다** |

### 자기검증 항목 (실기)

앱 진입점에 심어 로그로 확인한다. **성공 경로와 실패 경로를 모두** 본다:

```dart
check('PC 모델 로드', world.hasPcModel, world.pcModelError ?? '');
check('동작 클립', world.pcClipCount == pcClipNames.length,
    '(${world.pcClipCount}/${pcClipNames.length} · GLB: ${world.pcAvailableAnimations})');
check('빠진 동작 없음', world.pcMissingClips.isEmpty, '(${world.pcMissingClips})');

// 멀리 보내면 걷거나 뛰어야 하고, 도착해 멈추면 정지로 돌아와야 한다.
// 후자를 확인하지 않으면 "영원히 걷는 캐릭터" 를 통과시킨다.
world.movePcTo(far.x, far.z);
for (var i = 0; i < 6; i++) world.advance(1 / 60);
check('이동 중 동작 전환', world.pcMotionState != LocomotionState.idle);

for (var i = 0; i < 240; i++) world.advance(1 / 60);
check('정지 시 idle 복귀', world.pcMotionState == LocomotionState.idle);
```

### 스크린샷을 찍기 전에 카메라를 당긴다

⚠️ **이것이 없으면 검증 스크린샷이 쓸모없다**(실측). 기본 카메라 거리에서는 캐릭터가
수십 픽셀짜리 점이라, 모델이 제대로 섰는지·좌우가 뒤집히지 않았는지·크기가 타일과
맞는지를 눈으로 판별할 수 없다. 자기검증 끝에 줌인을 넣어 두고, 그 상태로 남긴다.

### 통합 테스트의 함정

`SceneView(autoTick: false)` 면 애니메이션도 진행하지 않는다. 스크린샷 검증 시 클립이
첫 프레임 포즈에 멈춰 있을 수 있으므로 명시적으로 프레임을 돌려야 한다.
