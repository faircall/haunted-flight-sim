"""Opt-in, read-only object pointing shared by the native 3D tools.

F8 pauses the host scene; clicks publish codex_selection.json in the repository.
Nothing in this module edits a scene, asset, camera document or save game.
Raylib is imported lazily so the record/ray helpers also work without a window.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import itertools
import json
import math
import os
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
DEFAULT_PATH = ROOT / 'codex_selection.json'
MAX_SELECTION = 64


def vector(value):
    if hasattr(value, 'x'):
        return [float(value.x), float(value.y), float(value.z)]
    return [float(v) for v in value]


def relative_path(path):
    if not path:
        return None
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def rectangle(value):
    if hasattr(value, 'width'):
        return (float(value.x), float(value.y), float(value.width), float(value.height))
    return tuple(float(v) for v in value)


def contains(rect, point):
    x, y, w, h = rectangle(rect)
    return w > 0 and h > 0 and x <= point[0] < x+w and y <= point[1] < y+h


def camera_record(camera):
    return dict(position=vector(camera.position), target=vector(camera.target),
                up=vector(camera.up), fovy=float(camera.fovy), projection=int(camera.projection))


def screen_ray(camera, point, viewport):
    """Perspective/orthographic ray through the displayed viewport, not its UI."""
    if not contains(viewport, point):
        return None
    c = camera if isinstance(camera, dict) else camera_record(camera)
    def unit(v):
        length = math.sqrt(sum(x*x for x in v))
        if length < 1e-10:
            raise ValueError('Degenerate selection camera')
        return tuple(x/length for x in v)
    def cross(a, b):
        return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    eye = c['position']
    forward = unit(tuple(b-a for a, b in zip(eye, c['target'])))
    right = unit(cross(forward, c['up']))
    up = cross(right, forward)
    x, y, w, h = rectangle(viewport)
    sx, sy = (2*(point[0]-x)/w-1)*w/h, 1-2*(point[1]-y)/h
    span = c['fovy']*.5 if c['projection'] == 1 else math.tan(math.radians(c['fovy'])*.5)
    offset = tuple((right[i]*sx+up[i]*sy)*span for i in range(3))
    if c['projection'] == 1:
        return tuple(eye[i]+offset[i] for i in range(3)), forward
    return tuple(eye), unit(tuple(forward[i]+offset[i] for i in range(3)))


def atomic_write(path, record):
    """Readers see either the last complete selection or the new complete one."""
    path = Path(path)
    encoded = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         prefix=path.name+'.', suffix='.tmp', dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def compose_transform(model, position=(0, 0, 0), scale=1., yaw=0., axis=(0, 1, 0)):
    """Match DrawModelEx, including the model's imported root transform."""
    import pyray as pr
    scale = (scale,)*3 if isinstance(scale, (int, float)) else scale
    matrix = pr.matrix_multiply(model.transform, pr.matrix_scale(*scale))
    matrix = pr.matrix_multiply(matrix, pr.matrix_rotate(pr.Vector3(*axis), math.radians(yaw)))
    return pr.matrix_multiply(matrix, pr.matrix_translate(*position))


def matrix_values(matrix):
    return [float(getattr(matrix, 'm'+str(i))) for i in range(16)]


def transformed_bounds(bounds, matrix):
    import pyray as pr
    points = [vector(pr.vector3_transform(pr.Vector3(*p), matrix))
              for p in itertools.product(*zip(vector(bounds.min), vector(bounds.max)))]
    return {'min': [min(p[i] for p in points) for i in range(3)],
            'max': [max(p[i] for p in points) for i in range(3)]}


class SelectionSession:
    def __init__(self, scene_id, source_file, output_path=None):
        self.scene_id = str(scene_id)
        self.source_file = relative_path(source_file)
        self.output_path = Path(output_path) if output_path else DEFAULT_PATH
        self.session_id = uuid.uuid4().hex
        self.enabled = False
        self.selected = []
        self.instances = []
        self.context = {}
        self.camera = None
        self.viewport = None
        self.status = ''
        self.error = None
        self._bounds = {}
        self._dirty = False
        self._cursor_hidden = False
        self._last_camera = None

    def set_enabled(self, enabled):
        import pyray as pr
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        if enabled:
            self._bounds.clear()
            self._cursor_hidden = bool(pr.is_cursor_hidden())
            pr.enable_cursor()
        elif self._cursor_hidden:
            pr.disable_cursor()
        else:
            pr.enable_cursor()
        self.enabled = enabled
        self._dirty = True
        self.status = 'Click an object to identify it.' if enabled else 'Selection retained for Codex.'
        if not enabled:
            self.save()

    def handle_keys(self):
        """True means normal Escape/exit, after giving selection mode first use."""
        import pyray as pr
        if pr.is_key_pressed(pr.KEY_F8):
            self.set_enabled(not self.enabled)
            return False
        if pr.is_key_pressed(pr.KEY_ESCAPE):
            if self.enabled:
                self.set_enabled(False)
                return False
            return True
        if self.enabled and pr.is_key_pressed(pr.KEY_BACKSPACE):
            self.clear()
        return False

    def begin_frame(self):
        self.instances.clear()

    def register_model(self, model, model_name, asset_path=None, position=(0, 0, 0),
                       scale=1., yaw=0., axis=(0, 1, 0), transform=None,
                       identity=None, metadata=None):
        if not self.enabled or not model.meshCount:
            return
        import pyray as pr
        matrix = transform if transform is not None else compose_transform(model, position, scale, yaw, axis)
        # Retain a value, not a borrowed Matrix field that a renderer restores.
        matrix = pr.ffi.new('Matrix *', matrix)[0]
        key = (int(pr.ffi.cast('uintptr_t', model.meshes)), int(model.meshCount))
        if key not in self._bounds:
            # GetModelBoundingBox already applies model.transform. Keep raw mesh
            # bounds here, then transform all eight corners exactly once below.
            boxes = [pr.get_mesh_bounding_box(model.meshes[i]) for i in range(model.meshCount)]
            low = [min(vector(box.min)[i] for box in boxes) for i in range(3)]
            high = [max(vector(box.max)[i] for box in boxes) for i in range(3)]
            self._bounds[key] = pr.BoundingBox(pr.Vector3(*low), pr.Vector3(*high))
        metadata = dict(metadata or {})
        bounds = metadata.get('world_bounds') or transformed_bounds(self._bounds[key], matrix)
        values = matrix_values(matrix)
        asset = relative_path(asset_path)
        digest = hashlib.sha1(json.dumps([str(model_name), asset, [round(v, 5) for v in values]],
                                        separators=(',', ':')).encode()).hexdigest()[:14]
        self.instances.append(dict(model=model, matrix=matrix, model_name=str(model_name),
                                   asset_path=asset, bounds=bounds, transform=values,
                                   instance_id=str(model_name)+':'+digest,
                                   identity=str(identity) if identity is not None else None,
                                   metadata=metadata))

    def pick_ray(self, origin, direction):
        """Exact nearest mesh hit; only animated GPU actors use labelled bounds."""
        import pyray as pr
        ray = pr.Ray(pr.Vector3(*origin), pr.Vector3(*direction))
        candidates = []
        for item in self.instances:
            if item['metadata'].get('pickable') is False:
                continue
            box = item['bounds']
            collision = pr.get_ray_collision_box(ray, pr.BoundingBox(pr.Vector3(*box['min']), pr.Vector3(*box['max'])))
            if collision.hit:
                # A ray starting inside a box has zero lower bound even if the
                # native box query returns its farther exit face.
                inside = all(a <= p <= b for p, a, b in zip(origin, box['min'], box['max']))
                candidates.append((0. if inside else max(0., float(collision.distance)), item, collision))
        nearest = None
        distance = math.inf
        for lower, item, box_hit in sorted(candidates, key=lambda c: c[0]):
            if lower > distance:
                continue
            animated = item['metadata'].get('animated', False)
            model = item['model']
            hits = [(None, box_hit)] if animated else (
                (i, self._mesh_hit(ray, model.meshes[i], item)) for i in range(model.meshCount))
            for mesh_index, collision in hits:
                if not collision.hit or collision.distance < 0 or collision.distance >= distance:
                    continue
                point = vector(collision.point)
                # Main renderers can reject shader-discarded portions of shared
                # source geometry, e.g. the old causeway beyond the canal join.
                reject = item['metadata'].get('_reject_hit')
                if reject and reject(point):
                    continue
                distance = float(collision.distance)
                nearest = {k: v for k, v in item.items() if k not in ('model', 'matrix', 'identity')}
                nearest['metadata'] = {k: v for k, v in item['metadata'].items() if not k.startswith('_')}
                nearest.update(hit_position=point, hit_normal=vector(collision.normal),
                               distance=distance, mesh_index=mesh_index,
                               pick_method='animated_bounds' if animated else 'mesh_triangles')
                nearest['id'] = item['identity'] or item['instance_id']
                nearest['label'] = item['metadata'].get('label', item['model_name'].replace('_', ' '))
                nearest['kind'] = item['metadata'].get('kind', 'model')
                nearest['source'] = dict(file=self.source_file, asset=item['asset_path'])
                nearest['selection_scope'] = 'object' if item['identity'] else 'model_instance'
                if item['identity']:
                    # Authored objects can be split into material batches.
                    # One selection highlights all of that object's pieces.
                    parts = [obj['bounds'] for obj in self.instances if obj['identity'] == item['identity']]
                    nearest['bounds'] = {'min': [min(b['min'][i] for b in parts) for i in range(3)],
                                         'max': [max(b['max'][i] for b in parts) for i in range(3)]}
                if not item['identity']:
                    from codex_scene_objects import resolve_hit
                    resolved = resolve_hit(self.scene_id, nearest)
                    if resolved:
                        nearest.update(resolved)
                        nearest['selection_scope'] = 'object'
                    elif max(b-a for a, b in zip(item['bounds']['min'], item['bounds']['max'])) > 25:
                        # A merged terrain batch has no editable object ID. Keep
                        # an honest surface marker, not a city-wide highlight.
                        nearest['selection_scope'] = 'surface'
                        nearest['id'] += ':at:'+','.join(str(round(v, 2)) for v in point)
                        nearest['label'] += ' (surface)'
        return nearest

    @staticmethod
    def _mesh_hit(ray, mesh, item):
        """Continue through shader-discarded faces in the same merged mesh."""
        import pyray as pr
        reject = item['metadata'].get('_reject_hit')
        collision = pr.get_ray_collision_mesh(ray, mesh, item['matrix'])
        if not reject:
            return collision
        direction = vector(ray.direction)
        origin = vector(ray.position)
        advanced = 0.
        # Each step moves past the rejected face; the bound also prevents bad
        # coplanar source geometry from making a click stall indefinitely.
        for _ in range(64):
            if not collision.hit:
                return collision
            point = vector(collision.point)
            if not reject(point):
                collision.distance += advanced
                return collision
            advanced = sum((point[i]-origin[i])*direction[i] for i in range(3)) + .0002
            next_origin = pr.Vector3(*(origin[i]+direction[i]*advanced for i in range(3)))
            collision = pr.get_ray_collision_mesh(pr.Ray(next_origin, ray.direction), mesh, item['matrix'])
        collision.hit = False
        return collision

    def select_hit(self, hit, additive=False):
        if hit is None:
            if not additive:
                self.selected.clear()
            self.status = 'No object at that point.'
        elif additive:
            existing = next((i for i, obj in enumerate(self.selected) if obj['id'] == hit['id']), None)
            if existing is not None:
                self.selected.pop(existing)
            elif len(self.selected) < MAX_SELECTION:
                self.selected.append(hit)
            else:
                self.status = f'Selection limit: {MAX_SELECTION} objects.'
                return
            self.status = f'{len(self.selected)} selected.'
        else:
            self.selected = [hit]
            self.status = hit['label']
        self._dirty = True
        self.save()

    def clear(self):
        self.selected.clear()
        self.status = 'Selection cleared.'
        self._dirty = True

    def record(self):
        return dict(schema_version=1, updated_at=datetime.now(timezone.utc).isoformat(),
                    session_id=self.session_id, process_id=os.getpid(), scene=self.scene_id,
                    mode_enabled=self.enabled, source_file=self.source_file,
                    camera=self.camera, viewport=self.viewport, context=self.context,
                    selected=self.selected)

    def save(self):
        if not self._dirty:
            return True
        try:
            atomic_write(self.output_path, self.record())
        except (OSError, TypeError, ValueError) as exc:
            self.error = 'Selection could not be saved: '+str(exc)
            return False
        self._dirty = False
        self.error = None
        return True

    def present(self, camera, viewport, context=None):
        import pyray as pr
        viewport = rectangle(viewport)
        x, y, w, h = viewport
        if not self.enabled:
            pr.draw_text('F8  Codex select', int(x+w-158), int(y+12), 14, pr.Color(180, 205, 195, 230))
            return
        self.camera = camera_record(camera)
        self._last_camera = camera
        self.viewport = list(viewport)
        self.context = dict(context or {})
        mouse = pr.get_mouse_position()
        point = (mouse.x, mouse.y)
        panel = (x+10, y+10, min(560., w-20), 76)
        if pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT) and not contains(panel, point):
            ray = screen_ray(self.camera, point, viewport)
            if ray:
                additive = pr.is_key_down(pr.KEY_LEFT_SHIFT) or pr.is_key_down(pr.KEY_RIGHT_SHIFT)
                try:
                    self.select_hit(self.pick_ray(*ray), additive)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self.error = 'Cannot identify that object: '+str(exc)
        self.save()
        pr.begin_scissor_mode(int(x), int(y), max(1, int(w)), max(1, int(h)))
        ink = pr.Color(255, 196, 78, 255)
        forward = vector(pr.vector3_normalize(pr.vector3_subtract(camera.target, camera.position)))
        eye = vector(camera.position)
        def project(p):
            if sum((p[i]-eye[i])*forward[i] for i in range(3)) <= .02:
                return None
            screen = pr.get_world_to_screen_ex(pr.Vector3(*p), camera, int(w), int(h))
            return pr.Vector2(screen.x+x, screen.y+y)
        for index, item in enumerate(self.selected, 1):
            bounds = item['bounds']
            if item.get('selection_scope') != 'surface':
                corners = list(itertools.product(*zip(bounds['min'], bounds['max'])))
                points = [project(p) for p in corners]
                for a in range(8):
                    for bit in (1, 2, 4):
                        b = a ^ bit
                        if a < b and points[a] is not None and points[b] is not None:
                            pr.draw_line_ex(points[a], points[b], 1.4, ink)
            p = project(item['hit_position'])
            if p is not None:
                pr.draw_circle_lines(int(p.x), int(p.y), 7, ink)
                pr.draw_line(int(p.x)-10, int(p.y), int(p.x)+10, int(p.y), ink)
                pr.draw_line(int(p.x), int(p.y)-10, int(p.x), int(p.y)+10, ink)
                label = f'{index}. {item["label"]}'
                if len(label) > 58:
                    label = label[:55]+'...'
                px = max(x+4, min(x+w-220, p.x+12)); py = max(y+90, min(y+h-22, p.y-8))
                pr.draw_rectangle(int(px)-3, int(py)-2, min(420, pr.measure_text(label, 14)+6), 20, pr.Color(12, 20, 23, 220))
                pr.draw_text(label, int(px), int(py), 14, ink)
        pr.draw_rectangle_rec(pr.Rectangle(*panel), pr.Color(12, 20, 23, 242))
        pr.draw_text(f'CODEX SELECTION  |  PAUSED  |  {len(self.selected)} selected', int(x+20), int(y+18), 16, ink)
        pr.draw_text('Click select   Shift+click add/remove   Backspace clear', int(x+20), int(y+41), 14, pr.RAYWHITE)
        message = self.error or 'F8 / Esc resume  |  Saved to codex_selection.json'
        pr.draw_text(message[:88], int(x+20), int(y+64), 12, pr.Color(240, 135, 120, 255) if self.error else pr.Color(170, 200, 188, 255))
        pr.end_scissor_mode()

    def close(self):
        if self.enabled:
            self.set_enabled(False)
        else:
            self.save()
        self.instances.clear()
        self._bounds.clear()


if __name__ == '__main__':
    if DEFAULT_PATH.exists():
        print(DEFAULT_PATH.read_text(encoding='utf-8'))
    else:
        print('No selection yet. Press F8 in a supported 3D scene or editor, then click an object.')
