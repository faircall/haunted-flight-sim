"""Same-camera game captures of the rejected photograph and three Blender views."""
from pathlib import Path
import pyray as pr
from PIL import Image,ImageDraw
import g_main
from moonlit_water_temple_photo import review_arena


def run():
    output=Path('photo_asset_pipeline/review');state={'frame':0};angles=('photo',30,40,50)
    game=g_main.update_and_render_module;original=game.update_and_render
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING);pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False;pr.is_key_released=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:.016;game.update_camera=lambda camera,**kwargs:camera
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame'];angle=angles[frame%4];arena=review_arena(game,arena,angle)
        camera=assets.setdefault('camera_3d',game.make_default_camera());camera.position.x=112.;camera.position.y=111.
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        if frame>=4:
            arena['lighting_profile'].update(ambient_color=[1.,1.,1.],ambient_strength=.70,black_point=0.)
            arena['lighting_profile']['moonlight']['intensity']=0.
        result=original(render,lighting,arena.set('time_elapsed',.5).set('auto_reload',False),assets,engine)
        capture=pr.load_image_from_texture(render.texture);pr.image_flip_vertical(capture)
        name=f'roof-scene-{angle}-'+('ambient' if frame>=4 else 'moon')
        pr.export_image(capture,str(output/(name+'.png')));pr.unload_image(capture)
        assert not result['sequence_runtime']['errors']
        if angle!='photo':
            import g_water_temple_art as art
            prop=result['entities']['lake_props']['roof'];image=art.image(prop['kind'],prop['width'],prop['height'],prop['asset'])
            assert set(image.getchannel('A').getdata())=={0,255}
            assert assets['water_prop_responses']['roof'].width==image.width
        state['frame']+=1;return result
    def safe(*args):
        try:return checked(*args)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=8;g_main.g_main()
    sheet=Image.new('RGB',(1920,600),(23,29,36));d=ImageDraw.Draw(sheet)
    for row,light in enumerate(('moon','ambient')):
        for col,angle in enumerate(angles):
            x=col*480;y=row*300
            title='Original photograph (rejected angle)' if angle=='photo' else f'Blender / {angle} degrees'
            d.text((x+8,y+8),title+' / '+light,fill='white')
            im=Image.open(output/f'roof-scene-{angle}-{light}.png').convert('RGB');sheet.paste(im,(x,y+26))
    sheet.save(output/'roof-in-scene-comparison.png')
    print('All roof views rendered with matching scene, camera, time, lighting and front-eave alignment.')


if __name__=='__main__':run()
