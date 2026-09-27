"""Actual GPU comparison against per-tile drawing, including cache invalidation."""
import numpy as np
import pyray as pr
import g_ground
import g_surfaces


def check(game, assets):
    local = dict(textures=dict(assets['textures']), shaders=assets['shaders'])
    tm = game.make_tile_map(80,25,16,16)
    for i,tile in enumerate(tm['tiles']):
        tile.update(index=i%len(tm['tile_types']),shape_index=i%5)
    g_surfaces.paint(tm,[(x,y) for y in range(4,10) for x in range(3,15)],'dirt',density=0.)
    tm['tiles'][6*80+7]['decals']=[dict(type='blood',offset_x=15,offset_y=14,size=5)]
    target = pr.load_render_texture(480,270)
    def capture(camera, fast):
        local['ground_batches_enabled'] = fast
        g_ground.prepare(local,tm,camera,game.draw_masked_tile_texture)
        pr.begin_texture_mode(target)
        pr.clear_background(pr.Color(33,25,68,255))
        game.update_render_tile_map_base(camera,{},tm,pr.Vector2(-100,-100),0,0,0,False,local,False,{},'play',None)
        pr.end_texture_mode()
        image = pr.load_image_from_texture(target.texture)
        result = np.frombuffer(bytes(pr.ffi.buffer(image.data,480*270*4)),np.uint8).reshape(270,480,4).copy()
        pr.unload_image(image)
        return result
    def compare(x=0.,y=0.):
        camera = pr.Vector2(x,y)
        fast, slow = capture(camera,True), capture(camera,False)
        error = np.abs(fast[:,:,:3].astype(int)-slow[:,:,:3].astype(int))
        if error.max() > 1:
            yy,xx,_ = np.unravel_index(error.argmax(),error.shape)
            raise AssertionError(f'ground batch RGB mismatch: {error.max()} at {(xx,yy)} fast={fast[yy,xx]} slow={slow[yy,xx]} wood={local["textures"]["wood_texture"].width}')
    try:
        compare()
        retained = local['surface_runtime']['chunks'][1,1]['texture'].id
        compare(700.)
        assert local['surface_runtime']['chunks'][1,1]['texture'].id == retained
        # Edit a retained chunk while it is offscreen, then revisit it.
        g_surfaces.paint(tm,[(6,6)],'grass',density=0.)
        tm['tiles'][6*80+7]['decals'][0]['offset_x'] = 2
        tm['tiles'][3*80+9]['shape_index'] = 4
        compare(.4,.4)
        # Oversized marks take the safe painter-order path.
        tm['tiles'][6*80+7]['decals'][0]['size'] = 40
        compare()
        assert local['ground_runtime']['fallback']
        tm['tiles'][6*80+7]['decals'][0]['size'] = 5
        # Simulate replacing a texture without replacing the map.
        original = local['textures']['wood_texture']
        image = pr.gen_image_color(original.width,original.height,pr.Color(90,140,60,255))
        replacement = pr.load_texture_from_image(image);pr.unload_image(image)
        local['textures']['wood_texture'] = replacement
        try:compare()
        finally:pr.unload_texture(replacement)
        image = pr.gen_image_color(original.width,original.height,pr.Color(90,140,60,128))
        replacement = pr.load_texture_from_image(image);pr.unload_image(image)
        local['textures']['wood_texture'] = replacement
        try:compare()
        finally:pr.unload_texture(replacement)
        print('ground batches: reference pixels, decals, offscreen edits, revisit, texture replacement passed')
    finally:
        g_ground.unload(local);g_surfaces.unload(local);pr.unload_render_texture(target)
