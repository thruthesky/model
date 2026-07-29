# Mixamo → Tripo 리타게팅 상세

`scripts/retarget.py` 의 동작 원리, 본 매핑표, 핵심 코드, 문제 해결. 이 문서만으로 스크립트를 재구현할 수 있어야 한다.

## 목차

- [핵심 개념 — 왜 이름 치환으로는 안 되는가](#핵심-개념--왜-이름-치환으로는-안-되는가)
- [핵심 로직 — 월드 공간 회전 델타](#핵심-로직--월드-공간-회전-델타)
- [본 매핑표](#본-매핑표)
- [핵심 소스코드](#핵심-소스코드)
- [Blender 5.x API 주의점](#blender-5x-api-주의점)
- [알려진 한계](#알려진-한계)
- [문제 해결](#문제-해결)

## 핵심 개념 — 왜 이름 치환으로는 안 되는가

두 리그의 실측값이다.

| | Mixamo (`./default/*.fbx`) | Tripo v1.0 Humanoid |
|---|---|---|
| 본 개수 | 65 | 41 |
| 이름 | `mixamorig:Hips`, `mixamorig:LeftArm` | `Hip`, `L_Upperarm` |
| 루트 | `mixamorig:Hips` | `Root` → `Hip` |
| 단위 | cm (오브젝트 스케일 0.01) | m (스케일 1.0) |
| 본 데이터 축 | Y-up (`Hips.head = (0, 105.2, 0)`) | Z-up (`Hip.head = (0, -0.019, 0.505)`) |
| 힙 높이 | 105.2 (로컬) | 0.505 |
| 손가락 본 | 있음 (30개) | **없음** |

본 이름을 바꿔치기하면 회전값이 그대로 복사되는데, 두 리그의 **rest 자세에서의 본 로컬 축이 다르다**. 같은 쿼터니언이 서로 다른 축 기준으로 해석되어 팔다리가 뒤틀린다.

## 핵심 로직 — 월드 공간 회전 델타

rest 자세(양쪽 모두 T-포즈)를 기준점으로 삼아 **상대 회전**만 옮긴다.

```
delta        = (소스 본의 포즈 월드행렬) × (소스 본의 rest 월드행렬)⁻¹
타겟 회전     = delta.to_quaternion() × (타겟 본 rest 월드 회전)
```

`delta` 는 "rest 에서 얼마나 돌았는가"이므로 본 길이·축 방향과 무관하다. 이를 타겟의 rest 회전에 곱하면 타겟 리그의 축 체계로 자연스럽게 옮겨진다.

세 가지 부수 규칙이 필요하다.

**1. 위치는 Hip 만 옮긴다.** 나머지 본의 위치는 부모 포즈로 결정된다. 위치까지 강제하면 본이 부모에서 분리된다.

**2. 부모 → 자식 순서로 처리한다.** 자식의 현재 월드 위치는 부모 포즈에 의존한다. 계층 깊이순으로 정렬하고, 본 하나를 설정할 때마다 `view_layer.update()` 로 의존성 그래프를 갱신한다.

**3. Hip 이동량은 스케일 보정한다.** `scale = 타겟 힙높이 / 소스 힙높이`. 이 값을 곱하지 않으면 cm 단위 이동이 m 단위 캐릭터에 적용되어 화면 밖으로 날아간다.

## 본 매핑표

Tripo v1.0 Humanoid 기준. 22쌍.

| Mixamo | Tripo | 비고 |
|---|---|---|
| `mixamorig:Hips` | `Hip` | 위치 + 회전 |
| `mixamorig:Spine` | `Waist` | |
| `mixamorig:Spine1` | `Spine01` | |
| `mixamorig:Spine2` | `Spine02` | |
| `mixamorig:Neck` | `NeckTwist01` | |
| `mixamorig:Head` | `Head` | |
| `mixamorig:LeftShoulder` | `L_Clavicle` | |
| `mixamorig:LeftArm` | `L_Upperarm` | |
| `mixamorig:LeftForeArm` | `L_Forearm` | |
| `mixamorig:LeftHand` | `L_Hand` | |
| `mixamorig:LeftUpLeg` | `L_Thigh` | |
| `mixamorig:LeftLeg` | `L_Calf` | |
| `mixamorig:LeftFoot` | `L_Foot` | |
| `mixamorig:LeftToeBase` | `L_ToeBase` | |
| (Right 6종) | (R_ 접두사로 동일) | |

**매핑하지 않는 본**

- `Pelvis` — Tripo 에만 있다. 다리의 부모라서 회전을 주면 이중 적용된다.
- `NeckTwist02` — 목 보조 본.
- `*Twist01/02` (`L_ForearmTwist01` 등 12개) — Mixamo 에 대응 본이 없다. 억지로 매핑하면 팔이 뒤틀린다. rest 상태로 두면 부모를 따라가 자연스럽다.
- Mixamo 손가락 본 30개 — Tripo 에 대응 본이 없다.

Tripo 계층 구조:

```
Root > Hip > Pelvis > L_Thigh > L_Calf > L_Foot > L_ToeBase
           > Waist > Spine01 > Spine02 > NeckTwist01 > NeckTwist02 > Head
                                       > L_Clavicle > L_Upperarm > L_Forearm > L_Hand
```

## 핵심 소스코드

프레임 루프의 본체다. 전체는 `scripts/retarget.py` 참조.

```python
def world_rest(arm, bone_name):
    return arm.matrix_world @ arm.data.bones[bone_name].matrix_local

def world_pose(arm, bone_name):
    return arm.matrix_world @ arm.pose.bones[bone_name].matrix

# 힙 높이 비율로 이동량 스케일을 맞춘다
scale = world_rest(tgt_arm, "Hip").to_translation().z / \
        world_rest(src_arm, "mixamorig:Hips").to_translation().z

for frame in range(f_start, f_end + 1):
    bpy.context.scene.frame_set(frame)

    for sname, tname in pairs:              # pairs 는 계층 깊이순 정렬
        src_pose_w = world_pose(src_arm, sname)
        delta_q = (src_pose_w @ src_rest_cache[sname].inverted()).to_quaternion()
        target_q = delta_q @ rest_cache[tname].to_quaternion()

        pb = tgt_arm.pose.bones[tname]

        if tname == ROOT_TGT:               # Hip 만 위치를 옮긴다
            offset = src_pose_w.to_translation() - src_rest_cache[sname].to_translation()
            loc_w = rest_cache[tname].to_translation() + offset * scale
        else:                               # 나머지는 부모가 정한 현재 위치를 유지
            bpy.context.view_layer.update()
            loc_w = (tgt_arm.matrix_world @ pb.matrix).to_translation()

        new_w = Matrix.Translation(loc_w) @ target_q.to_matrix().to_4x4()
        pb.matrix = tgt_world_inv @ new_w
        bpy.context.view_layer.update()     # 자식이 갱신된 부모를 보게 한다

    for _, tname in pairs:
        tgt_arm.pose.bones[tname].keyframe_insert("rotation_quaternion", frame=frame)
        if tname == ROOT_TGT:
            tgt_arm.pose.bones[tname].keyframe_insert("location", frame=frame)
```

계층 정렬:

```python
def ordered_targets(tgt_arm, pairs):
    depth = {}
    for _, tname in pairs:
        b, d = tgt_arm.data.bones[tname], 0
        p = b.parent
        while p:
            d += 1
            p = p.parent
        depth[tname] = d
    return sorted(pairs, key=lambda p: depth[p[1]])
```

FBX 내보내기 — 모든 액션을 별도 AnimStack 으로 저장하는 옵션이 핵심이다:

```python
bpy.ops.export_scene.fbx(
    filepath=fbx_out,
    use_selection=True,
    add_leaf_bones=False,
    bake_anim=True,
    bake_anim_use_all_actions=True,    # 이게 없으면 액션 하나만 나간다
    bake_anim_use_nla_strips=False,
    path_mode="COPY",
    embed_textures=True,
    mesh_smooth_type="FACE",
)
```

## Blender 5.x API 주의점

Blender 4.4 부터 액션이 슬롯 구조로 바뀌었다. 구버전 코드는 예외를 던진다.

**`action.fcurves` 가 없다:**

```python
def count_fcurves(action):
    if hasattr(action, "fcurves"):          # 4.3 이하
        return len(action.fcurves)
    total = 0                                # 4.4+
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                bag = strip.channelbag(slot)
                if bag:
                    total += len(bag.fcurves)
    return total
```

**액션 할당 시 슬롯까지 연결해야 한다:**

```python
def assign_action(obj, action):
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = action
    if not hasattr(obj.animation_data, "action_slot"):
        return                               # 구버전이면 여기서 끝
    slot = action.slots[0] if len(action.slots) else None
    if slot is None:
        try:
            slot = action.slots.new(id_type="OBJECT", name=obj.name)
        except (TypeError, RuntimeError):
            slot = None
    if slot is not None:
        obj.animation_data.action_slot = slot
```

**`NlaStrips.new(name, start, action)` 의 `start` 는 int 여야 한다.** `strip.frame_end` 는 float 를 반환하므로 다음 스트립 시작 위치를 계산할 때 `int()` 로 감쌀 것.

## 알려진 한계

**손가락이 움직이지 않는다.** Tripo 리그에 손가락 본이 없다. Mixamo 의 주먹 쥐기·손가락 동작은 손목 회전만 남아 `run`·`hit` 에서 손 모양이 어색하다. 손가락이 필요하면 Mixamo 오토리깅을 쓰거나 Blender 에서 본을 추가해야 한다.

**폴리곤이 매우 많다.** Tripo 출력은 약 200만 페이스다. 게임 엔진에 넣으려면 Tripo `Retopo` 또는 Blender Decimate 로 줄여야 한다.

**처리 시간.** 본 하나를 설정할 때마다 `view_layer.update()` 를 호출하므로 프레임 × 본 수만큼 의존성 그래프가 갱신된다. 6개 동작(약 270프레임) 기준 수 분이 걸린다. 정확도를 위한 의도적 선택이다.

## 문제 해결

| 증상 | 원인 | 대처 |
|---|---|---|
| `아마추어 없음` | Export Skeleton 을 끄고 내보냄, 또는 리깅 전 파일 | Tripo 에서 스켈레톤 포함해 다시 Export |
| `[경고] 타겟에 없는 본` | AI Model 을 `v2.5 Good for Animals` 로 리깅함 | `v1.0 - Good for Humanoid` 로 다시 리깅 |
| F-커브 0개 | Blender 4.4+ 슬롯 미연결 | `assign_action()` 사용 확인 |
| 팔다리가 뒤틀림 | Twist 본을 매핑했거나 rest 자세가 T-포즈가 아님 | Twist 매핑 제거, 생성 시 T-Pose 토글 확인 |
| 캐릭터가 화면 밖으로 날아감 | Hip 이동량 스케일 보정 누락 | `scale` 계산 확인 |
| 동작이 서로 섞임 | NLA 스트립 `extrapolation` 이 `HOLD` | `"NOTHING"` 으로 설정 |
