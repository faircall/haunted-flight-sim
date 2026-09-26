"""Independent roof paint, connected footprints and camera-height cutaways."""
import math
from PIL import Image, ImageDraw
import pyray as pr
import g_effects
import g_surfaces

RUNTIME_GENERATION=globals().get('RUNTIME_GENERATION',0)+1
DEFAULT_HEIGHT=44
FADE_SECONDS=.30


def paint(tm, points, material='black', height=DEFAULT_HEIGHT):
    changed=0;w,h=tm['map_width'],tm['map_height']
    height=max(16,min(192,int(height)))
    for x,y in set(points):
        if not (0<=x<w and 0<=y<h):continue
        tile=tm['tiles'][y*w+x]
        if material=='none':
            if tile.pop('roof_material',None) is not None:
                tile.pop('roof_height',None);changed+=1
        elif tile.get('roof_material')!=material or tile.get('roof_height')!=height:
            tile.update(roof_material=material,roof_height=height);changed+=1
    if changed:
        tm['roof_revision']=tm.get('roof_revision',0)+1
        g_effects.mark_rain_exposure_dirty(tm)
    return changed


def flood(tm,x,y,material='black',height=DEFAULT_HEIGHT):
    w,h=tm['map_width'],tm['map_height']
    if not (0<=x<w and 0<=y<h):return 0
    first=tm['tiles'][y*w+x];roof=first.get('roof_material')
    floor=(first.get('index',0),first.get('surface_material'))
    seen=set();todo=[(x,y)];points=[]
    while todo:
        x,y=todo.pop()
        if (x,y) in seen or not (0<=x<w and 0<=y<h):continue
        seen.add((x,y));tile=tm['tiles'][y*w+x]
        if tile.get('roof_material')!=roof:continue
        if roof is None and (tile.get('index',0),tile.get('surface_material'))!=floor:continue
        points.append((x,y));todo.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
    return paint(tm,points,material,height)


def layout(tm):
    """Four-connected roof cells share a cutaway, independent of floor finish."""
    w,h=tm['map_width'],tm['map_height'];tw,th=tm['tile_width'],tm['tile_height']
    remaining={i for i,t in enumerate(tm['tiles']) if i<w*h and t.get('roof_material')}
    groups=[];lookup={}
    while remaining:
        root=min(remaining);todo=[root];cells=[];remaining.remove(root)
        while todo:
            i=todo.pop();cells.append(i);x,y=i%w,i//w
            for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                n=ny*w+nx
                if 0<=nx<w and 0<=ny<h and n in remaining:
                    remaining.remove(n);todo.append(n)
        rectangles=[]
        for i in cells:
            tile=tm['tiles'][i];height=max(16,min(192,int(tile.get('roof_height',DEFAULT_HEIGHT))))
            rectangles.append((i%w*tw,i//w*th-height,tw,th))
            lookup[i]=root
        left=min(r[0] for r in rectangles);top=min(r[1] for r in rectangles)
        right=max(r[0]+r[2] for r in rectangles);bottom=max(r[1]+r[3] for r in rectangles)
        groups.append(dict(id=root,cells=cells,rectangles=rectangles,
                           bounds=dict(x=left,y=top,width=right-left,height=bottom-top),
                           sort_y=max((i//w+1)*th for i in cells)-.5))
    return groups,lookup


def player_region(tm, lookup, player):
    if not player:return None
    pos=g_effects.position_to_world(player.get('position',{}),tm)
    base=player.get('render_base_offset',{'x':0.,'y':14.})
    x=math.floor((pos['x']+base.get('x',0.))/tm['tile_width'])
    y=math.floor((pos['y']+base.get('y',0.))/tm['tile_height'])
    if not (0<=x<tm['map_width'] and 0<=y<tm['map_height']):return None
    return lookup.get(y*tm['map_width']+x)


def prepare(assets,tm,player,mode='play',dt=0.):
    stamp=(id(tm),tm.get('roof_revision',0),tm['map_width'],tm['map_height'],tm['tile_width'],tm['tile_height'],RUNTIME_GENERATION)
    rt=assets.get('roof_runtime')
    if rt is None or rt['stamp']!=stamp:
        unload(assets)
        groups,lookup=layout(tm);textures={}
        for group in groups:
            b=group['bounds'];image=Image.new('RGBA',(b['width'],b['height']))
            draw=ImageDraw.Draw(image)
            for x,y,w,h in group['rectangles']:
                draw.rectangle((x-b['x'],y-b['y'],x-b['x']+w-1,y-b['y']+h-1),fill=(0,0,0,255))
            textures[str(group['id'])]=g_surfaces.upload_image(image)
        rt=dict(stamp=stamp,map=tm,groups=groups,lookup=lookup)
        assets.update(roof_runtime=rt,roof_textures=textures)
    # Editing exposes the floor; explicit exterior preview shows every roof.
    rt['visible']=(mode=='play' or assets.get('editor_state',{}).get('roof_preview',False))
    rt['hidden']=player_region(tm,rt['lookup'],player) if mode=='play' else None
    # Keep a reversible progress value per building. Loading / changing editor
    # modes starts at the correct endpoint instead of flashing a roof indoors.
    snap=mode!='play' or rt.get('mode')!=mode
    progress=rt.setdefault('fade_progress',{})
    step=max(0.,float(dt))/FADE_SECONDS
    for group in rt['groups']:
        identity=group['id']
        target=float(rt['visible'] and identity!=rt['hidden'])
        value=progress.get(identity,target)
        progress[identity]=target if snap else max(target,value-step) if target<value else min(target,value+step)
    rt['mode']=mode


def render_items(assets):
    import g_render_order as order
    rt=assets.get('roof_runtime',{})
    if not rt.get('visible'):return []
    items=[]
    for group in rt['groups']:
        progress=rt['fade_progress'][group['id']]
        opacity=progress*progress*(3.-2.*progress)
        if opacity<=0.:continue
        b=group['bounds'];base=dict(x=b['x'],y=group['sort_y'])
        entity=dict(render_anchor_offset={'x':0.,'y':b['y']-base['y']},
                    visual_height=0.,occludes_render_items=True,shadow={'mode':'none'},
                    self_shadow={'mode':'none'},outline={'policy':'never'})
        item=order.make_world_render_item('roof','roof','roof:'+str(group['id']),group['id'],entity,base,b['width'],b['height'],
            order.make_texture_reference('roof_textures',str(group['id'])),dict(x=0.,y=0.,width=b['width'],height=b['height']))
        item['opacity']=opacity
        items.append(item)
    return items


def draw_overlay(editor,mode,camera,tm):
    if mode!='tile' or editor.get('tile_edit_mode')!='roofs':return
    import g_render_order as order
    tw,th=tm['tile_width'],tm['tile_height'];w=tm['map_width']
    for i,tile in enumerate(tm['tiles']):
        if not tile.get('roof_material'):continue
        p=order.world_to_screen_pixel(i%w*tw,i//w*th,camera)
        if p['x']+tw<0 or p['y']+th<0 or p['x']>=480 or p['y']>=270:continue
        pr.draw_rectangle(p['x'],p['y'],tw,th,pr.Color(66,154,191,70))
        pr.draw_rectangle_lines(p['x'],p['y'],tw,th,pr.Color(125,213,239,170))


def draw_controls(ui,editor):
    import g_ui
    pr.draw_rectangle(328,59,149,109,g_ui.UI_BACKGROUND)
    material=editor.get('roof_material','black')
    if g_ui.ui_button(ui,'roof:paint','Black roof',pr.Rectangle(332,62,83,16),selected=material=='black'):material='black'
    if g_ui.ui_button(ui,'roof:erase','Erase',pr.Rectangle(418,62,52,16),selected=material=='none'):material='none'
    editor['roof_material']=material
    editor['roof_height'],_=g_ui.ui_number_input_int(ui,'roof:height','height',editor.get('roof_height',DEFAULT_HEIGHT),16,192,pr.Rectangle(332,82,138,16))
    editor['roof_preview'],_=g_ui.ui_checkbox(ui,'roof:preview','Preview exterior',editor.get('roof_preview',False),pr.Rectangle(332,103,138,14))
    pr.draw_text('Left: paint / right: fill',332,124,7,g_ui.UI_MUTED)
    pr.draw_text('Roof joins hide together',332,136,7,g_ui.UI_MUTED)
    pr.draw_text('Floors remain underneath',332,148,7,g_ui.UI_MUTED)


def unload(assets):
    for texture in assets.pop('roof_textures',{}).values():pr.unload_texture(texture)
    assets.pop('roof_runtime',None)
