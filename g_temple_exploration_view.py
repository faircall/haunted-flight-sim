"""Small low-poly exploration props, shared gameplay UI and spatial audio."""
import math
import pyray as pr
import g_audio
import g_interactions
import g_narrative_text as text
import g_puzzles
import g_temple_structure as structure


class Props:
    def __init__(self, shader):
        self.models = {}
        for name, mesh in (('cube', pr.gen_mesh_cube(1, 1, 1)), ('ring', pr.gen_mesh_torus(.35, 1, 6, 8))):
            model = pr.load_model_from_mesh(mesh)
            model.materials[0].shader = shader
            self.models[name] = model

    def part(self, name, position, size, color, yaw=0):
        pr.draw_model_ex(self.models[name], pr.Vector3(*position), pr.Vector3(0, 1, 0), yaw, pr.Vector3(*size), color)

    def draw(self, gameplay, editor=False):
        tm = gameplay.arena['tile_map']
        for obj in gameplay.scene.document['objects']:
            kind, identity = obj['kind'], obj['id']
            if kind=='gate':
                x,z=obj['position'];h=structure.floor_height(tm,x,z);yaw=obj.get('rotation',0)
                a=math.radians(yaw)
                def at(dx,y,dz=0):return (x+dx*math.cos(a)+dz*math.sin(a),h+y,z-dx*math.sin(a)+dz*math.cos(a))
                wood=pr.Color(99,74,53,255)
                for dx in (-15,15):self.part('cube',at(dx,15),(2,30,2),wood,yaw)
                self.part('cube',at(0,29),(32,2,2),wood,yaw)
                state=gameplay.arena['puzzle_state']['objects'].get(identity+':0',{})
                if not state.get('open'):
                    for dx in range(-12,13,4):self.part('cube',at(dx,14),(1.2,26,1.2),pr.Color(59,68,70,255),yaw)
                    for y in (7,20):self.part('cube',at(0,y),(28,1.2,1.2),wood,yaw)
                continue
            if kind not in ('key', 'medicine', 'inscription','ammo'):
                continue
            if not editor:
                if kind == 'key' and gameplay.arena['puzzle_state']['objects'].get(identity, {}).get('collected'):
                    continue
                if kind in ('medicine','ammo') and identity in gameplay.collected:
                    continue
            x, z = obj['position']
            h = structure.floor_height(tm, x, z)
            yaw = obj.get('rotation', 0)
            if kind == 'key':
                gold = pr.Color(238, 196, 94, 255)
                a = math.radians(yaw)
                def at(dx, dz, y):
                    return (x+dx*math.cos(a)+dz*math.sin(a), h+y, z-dx*math.sin(a)+dz*math.cos(a))
                self.part('ring', at(-2, 0, 1), (1.2, 1.2, .4), gold, yaw)
                self.part('cube', at(.5, 0, 1), (4, .7, .7), gold, yaw)
                for dx in (1.4, 2.4):
                    self.part('cube', at(dx, .55, 1), (.7, .7, 1.6), gold, yaw)
            elif kind=='ammo':
                self.part('cube',(x,h+1.2,z),(4,2.4,3),pr.Color(107,116,84,255),yaw)
                self.part('cube',(x,h+2.45,z),(3,.15,1.2),pr.Color(208,184,119,255),yaw)
            elif kind == 'medicine':
                self.part('cube', (x, h+1.5, z), (4, 3, 3), pr.Color(211, 204, 174, 255), yaw)
                self.part('cube', (x, h+3.1, z), (2.8, .25, .6), pr.Color(154, 62, 56, 255), yaw)
                self.part('cube', (x, h+3.15, z), (.6, .25, 2.1), pr.Color(154, 62, 56, 255), yaw)
            else:
                self.part('cube', (x, h+3.5, z), (9, 7, 2), pr.Color(165, 160, 138, 255), yaw)
                for y in (2, 3.5, 5):
                    self.part('cube', (x, h+y, z+1.1), (6, .3, .2), pr.Color(63, 63, 58, 255), yaw)

    def close(self):
        for model in self.models.values():
            pr.unload_model(model)


class Audio:
    def __init__(self,automated=False):
        self.engine = g_audio.make_audio_engine(automated)
        self.runtime = g_audio.make_audio_runtime(self.engine)
        self.profile = g_audio.make_audio_profile()

    def update(self, gameplay, dt):
        for event in gameplay.footsteps + gameplay.combat.events + gameplay.arena['puzzle_runtime']['sounds']:
            g_audio.queue_audio_event(self.runtime, event)
        gameplay.arena['puzzle_runtime']['sounds'].clear()
        gameplay.combat.events.clear()
        entities = gameplay.arena['entities']
        listener = dict(world_position=dict(x=gameplay.walk.x, y=gameplay.walk.y))
        g_audio.update_audio(self.runtime, self.engine, 0 if gameplay.paused else dt, listener,
            gameplay.arena['tile_map'], entities, {}, entities.get('emitters', {}), self.profile)

    def clear(self):
        g_audio.shutdown_audio_runtime({'audio_runtime': self.runtime})
        self.runtime = g_audio.make_audio_runtime(self.engine)

    def close(self):
        g_audio.shutdown_audio_runtime({'audio_runtime': self.runtime})
        self.engine.close()


def draw_ui(gameplay, status=''):
    assets, arena = gameplay.assets, gameplay.arena
    pr.draw_rectangle(12, 10, 88, 17, pr.Color(7, 12, 20, 180))
    pr.draw_text(f"HP {arena['player_info']['health']:.0f}", 18, 14, 10, pr.Color(210, 203, 177, 255))
    message = arena['puzzle_runtime']
    if message['message_time'] > 0:
        lines = text.wrap(assets, message['message'], 420)
        for i, line in enumerate(lines[:2]):
            text.draw(assets, line, 24, 38+i*16, pr.YELLOW)
    if status:
        pr.draw_rectangle(12, 72, 456, 22, pr.Color(7, 12, 20, 220))
        text.draw(assets, status, 20, 76, pr.YELLOW)
    if not gameplay.combat.dead:g_interactions.draw(arena, assets)
