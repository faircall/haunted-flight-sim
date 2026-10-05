"""3D encounter adapter over the game's redhead behaviour and damage rules.

Authoring contains spawn/trigger definitions; progress contains only actor and
encounter state. GPU poses, sounds and short-lived shot trails are never saved.
"""
from copy import deepcopy
import math

import g_audio
import g_inventory as inventory
import g_update_and_render as game
import g_temple_structure as structure

STATES = {'idle', 'noticing', 'light startle', 'angry chase', 'angry and attacking',
          'evade', 'flee', 'stagger', 'dead'}
MAGAZINE=20
ENEMY_HEIGHT=21.6
ENEMY_AIM_HEIGHT=14.5
ACTOR_FIELDS = ('health', 'position', 'current_state', 'previous_state', 'heading',
    'notice_timer', 'attack_timer', 'attack_substate', 'attack_direction',
    'attack_out_of_range_timer', 'stagger_timer', 'death_timer', 'last_seen_player_pos',
    'has_fled', 'previous_state_on_stagger', 'ai_velocity', 'bullet_impulse',
    'bullet_impact_elapsed', 'bullet_impact_duration', 'bullet_impact_deceleration',
    'light_startle_timer', 'breadcrumb_timer', 'evade_elapsed', 'evade_stuck_timer',
    'evade_cooldown_timer', 'evade_retry_timer', 'evade_reaction_timer', 'flee_plan_retry_timer')


def world(actor, tm):
    p = game.make_pos_abs(actor['position'], tm['tile_width'], tm['tile_height'])
    return p['x'], p['y']


def ray_box(start, end, low, high):
    """First segment intersection with a 3D AABB, including a start inside it."""
    enter, leave = 0., 1.
    for a, b, lo, hi in zip(start, end, low, high):
        delta = b-a
        if abs(delta) < 1e-8:
            if not lo <= a <= hi:return None
        else:
            x, y = (lo-a)/delta, (hi-a)/delta
            enter, leave = max(enter, min(x,y)), min(leave, max(x,y))
            if enter > leave:return None
    return enter


class Combat:
    def __init__(self, gameplay):
        self.gameplay = gameplay
        self.actors = {}
        self.encounters = {}
        self.audio = g_audio.make_audio_runtime()
        self.events = []
        self.trails = []
        self.aiming = False
        self.aim = None
        self.heading = (1., 0.)
        self.cooldown = 0.
        self.recoil = 0.
        self.reload = 0.
        self.death_time = 0.
        self.hurt_time = 0.
        self.shots = 0
        self.sync()

    @property
    def dead(self):return self.gameplay.player['health'] <= 0

    def reset(self):
        g=self.gameplay
        self.actors={};self.encounters={}
        self.reload=self.cooldown=self.recoil=self.hurt_time=self.death_time=0.
        self.events=[];self.trails=[];self.aiming=False;self.aim=None
        self.audio['event_queue'].clear()
        for trigger in self.definitions('encounter'):
            g.arena['puzzle_state']['facts'].pop(trigger['group']+':complete',None)
        for gate in self.definitions('gate'):
            for leaf in (0,1):g.arena['puzzle_state']['objects'][gate['id']+':'+str(leaf)]=dict(open=False,unlocked=False)
        g.player['health']=100;g.player['ammo']['pistol']=MAGAZINE
        self.sync();g.sync_doors()

    def definitions(self, kind):
        return [o for o in self.gameplay.scene.document['objects'] if o['kind']==kind]

    def sync(self):
        # A move, save or undo must not resurrect an already defeated actor.
        ids = {o['id'] for o in self.definitions('enemy_spawn')}
        self.actors = {k:a for k,a in self.actors.items() if k in ids}
        groups = {o['group'] for o in self.definitions('encounter')}
        self.encounters = {k:v for k,v in self.encounters.items() if k in groups}
        for group in groups:self.encounters.setdefault(group, dict(started=False, complete=False))
        active_ids={o['id'] for o in self.definitions('enemy_spawn') if self.encounters.get(o['group'],{}).get('started')}
        self.actors={k:a for k,a in self.actors.items() if k in active_ids}
        for spawn in self.definitions('enemy_spawn'):
            state = self.encounters.get(spawn['group'], {})
            if state.get('started') and spawn['id'] not in self.actors:
                self.spawn(spawn)
        self.gameplay.arena['entities']['brains'] = self.actors
        tm = self.gameplay.arena['tile_map']
        for tile in tm['tiles']:tile.pop('current_entities',None)
        game.update_tile_manager(self.gameplay.player['position'],self.gameplay.player['position'],
            'player',tm,entity=self.gameplay.player)
        # Layout rebuilds replace the spatial manager. Seed it from actual actors.
        for identity, actor in self.actors.items():
            game.update_tile_manager(actor['position'], actor['position'], identity, tm,
                remove_only=actor['health']<=0, entity=actor)
        self.unlock_completed()

    def spawn(self, definition):
        g = self.gameplay
        x,z = definition['position']
        if not g.can_walk(x,z):return False
        if math.hypot(x-g.walk.x,z-g.walk.y)<7:return False
        if any(a['health']>0 and math.dist((x,z),world(a,g.arena['tile_map']))<7 for a in self.actors.values()):return False
        actor = self.make_actor(definition)
        if self.encounters.get(definition['group'],{}).get('complete'):
            actor.update(health=0,current_state='dead',death_timer=1.)
        self.actors[definition['id']] = actor
        return True

    def make_actor(self,definition):
        g=self.gameplay;x,z=definition['position']
        yaw=math.radians(definition.get('rotation',0))
        actor = dict(id=definition['id'], type='red head',
            position=game.get_tile_index_and_offset_from_pos(dict(x=x,y=z),g.arena['tile_map']),
            entity_width=6, entity_height=6, current_state='idle', previous_state='idle',
            heading=[math.sin(yaw),math.cos(yaw)],ai_velocity=dict(x=0.,y=0.),bullet_impulse=dict(x=0.,y=0.))
        game.give_entity_stats_from_type(actor,'red head')
        actor.update(collision_center_offset=dict(x=0.,y=0.), collision_radius_reduction=0.,
            attack_engage_distance=11.)
        actor['movement_settings'].update(max_speed=26., acceleration=180., deceleration=260.,
                                         reverse_acceleration=300., arrival_radius=1.)
        return actor

    def unlock_completed(self):
        g=self.gameplay
        for gate in self.definitions('gate'):
            if self.encounters.get(gate['group'],{}).get('complete'):
                for leaf in g.arena['entities']['puzzles'].values():
                    if leaf.get('compound_id')==gate['id']:
                        g.arena['puzzle_state']['objects'].setdefault(leaf['persistent_id'],{}).update(unlocked=True)

    def event(self, kind, position=None, **kwargs):
        g=self.gameplay
        game.queue_gameplay_audio(self.audio,kind,'player','player',
            position or dict(x=g.walk.x,y=g.walk.y),**kwargs)

    def obstruction(self, start, end):
        """Height-aware terrain/door/prop trace; bullets can cross open water."""
        g=self.gameplay;tm=g.arena['tile_map']
        length=math.dist(start,end)
        count=max(1,math.ceil(length))
        for i in range(count+1):
            t=i/count
            x,h,z=(a+(b-a)*t for a,b in zip(start,end))
            tx,tz=math.floor(x/16),math.floor(z/16)
            if not (0<=tx<tm['map_width'] and 0<=tz<tm['map_height']):return t
            tile=tm['tiles'][tz*tm['map_width']+tx]
            top=structure.floor_height(tm,x,z)
            if tile.get('puzzle_blocked'):top+=32
            elif tile.get('surface_material')=='wall' or (not tile.get('water') and game.tile_is_collidable(tile,tm)):top+=48
            if h<=top+.1:return t
            for prop in g.arena['entities']['lake_props'].values():
                radius,height={'altar':(9,16),'column':(3,64),'brazier':(4,16),'pile':(2.5,54)}.get(prop['kind'],(0,0))
                p=prop['position']
                if radius and h<=prop.get('base_height',0)+height and math.hypot(x-p['x'],z-p['y'])<radius:return t
        return 1.

    def fire(self):
        g=self.gameplay
        if self.dead or not self.aiming or self.reload or self.cooldown:return False
        self.cooldown=.24
        if g.player['ammo'].get('pistol',0)<=0:
            self.event('weapon_empty',priority=1.3)
            return False
        heading=self.heading
        floor=structure.floor_height(g.arena['tile_map'],g.walk.x,g.walk.y)
        start=(g.walk.x+heading[0]*9.7+heading[1]*.6, floor+18.66, g.walk.y+heading[1]*9.7-heading[0]*.6)
        goal=self.aim or (g.walk.x+heading[0]*100,floor+18.5,g.walk.y+heading[1]*100)
        direction=tuple(b-a for a,b in zip(start,goal));length=math.sqrt(sum(v*v for v in direction))
        if length<.01:return False
        direction=tuple(v/length for v in direction)
        end=tuple(a+v*240 for a,v in zip(start,direction))
        fraction=self.obstruction(start,end)
        body=(g.walk.x,floor+18.66,g.walk.y)
        if self.obstruction(body,start)<1.:fraction=0.
        hit=None
        for identity,actor in self.actors.items():
            if actor['health']<=0:continue
            x,z=world(actor,g.arena['tile_map']);h=structure.floor_height(g.arena['tile_map'],x,z)
            t=ray_box(start,end,(x-3,h+2,z-3),(x+3,h+ENEMY_HEIGHT,z+3))
            if t is not None and t<fraction:
                fraction=t;hit=(identity,actor)
        impact=tuple(a+(b-a)*fraction for a,b in zip(start,end))
        if hit:
            identity,actor=hit
            bullet=dict(velocity=dict(x=direction[0],y=direction[2]), damage=game.DEFAULT_BULLET_DAMAGE,
                        impact_speed=12.,impact_duration=.15,combined_impact_cap=18.)
            game.apply_bullet_hit_to_redhead(actor,identity,bullet,actor['current_state'],
                g.arena['tile_map'],self.audio,player_info=g.player)
        self.trails.append(dict(start=start,end=impact,time=.075,hit=bool(hit)))
        self.recoil=.18;self.shots+=1;g.player['ammo']['pistol']-=1
        self.event('gunshot',priority=2.,data=dict(weapon='pistol'))
        return True

    def tick(self,dt,aiming=False,aim=None,fire=False,reload=False):
        g=self.gameplay;tm=g.arena['tile_map']
        self.events=[]
        self.cooldown=max(0.,self.cooldown-dt);self.recoil=max(0.,self.recoil-dt)
        self.hurt_time=max(0.,self.hurt_time-dt)
        self.trails=[dict(t,time=t['time']-dt) for t in self.trails if t['time']>dt]
        if self.dead:
            self.death_time+=dt;self.aiming=False
            return
        self.aiming=bool(aiming)
        self.heading=g.walk.facing
        if aim is not None:
            self.aim=aim
            dx,dz=aim[0]-g.walk.x,aim[2]-g.walk.y
            length=math.hypot(dx,dz)
            if length>.01:self.heading=(dx/length,dz/length)
            if aiming and not self.reload:g.walk.facing=self.heading
        if self.reload:
            self.reload=max(0.,self.reload-dt)
            if not self.reload:
                amount=max(0,min(MAGAZINE-g.player['ammo'].get('pistol',0),inventory.count(g.player['inventory'],'ammo')))
                inventory.consume(g.player['inventory'],'ammo',amount)
                g.player['ammo']['pistol']=g.player['ammo'].get('pistol',0)+amount
                inventory.sync_ammo(g.player);self.event('reload_stop')
        elif reload and g.player['ammo'].get('pistol',0)<MAGAZINE and inventory.count(g.player['inventory'],'ammo'):
            self.reload=1.15;self.event('reload_start')
        if fire:self.fire()
        for trigger in self.definitions('encounter'):
            state=self.encounters[trigger['group']]
            a,b=trigger['position'],trigger['end']
            if not state['started'] and min(a[0],b[0])<=g.walk.x<=max(a[0],b[0]) and min(a[1],b[1])<=g.walk.y<=max(a[1],b[1]):
                state['started']=True
                g.arena['puzzle_runtime'].update(message='Something is moving nearby.',message_time=3.)
            if state['started'] and not state['complete']:
                spawns=[o for o in self.definitions('enemy_spawn') if o['group']==trigger['group']]
                for spawn in spawns:
                    if spawn['id'] not in self.actors:self.spawn(spawn)
                if spawns and all(o['id'] in self.actors and self.actors[o['id']]['health']<=0 for o in spawns):
                    state['complete']=True
                    g.arena['puzzle_state']['facts'][trigger['group']+':complete']=True
                    self.unlock_completed();g.sync_doors()
                    gates=[o for o in self.definitions('gate') if o['group']==trigger['group']]
                    message=gates[0]['label']+' is unlocked.' if len(gates)==1 else 'The gates are unlocked.' if gates else 'The area is clear.'
                    g.arena['puzzle_runtime'].update(message=message,message_time=4.)
        g.arena['entities']['brains']=self.actors
        game.update_redhead_sound_awareness(g.arena['entities'],tm,g.footsteps+self.audio['event_queue'],dt)
        game.update_actor_passthrough_runtime(tm,{k for k,a in self.actors.items() if a['health']>0},dt)
        health=g.player['health']
        for identity,actor in self.actors.items():
            before=deepcopy(actor['position']);old=world(actor,tm)
            target_player=dict(g.player);event_start=len(self.audio['event_queue'])
            actor['current_state']=game.transition_entity_state(actor,actor['current_state'],target_player,tm,
                None,self.audio,dt,dict(entities=g.arena['entities'],flee_plans_remaining=1))
            if target_player['health']<g.player['health']:
                point=actor.get('attack_point',dict(x=old[0],y=old[1]))
                in_reach=math.hypot(point['x']-g.walk.x,point['y']-g.walk.y)<=6
                same_height=abs(structure.floor_height(tm,*old)-structure.floor_height(tm,g.walk.x,g.walk.y))<=8
                if in_reach and same_height:g.player['health']=target_player['health']
                else:
                    # The sprite game's generous hit rectangle is larger than
                    # the visible 3D bodies. Keep its attack timing, then resolve
                    # contact against the actual ground reach and elevation.
                    self.audio['event_queue'][event_start:]=[e for e in self.audio['event_queue'][event_start:]
                        if not (e['type']=='stagger_impact' and e['source_id']=='player')]
                    game.queue_gameplay_audio(self.audio,'melee_whoosh','enemy:'+identity,'enemy',point,priority=.8)
            x,z=world(actor,tm)
            # Shared AI operates on ground coordinates; check its swept path
            # against the 3D prop footprints and actual stair/ledge heights.
            distance=math.dist(old,(x,z));steps=max(1,math.ceil(distance/.8))
            previous=old;valid=True
            for i in range(1,steps+1):
                p=tuple(a+(b-a)*i/steps for a,b in zip(old,(x,z)))
                if not g.can_walk(*p,ignore_actor=identity) or abs(structure.floor_height(tm,*p)-structure.floor_height(tm,*previous))>4.001:
                    valid=False;break
                previous=p
            if not valid:
                actor['position']=before;actor['ai_velocity']=dict(x=0.,y=0.);x,z=old
            elif distance>.001:actor['heading']=[(x-old[0])/distance,(z-old[1])/distance]
            actor['travelled']=math.dist(old,(x,z))
            game.update_tile_manager(before,actor['position'],identity,tm,remove_only=actor['health']<=0,entity=actor)
            g_audio.update_actor_footstep_travel(actor,dict(x=x,y=z),14.,'enemy:'+identity,'enemy',self.audio,gait='walk')
        if g.player['health']<health:
            self.hurt_time=.3;g.player['health']=max(0,g.player['health'])
        self.events=list(self.audio['event_queue']);self.audio['event_queue'].clear()

    def snapshot(self):
        return dict(encounters=deepcopy(self.encounters),
            actors={k:{field:deepcopy(a[field]) for field in ACTOR_FIELDS if field in a} for k,a in self.actors.items()},
            reload=self.reload,death_time=self.death_time)

    def validate_snapshot(self,value):
        if not isinstance(value,dict) or not isinstance(value.get('encounters'),dict) or not isinstance(value.get('actors'),dict):raise ValueError('Invalid encounter progress.')
        ids={o['id'] for o in self.definitions('enemy_spawn')}
        groups={o['group'] for o in self.definitions('encounter')}
        for group,state in value['encounters'].items():
            if group not in groups or not isinstance(state,dict) or any(type(state.get(k)) is not bool for k in ('started','complete')) or (state['complete'] and not state['started']):raise ValueError('Invalid saved encounter state.')
        for identity,actor in value['actors'].items():
            if identity not in ids or not isinstance(actor,dict) or actor.get('current_state') not in STATES:raise ValueError('Invalid saved enemy.')
            if not actor.keys()<=set(ACTOR_FIELDS):raise ValueError('Unknown saved enemy fields.')
            spawn=next(o for o in self.definitions('enemy_spawn') if o['id']==identity)
            encounter=value['encounters'].get(spawn['group'],{})
            if not encounter.get('started'):raise ValueError('A saved enemy needs an active encounter.')
            h=actor.get('health')
            if isinstance(h,bool) or not isinstance(h,(int,float)) or not math.isfinite(h) or not -100<=h<=60:raise ValueError('Invalid saved enemy health.')
            if (h<=0)!=(actor['current_state']=='dead') or (encounter.get('complete') and h>0):raise ValueError('Saved enemy health and encounter state disagree.')
            p=actor.get('position',{})
            if not isinstance(p,dict) or any(not isinstance(p.get(k),(int,float)) or not math.isfinite(p[k]) for k in ('tile_x','tile_y','x','y')):raise ValueError('Invalid saved enemy position.')
            if any(type(p[k]) is not int or not 0<=p[k]<limit for k,limit in (('tile_x',56),('tile_y',40))) or any(not 0<=p[k]<16 for k in ('x','y')):raise ValueError('Invalid saved enemy cell or offset.')
            x,z=world(actor,self.gameplay.arena['tile_map'])
            if not (0<=x<896 and 0<=z<640):raise ValueError('Saved enemy is outside the map.')
            if any(actor.get(k,'idle') not in STATES for k in ('previous_state','previous_state_on_stagger')):raise ValueError('Invalid saved enemy transition.')
            for field in ('ai_velocity','bullet_impulse','attack_direction'):
                if field in actor:
                    v=actor[field]
                    if not isinstance(v,dict) or any(isinstance(v.get(k),bool) or not isinstance(v.get(k),(int,float)) or not math.isfinite(v[k]) for k in ('x','y')):raise ValueError('Invalid saved enemy vector.')
            if 'heading' in actor:
                v=actor['heading']
                if not isinstance(v,list) or len(v)!=2 or any(isinstance(k,bool) or not isinstance(k,(int,float)) or not math.isfinite(k) for k in v):raise ValueError('Invalid saved enemy heading.')
            if actor.get('attack_substate','windup') not in ('windup','committed','attacking'):raise ValueError('Invalid saved attack phase.')
            for k,v in actor.items():
                if k.endswith(('_timer','_elapsed')) or k in ('bullet_impact_duration','bullet_impact_deceleration'):
                    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError('Invalid saved enemy timing.')
        for k in ('reload','death_time'):
            v=value.get(k,0.)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=100000:raise ValueError('Invalid saved combat timing.')
        return value

    def restore(self,value):
        self.encounters=deepcopy(value['encounters']);self.actors={}
        for spawn in self.definitions('enemy_spawn'):
            if spawn['id'] in value['actors']:
                saved=value['actors'][spawn['id']]
                actor=self.make_actor(spawn)
                actor.update(deepcopy(saved));self.actors[spawn['id']]=actor
        self.reload=value.get('reload',0.);self.death_time=value.get('death_time',0.)
        self.cooldown=self.recoil=self.hurt_time=0.;self.aiming=False;self.aim=None
        self.trails=[];self.events=[];self.audio['event_queue'].clear();self.sync()
