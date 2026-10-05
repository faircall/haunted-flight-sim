"""Saved blockout, objects and encounter definitions, with stable authoring IDs.

Graphics resources and playthrough progress remain outside the scene document.
"""
from copy import deepcopy
from pathlib import Path
import json
import math
import uuid
import g_temple_layout as layout

ROOT = Path(__file__).resolve().parent
SCENE_FILE = ROOT / 'art' / 'temple' / 'exploration.scene.json'
KINDS = {'prop', 'key', 'medicine', 'inscription', 'door', 'enemy_spawn', 'encounter', 'gate', 'ammo'}
PROP_LABELS = {'altar': 'Altar', 'banner': 'Banner', 'lantern_paper': 'Paper lantern',
               'lantern_porcelain': 'Porcelain lantern', 'pile54': 'Lantern post',
               'lily_cluster': 'Water lilies', 'lily_leaves': 'Lily leaves', 'brazier': 'Fire bowl'}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8',newline='\n')
    temporary.replace(path)


def prop_origin(identity, prop, records):
    """Shared physical origin for rendered and editor-picked temple props."""
    name = prop['asset'].removeprefix('baked:')
    p = prop['position']
    offset = prop.get('geometry_offset', (0, 0, 0))
    height = prop.get('base_height', 16) + offset[2]
    if identity == 'lantern:2':
        height = prop.get('base_height', 16) + records['pile54']['position_max'][2]
    elif identity == 'lantern:3':
        height = prop.get('base_height', 16) + records['pile54']['position_max'][2] - records[name]['position_max'][2]
    return p['x']+offset[0], height, p['y']+offset[1]


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('A scene position must contain [x, z].')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError('Scene positions must be finite numbers.')
    if not (0 <= value[0] < 896 and 0 <= value[1] < 640):
        raise ValueError('Scene position is outside the temple map.')
    return value


def validate(document):
    if not isinstance(document, dict) or not all(isinstance(document.get(k), list) for k in ('objects', 'marks')):
        raise ValueError('A scene needs object and markup arrays.')
    if document.get('version') != 1 or document.get('scene_id') != 'moonlit-temple':
        raise ValueError('Unsupported temple scene.')
    if 'layout' in document:layout.validate(document['layout'])
    point(document['spawn'])
    for collection, kinds in (('objects', KINDS), ('marks', {'note', 'arrow', 'area'})):
        if any(not isinstance(o, dict) or o.get('kind') not in kinds for o in document[collection]):
            raise ValueError('Invalid ' + collection + ' collection.')
    identities = set()
    for obj in document['objects'] + document['marks']:
        if not isinstance(obj, dict):
            raise ValueError('Scene objects must be records.')
        identity = obj['id']
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError('Scene IDs must be unique nonempty strings.')
        identities.add(identity)
        point(obj['position'])
        if obj['kind'] not in KINDS | {'note', 'arrow', 'area'}:
            raise ValueError('Unknown scene object: ' + str(obj['kind']))
        if obj['kind'] in ('arrow', 'area', 'encounter'):
            point(obj['end'])
        if obj['kind'] in ('note', 'arrow', 'area'):
            if not isinstance(obj.get('text', ''), str):
                raise ValueError('Markup text must be a string.')
            if not isinstance(obj.get('color', 0), int):
                raise ValueError('Markup colour must be an integer.')
        else:
            yaw = obj.get('rotation', 0)
            if not isinstance(yaw, (int, float)) or not math.isfinite(yaw):
                raise ValueError('Object rotation must be finite.')
            if obj['kind'] == 'prop' and (not isinstance(obj.get('template'), dict) or not obj['template'].get('asset', '').startswith('baked:')):
                raise ValueError('Props need an existing temple asset.')
            if obj['kind'] == 'prop' and obj['template']['asset'].removeprefix('baked:') not in PROP_LABELS:
                raise ValueError('Unknown decorative temple asset.')
            if not isinstance(obj.get('label'), str):
                raise ValueError('Exploration objects need a label.')
            if obj['kind'] == 'key' and not isinstance(obj.get('group'), str):
                raise ValueError('Keys need a door group.')
            if obj['kind'] in ('enemy_spawn','encounter','gate') and (not isinstance(obj.get('group'),str) or not obj['group'].strip() or len(obj['group'])>80):
                raise ValueError('Encounter objects need a group name (up to 80 characters).')
            if obj['kind']=='gate' and obj.get('rotation',0) not in (0,90,180,270):
                raise ValueError('Gates align to map directions (90-degree turns).')
            if obj['kind']=='encounter' and (obj['position'][0]==obj['end'][0] or obj['position'][1]==obj['end'][1]):
                raise ValueError('A trigger needs an area, not a line.')
            if obj['kind']=='encounter' and 'camera_offset' in obj:
                offset=obj['camera_offset'];span=obj.get('camera_span',140)
                if not isinstance(offset,list) or len(offset)!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in offset) or offset[1]<40 or math.hypot(offset[0],offset[2])<10 or not isinstance(span,(int,float)) or not 70<=span<=400:
                    raise ValueError('Invalid encounter camera.')
    doors = [o for o in document['objects'] if o['kind'] == 'door']
    if len(doors) != 1 or doors[0]['id'] != 'temple-entrance' or doors[0]['position'] != [480, 264] or doors[0].get('rotation', 0) != 0:
        raise ValueError('The temple entrance remains fixed in this placement milestone.')
    return document


def default_document(arena):
    objects = []
    for identity, prop in arena['entities']['lake_props'].items():
        if prop['kind'] in ('roof', 'rail', 'column'):
            continue
        if prop['kind'] == 'pile' and not identity.startswith('lantern-post:'):
            continue
        template = deepcopy(prop)
        template.pop('position', None)
        template.pop('base_height', None)
        template.pop('rotation_y', None)
        label = PROP_LABELS.get(prop['asset'].removeprefix('baked:'), prop['kind'].capitalize())
        if ':' in identity:
            label += ' (' + identity.split(':', 1)[1] + ')'
        objects.append(dict(id=identity, kind='prop', label=label, template=template,
                            position=[prop['position']['x'], prop['position']['y']],
                            rotation=prop.get('rotation_y', 0)))
    objects += [
        dict(id='temple-key', kind='key', label='Brass key', position=[352, 334], rotation=25, group='temple'),
        dict(id='bridge-medicine', kind='medicine', label='Medicine', position=[244, 342], rotation=0),
        dict(id='temple-entrance', kind='door', label='Temple door', position=[480, 264], rotation=0, group='temple'),
        dict(id='altar-inscription', kind='inscription', label='Altar inscription', position=[480, 236], rotation=0,
             description='old_inscription'),
    ]
    return validate(dict(version=1, scene_id='moonlit-temple', spawn=[256, 334], objects=objects, marks=[]))


class Scene:
    """One authoring document; a drag or text edit is a single undo operation."""
    def __init__(self, document, path=SCENE_FILE):
        self.document = json.loads(json.dumps(validate(document), allow_nan=False))
        self.document.setdefault('layout', json.loads(json.dumps(layout.default_layout())))
        self.path = Path(path)
        self.saved = deepcopy(self.document)
        self.undo_stack = []
        self.redo_stack = []

    @classmethod
    def load(cls, path=SCENE_FILE):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')), path)

    @property
    def dirty(self):
        return self.document != self.saved

    def get(self, identity):
        return next((o for o in self.document['objects'] + self.document['marks'] if o['id'] == identity), None)

    def checkpoint(self):
        return deepcopy(self.document)

    def commit(self, before):
        try:
            validate(self.document)
        except (ValueError, KeyError, TypeError):
            self.document = before
            raise
        if before != self.document:
            self.undo_stack.append(before)
            self.undo_stack = self.undo_stack[-100:]
            self.redo_stack.clear()
            return True
        return False

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.checkpoint())
        self.document = self.undo_stack.pop()
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.checkpoint())
        self.document = self.redo_stack.pop()
        return True

    def save(self):
        atomic_json(self.path, validate(self.document))
        self.saved = self.checkpoint()

    def reload(self):
        loaded = Scene.load(self.path).document
        before = self.checkpoint()
        self.document = loaded
        self.commit(before)
        self.saved = self.checkpoint()

    def add(self, obj, markup=False):
        before = self.checkpoint()
        obj = json.loads(json.dumps(obj, allow_nan=False))
        obj['id'] = obj.get('id', 'placed:' + uuid.uuid4().hex)
        self.document['marks' if markup else 'objects'].append(obj)
        self.commit(before)
        return obj['id']

    def duplicate(self, identity):
        obj = self.get(identity)
        if not obj or obj['kind'] == 'door':
            return None
        obj = deepcopy(obj)
        obj.pop('id')
        # Keep duplicate inside map bounds, including markup endpoints.
        dx = 4 if max(obj['position'][0], obj.get('end', [0, 0])[0]) < 890 else -4
        obj['position'][0] += dx
        if 'end' in obj:
            obj['end'][0] += dx
        return self.add(obj, obj['kind'] in ('note', 'arrow', 'area'))

    def delete(self, identity):
        obj = self.get(identity)
        if not obj or obj['kind'] == 'door':
            return False
        before = self.checkpoint()
        for collection in ('objects', 'marks'):
            self.document[collection][:] = [o for o in self.document[collection] if o['id'] != identity]
        return self.commit(before)
