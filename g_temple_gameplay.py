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
import g_temple_layout as layout
from g_temple_scene import atomic_json, point
from g_temple_combat import Combat
from photo_asset_pipeline.temple3d.living.gait import SETTINGS

SAVE_FILE = Path(__file__).resolve().parent / 'saved_editor_states' / 'temple3d-progress.json'


class Exploration:
    def __init__(self, arena, scene, assets=None):
        self.scene = scene
        self.assets = assets if assets is not None else {}
        self.arena = interactions.ensure(puzzles.ensure_arena(arena))
        self.arena['player_info'].update(entity_width=6,entity_height=6,collision_center_offset=dict(x=0.,y=0.))
        self.base_tile_map = deepcopy(arena['tile_map'])
        self.applied_layout = None
        self.geometry_revision = 0
        self.walk = cameras.TankWalkthrough(*scene.document['spawn'])
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
        self.spawn_error=''
        try:self.ensure_clear_position()
        except ValueError as exc:self.spawn_error=str(exc)
        self.combat=Combat(self)
        self.initial_progress=self.snapshot()

    @property
    def player(self):
        return self.arena['player_info']

    @property
    def modal(self):
        return self.arena['interaction_runtime']['modal']

    def set_position(self, x, z):
        previous=deepcopy(self.player['position'])
        self.walk.x, self.walk.y = float(x), float(z)
        self.walk.director.update(x, z)
        self.update_camera()
        self.walk.intent = cameras.MovementIntent()
        self.walk.stop()
        self.player['position'] = dict(game.get_tile_index_and_offset_from_pos(dict(x=x, y=z), self.arena['tile_map']), z=0.)
        game.update_tile_manager(previous,self.player['position'],'player',self.arena['tile_map'],entity=self.player)
        self.player.pop('audio_step_state', None)
        g_audio.update_actor_footstep_travel(self.player, dict(x=x, y=z), SETTINGS['walk']['stride']/2, 'player', 'player')

    def sync_position(self):
        previous=deepcopy(self.player['position'])
        self.player['position'].update(game.get_tile_index_and_offset_from_pos(
            dict(x=self.walk.x, y=self.walk.y), self.arena['tile_map']))
        game.update_tile_manager(previous,self.player['position'],'player',self.arena['tile_map'],entity=self.player)

    def update_camera(self,dt=0.):
        tm=self.arena['tile_map']
        tx,tz=layout.cell_at((self.walk.x,self.walk.y))
        if tz*layout.WIDTH+tx not in self.new_floor_indices:
            self.walk.director.override=None
            return
        # New floor outside the original footprint gets a clear local view.
        # The accepted authored shots still cover the original temple/bridge.
        floor=structure.floor_height(tm,self.walk.x,self.walk.y)
        target=(self.walk.x,floor+14,self.walk.y)
        previous=self.walk.director.override
        if previous and dt:
            amount=1-math.exp(-dt*12)
            target=tuple(old+(goal-old)*amount for old,goal in zip(previous['target'],target))
        offset=(100,151,220);span=140;title='New layout'
        for trigger in self.scene.document['objects']:
            if trigger['kind']!='encounter' or 'camera_offset' not in trigger:continue
            points=[trigger['position'],trigger['end']]+[o['position'] for o in self.scene.document['objects'] if o.get('group')==trigger['group']]
            if min(p[0] for p in points)-32<=self.walk.x<=max(p[0] for p in points)+48 and min(p[1] for p in points)-32<=self.walk.y<=max(p[1] for p in points)+32:
                offset=trigger['camera_offset'];span=trigger.get('camera_span',140);title=trigger['label'];break
        self.walk.director.override=dict(title=title,target=target,
            eye=tuple(a+b for a,b in zip(target,offset)),span=span,
            hide_front_facade=self.walk.director.shots[self.walk.director.active].get('hide_front_facade',False))

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
        tm=self.arena['tile_map']
        candidates=sorted(((math.hypot((x+.5)*16-self.walk.x,(z+.5)*16-self.walk.y),x,z)
            for z in range(tm['map_height']) for x in range(tm['map_width'])))
        for _,x,z in candidates:
            if self.can_walk((x+.5)*16,(z+.5)*16):
                self.set_position((x+.5)*16,(z+.5)*16)
                return
        raise ValueError('No clear player position near the edited layout.')

    def apply_scene(self):
        authored_layout=self.scene.document['layout']
        if authored_layout != self.applied_layout:
            self.geometry_revision += 1
            self.arena=self.arena.set('tile_map',layout.apply(self.base_tile_map,authored_layout,self.geometry_revision))
            self.applied_layout=deepcopy(authored_layout)
            tm=self.arena['tile_map']
            self.new_floor_indices={i for i,t in enumerate(tm['tiles']) if not t.get('water') and not t.get('force_collidable')
                and (self.base_tile_map['tiles'][i].get('water') or self.base_tile_map['tiles'][i].get('force_collidable'))}
            self.update_camera()
        entities = self.arena['entities']
        entities['lake_props'] = deepcopy(self.static_props)
        if layout.authored(authored_layout) or not authored_layout['rails']:
            entities['lake_props']={k:p for k,p in entities['lake_props'].items() if p['kind']!='rail'}
            if authored_layout['rails']:
                entities['lake_props'].update(layout.generated_rails(self.arena['tile_map']))
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
            if kind in ('enemy_spawn','encounter'):
                continue
            if kind in ('medicine','ammo'):
                if identity not in self.collected:
                    entities['pickups'][identity] = dict(id=identity, persistent_id=identity,
                        type='health_pickup' if kind=='medicine' else 'pistol_ammo_pickup', label=record['label'], value=25 if kind=='medicine' else 12,
                        position=game.get_tile_index_and_offset_from_pos(dict(x=x, y=z), tm))
                continue
            if kind in ('door','gate'):
                # The existing entrance is two cells wide. Both leaves share a
                # single interaction and retain the shared full-cell collision.
                for index, dx in enumerate((-8, 8)):
                    a=math.radians(record.get('rotation',0))
                    leaf_id = identity + ':' + str(index)
                    leaf = puzzles.init_object(dict(id=leaf_id, type='key door',
                        position=game.get_tile_index_and_offset_from_pos(dict(x=x+dx*math.cos(a), y=z-dx*math.sin(a)), tm)), 'key door')
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
        if hasattr(self,'combat'):self.combat.sync()
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
            self.arena = puzzles.message(self.arena, obj.get('label','Door') + ' is ' + ('open.' if state['open'] else 'closed.'))
        elif not state.get('unlocked'):
            self.arena = puzzles.message(self.arena, 'The temple door is locked. Look for a brass key.' if obj['compound_id']=='temple-entrance' else 'The gate is sealed. Clear its encounter to unlock it.')
        for leaf in leaves:
            puzzles.object_state(self.arena, leaf).update(state)
        self.sync_doors()

    def can_walk(self, x, z, ignore_actor=None):
        tm = self.arena['tile_map']
        if hasattr(self,'combat'):
            from g_temple_combat import world
            for identity,actor in self.combat.actors.items():
                if identity!=ignore_actor and actor['health']>0 and math.dist((x,z),world(actor,tm))<6:
                    return False
            if ignore_actor and math.hypot(x-self.walk.x,z-self.walk.y)<6:return False
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

    def can_move_to(self,x,z):
        if not self.can_walk(x,z):return False
        tm=self.arena['tile_map']
        # Check both directions at a ledge; authored stairs are small risers.
        return abs(structure.floor_height(tm,x,z)-structure.floor_height(tm,self.walk.x,self.walk.y))<=4.001

    def tick(self, dt, keys=(), running=False, pressed=(), editor=False, aiming=False, aim=None, fire=False, reload=False):
        dt = max(0., min(.05, dt))
        pressed = set(pressed)
        self.travel = 0.
        self.footsteps = []
        self.walk.stop()
        if editor:
            self.walk.moving = False
            self.walk.intent = cameras.MovementIntent()
            self.paused = True
            self.combat.aiming=False
            return
        if self.combat.dead:
            if 'ENTER' in pressed:
                restart=deepcopy(self.initial_progress)
                restart['position']=list(self.scene.document['spawn'])
                restart['combat']=dict(encounters={},actors={},reload=0.,death_time=0.)
                self.restore(restart)
                self.ensure_clear_position()
            else:self.combat.tick(dt)
            self.walk.moving=False;self.paused=True
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
            start=self.walk.x,self.walk.y
            def move_allowed(x,z):
                if not self.can_walk(x,z):return False
                tm=self.arena['tile_map']
                # Track each accepted swept position, rather than comparing an
                # entire frame's stair ascent to its initial elevation.
                allowed=abs(structure.floor_height(tm,x,z)-structure.floor_height(tm,*move_allowed.previous))<=4.001
                if allowed:move_allowed.previous=(x,z)
                return allowed
            move_allowed.previous=start
            frozen=bool(self.combat.reload or reload)
            target=(aim[0],aim[2]) if aim is not None else None
            self.walk.step(() if frozen else keys, dt, move_allowed, SETTINGS[gait]['speed'],
                aiming=aiming and not frozen,aim=target,running=running)
            gait='run' if self.walk.running and not aiming else 'walk'
            self.travel = math.hypot(self.walk.x-old[0], self.walk.y-old[1])
            self.sync_position()
            self.update_camera(dt)
            self.footsteps = g_audio.update_actor_footstep_travel(self.player,
                dict(x=self.walk.x, y=self.walk.y), SETTINGS[gait]['stride']/2, 'player', 'player', gait=gait)
            self.clock += dt
            self.combat.tick(dt,aiming,aim,fire,reload)
            runtime = self.arena['puzzle_runtime']
            runtime['message_time'] = max(0., runtime['message_time']-dt)
        self.collected.update(o['id'] for o in self.scene.document['objects']
            if o['kind'] in ('medicine','ammo') and o['id'] not in self.arena['entities']['pickups'])

    def snapshot(self):
        return dict(version=1, scene_id=self.scene.document['scene_id'],
            position=[self.walk.x, self.walk.y], heading=list(self.walk.facing), clock=self.clock,
            player={k: deepcopy(self.player[k]) for k in ('health', 'ammo', 'inventory', 'inventory_overflow')},
            puzzle_state=deepcopy(self.arena['puzzle_state']), collected=sorted(self.collected),combat=self.combat.snapshot())

    def save(self, path=SAVE_FILE):
        atomic_json(path, self.snapshot())

    def load(self, path=SAVE_FILE):
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        self.restore(value)

    def restore(self,value):
        if not isinstance(value, dict) or value.get('version') != 1 or value.get('scene_id') != self.scene.document['scene_id']:
            raise ValueError('This progress belongs to a different scene.')
        combat=value.get('combat',dict(encounters={},actors={},reload=0.,death_time=0.))
        self.combat.validate_snapshot(combat)
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
        for door in (o for o in self.scene.document['objects'] if o['kind'] in ('door','gate')):
            door_states = [state['objects'].get(door['id']+':' + str(i), {}) for i in (0, 1)]
            if any(s.get('open') and not s.get('unlocked') for s in door_states) or any(
                bool(door_states[0].get(k)) != bool(door_states[1].get(k)) for k in ('open', 'unlocked')):
                raise ValueError('The saved door leaves disagree.')
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
        self.combat.actors={};self.combat.encounters={}
        self.apply_scene()
        self.set_position(*value['position'])
        self.ensure_clear_position()
        length=math.hypot(*heading)
        self.walk.facing = tuple(v/length for v in heading) if length>1e-6 else (1.,0.)
        self.walk.heading = self.walk.facing
        self.combat.restore(combat)
        self.sync_doors()
