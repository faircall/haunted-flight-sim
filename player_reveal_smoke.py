"""Pixel regressions in the real renderer: python .tree_game_smoke.py --night."""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import pyray as pr
import g_graphics as graphics
import g_player_reveal as reveal
import g_render_order as order
import g_surfaces as surfaces
import g_night as night


def check(game,assets):
    from night_lighting_smoke import pixels,assert_camera_locked
    out=Path('artifacts/player-reveal');out.mkdir(parents=True,exist_ok=True)
    target=pr.load_render_texture(240,240)
    body=Image.new('RGBA',(32,32));ImageDraw.Draw(body).rectangle((12,2,19,29),fill=(35,155,215,255))
    wall=Image.new('RGBA',(80,80),(155,74,39,255))
    hole=wall.copy();ImageDraw.Draw(hole).rectangle((22,16,41,53),fill=(0,0,0,0))
    textures={k:surfaces.upload_image(im) for k,im in dict(body=body,wall=wall,hole=hole,roof=Image.new('RGBA',(80,80),(0,0,0,255))).items()}
    local={'shaders':assets['shaders'],'test_textures':textures}
    def sprite(identity,name,x,y,w,h,depth,blocks=False):
        result=order.make_world_render_item('test','test',identity,identity,
            dict(occludes_render_items=blocks),dict(x=x,y=y),w,h,
            order.make_texture_reference('test_textures',name),dict(x=0,y=0,width=w,height=h))
        result['sort_y']=depth
        return result
    player=sprite('player','body',88,88,32,32,120)
    blocker=sprite('wall','wall',72,72,80,80,145,True)
    camera=pr.Vector2(0,0)
    profile=dict(ambient_color=[1.,1.,1.],ambient_strength=1.,contrast=1.,black_point=0.,shadow_color=[0.,0.,0.])
    readability=graphics.get_or_create_render_target(local,'reveal_test_readability',240,240)
    pr.begin_texture_mode(readability);pr.clear_background(pr.BLACK);pr.end_texture_mode()
    def render(items,pan=camera,lit=True):
        pr.begin_texture_mode(target);pr.clear_background(pr.Color(22,28,31,255));pr.end_texture_mode()
        graphics.draw_sorted_world_render_items(items,target,pan,local,profile,
            entity_readability_lighting=readability if lit else None)
        return pixels(target)
    try:
        items=[player,blocker]
        before=render(items)
        reveal.prepare(local,items,target,camera,0.)
        assert np.array_equal(before,render(items)),'zero-strength reveal alters the lit object'
        for _ in range(5):reveal.prepare(local,items,target,camera,.04)
        state=local['player_reveal_runtime']['states']['wall'][0]
        assert pixels(state)[0,0,0]==255,'opaque object did not reveal player'
        after=render(items)
        expected=np.array([155,74,39])*.35+np.array([35,155,215])*.65
        assert np.abs(after[104,104,:3].astype(float)-expected).max()<=2.,'player is not visible through lit object'
        assert np.array_equal(before[76:80,76:145],after[76:80,76:145]),'whole object fades instead of local patch'
        assert not np.array_equal(before[104,96],after[104,96]),'patch is only a player-shaped highlight'
        assert np.array_equal(after,render(items,lit=False)),'lit and unlit paths disagree on patch opacity'
        Image.fromarray(before).save(out/'solid.png');Image.fromarray(after).save(out/'local-transparency.png')
        def pan_render(pan):
            reveal.prepare(local,items,target,pan,0.)
            render(items,pan)
        assert_camera_locked(target,pan_render,'localized player reveal')
        reveal.prepare(local,items,target,camera,0.)

        # A foreground object remains fully solid; enemies aren't outlined or
        # overdrawn on top of the occluder by this treatment.
        front=sprite('front','body',88,88,32,32,180)
        foreground=render(items+[front])
        assert np.array_equal(foreground[104,104,:3],[35,155,215]),'foreground draw order broken'

        # Exact alpha coverage: the player fits through a gap despite a large
        # bounding-box overlap. Once fully in that gap, transition decays away.
        blocker['texture']=order.make_texture_reference('test_textures','hole')
        for _ in range(7):reveal.prepare(local,items,target,camera,.04)
        state=local['player_reveal_runtime']['states']['wall'][0]
        assert not pixels(state)[0,0,:3].any(),'transparent opening falsely counted as an obstruction'
        without=dict(blocker);without.pop('_player_reveal')
        assert np.array_equal(render(items),render([player,without])),'gap changes despite zero occlusion'
        Image.fromarray(render(items)).save(out/'clear-through-gap.png')
        # A fresh gap must never trigger even transiently.
        reveal.unload(local);reveal.prepare(local,items,target,camera,.2)
        assert pixels(local['player_reveal_runtime']['states']['wall'][0])[0,0,0]==0

        blocker['texture']=order.make_texture_reference('test_textures','wall')
        reveal.prepare(local,items,target,camera,.08)
        mid=pixels(local['player_reveal_runtime']['states']['wall'][0])[0,0,0]
        assert 110<mid<145,'entry fade jumps to full transparency'
        reveal.prepare(local,items,target,camera,0.)
        assert pixels(local['player_reveal_runtime']['states']['wall'][0])[0,0,0]==mid,'paused fade advances'
        # Local emission uses the same patch: no glowing solid frame left behind.
        local['night_runtime']={'entries':{}}
        emissive=dict(blocker,_emission=textures['wall'])
        for _ in range(5):reveal.prepare(local,[player,emissive],target,camera,.04)
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK);pr.end_texture_mode()
        night.draw_emission(target,[player,emissive],camera,local)
        assert pixels(target)[104,104,0]<155*.5,'emission did not follow transparency'

        # The global roof fade and the local patch multiply their opacity once.
        roof=dict(blocker,source='roof',source_id='roof',opacity=.5,
                  texture=order.make_texture_reference('test_textures','roof'))
        roof.pop('_player_reveal',None)
        for _ in range(5):reveal.prepare(local,[player,roof],target,camera,.04)
        roof_view=render([player,roof])
        expected=np.array([35,155,215])*(1.-.5*(1.-reveal.TRANSPARENCY))
        assert np.abs(roof_view[104,104,:3].astype(float)-expected).max()<=3.,'roof fade and local transparency fight each other'

        reveal.prepare(local,[player],target,camera,.016)
        assert not local['player_reveal_runtime']['states'],'departed blockers retain GPU history'
        # Review with the actual animated tree texture and player cutout rig.
        actual_player=order.build_player_render_item(game.make_default_player(112.,112.,0.),game.make_tile_map(15,15,16,16),assets)
        tree_name=next(iter(assets['tree_textures']))
        tree=sprite('tree','wall',40,28,160,160,180,True)
        tree.update(texture=order.make_texture_reference('tree_textures',tree_name),source_rect=dict(x=0,y=0,width=160,height=160))
        local.update(tree_textures=assets['tree_textures'],sprite_sheets=assets['sprite_sheets'],textures=assets['textures'])
        real_items=[actual_player,tree]
        plain=render(real_items)
        for _ in range(5):reveal.prepare(local,real_items,target,camera,.04)
        softened=render(real_items)
        assert np.any(softened!=plain),'actual tree / player cutout not revealed'
        sheet=Image.new('RGBA',(480,240));sheet.paste(Image.fromarray(plain),(0,0));sheet.paste(Image.fromarray(softened),(240,0));sheet.save(out/'tree-comparison.png')
        reveal.prepare(local,[],target,camera,.016,scene_key='next-level')
        assert 'player_reveal_runtime' not in local,'new level retained old reveal resources'
        print('Player reveal GPU: true alpha coverage, local lit transparency, gap rejection, fades, foreground sorting, emission, camera locking and actual willow passed.')
    finally:
        reveal.unload(local);night.unload(local)
        for rt in local.get('render_targets',{}).values():pr.unload_render_texture(rt)
        for texture in textures.values():pr.unload_texture(texture)
        pr.unload_render_texture(target)
