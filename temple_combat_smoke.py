"""Real GPU/audio encounter review; isolated scene and progress files only."""
from copy import deepcopy
import json
import math
from unittest.mock import patch
import pyray as pr
import g_inventory as inventory
from g_temple_combat import world,ENEMY_AIM_HEIGHT
from g_temple_combat_view import controls
from g_temple_editor import gameplay_camera
from g_temple_encounter import install_terrace
from temple_exploration_smoke import Review as ExplorationReview


class Review(ExplorationReview):
    def __init__(self,g,editor,folder):
        self.action={};self.visual_clips=set();self.player_clips=set();self.cpu_vertices={}
        self.camera_override=None;self.inspection=False
        self.turn_plants={};self.turn_lift=0.
        super().__init__(g,editor,folder.parent/'temple-combat')

    def aim_actor(self,fire=False):
        g=self.gameplay;actor=g.combat.actors['terrace-redhead'];x,z=world(actor,g.arena['tile_map'])
        camera=gameplay_camera(g)
        height=16+ENEMY_AIM_HEIGHT
        p=pr.get_world_to_screen_ex(pr.Vector3(x,height,z),camera,480,270)
        mouse=pr.Vector2(p.x*3,p.y*3)
        with patch.object(pr,'get_mouse_position',return_value=mouse), \
             patch.object(pr,'is_mouse_button_down',side_effect=lambda k:k==pr.MOUSE_BUTTON_RIGHT), \
             patch.object(pr,'is_mouse_button_pressed',side_effect=lambda k:k==pr.MOUSE_BUTTON_LEFT and fire), \
             patch.object(pr,'is_key_pressed',return_value=False):
            self.action=controls(g)
        assert self.action['aiming'] and self.action['aim']==(x,height,z)

    def native_trigger(self):
        from g_temple_editor import VIEW_SCALE,VIEW_TOP
        g=self.gameplay;editor=self.editor;editor.choose_tool(8)
        count=len(g.scene.document['objects']);before=g.scene.checkpoint()
        for point in ((672,340),(696,360)):
            camera=editor.camera(gameplay_camera(g))
            p=pr.get_world_to_screen_ex(pr.Vector3(point[0],16,point[1]),camera,480,270)
            mouse=pr.Vector2(p.x*VIEW_SCALE,p.y*VIEW_SCALE+VIEW_TOP)
            with patch.object(pr,'get_mouse_position',return_value=mouse), \
                 patch.object(pr,'is_key_down',return_value=False),patch.object(pr,'is_key_pressed',return_value=False), \
                 patch.object(pr,'get_mouse_wheel_move',return_value=0), \
                 patch.object(pr,'is_mouse_button_pressed',side_effect=lambda k:k==pr.MOUSE_BUTTON_LEFT), \
                 patch.object(pr,'is_mouse_button_released',return_value=False),patch.object(pr,'is_mouse_button_down',return_value=False):
                editor.update(g,camera,.05)
        assert len(g.scene.document['objects'])==count+1 and editor.edit_field=='group'
        editor.finish_text()
        assert g.scene.undo();g.apply_scene();assert g.scene.document==before
        self.metrics['native_trigger_placement_and_undo']=True

    def run(self):
        g=self.gameplay;c=g.combat;editor=self.editor
        install_terrace(g.scene);g.apply_scene()
        g.scene.path=self.folder/'encounter.scene.json';g.scene.save()
        g.set_position(550,344)
        frozen=(g.walk.x,g.walk.y)
        self.camera_override=dict(eye=(g.walk.x-70,50,g.walk.y),target=(g.walk.x,29,g.walk.y),span=40)
        self.inspection=True
        for i in range(12):
            if i in (4,9):self.capture='00-turn-left-'+str(i)
            yield {'a'},set(),False
        for i in range(12):
            if i==7:self.capture='00-turn-right'
            yield {'d'},set(),False
        assert (g.walk.x,g.walk.y)==frozen
        for i in range(6):
            if i==4:self.capture='00-backward-step'
            yield {'s'},set(),False
        self.camera_override=None;self.inspection=False
        self.metrics['tank_turns_and_backward_steps']=True
        yield from self.wait(2,'01-terrace-approach')
        assert not c.actors
        yield from self.move((580,344))
        assert len(c.actors)==1
        for _ in range(400):
            if g.player['health']<100:break
            yield from self.wait(1)
        assert 0<g.player['health']<100
        self.metrics['shared_ai_pursuit_and_melee']=True
        yield from self.wait(1,'02-enemy-attack')
        actor=c.actors['terrace-redhead'];x,z=world(actor,g.arena['tile_map'])
        fx,fz=actor['heading'];rx,rz=fz,-fx
        self.inspection=True
        self.camera_override=dict(eye=(x+fx*65+rx*32,47,z+fz*65+rz*32),target=(x,27,z),span=38)
        yield from self.wait(1,'02b-chorus-front')
        self.camera_override=dict(eye=(x+rx*75,43,z+rz*75),target=(x,27,z),span=38)
        yield from self.wait(1,'02c-chorus-side')
        self.camera_override=None;self.inspection=False
        g.save(self.folder/'active.json');saved=g.snapshot()
        yield from self.wait(3)
        g.load(self.folder/'active.json');assert g.snapshot()==saved
        self.metrics['active_progress_round_trip']=True
        self.aim_actor()
        yield from self.wait(8,'03-player-aim')
        self.camera_override=dict(eye=(g.walk.x+65,91,g.walk.y+80),target=(g.walk.x+5,29,g.walk.y),span=58)
        self.inspection=True
        yield from self.wait(1,'03b-combat-pose-inspection')
        self.camera_override=None;self.inspection=False
        yield from self.press('TAB')
        frozen=g.clock,g.player['health'],g.player['ammo']['pistol'],deepcopy(c.actors)
        self.aim_actor(fire=True)
        yield from self.wait(8,'04-inventory-pause')
        assert frozen==(g.clock,g.player['health'],g.player['ammo']['pistol'],c.actors)
        yield from self.press('TAB');self.action={}
        self.metrics['combat_modal_pause']=True
        for shot in range(3):
            self.aim_actor(fire=True)
            yield from self.wait(1,'05-recoil' if shot==0 else None)
            self.action={};yield from self.wait(6)
        actor=c.actors['terrace-redhead']
        assert actor['health']<=0 and c.encounters['temple-terrace']['complete']
        assert g.arena['puzzle_state']['objects']['terrace-gate:0']['unlocked']
        yield from self.wait(20,'06-enemy-death')
        g.save(self.folder/'complete.json');saved=g.snapshot()
        yield from self.wait(4)
        g.load(self.folder/'complete.json');assert g.snapshot()==saved
        self.metrics['death_completion_round_trip']=True
        yield from self.move((600,376));yield from self.confirm_pickup()
        before=g.player['health']
        yield from self.press('TAB')
        slots=g.player['inventory'];index=next(i for i,s in enumerate(slots) if s and s['kind']=='health')
        for _ in range(index):yield from self.press('RIGHT')
        yield from self.press('E')
        assert g.player['health']>before
        yield from self.press('TAB')
        self.metrics['pickup_and_heal']=True
        yield from self.move((650,352));yield from self.press('E')
        assert g.can_walk(664,352)
        yield from self.move((684,352));yield from self.confirm_pickup()
        yield from self.wait(2,'07-open-gate-and-reward')
        self.metrics['gate_traversal_and_ammo_pickup']=True
        g.player['ammo']['pistol']=3;self.action=dict(reload=True)
        yield from self.wait(1);self.action={}
        yield from self.wait(26,'08-reloaded')
        assert g.player['ammo']['pistol']==20
        self.metrics['inventory_reload']=True
        self.action=dict(aiming=True,aim=(g.walk.x+100,34.5,g.walk.y))
        for _ in range(8):yield {'a'},set(),False
        self.action={}
        self.metrics['aimed_locomotion']=True
        editor.toggle(g);editor.selected='terrace-redhead';editor.choose_tool(8)
        self.native_trigger()
        yield from self.wait(2,'09-encounter-editor')
        editor.toggle(g)
        self.metrics['native_camera_aiming']=True
        g.player['health']=0
        yield from self.wait(22,'10-player-death')
        assert c.dead
        yield from self.press('ENTER');yield from self.wait(2,'11-restart')
        assert g.player['health']==100 and not c.actors
        self.metrics['death_and_restart']=True
        self.metrics.update(frames=self.frames,player_clips=sorted(self.player_clips),enemy_clips=sorted(self.visual_clips),
            accepted_audio_events=self.audio_events,missing_audio=sorted(self.missing_audio))
        plant_error=max((max(math.dist(a,b) for a in track for b in track)
                         for track in self.turn_plants.values()),default=0.)
        assert self.turn_lift>.5,self.turn_lift
        assert plant_error<.25,plant_error
        self.metrics['native_turn_foot_lift']=self.turn_lift
        self.metrics['native_turn_plant_drift']=plant_error
        assert {'aim','recoil','reload','hurt','death','turn_left','turn_right','walk_back'}<=self.player_clips
        assert any(c in self.player_clips for c in ('aim_walk','aim_left','aim_right','aim_back'))
        assert {'enemy_walk','enemy_attack','enemy_death'}<=self.visual_clips
        assert self.audio_events>0
        assert 'weapons.pistol_shot' not in self.missing_audio
        (self.folder/'report.json').write_text(json.dumps(self.metrics,indent=2)+'\n')
        self.done=True

    def observe_visual(self,player,view):
        self.player_clips.add(player.clip)
        walk=self.gameplay.walk
        if player.clip.startswith('turn_') and player.pose_blend>.99 and not walk.moving:
            yaw=math.radians(player.yaw);cos,sin=math.cos(yaw),math.sin(yaw)
            phase=walk.turn_distance/120
            for suffix,offset in (('L',0.),('R',.5)):
                index=next(i for i in range(player.player.boneCount)
                    if pr.ffi.string(player.player.bones[i].name).decode()=='foot.'+suffix)
                bind=player.player.bindPose[index].translation
                point=pr.vector3_transform(bind,player.player.meshes[0].boneMatrices[index])
                self.turn_lift=max(self.turn_lift,point.y-1)
                p=(phase+offset)%1
                if p<.5:
                    key=(player.clip,suffix,math.floor(phase+offset))
                    self.turn_plants.setdefault(key,[]).append((point.x*cos+point.z*sin,-point.x*sin+point.z*cos))
        if self.capture=='03b-combat-pose-inspection':assert player.pose_blend>.99
        for identity,model in view.enemies.items():
            self.visual_clips.add(model.clip)
            assert model.player.boneCount==15
            # The shader must deform persistent vertices, never re-upload them.
            mesh=model.player.meshes[0]
            vertices=bytes(pr.ffi.buffer(mesh.vertices,mesh.vertexCount*3*4))
            if identity in self.cpu_vertices:assert self.cpu_vertices[identity]==vertices
            self.cpu_vertices[identity]=vertices
