"""Selection ownership and authored-instance checks for the temple/editor view.

CPU checks use a recording session; the optional native smoke drives the real
viewer in a hidden muted window without writing the shipped scene or progress.
"""
import json
import os
import sys
import unittest
import tempfile
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ['HAUNTED_MUTE_AUDIO']='1'
import pyray as pr
import temple_3d_viewer as viewer
from g_temple_editor import Editor
from g_temple_exploration_view import Props
from g_temple_scene import Scene,SCENE_FILE


class RecordingSession:
    def __init__(self,enabled=False):
        self.enabled=enabled
        self.next_enabled=enabled
        self.exit_requested=False
        self.records=[]

    def handle_keys(self):
        self.enabled=self.next_enabled
        return self.exit_requested

    def register_model(self,model,name,**values):
        self.records.append(dict(model=model,name=name,**values))


class TempleSelectionIntegrationTests(unittest.TestCase):
    def test_selection_pauses_and_resumes_the_audio_engine_once(self):
        engine=unittest.mock.Mock();audio=SimpleNamespace(engine=engine)
        paused=False
        for enabled in (False,True,True,True,False,False):
            paused=viewer.selection_audio(audio,enabled,paused)
        engine.stop.assert_called_once_with();engine.start.assert_called_once_with()
        self.assertFalse(paused)

    def test_selection_transition_owns_both_toggle_frames_and_escape(self):
        session=RecordingSession()
        game=SimpleNamespace(modal=False)
        editor=SimpleNamespace(active=False,suspend_input=unittest.mock.Mock())
        session.next_enabled=True
        self.assertEqual(viewer.selection_input(session,game,editor),(True,False))
        editor.suspend_input.assert_called_once()
        self.assertEqual(viewer.selection_input(session,game,editor),(True,False))
        editor.suspend_input.assert_called_once()
        session.next_enabled=False
        self.assertEqual(viewer.selection_input(session,game,editor),(True,False))
        self.assertEqual(viewer.selection_input(session,game,editor),(False,False))
        session.exit_requested=True
        self.assertEqual(viewer.selection_input(session,game,editor),(False,True))
        game.modal=True
        self.assertEqual(viewer.selection_input(session,game,editor),(False,False))
        game.modal=False;editor.active=True
        self.assertEqual(viewer.selection_input(session,game,editor),(False,False))

    def test_entering_selection_finishes_existing_drag_without_moving_or_saving(self):
        scene=Scene.load(SCENE_FILE);editor=Editor(scene)
        before=scene.checkpoint()
        obj=next(o for o in scene.document['objects'] if o['kind']=='prop')
        obj['position'][0]+=2
        editor.drag=dict(before=before)
        editor.floor_drag=dict(start=(1,1))
        visible=scene.checkpoint()
        session=RecordingSession();session.next_enabled=True
        with patch.object(scene,'save') as save:
            blocked,exit_requested=viewer.selection_input(session,SimpleNamespace(modal=False),editor)
        self.assertTrue(blocked);self.assertFalse(exit_requested)
        self.assertEqual(scene.document,visible)
        self.assertEqual(scene.undo_stack,[before])
        self.assertIsNone(editor.drag);self.assertIsNone(editor.floor_drag)
        save.assert_not_called()
        self.assertTrue(scene.undo());self.assertEqual(scene.document,before)

    def test_registration_uses_authored_id_exact_transform_and_copied_source(self):
        scene=Scene.load(SCENE_FILE);obj=next(o for o in scene.document['objects'] if o['kind']=='prop')
        session=RecordingSession(True);adapter=viewer.TempleSelection(session)
        adapter.gameplay=SimpleNamespace(scene=scene)
        model=object()
        for _ in range(2):
            adapter.record(model,'lantern','lantern.obj',pr.Vector3(7,9,11),(2,3,4),37,obj['id'])
        self.assertEqual(len(session.records),2)
        record=session.records[0]
        self.assertEqual(record['identity'],obj['id'])
        self.assertEqual(record['position'],(7,9,11))
        self.assertEqual(record['scale'],(2,3,4));self.assertEqual(record['yaw'],37)
        self.assertEqual(record['metadata']['object_data'],obj)
        self.assertEqual(record['metadata']['source_document'],str(scene.path))
        record['metadata']['object_data']['position'][0]=999
        self.assertNotEqual(obj['position'][0],999)
        session.enabled=False
        adapter.record(model,'hidden')
        self.assertEqual(len(session.records),2)

    def test_procedural_parts_register_only_the_drawn_authored_objects(self):
        objects=[dict(id='key',kind='key',position=[10,20],rotation=35),
                 dict(id='gate',kind='gate',position=[30,40],rotation=90),
                 dict(id='medicine',kind='medicine',position=[50,60],rotation=0),
                 dict(id='ammo',kind='ammo',position=[70,80],rotation=0)]
        scene=SimpleNamespace(document={'objects':objects},path=Path('fixture.scene.json'),
                              get=lambda identity:next((o for o in objects if o['id']==identity),None))
        game=SimpleNamespace(scene=scene,collected={'ammo'},arena={
            'tile_map':{},'puzzle_state':{'objects':{'key':{'collected':True},'gate:0':{'open':True}}}})
        props=Props.__new__(Props);props.models={'cube':object(),'ring':object()}
        session=RecordingSession(True);adapter=viewer.TempleSelection(session);adapter.gameplay=game
        original=props.part
        with patch('g_temple_structure.floor_height',return_value=0),patch.object(pr,'draw_model_ex') as draw:
            adapter.draw_props(props,game,False)
        self.assertEqual(draw.call_count,len(session.records))
        self.assertEqual({r['identity'] for r in session.records},{'gate','medicine'})
        self.assertEqual(sum(r['identity']=='gate' for r in session.records),3)
        self.assertEqual(props.part,original)
        session.records.clear()
        with patch('g_temple_structure.floor_height',return_value=0),patch.object(pr,'draw_model_ex') as draw:
            adapter.draw_props(props,game,True)
        self.assertEqual(draw.call_count,len(session.records))
        self.assertEqual({r['identity'] for r in session.records},{'key','gate','medicine','ammo'})
        # Exceptions must never leave a capture wrapper installed on Props.
        with patch.object(props,'draw',side_effect=ValueError('fixture')):
            with self.assertRaises(ValueError):adapter.draw_props(props,game,True)
        self.assertEqual(props.part,original)

    def test_editor_viewport_and_source_revision_track_actual_scene(self):
        scene=Scene.load(SCENE_FILE);adapter=viewer.TempleSelection(RecordingSession(True))
        adapter.gameplay=SimpleNamespace(scene=scene,geometry_revision=3)
        camera=pr.Camera3D(pr.Vector3(1,2,3),pr.Vector3(4,5,6),pr.Vector3(0,1,0),80,pr.CAMERA_ORTHOGRAPHIC)
        a=adapter.context(SimpleNamespace(active=True),(7,8,9),camera)
        self.assertEqual(a['render_size'],[480,270])
        self.assertEqual(a['player_position'],[7,8,9])
        self.assertEqual(a['camera']['position'],[1,2,3])
        self.assertEqual(viewer.selection_viewport(),(0,0,1440,810))
        x,y,w,h=viewer.selection_viewport(SimpleNamespace(active=True))
        self.assertEqual((x,w),(0,1140));self.assertAlmostEqual(y,84.375);self.assertAlmostEqual(h,641.25)
        scene.document['objects'][0]['position'][0]+=1
        b=adapter.context(SimpleNamespace(active=True),(7,8,9),camera)
        self.assertNotEqual(a['source_document_revision'],b['source_document_revision'])


def native_smoke():
    """Exercise the actual main render loop, exact picking and editor ownership."""
    import codex_selection
    import g_temple_gameplay
    import g_temple_combat_view
    import g_temple_exploration_view
    output_root=viewer.ROOT/'artifacts'/'codex_selection'
    output_root.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='temple-native-',dir=output_root))
    scene_path=folder/'scene.json';scene_path.write_bytes(SCENE_FILE.read_bytes())
    original_scene=SCENE_FILE.read_bytes();fixture_scene=scene_path.read_bytes()
    output=folder/'selection.json'
    holders={};states=[];editor_updates=[];combat_calls=[];audio_transitions=[]
    phase=lambda:holders['session'].frame if 'session' in holders else 0
    original_game_init=g_temple_gameplay.Exploration.__init__
    original_editor_init=Editor.__init__
    original_editor_update=Editor.update
    original_controls=g_temple_combat_view.controls
    original_audio_init=g_temple_exploration_view.Audio.__init__
    original_selection_audio=viewer.selection_audio

    def selection_audio(audio,paused,was_paused):
        if audio and paused!=was_paused:audio_transitions.append([phase(),paused])
        return original_selection_audio(audio,paused,was_paused)

    def audio_init(self,*args,**kwargs):
        original_audio_init(self,*args,**kwargs);holders['audio']=self

    def game_init(self,*args,**kwargs):
        original_game_init(self,*args,**kwargs);holders['game']=self

    def editor_init(self,*args,**kwargs):
        original_editor_init(self,*args,**kwargs);holders['editor']=self

    def editor_update(self,*args,**kwargs):
        editor_updates.append(phase());return original_editor_update(self,*args,**kwargs)

    def controls(*args,**kwargs):
        combat_calls.append(phase());return original_controls(*args,**kwargs)

    def pressed(key):
        schedule={2:{pr.KEY_F8},3:{pr.KEY_E,pr.KEY_F5},4:{pr.KEY_ESCAPE},
                  5:{pr.KEY_F2},6:{pr.KEY_F8},7:{pr.KEY_DELETE,pr.KEY_S,pr.KEY_F2},
                  9:{pr.KEY_ESCAPE},10:{pr.KEY_F2},12:{pr.KEY_ESCAPE}}
        return key in schedule.get(phase(),set())

    def down(key):
        return key==pr.KEY_W or (phase()==7 and key==pr.KEY_LEFT_CONTROL)

    base=codex_selection.SelectionSession
    class ProbeSession(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,output_path=output,**kwargs)
            self.frame=0;self.mouse=(900.,500.);self.expected=None;holders['session']=self

        def handle_keys(self):
            self.frame+=1
            return super().handle_keys()

        def present(self,camera,viewport,context=None):
            game,editor=holders['game'],holders['editor']
            before=deepcopy(self.selected)
            if self.frame in (3,8):
                rect=codex_selection.rectangle(viewport);x,y,w,h=rect
                # Use a visible authored component, verified by the same exact
                # ray the real pointer will use. Avoid the selection HUD.
                candidates=[i for i in self.instances if i['metadata'].get('authored_object_id') and not i['metadata'].get('animated')]
                for item in candidates:
                    center=[(a+b)*.5 for a,b in zip(item['bounds']['min'],item['bounds']['max'])]
                    p=pr.get_world_to_screen_ex(pr.Vector3(*center),camera,int(w),int(h))
                    point=(p.x+x,p.y+y)
                    if not (x+5<point[0]<x+w-5 and y+95<point[1]<y+h-5):continue
                    ray=codex_selection.screen_ray(camera,point,rect)
                    hit=self.pick_ray(*ray)
                    if hit and hit['metadata'].get('authored_object_id'):
                        self.mouse=point;self.expected=hit['id'];break
                else:raise AssertionError('No visible authored object in native selection fixture')
            elif self.frame==7:self.mouse=(1300.,400.)
            super().present(camera,viewport,context)
            state=dict(frame=self.frame,enabled=self.enabled,editor=editor.active,
                clock=game.clock,player=[game.walk.x,game.walk.y],focus=list(editor.focus),
                document=deepcopy(game.scene.document),ammo=deepcopy(game.player['ammo']),
                audio_time_ms=holders['audio'].engine.time_ms,
                selected=[i['id'] for i in self.selected],instances=len(self.instances),
                viewport=list(codex_selection.rectangle(viewport)))
            states.append(state)
            assert not pr.is_audio_device_ready(),'Automated selection review opened Raylib audio'
            assert holders['audio'].engine.volume==0.,'Automated miniaudio output was audible'
            if self.frame==1:
                assert not output.exists(),'Selection wrote a file while disabled'
                assert not self.instances
            if self.frame in (2,3,4):
                for key in ('clock','player','document','ammo'):
                    assert state[key]==states[0][key],('Selection leaked gameplay input',self.frame,key)
            if self.frame in (3,4):
                assert state['audio_time_ms']==states[1]['audio_time_ms'],'Selection audio kept advancing'
            if self.frame in (6,7,8,9):
                baseline=next(s for s in states if s['frame']==5)
                for key in ('clock','player','focus','document','ammo'):
                    assert state[key]==baseline[key],('Selection mutated editor/gameplay',self.frame,key)
            if self.frame in (3,8):
                assert self.selected and self.selected[0]['id']==self.expected
                assert self.selected[0]['pick_method']=='mesh_triangles'
                assert self.selected[0]['metadata']['source_document']==str(scene_path)
                pr.rl.rlDrawRenderBatchActive()
                image=pr.load_image_from_screen()
                pr.export_image(image,str(folder/('editor-selection.png' if editor.active else 'gameplay-selection.png')))
                pr.unload_image(image)
            if self.frame==7:assert self.selected==before,'Editor sidebar click changed selection'
            if self.frame==11:
                assert state['clock']>states[-2]['clock'],'Gameplay did not resume'
                assert state['player']!=states[-2]['player'],'W did not resume movement'

    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    with ExitStack() as stack:
        stack.enter_context(patch.object(codex_selection,'SelectionSession',ProbeSession))
        stack.enter_context(patch.object(g_temple_gameplay.Exploration,'__init__',game_init))
        stack.enter_context(patch.object(Editor,'__init__',editor_init))
        stack.enter_context(patch.object(Editor,'update',editor_update))
        stack.enter_context(patch.object(g_temple_exploration_view.Audio,'__init__',audio_init))
        stack.enter_context(patch.object(viewer,'selection_audio',selection_audio))
        stack.enter_context(patch.object(g_temple_combat_view,'controls',controls))
        stack.enter_context(patch.object(pr,'is_key_pressed',side_effect=pressed))
        stack.enter_context(patch.object(pr,'is_key_down',side_effect=down))
        stack.enter_context(patch.object(pr,'is_mouse_button_pressed',side_effect=lambda key:key==pr.MOUSE_BUTTON_LEFT and phase() in (3,7,8)))
        stack.enter_context(patch.object(pr,'is_mouse_button_down',side_effect=lambda key:key==pr.MOUSE_BUTTON_LEFT and phase() in (3,7,8)))
        stack.enter_context(patch.object(pr,'is_mouse_button_released',return_value=False))
        stack.enter_context(patch.object(pr,'get_mouse_position',side_effect=lambda:pr.Vector2(*holders['session'].mouse)))
        stack.enter_context(patch.object(pr,'get_mouse_wheel_move',return_value=0.))
        stack.enter_context(patch.object(pr,'get_frame_time',return_value=1/60))
        stack.enter_context(patch.object(sys,'argv',['temple_3d_viewer.py','--skip-intro','--scene',str(scene_path)]))
        viewer.run(fixed_cameras=True,living_assets=True)
    assert SCENE_FILE.read_bytes()==original_scene
    assert scene_path.read_bytes()==fixture_scene
    assert editor_updates==[5],editor_updates
    # The existing editor-to-play handoff reads controls once, while its
    # gameplay tick is still paused; selection-owned frames read none.
    assert combat_calls==[1,10,11],combat_calls
    assert audio_transitions==[[2,True],[5,False],[6,True],[10,False]],audio_transitions
    assert len(states)==11
    saved=json.loads(output.read_text(encoding='utf-8'))
    captures={}
    for name in ('gameplay','editor'):
        target=output_root/f'temple-{name}-selection.png'
        target.write_bytes((folder/f'{name}-selection.png').read_bytes())
        captures[name]=str(target)
    report=dict(frames=len(states),paused_frames=[2,3,4,6,7,8,9],editor_updates=editor_updates,
        combat_input_frames=combat_calls,authored_files_unchanged=True,audio_muted=True,
        raylib_audio_device_opened=False,audio_output_gain=0.,audio_pause_transitions=audio_transitions,
        window_hidden=True,output=str(output),
        selected=saved.get('selected'),captures=captures,
        states=[{k:v for k,v in s.items() if k!='document'} for s in states])
    (output_root/'temple-native-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    if '--native' in sys.argv:native_smoke()
    else:unittest.main()
