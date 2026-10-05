"""Small in-game placement/markup editor over the shared temple scene document."""
from copy import deepcopy
import math

import pyray as pr
import g_narrative_text as text
import g_temple_structure as structure
import g_temple_layout as layout
from g_temple_scene import PROP_LABELS, prop_origin

TOOLS = ('Select', 'Place', 'Note', 'Arrow', 'Area', 'Floor / walkway', 'Stairs', 'Player spawn', 'Encounter trigger')
COLORS = (pr.Color(242, 191, 83, 255), pr.Color(99, 202, 239, 255), pr.Color(238, 112, 111, 255))
VIEW_SCALE = 1140 / 480
VIEW_TOP = (810 - 270 * VIEW_SCALE) / 2
TOOL_TOP,TOOL_ROW,PALETTE_TOP,PALETTE_ROW=80,24,338,20
FLOOR_LABELS=('Wood walkway','Stone floor','Grass / ground','Wall','Water / erase','Restore original')


def ground_point(eye, target, up, span, screen, floor, levels=None):
    """Orthographic ray / stepped floor intersection, independent of Raylib."""
    def normalize(v):
        length = math.sqrt(sum(a*a for a in v))
        return tuple(a/length for a in v)
    def cross(a, b):
        return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    forward = normalize(tuple(b-a for a, b in zip(eye, target)))
    right = normalize(cross(forward, up))
    vertical = cross(right, forward)
    sx, sy = (screen[0]/480-.5)*span*480/270, (.5-screen[1]/270)*span
    origin = tuple(eye[i]+right[i]*sx+vertical[i]*sy for i in range(3))
    if abs(forward[1]) < 1e-6:
        return None
    # Test actual discrete levels, avoiding oscillation across stair edges.
    candidates = []
    for height in levels or (0., 16., 18., 20., 22., 24., 16/6, 32/6, 8., 64/6, 80/6):
        distance = (height-origin[1])/forward[1]
        x, z = origin[0]+forward[0]*distance, origin[2]+forward[2]*distance
        if distance >= 0 and 0 <= x < 896 and 0 <= z < 640 and abs(floor(x, z)-height) < .01:
            candidates.append((distance, x, z))
    return tuple(min(candidates)[1:]) if candidates else None


class Editor:
    def __init__(self, scene):
        self.scene = scene
        import g_baked_assets
        self.records = g_baked_assets.manifest()
        self.active = False
        self.overhead = True
        self.focus = [415., 285.]
        self.span = 220.
        self.tool = 0
        self.snap = True
        self.selected = None
        self.drag = None
        self.pending = None
        self.edit_text = None
        self.text_before = None
        self.color = 0
        self.material='wood'
        self.floor_height=16.
        self.grain='x'
        self.stair_axis='x'
        self.floor_drag=None
        self.hover=None
        self.status = ''
        self.palette_index = 0
        self.palette_scroll=0
        self.edit_field='text'
        self.palette = [dict(kind='key', label='Brass key', rotation=0, group='temple'),
                        dict(kind='medicine', label='Medicine', rotation=0),
                        dict(kind='inscription', label='Inscription', rotation=0, description='old_inscription')]
        self.palette += [dict(kind='enemy_spawn',label='Pale chorus spawn',rotation=0,group='temple-terrace'),
                         dict(kind='gate',label='Encounter gate',rotation=0,group='temple-terrace'),
                         dict(kind='ammo',label='Pistol ammunition',rotation=0)]
        seen = set()
        for obj in scene.document['objects']:
            if obj['kind'] != 'prop':
                continue
            asset = obj['template']['asset']
            if asset in seen:
                continue
            seen.add(asset)
            self.palette.append(dict(kind='prop', label=PROP_LABELS.get(asset.removeprefix('baked:'), asset.removeprefix('baked:')),
                                     rotation=0, template=deepcopy(obj['template'])))

    def camera(self, game_camera):
        if not self.overhead:
            return game_camera
        x, z = self.focus
        return pr.Camera3D(pr.Vector3(x, 400, z), pr.Vector3(x, 0, z),
                           pr.Vector3(0, 0, -1), self.span, pr.CAMERA_ORTHOGRAPHIC)

    def snapped(self, position):
        step = 4 if self.snap and not pr.is_key_down(pr.KEY_LEFT_SHIFT) else 1
        return [max(0., min(limit-1., round(v/step)*step)) for v, limit in zip(position, (896, 640))]

    def begin_text(self, identity):
        obj = self.scene.get(identity)
        if not obj or obj['kind'] not in ('note', 'arrow', 'area','enemy_spawn','encounter','gate'):
            return
        self.edit_field='group' if obj['kind'] in ('enemy_spawn','encounter','gate') else 'text'
        self.text_before = self.scene.checkpoint()
        self.edit_text = obj.get(self.edit_field, '')
        self.selected = identity

    def finish_text(self, cancel=False):
        if self.edit_text is not None:
            if not cancel:
                self.scene.get(self.selected)[self.edit_field] = self.edit_text
                try:self.scene.commit(self.text_before)
                except ValueError as exc:
                    self.status=str(exc)
                    return False
            self.edit_text = None
            self.text_before = None
        return True

    def toggle(self, gameplay):
        if not self.finish_text():return
        if self.drag:
            self.scene.commit(self.drag['before'])
            self.drag = None
        if self.floor_drag:self.finish_floor(gameplay)
        self.pending = None
        self.active = not self.active
        if self.active:
            self.focus = [gameplay.walk.x, gameplay.walk.y]
        gameplay.apply_scene()
        if not self.active:
            try:gameplay.ensure_clear_position()
            except ValueError:
                self.active=True
                raise

    def finish_floor(self,gameplay):
        drag=self.floor_drag
        self.floor_drag=None
        if drag and self.hover:
            changed=layout.paint(self.scene,drag['start'],self.hover,drag['material'],drag['height'],drag['axis'])
            if changed:gameplay.apply_scene()

    def choose_tool(self,index):
        self.tool=index
        self.pending=None
        self.floor_drag=None
        if index>=5:self.selected=None

    def pick(self, camera, mouse, tm):
        candidates = []
        def project(x, h, z):
            p = pr.get_world_to_screen_ex(pr.Vector3(x, h, z), camera, 480, 270)
            return p.x, p.y
        def segment_distance(p, a, b):
            dx, dy = b[0]-a[0], b[1]-a[1]
            amount = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy or 1)))
            return math.hypot(p[0]-a[0]-dx*amount, p[1]-a[1]-dy*amount)
        for obj in self.scene.document['objects'] + self.scene.document['marks']:
            x, z = obj['position']
            floor = structure.floor_height(tm, x, z)
            kind = obj['kind']
            if kind in ('note', 'arrow', 'area','encounter'):
                points = [obj['position']]
                if kind == 'arrow':
                    points.append(obj['end'])
                elif kind in ('area','encounter'):
                    a, b = obj['position'], obj['end']
                    points = [a, [b[0], a[1]], b, [a[0], b[1]], a]
                points = [project(p[0], structure.floor_height(tm, *p)+1, p[1]) for p in points]
                distance = min((segment_distance(mouse, a, b) for a, b in zip(points, points[1:])),
                               default=math.hypot(points[0][0]-mouse[0], points[0][1]-mouse[1]))
                if distance <= 6:
                    candidates.append((distance, obj['id']))
                continue
            if kind == 'prop':
                prop = dict(obj['template'], position=dict(x=x, y=z), base_height=0 if obj['template']['kind'] == 'lily' else floor)
                origin = prop_origin(obj['id'], prop, self.records)
                rec = self.records[prop['asset'].removeprefix('baked:')]
                low, high = rec['position_min'], rec['position_max']
            else:
                origin = x, floor, z
                width, depth, height = {'key': (7, 4, 2), 'medicine': (4, 3, 3),
                                        'inscription': (9, 2, 7), 'door': (32, 4, 24),
                                        'enemy_spawn':(6,6,28),'gate':(32,4,30),'ammo':(4,3,3)}[kind]
                low, high = (-width/2, -depth/2, 0), (width/2, depth/2, height)
            a = math.radians(obj.get('rotation', 0))
            corners = [project(origin[0]+dx*math.cos(a)+dz*math.sin(a), origin[1]+h,
                               origin[2]-dx*math.sin(a)+dz*math.cos(a))
                       for dx in (low[0], high[0]) for dz in (low[1], high[1]) for h in (low[2], high[2])]
            xs, ys = [p[0] for p in corners], [p[1] for p in corners]
            distance = math.hypot((min(xs)+max(xs))/2-mouse[0], (min(ys)+max(ys))/2-mouse[1])
            if min(xs)-4 <= mouse[0] <= max(xs)+4 and min(ys)-4 <= mouse[1] <= max(ys)+4:
                candidates.append((distance, obj['id']))
        return min(candidates)[1] if candidates else None

    def update(self, gameplay, camera, dt):
        if not self.active:
            return
        scene = self.scene
        before = scene.checkpoint()
        control = pr.is_key_down(pr.KEY_LEFT_CONTROL) or pr.is_key_down(pr.KEY_RIGHT_CONTROL)
        if self.edit_text is not None:
            code = pr.get_char_pressed()
            while code:
                if code >= 32 and len(self.edit_text) < 240:
                    self.edit_text += chr(code)
                code = pr.get_char_pressed()
            if pr.is_key_pressed(pr.KEY_BACKSPACE):
                self.edit_text = self.edit_text[:-1]
            if pr.is_key_pressed(pr.KEY_ENTER):
                if self.finish_text():gameplay.apply_scene()
            if pr.is_key_pressed(pr.KEY_ESCAPE):
                self.finish_text(cancel=True)
            return
        changed = False
        try:
            if pr.is_key_pressed(pr.KEY_F4):
                gameplay.combat.reset()
                self.status='Encounters reset; health and pistol restored. Layout retained.'
            if control:
                if pr.is_key_pressed(pr.KEY_S):
                    if self.floor_drag:
                        self.finish_floor(gameplay)
                        before=scene.checkpoint()
                        changed=True
                    scene.save()
                    self.status = 'Scene saved.'
                if pr.is_key_pressed(pr.KEY_O):
                    self.floor_drag=None;self.pending=None
                    scene.reload()
                    self.selected = None
                    changed = True
                    self.status = 'Scene reloaded; Ctrl+Z restores previous edits.'
                if pr.is_key_pressed(pr.KEY_Z):
                    self.floor_drag=None;self.pending=None
                    changed = scene.undo()
                if pr.is_key_pressed(pr.KEY_Y):
                    self.floor_drag=None;self.pending=None
                    changed = scene.redo()
                if pr.is_key_pressed(pr.KEY_D):
                    self.selected = scene.duplicate(self.selected) or self.selected
                    changed = True
            else:
                if pr.is_key_pressed(pr.KEY_C):
                    self.overhead = not self.overhead
                if pr.is_key_pressed(pr.KEY_G):
                    self.snap = not self.snap
                if pr.is_key_pressed(pr.KEY_K):
                    self.color = (self.color+1) % len(COLORS)
                if pr.is_key_pressed(pr.KEY_J):
                    scene.document['layout']['rails']=not scene.document['layout']['rails']
                if self.tool in (5,6):
                    self.floor_height=max(0,min(48,self.floor_height+4*(int(pr.is_key_pressed(pr.KEY_RIGHT_BRACKET))-int(pr.is_key_pressed(pr.KEY_LEFT_BRACKET)))))
                    if pr.is_key_pressed(pr.KEY_V):
                        if self.tool==5:self.grain='y' if self.grain=='x' else 'x'
                        else:self.stair_axis=layout.AXES[(layout.AXES.index(self.stair_axis)+1)%4]
                for i, key in enumerate((pr.KEY_ONE, pr.KEY_TWO, pr.KEY_THREE, pr.KEY_FOUR, pr.KEY_FIVE,pr.KEY_SIX,pr.KEY_SEVEN,pr.KEY_EIGHT,pr.KEY_NINE)):
                    if pr.is_key_pressed(key):
                        self.choose_tool(i)
                if self.overhead:
                    self.focus[0] = max(0, min(896, self.focus[0] +
                        (int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A)))*self.span*dt))
                    self.focus[1] = max(0, min(640, self.focus[1] +
                        (int(pr.is_key_down(pr.KEY_S))-int(pr.is_key_down(pr.KEY_W)))*self.span*dt))
                    self.span = max(60, min(640, self.span-pr.get_mouse_wheel_move()*16))
                if pr.is_key_pressed(pr.KEY_ESCAPE):
                    self.choose_tool(0)
            obj = scene.get(self.selected)
            if obj and obj['kind'] != 'door' and not control:
                step = 1 if pr.is_key_down(pr.KEY_LEFT_SHIFT) else 4
                dx = step*(int(pr.is_key_pressed(pr.KEY_RIGHT))-int(pr.is_key_pressed(pr.KEY_LEFT)))
                dz = step*(int(pr.is_key_pressed(pr.KEY_DOWN))-int(pr.is_key_pressed(pr.KEY_UP)))
                if dx or dz:
                    points = [obj['position']] + ([obj['end']] if 'end' in obj else [])
                    if all(0 <= p[0]+dx < 896 and 0 <= p[1]+dz < 640 for p in points):
                        for p in points:
                            p[0] += dx
                            p[1] += dz
                if obj['kind'] not in ('note', 'arrow', 'area'):
                    obj['rotation'] = (obj.get('rotation', 0)+(90 if obj['kind']=='gate' else 15)*
                        (int(pr.is_key_pressed(pr.KEY_E))-int(pr.is_key_pressed(pr.KEY_Q)))) % 360
                if pr.is_key_pressed(pr.KEY_DELETE):
                    scene.delete(self.selected)
                    self.selected = None
                    changed = True
                    before = scene.checkpoint()
                if pr.is_key_pressed(pr.KEY_ENTER):
                    self.begin_text(self.selected)
            mouse = pr.get_mouse_position()
            if mouse.x >= 1140:
                if self.tool<5:
                    self.palette_scroll=max(0,min(max(0,len(self.palette)-10),self.palette_scroll-int(pr.get_mouse_wheel_move())))
                if pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT):
                    if TOOL_TOP <= mouse.y < TOOL_TOP+len(TOOLS)*TOOL_ROW:
                        self.choose_tool(int((mouse.y-TOOL_TOP)//TOOL_ROW))
                    if self.tool==5 and PALETTE_TOP <= mouse.y < PALETTE_TOP+len(FLOOR_LABELS)*PALETTE_ROW:
                        self.material=layout.MATERIALS[int((mouse.y-PALETTE_TOP)//PALETTE_ROW)]
                    elif self.tool==6 and PALETTE_TOP <= mouse.y < PALETTE_TOP+4*PALETTE_ROW:
                        self.stair_axis=layout.AXES[int((mouse.y-PALETTE_TOP)//PALETTE_ROW)]
                    elif self.tool<5 and PALETTE_TOP <= mouse.y < PALETTE_TOP+min(10,len(self.palette))*PALETTE_ROW:
                        self.palette_index = self.palette_scroll+int((mouse.y-PALETTE_TOP)//PALETTE_ROW)
                        self.choose_tool(1)
            else:
                # Camera may have changed from panning or toggling this frame.
                camera = self.camera(gameplay_camera(gameplay))
                coordinates = (mouse.x/VIEW_SCALE, (mouse.y-VIEW_TOP)/VIEW_SCALE)
                values = lambda v: (v.x, v.y, v.z)
                p = ground_point(values(camera.position), values(camera.target), values(camera.up),
                    camera.fovy, coordinates, lambda x, z: structure.floor_height(gameplay.arena['tile_map'], x, z),
                    gameplay.arena['tile_map'].get('temple3d_levels')) if 0 <= coordinates[1] < 270 else None
                if p:self.hover=p
                if p and self.tool==5:
                    if pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT) and pr.is_key_down(pr.KEY_LEFT_ALT):
                        tx,tz=layout.cell_at(p)
                        tile=gameplay.arena['tile_map']['tiles'][tz*layout.WIDTH+tx]
                        self.material='water' if tile.get('water') else tile.get('surface_material','grass')
                        self.floor_height=structure.floor_height(gameplay.arena['tile_map'],*p)
                        self.grain=tile.get('surface_axis','x')
                    elif pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT) or pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_RIGHT):
                        self.floor_drag=dict(start=p,material='water' if pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_RIGHT) else self.material,
                                             height=self.floor_height,axis=self.grain)
                    if self.floor_drag and (pr.is_mouse_button_released(pr.MOUSE_BUTTON_LEFT) or pr.is_mouse_button_released(pr.MOUSE_BUTTON_RIGHT)):
                        self.finish_floor(gameplay)
                        before=scene.checkpoint()
                        changed=True
                if p and self.tool==6 and pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_RIGHT):
                    changed=layout.remove_stairs(scene,p)
                    before=scene.checkpoint()
                if p and self.tool!=5 and pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT):
                    p = self.snapped(p)
                    if self.tool == 0:
                        self.selected = self.pick(camera, coordinates, gameplay.arena['tile_map'])
                        obj = scene.get(self.selected)
                        if obj and obj['kind'] != 'door':
                            self.drag = dict(before=scene.checkpoint(), position=list(obj['position']),
                                end=list(obj['end']) if 'end' in obj else None, mouse=p)
                    elif self.tool == 1:
                        if self.palette[self.palette_index]['kind'] in ('enemy_spawn','gate','ammo') and not gameplay.can_walk(*p):raise ValueError('Place this encounter object on clear floor.')
                        self.selected = scene.add(dict(deepcopy(self.palette[self.palette_index]), position=p))
                        changed = True
                    elif self.tool == 2:
                        self.selected = scene.add(dict(kind='note', position=p, text='', color=self.color), markup=True)
                        self.begin_text(self.selected)
                        changed = True
                    elif self.tool==6:
                        if self.pending is None:
                            self.pending=dict(position=p,bottom=structure.floor_height(gameplay.arena['tile_map'],*p))
                        else:
                            layout.add_stairs(scene,self.pending['position'],p,self.pending['bottom'],self.floor_height,self.stair_axis)
                            self.pending=None
                            changed=True
                    elif self.tool==7:
                        if not gameplay.can_walk(*p):raise ValueError('Choose a clear walkable spot for the player spawn.')
                        scene.document['spawn']=p
                    elif self.tool==8:
                        if self.pending is None:self.pending=p
                        else:
                            self.selected=scene.add(dict(kind='encounter',position=self.pending,end=p,
                                label='Encounter area',rotation=0,group='temple-terrace',camera_offset=[-180,151,140],camera_span=130))
                            self.pending=None;changed=True
                            self.begin_text(self.selected)
                    elif self.pending is None:
                        self.pending = p
                    else:
                        self.selected = scene.add(dict(kind='arrow' if self.tool == 3 else 'area',
                            position=self.pending, end=p, text='', color=self.color), markup=True)
                        self.pending = None
                        self.begin_text(self.selected)
                        changed = True
                if p and self.drag and pr.is_mouse_button_down(pr.MOUSE_BUTTON_LEFT):
                    obj = scene.get(self.selected)
                    p = self.snapped(p)
                    dx, dz = p[0]-self.drag['mouse'][0], p[1]-self.drag['mouse'][1]
                    points = [self.drag['position']] + ([self.drag['end']] if self.drag['end'] else [])
                    if all(0 <= q[0]+dx < 896 and 0 <= q[1]+dz < 640 for q in points):
                        obj['position'] = [self.drag['position'][0]+dx, self.drag['position'][1]+dz]
                        if self.drag['end']:
                            obj['end'] = [self.drag['end'][0]+dx, self.drag['end'][1]+dz]
                        changed = True
            if self.drag and pr.is_mouse_button_released(pr.MOUSE_BUTTON_LEFT):
                scene.commit(self.drag['before'])
                self.drag = None
            if self.floor_drag and (pr.is_mouse_button_released(pr.MOUSE_BUTTON_LEFT) or pr.is_mouse_button_released(pr.MOUSE_BUTTON_RIGHT)):
                self.finish_floor(gameplay)
                before=scene.checkpoint()
                changed=True
            elif not self.drag and before != scene.document and not changed:
                changed = scene.commit(before)
            if changed:
                gameplay.apply_scene()
        except (OSError, ValueError, KeyError) as exc:
            self.status = str(exc)

    def draw_world(self, tm):
        def vec(p):
            return pr.Vector3(p[0], structure.floor_height(tm, *p)+.7, p[1])
        for mark in self.scene.document['marks']:
            color = COLORS[mark.get('color', 0) % len(COLORS)]
            a = mark['position']
            if mark['kind'] == 'note':
                pr.draw_cube(vec(a), 2, 4, 2, color)
            elif mark['kind'] == 'arrow':
                b = mark['end']
                pr.draw_line_3d(vec(a), vec(b), color)
                angle = math.atan2(b[1]-a[1], b[0]-a[0])
                for offset in (-.5, .5):
                    p = [b[0]-6*math.cos(angle+offset), b[1]-6*math.sin(angle+offset)]
                    pr.draw_line_3d(vec(b), vec(p), color)
            else:
                b = mark['end']
                corners = (a, [b[0], a[1]], b, [a[0], b[1]])
                for p, q in zip(corners, corners[1:]+corners[:1]):
                    pr.draw_line_3d(vec(p), vec(q), color)
        for obj in self.scene.document['objects']:
            if obj['kind']=='enemy_spawn':
                pr.draw_cube_wires(vec(obj['position']),6,28,6,pr.Color(220,96,83,255))
            elif obj['kind']=='encounter':
                a,b=obj['position'],obj['end']
                corners=(a,[b[0],a[1]],b,[a[0],b[1]])
                for p,q in zip(corners,corners[1:]+corners[:1]):pr.draw_line_3d(vec(p),vec(q),pr.SKYBLUE)
        obj = self.scene.get(self.selected)
        if obj:
            pr.draw_cube_wires(vec(obj['position']), 9, 6, 9, pr.YELLOW)
        if self.pending:
            pr.draw_cube_wires(vec(self.pending['position'] if isinstance(self.pending,dict) else self.pending), 4, 4, 4, COLORS[self.color])

    def draw_overlay(self, camera, tm, assets):
        # Native-resolution editor text remains legible over the PS1 viewport.
        def projected(point, height=1.):
            x, z = point
            p = pr.get_world_to_screen_ex(pr.Vector3(x, structure.floor_height(tm, x, z)+height, z), camera, 480, 270)
            return pr.Vector2(p.x*VIEW_SCALE, p.y*VIEW_SCALE+VIEW_TOP)
        pr.begin_scissor_mode(0, int(VIEW_TOP), 1140, int(270*VIEW_SCALE))
        # Markup remains visible over geometry in either camera view.
        for mark in self.scene.document['marks']:
            color = COLORS[mark.get('color', 0) % len(COLORS)]
            a = mark['position']
            if mark['kind'] == 'note':
                pr.draw_circle_v(projected(a), 4, color)
            elif mark['kind'] == 'arrow':
                b = mark['end']
                pr.draw_line_ex(projected(a), projected(b), 2, color)
                angle = math.atan2(b[1]-a[1], b[0]-a[0])
                for offset in (-.5, .5):
                    end = [b[0]-6*math.cos(angle+offset), b[1]-6*math.sin(angle+offset)]
                    pr.draw_line_ex(projected(b), projected(end), 2, color)
            else:
                b = mark['end']
                corners = (a, [b[0], a[1]], b, [a[0], b[1]])
                for p, q in zip(corners, corners[1:]+corners[:1]):
                    pr.draw_line_ex(projected(p), projected(q), 2, color)
        for mark in self.scene.document['marks']:
            p = projected(mark['position'], 5)
            if 0 <= p.x < 1120 and VIEW_TOP <= p.y < 750:
                label = self.edit_text if mark['id'] == self.selected and self.edit_text is not None else mark.get('text', '')
                if label:
                    label = label[:80]
                    pr.draw_rectangle(int(p.x)-4, int(p.y)-3, min(900, int(text.width(assets, label))+8), 22, pr.Color(10, 16, 24, 225))
                    text.draw(assets, label, p.x, p.y, COLORS[mark.get('color', 0) % len(COLORS)])
        selected = self.scene.get(self.selected)
        for obj in self.scene.document['objects']:
            if obj['kind'] in ('enemy_spawn','encounter','gate'):
                p=projected(obj['position'],5)
                if 0<=p.x<1100 and VIEW_TOP<=p.y<750:
                    text.draw(assets,obj['label']+' / '+obj['group'],p.x+8,p.y,pr.SKYBLUE)
        if selected:
            p = projected(selected['position'])
            pr.draw_circle_lines(int(p.x), int(p.y), 12, pr.YELLOW)
        spawn=projected(self.scene.document['spawn'])
        pr.draw_circle_lines(int(spawn.x),int(spawn.y),10,pr.GREEN)
        pr.draw_text('Spawn',int(spawn.x)+13,int(spawn.y)-7,14,pr.GREEN)
        preview=None
        if self.tool==5 and self.hover:
            preview=layout.rectangle(self.floor_drag['start'] if self.floor_drag else self.hover,self.hover)
        elif self.tool==6 and self.pending and self.hover:
            preview=layout.rectangle(self.pending['position'],self.hover)
        if preview:
            x0,z0,x1,z1=preview
            height=self.floor_height if self.material!='water' or self.tool==6 else 0.
            corners=[]
            for x,z in ((x0,z0),(x1,z0),(x1,z1),(x0,z1)):
                p=pr.get_world_to_screen_ex(pr.Vector3(x,height+.7,z),camera,480,270)
                corners.append(pr.Vector2(p.x*VIEW_SCALE,p.y*VIEW_SCALE+VIEW_TOP))
            for a,b in zip(corners,corners[1:]+corners[:1]):pr.draw_line_ex(a,b,3,pr.YELLOW)
            pr.draw_text(f'{x1-x0:.0f} x {z1-z0:.0f} | height {height:g}',int(corners[0].x)+4,int(corners[0].y)-20,14,pr.YELLOW)
        if self.tool==6:
            for stairs in self.scene.document['layout']['stairs']:
                x0,z0,x1,z1=stairs['bounds']
                a=projected([(x0+x1)/2,(z0+z1)/2])
                pr.draw_text('Stairs '+stairs['axis'],int(a.x)-24,int(a.y),14,pr.SKYBLUE)
        pr.end_scissor_mode()
        pr.draw_rectangle(1140, 0, 300, 810, pr.Color(13, 20, 30, 245))
        pr.draw_text('LEVEL EDITOR', 1156, 20, 20, pr.RAYWHITE)
        pr.draw_text(('Unsaved edits' if self.scene.dirty else 'Scene saved') + ' | simulation paused', 1156, 50, 14, pr.YELLOW if self.scene.dirty else pr.GRAY)
        for i, label in enumerate(TOOLS):
            y = TOOL_TOP+i*TOOL_ROW
            if i == self.tool:
                pr.draw_rectangle(1148, y, 282, TOOL_ROW-2, pr.Color(48, 65, 80, 255))
            pr.draw_text(f'{i+1}  {label}', 1160, y+4, 16, pr.RAYWHITE)
        heading='Floor material:' if self.tool==5 else 'Stairs rise toward:' if self.tool==6 else 'Spawn placement' if self.tool==7 else 'Place an object:'
        if self.tool==8:heading='Click two corners; name the group.'
        pr.draw_text(heading,1156,314,16,pr.GRAY)
        if self.tool==5:
            entries=FLOOR_LABELS
            active=layout.MATERIALS.index(self.material)
        elif self.tool==6:
            entries=('Map right (+X)','Map down (+Z)','Map left (-X)','Map up (-Z)')
            active=layout.AXES.index(self.stair_axis)
        elif self.tool in (7,8):
            entries=('Click a clear walkable spot.',) if self.tool==7 else ('Same group links trigger,','enemy spawns and gates.')
            active=-1
        else:
            entries=[o['label'][:26] for o in self.palette[self.palette_scroll:self.palette_scroll+10]]
            active=self.palette_index-self.palette_scroll
        for i,label in enumerate(entries):
            y=PALETTE_TOP+i*PALETTE_ROW
            if i==active:pr.draw_rectangle(1148,y,282,PALETTE_ROW-1,pr.Color(48,65,80,255))
            pr.draw_text(label,1160,y+3,14,pr.RAYWHITE)
        if self.tool<5 and len(self.palette)>10:pr.draw_text('Wheel over palette: more objects',1156,550,14,pr.GRAY)
        if self.tool==8:
            pr.draw_text('Enter: edit a selected group',1156,458,14,pr.RAYWHITE)
            pr.draw_text('F4: reset encounters, HP and pistol',1156,484,14,pr.RAYWHITE)
            pr.draw_text('Q/E: turn a selected gate 90 deg',1156,506,14,pr.RAYWHITE)
        if self.tool in (5,6):
            label='Upper landing' if self.tool==6 else 'Wall base' if self.material=='wall' else 'Floor'
            pr.draw_text(f'{label} height: {self.floor_height:g}',1156,474,16,pr.YELLOW)
            pr.draw_text('[ / ]: height - / + 4 units',1156,498,14,pr.RAYWHITE)
            pr.draw_text('V: grain '+self.grain if self.tool==5 else 'V: cycle stair direction',1156,520,14,pr.RAYWHITE)
            pr.draw_text('Drag a rectangle to build.' if self.tool==5 else 'Click low corner, then high corner.',1156,542,14,pr.RAYWHITE)
            pr.draw_text('Right drag: erase | Alt+click: sample' if self.tool==5 else 'Right click: remove a stair flight',1156,564,14,pr.RAYWHITE)
        obj = self.scene.get(self.selected)
        y=584
        if obj:
            text.draw(assets, obj.get('label', obj['kind'])[:28], 1156, y, pr.YELLOW)
            pr.draw_text(f"X {obj['position'][0]:.0f}  Z {obj['position'][1]:.0f}", 1156, y+22, 14, pr.RAYWHITE)
            if obj['kind'] in ('enemy_spawn','encounter','gate'):text.draw(assets,'Enter: edit group',1156,y+40,pr.SKYBLUE)
        pr.draw_text('C: overhead / game camera', 1156, y+60, 14, pr.RAYWHITE)
        pr.draw_text('WASD: pan | wheel: zoom', 1156, y+80, 14, pr.RAYWHITE)
        if self.tool<5:
            pr.draw_text('Drag / arrows: move | Q/E: rotate',1156,y+100,14,pr.RAYWHITE)
            pr.draw_text('G: snap '+('ON' if self.snap else 'OFF')+' | Shift: fine | K: colour',1156,y+120,14,pr.RAYWHITE)
            pr.draw_text('Ctrl+D: duplicate | Delete: remove',1156,y+140,14,pr.RAYWHITE)
        else:
            pr.draw_text('Floor edges snap to 16 units.',1156,y+100,14,pr.RAYWHITE)
            pr.draw_text('J: edge rails '+('ON' if self.scene.document['layout']['rails'] else 'OFF'),1156,y+120,14,pr.RAYWHITE)
            pr.draw_text('Esc: cancel / return to Select',1156,y+140,14,pr.RAYWHITE)
        pr.draw_text('Ctrl+Z/Y: undo/redo | Enter: edit',1156,y+160,14,pr.RAYWHITE)
        pr.draw_text('Ctrl+S: save | Ctrl+O: reload | F2: play',1156,y+180,14,pr.RAYWHITE)
        if self.edit_text is not None:
            pr.draw_rectangle(18, 718, 1104, 70, pr.Color(13, 20, 30, 250))
            pr.draw_text(('ENCOUNTER GROUP' if self.edit_field=='group' else 'DESIGN NOTE')+' | Enter: finish | Esc: cancel', 30, 728, 16, pr.YELLOW)
            text.draw(assets, self.edit_text[-110:]+'_', 30, 755)
        if self.status:
            pr.draw_text(self.status[:130], 18, 18, 16, pr.YELLOW)


def gameplay_camera(gameplay):
    shot = gameplay.walk.director.shot
    return pr.Camera3D(pr.Vector3(*shot['eye']), pr.Vector3(*shot['target']),
                       pr.Vector3(0, 1, 0), shot['span'], pr.CAMERA_ORTHOGRAPHIC)
