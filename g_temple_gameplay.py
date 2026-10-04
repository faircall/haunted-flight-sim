"""Exploration controller using the original game's inventory and puzzle rules.

Rendering, UI resources and audio voices remain outside save data. The camera
walker is an adapter: player_info.position is updated every movement frame.
"""
from copy import deepcopy
from pathlib import Path
import json
import math

import g_update_and_render as game
import g_interactions as interactions
import g_inventory as inventory
import g_puzzles as puzzles
import g_night
import g_audio
import g_temple_cameras as cameras
import g_temple_structure as structure
from g_temple_scene import atomic_json, point
from photo_asset_pipeline.temple3d.living.gait import SETTINGS

SAVE_FILE = Path(__file__).resolve().parent / 'saved_editor_states' / 'temple3d-progress.json'


class Exploration:
    def __init__(self, arena, scene, assets=None):
        self.scene = scene
        self.assets = assets if assets is not None else {}
        self.arena = interactions.ensure(puzzles.ensure_arena(arena))
        self.walk = cameras.Walkthrough(*scene.document['spawn'])
        self.static_props = {k: deepcopy(p) for k, p in arena['entities']['lake_props'].items()
                             if p['kind'] in ('roof', 'rail', 'column')}
        self.static_emitters = deepcopy(arena['entities']['emitters'])
        self.collected = set()
        self.clock = 0.
        self.travel = 0.
        self.paused = False
        self.footsteps = []
        self.apply_scene()
        self.set_position(self.walk.x, self.walk.y)

    @property
    def player(self):
        return self.arena['player_info']

    @property
    def modal(self):
        return self.arena['interaction_runtime']['modal']

    def set_position(self, x, z):
        self.walk.x, self.walk.y = float(x), float(z)
        self.walk.director.update(x, z)
        self.walk.intent = cameras.MovementIntent()
        self.walk.moving = False
        self.player['position'] = dict(game.get_tile_index_and_offset_from_pos(dict(x=x, y=z), self.arena['tile_map']), z=0.)
        self.player.pop('audio_step_state', None)
        g_audio.update_actor_footstep_travel(self.player, dict(x=x, y=z), SETTINGS['walk']['stride']/2, 'player', 'player')

    def sync_position(self):
        self.player['position'].update(game.get_tile_index_and_offset_from_pos(
            dict(x=self.walk.x, y=self.walk.y), self.arena['tile_map']))

    def ensure_clear_position(self):
        if self.can_walk(self.walk.x, self.walk.y):
            return
        for origin in ((self.walk.x, self.walk.y), self.scene.document['spawn']):
            for radius in range(2, 66, 2):
                for angle in range(0, 360, 15):
                    a = math.radians(angle)
                    x, z = origin[0]+radius*math.cos(a), origin[1]+radius*math.sin(a)
                    if self.can_walk(x, z):
                        self.set_position(x, z)
                        return
        raise ValueError('No clear player position near the edited layout.')

    def apply_scene(self):
        entities = self.arena['entities']
        entities['lake_props'] = deepcopy(self.static_props)
        entities['emitters'] = deepcopy(self.static_emitters)
        # Authored bowls own their emitters; removing a bowl removes its light.
        for identity in list(entities['emitters']):
            if 'bowl:' + identity not in self.static_props:
                entities['emitters'].pop(identity)
        entities['puzzles'] = {}
        entities['pickups'] = {}
        tm = self.arena['tile_map']
        for record in self.scene.document['objects']:
            identity, kind = record['id'], record['kind']
            x, z = record['position']
            floor = structure.floor_height(tm, x, z)
            if kind == 'prop':
                prop = deepcopy(record['template'])
                prop.update(position=dict(x=x, y=z), rotation_y=record.get('rotation', 0),
                            base_height=0 if prop['kind'] == 'lily' else floor)
                entities['lake_props'][identity] = prop
                if prop['kind'] == 'brazier':
                    original = self.static_emitters.get(identity.removeprefix('bowl:'))
                    if original is None:
                        original = next((e for e in self.static_emitters.values() if e.get('type') == 'fire'), None)
                    if original:
                        emitter = deepcopy(original)
                        emitter.update(position=dict(x=x, y=z), base_height=floor)
                        entities['emitters'][identity.removeprefix('bowl:')] = emitter
                continue
            if kind == 'medicine':
                if identity not in self.collected:
                    entities['pickups'][identity] = dict(id=identity, persistent_id=identity,
                        type='health_pickup', label=record['label'], value=25,
                        position=game.get_tile_index_and_offset_from_pos(dict(x=x, y=z), tm))
                continue
            if kind == 'door':
                # The existing entrance is two cells wide. Both leaves share a
                # single interaction and retain the shared full-cell collision.
                for index, dx in enumerate((-8, 8)):
                    leaf_id = identity + ':' + str(index)
                    leaf = puzzles.init_object(dict(id=leaf_id, type='key door',
                        position=game.get_tile_index_and_offset_from_pos(dict(x=x+dx, y=z), tm)), 'key door')
                    leaf.update(persistent_id=leaf_id, compound_id=identity,
                                puzzle_group=record.get('group', 'temple'), label=record['label'])
                    entities['puzzles'][leaf_id] = leaf
                continue
            puzzle_kind = 'puzzle key' if kind == 'key' else 'inspectable'
            obj = puzzles.init_object(dict(id=identity, type=puzzle_kind,
                position=game.get_tile_index_and_offset_from_pos(dict(x=x, y=z), tm)), puzzle_kind)
            obj.update(persistent_id=identity, puzzle_group=record.get('group', 'temple'), label=record['label'])
            if kind == 'inscription':
                obj['description_id'] = record.get('description', 'old_inscription')
            entities['puzzles'][identity] = obj
        self.sync_doors()

    def sync_doors(self):
        door = self.arena['entities']['facades'].get('door')
        if door:
            door['door_id'] = 'temple-entrance:0'
            door['open'] = bool(self.arena['puzzle_state']['objects'].get('temple-entrance:0', {}).get('open'))
        puzzles.sync_door_tiles(self.arena)
        g_night.sync_collision(self.arena)

    def activate_door(self, obj):
        leaves = [o for o in puzzles.objects(self.arena) if o.get('compound_id') == obj['compound_id']]
        state = puzzles.object_state(self.arena, obj)
        was_open = bool(state.get('open'))
        if state.get('open') and any(puzzles.door_is_occupied(self.arena, leaf) for leaf in leaves):
            self.arena = puzzles.message(self.arena, 'The doorway is occupied.')
            return
        self.arena = puzzles.interact(self.arena, obj['persistent_id'])
        if bool(state.get('open')) != was_open:
            self.arena = puzzles.message(self.arena, 'The temple door is ' + ('open.' if state['open'] else 'closed.'))
        elif not state.get('unlocked'):
            self.arena = puzzles.message(self.arena, 'The temple door is locked. Look for a brass key.')
        for leaf in leaves:
            puzzles.object_state(self.arena, leaf).update(state)
        self.sync_doors()

    def can_walk(self, x, z):
        tm = self.arena['tile_map']
        for dx, dz in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
            p = game.get_tile_index_and_offset_from_pos(dict(x=x+dx, y=z+dz), tm)
            if game.tile_not_in_bounds(p['tile_x'], p['tile_y'], tm) or game.position_collides_within_tile_shape(p, tm):
                return False
        # Only solid ground props block; hanging lanterns, lilies and pickups do
        # not. This same authored position also drives their visible geometry.
        for prop in self.arena['entities']['lake_props'].values():
            radius = {'brazier': 4., 'pile': 2.5, 'column': 3., 'altar': 9.}.get(prop['kind'], 0.)
            p = prop['position']
            if radius and math.hypot(x-p['x'], z-p['y']) < radius + 3:
                return False
        return True

    def tick(self, dt, keys=(), running=False, pressed=(), editor=False):
        dt = max(0., min(.05, dt))
        pressed = set(pressed)
        self.travel = 0.
        self.footsteps = []
        if editor:
            self.walk.moving = False
            self.walk.intent = cameras.MovementIntent()
            self.paused = True
            return
        candidate = interactions.nearest(self.arena) if not self.modal else None
        door_action = candidate and candidate[2].get('compound_id') and 'E' in pressed
        if door_action:
            self.activate_door(candidate[2])
        self.arena, owned = interactions.update(self.arena, True, self.assets, dt=dt,
            pressed=lambda name: name in pressed and not (door_action and name == 'E'))
        self.paused = bool(owned or door_action)
        if self.paused:
            self.walk.moving = False
            self.walk.intent = cameras.MovementIntent()
        else:
            old = self.walk.x, self.walk.y
            gait = 'run' if running else 'walk'
            self.walk.step(keys, dt, self.can_walk, SETTINGS[gait]['speed'])
            self.travel = math.hypot(self.walk.x-old[0], self.walk.y-old[1])
            self.sync_position()
            self.footsteps = g_audio.update_actor_footstep_travel(self.player,
                dict(x=self.walk.x, y=self.walk.y), SETTINGS[gait]['stride']/2, 'player', 'player', gait=gait)
            self.clock += dt
            runtime = self.arena['puzzle_runtime']
            runtime['message_time'] = max(0., runtime['message_time']-dt)
        self.collected.update(o['id'] for o in self.scene.document['objects']
            if o['kind'] == 'medicine' and o['id'] not in self.arena['entities']['pickups'])

    def snapshot(self):
        return dict(version=1, scene_id=self.scene.document['scene_id'],
            position=[self.walk.x, self.walk.y], heading=list(self.walk.heading), clock=self.clock,
            player={k: deepcopy(self.player[k]) for k in ('health', 'ammo', 'inventory', 'inventory_overflow')},
            puzzle_state=deepcopy(self.arena['puzzle_state']), collected=sorted(self.collected))

    def save(self, path=SAVE_FILE):
        atomic_json(path, self.snapshot())

    def load(self, path=SAVE_FILE):
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value, dict) or value.get('version') != 1 or value.get('scene_id') != self.scene.document['scene_id']:
            raise ValueError('This progress belongs to a different scene.')
        point(value['position'])
        player = value['player']
        if not isinstance(player, dict) or not isinstance(player.get('health'), (int, float)) or not 0 <= player['health'] <= 100:
            raise ValueError('Invalid saved health.')
        def valid_item(item):
            return item is None or (isinstance(item, dict) and item.get('kind') in ('key', 'health', 'ammo') and
                type(item.get('count')) is int and 1 <= item['count'] <= {'key': 1, 'health': 1, 'ammo': 60}[item['kind']] and
                (item['kind'] != 'key' or isinstance(item.get('group'), str)) and
                (item['kind'] != 'health' or isinstance(item.get('value', 25), (int, float)) and 0 < item.get('value', 25) <= 100))
        slots = player.get('inventory')
        if not isinstance(slots, list) or len(slots) != 8 or not all(valid_item(s) for s in slots):
            raise ValueError('Invalid saved inventory.')
        state = value['puzzle_state']
        if not isinstance(state, dict) or any(not isinstance(state.get(k), dict) for k in ('objects', 'inventory', 'facts', 'spawns')):
            raise ValueError('Invalid saved puzzle state.')
        if any(not isinstance(v, dict) or any(not isinstance(v.get(k, False), bool) for k in ('collected', 'open', 'unlocked'))
               for v in state['objects'].values()):
            raise ValueError('Invalid saved object state.')
        door_states = [state['objects'].get('temple-entrance:' + str(i), {}) for i in (0, 1)]
        if any(s.get('open') and not s.get('unlocked') for s in door_states) or any(
            bool(door_states[0].get(k)) != bool(door_states[1].get(k)) for k in ('open', 'unlocked')):
            raise ValueError('The saved entrance leaves disagree.')
        if not isinstance(value.get('collected'), list) or any(not isinstance(v, str) for v in value['collected']):
            raise ValueError('Invalid saved pickup IDs.')
        if not isinstance(player.get('ammo'), dict) or any(not isinstance(v, int) or v < 0 for v in player['ammo'].values()):
            raise ValueError('Invalid saved ammunition.')
        if not isinstance(player.get('inventory_overflow'), list) or not all(valid_item(s) for s in player['inventory_overflow']):
            raise ValueError('Invalid saved inventory overflow.')
        heading = value.get('heading', [1., 0.])
        clock = value.get('clock', 0.)
        if not isinstance(heading, list) or len(heading) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in heading) or not isinstance(clock, (int, float)) or not math.isfinite(clock) or clock < 0:
            raise ValueError('Invalid saved motion.')
        # Validate completely before replacing the running state.
        self.player.update({k: deepcopy(player[k]) for k in ('health', 'ammo', 'inventory', 'inventory_overflow')})
        inventory.sync_ammo(self.player)
        self.arena = self.arena.set('puzzle_state', deepcopy(state))
        self.arena = self.arena.set('interaction_runtime', {'modal': None, 'selected': 0})
        self.arena['puzzle_runtime'].update(message='', message_time=0., sounds=[], keypad=None)
        self.collected = set(value['collected'])
        self.clock = clock
        self.apply_scene()
        self.set_position(*value['position'])
        self.ensure_clear_position()
        self.walk.heading = tuple(heading)
