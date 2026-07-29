"""
Blender GUI 가 뜬 직후 3D 뷰를 정리하고 애니메이션 재생을 자동으로 시작한다.
(blender female_animated.blend --python play.py 형태로 사용)
"""
import bpy


def start():
    wm = bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is None:
                continue

            space = area.spaces.active
            space.shading.type = "SOLID"
            space.shading.color_type = "TEXTURE"
            space.shading.light = "STUDIO"
            space.overlay.show_overlays = False

            with bpy.context.temp_override(window=window, area=area, region=region):
                space.region_3d.view_perspective = "CAMERA"
                # 카메라 화면이 뷰포트를 가득 채우게 맞춘다
                bpy.ops.view3d.view_center_camera()
                if not bpy.context.screen.is_animation_playing:
                    bpy.ops.screen.animation_play()
            return None          # 성공했으니 타이머 종료

    return 0.5                   # 아직 창이 준비되지 않았으면 다시 시도


bpy.app.timers.register(start, first_interval=1.0)
