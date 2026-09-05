from pathlib import Path
from unittest import mock
import pyray as pr
import g_editor,g_ui,g_update_and_render as game
pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN);pr.init_window(480,270,'player authoring validation')
textures={name:pr.load_texture(path) for name,path in {**game.PLAYER_CUTOUT_TEXTURE_PATHS,**game.REDHEAD_CUTOUT_TEXTURE_PATHS}.items()}
target=pr.load_render_texture(480,270)
try:
    for facing,track,group,field in (('right','walk','legs','near_upper_leg_degrees'),('up','run','arms','near_hand_y_pixels'),('down','run','legs','near_foot_x_pixels')):
        state=g_editor.make_editor_state();state['animation_debug'].update(preview_source='Player preview',authoring=True,authoring_character='player',edit_group=group,edit_field=field,facing=facing,track=track,highlight_component=True,playback='keyframe')
        ui=g_ui.make_ui_state()
        pr.begin_texture_mode(target);pr.clear_background(pr.Color(40,48,45,255))
        with mock.patch.object(g_ui,'get_mouse_position',return_value=pr.Vector2(-100,-100)):
            g_editor.draw_editor_overlay(ui,state,'animation',{},None,None,None,pr.Vector2(0,0),{},True,game_assets={'textures':textures})
        assert state.get('player_animation_draft'), state['animation_debug']
        assert not state['animation_debug'].get('authoring_error'), state['animation_debug']
        pr.end_texture_mode();im=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(im);pr.image_resize_nn(im,1440,810)
        pr.export_image(im,'artifacts/redhead-animation/player_edit_'+facing+'.png');pr.unload_image(im)
finally:
    for texture in textures.values():pr.unload_texture(texture)
    pr.unload_render_texture(target);pr.close_window()
print('Player authoring renders passed')
