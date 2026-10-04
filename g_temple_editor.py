"""Small in-game placement/markup editor over the shared temple scene document."""
from copy import deepcopy
import math

import pyray as pr
import g_narrative_text as text
import g_temple_structure as structure
from g_temple_scene import PROP_LABELS, prop_origin

TOOLS = ('Select', 'Place', 'Note', 'Arrow', 'Area')
COLORS = (pr.Color(242, 191, 83, 255), pr.Color(99, 202, 239, 255), pr.Color(238, 112, 111, 255))
VIEW_SCALE = 1140 / 480
VIEW_TOP = (810 - 270 * VIEW_SCALE) / 2


def ground_point(eye, target, up, span, screen, floor):
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
    for height in (0., 16., 18., 20., 22., 24., 16/6, 32/6, 8., 64/6, 80/6):
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
        self.status = ''
        self.palette_index = 0
        self.palette = [dict(kind='key', label='Brass key', rotation=0, group='temple'),
                        dict(kind='medicine', label='Medicine', rotation=0),
                        dict(kind='inscription', label='Inscription', rotation=0, description='old_inscription')]
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
        if not obj or obj['kind'] not in ('note', 'arrow', 'area'):
            return
        self.text_before = self.scene.checkpoint()
        self.edit_text = obj.get('text', '')
        self.selected = identity

    def finish_text(self, cancel=False):
        if self.edit_text is not None:
            if not cancel:
                self.scene.get(self.selected)['text'] = self.edit_text
                self.scene.commit(self.text_before)
            self.edit_text = None
            self.text_before = None

    def toggle(self, gameplay):
        self.finish_text()
        if self.drag:
            self.scene.commit(self.drag['before'])
            self.drag = None
        self.pending = None
        self.active = not self.active
        if self.active:
            self.focus = [gameplay.walk.x, gameplay.walk.y]
        gameplay.apply_scene()
        if not self.active:
            gameplay.ensure_clear_position()

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
            if kind in ('note', 'arrow', 'area'):
                points = [obj['position']]
                if kind == 'arrow':
                    points.append(obj['end'])
                elif kind == 'area':
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
                                        'inscription': (9, 2, 7), 'door': (32, 4, 24)}[kind]
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
                self.finish_text()
            if pr.is_key_pressed(pr.KEY_ESCAPE):
                self.finish_text(cancel=True)
            return
        changed = False
        try:
            if control:
                if pr.is_key_pressed(pr.KEY_S):
                    scene.save()
                    self.status = 'Scene saved.'
                if pr.is_key_pressed(pr.KEY_O):
                    scene.reload()
                    self.selected = None
                    changed = True
                    self.status = 'Scene reloaded; Ctrl+Z restores previous edits.'
                if pr.is_key_pressed(pr.KEY_Z):
                    changed = scene.undo()
                if pr.is_key_pressed(pr.KEY_Y):
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
                for i, key in enumerate((pr.KEY_ONE, pr.KEY_TWO, pr.KEY_THREE, pr.KEY_FOUR, pr.KEY_FIVE)):
                    if pr.is_key_pressed(key):
                        self.tool, self.pending = i, None
                if self.overhead:
                    self.focus[0] = max(0, min(896, self.focus[0] +
                        (int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A)))*self.span*dt))
                    self.focus[1] = max(0, min(640, self.focus[1] +
                        (int(pr.is_key_down(pr.KEY_S))-int(pr.is_key_down(pr.KEY_W)))*self.span*dt))
                    self.span = max(60, min(640, self.span-pr.get_mouse_wheel_move()*16))
                if pr.is_key_pressed(pr.KEY_ESCAPE):
                    self.tool, self.pending = 0, None
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
                    obj['rotation'] = (obj.get('rotation', 0)+15*
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
                if pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT):
                    if 80 <= mouse.y < 80+len(TOOLS)*30:
                        self.tool = int((mouse.y-80)//30)
                        self.pending = None
                    if 290 <= mouse.y < 290+len(self.palette)*24:
                        self.palette_index = int((mouse.y-290)//24)
                        self.tool = 1
            else:
                # Camera may have changed from panning or toggling this frame.
                camera = self.camera(gameplay_camera(gameplay))
                coordinates = (mouse.x/VIEW_SCALE, (mouse.y-VIEW_TOP)/VIEW_SCALE)
                values = lambda v: (v.x, v.y, v.z)
                p = ground_point(values(camera.position), values(camera.target), values(camera.up),
                    camera.fovy, coordinates, lambda x, z: structure.floor_height(gameplay.arena['tile_map'], x, z)) if 0 <= coordinates[1] < 270 else None
                if p and pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT):
                    p = self.snapped(p)
                    if self.tool == 0:
                        self.selected = self.pick(camera, coordinates, gameplay.arena['tile_map'])
                        obj = scene.get(self.selected)
                        if obj and obj['kind'] != 'door':
                            self.drag = dict(before=scene.checkpoint(), position=list(obj['position']),
                                end=list(obj['end']) if 'end' in obj else None, mouse=p)
                    elif self.tool == 1:
                        self.selected = scene.add(dict(deepcopy(self.palette[self.palette_index]), position=p))
                        changed = True
                    elif self.tool == 2:
                        self.selected = scene.add(dict(kind='note', position=p, text='', color=self.color), markup=True)
                        self.begin_text(self.selected)
                        changed = True
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
        obj = self.scene.get(self.selected)
        if obj:
            pr.draw_cube_wires(vec(obj['position']), 9, 6, 9, pr.YELLOW)
        if self.pending:
            pr.draw_cube_wires(vec(self.pending), 4, 4, 4, COLORS[self.color])

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
        if selected:
            p = projected(selected['position'])
            pr.draw_circle_lines(int(p.x), int(p.y), 12, pr.YELLOW)
        pr.end_scissor_mode()
        pr.draw_rectangle(1140, 0, 300, 810, pr.Color(13, 20, 30, 245))
        pr.draw_text('LEVEL PLACEMENT', 1156, 20, 20, pr.RAYWHITE)
        pr.draw_text(('Unsaved edits' if self.scene.dirty else 'Scene saved') + ' | simulation paused', 1156, 50, 14, pr.YELLOW if self.scene.dirty else pr.GRAY)
        for i, label in enumerate(TOOLS):
            y = 80+i*30
            if i == self.tool:
                pr.draw_rectangle(1148, y, 282, 28, pr.Color(48, 65, 80, 255))
            pr.draw_text(f'{i+1}  {label}', 1160, y+6, 16, pr.RAYWHITE)
        pr.draw_text('Place an object:', 1156, 260, 16, pr.GRAY)
        for i, obj in enumerate(self.palette):
            if i == self.palette_index:
                pr.draw_rectangle(1148, 290+i*24, 282, 23, pr.Color(48, 65, 80, 255))
            pr.draw_text(obj['label'][:26], 1160, 294+i*24, 14, pr.RAYWHITE)
        obj = self.scene.get(self.selected)
        y = max(590, 300+len(self.palette)*24)
        if obj:
            text.draw(assets, obj.get('label', obj['kind'])[:28], 1156, y, pr.YELLOW)
            pr.draw_text(f"X {obj['position'][0]:.0f}  Z {obj['position'][1]:.0f}", 1156, y+22, 14, pr.RAYWHITE)
        pr.draw_text('C: overhead / game camera', 1156, y+48, 14, pr.RAYWHITE)
        pr.draw_text('WASD: pan | wheel: zoom', 1156, y+68, 14, pr.RAYWHITE)
        pr.draw_text('Drag / arrows: move | Q/E: rotate', 1156, y+88, 14, pr.RAYWHITE)
        pr.draw_text('G: snap '+('ON' if self.snap else 'OFF')+' | Shift: fine | K: colour', 1156, y+108, 14, pr.RAYWHITE)
        pr.draw_text('Ctrl+D: duplicate | Delete: remove', 1156, y+128, 14, pr.RAYWHITE)
        pr.draw_text('Ctrl+Z/Y: undo/redo | Enter: note', 1156, y+148, 14, pr.RAYWHITE)
        pr.draw_text('Ctrl+S: save | Ctrl+O: reload | F2: play', 1156, y+168, 14, pr.RAYWHITE)
        if self.edit_text is not None:
            pr.draw_rectangle(18, 718, 1104, 70, pr.Color(13, 20, 30, 250))
            pr.draw_text('DESIGN NOTE | Enter: finish | Esc: cancel', 30, 728, 16, pr.YELLOW)
            text.draw(assets, self.edit_text[-110:]+'_', 30, 755)
        if self.status:
            pr.draw_text(self.status[:130], 18, 18, 16, pr.YELLOW)


def gameplay_camera(gameplay):
    shot = gameplay.walk.director.shot
    return pr.Camera3D(pr.Vector3(*shot['eye']), pr.Vector3(*shot['target']),
                       pr.Vector3(0, 1, 0), shot['span'], pr.CAMERA_ORTHOGRAPHIC)
