"""Opt-in selection contracts, including small hidden native raycasts.

All persistence goes to temporary directories. No test opens an audio device or
changes the user's codex_selection.json, scene files, or exported assets.
"""
import copy
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_selection import (MAX_SELECTION, SelectionSession, atomic_write,
    compose_transform, contains, matrix_values, screen_ray)


def picked(identity, x=0.):
    return dict(id=identity,label=identity,kind='prop',instance_id=identity,
        model_name='test_prop',asset_path='art/test_prop.glb',mesh_index=0,
        hit_position=[x,1.,-3.],hit_normal=[0.,0.,1.],distance=3.,
        bounds={'min':[x-.5,0.,-3.5],'max':[x+.5,2.,-2.5]},
        source={'file':'test_codex_selection.py','asset':'art/test_prop.glb'})


class SelectionPureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'selection.json'
        self.session=SelectionSession('test_scene',__file__,self.path)
        self.camera=dict(position=[0.,0.,0.],target=[0.,0.,-1.],up=[0.,1.,0.],fovy=90.,projection=0)

    def assertVector(self, actual, expected, places=6):
        for a,b in zip(actual,expected):
            self.assertAlmostEqual(a,b,places=places)

    def test_perspective_rays_use_offset_viewport_and_its_aspect_ratio(self):
        viewport=(100.,80.,800.,400.)
        origin,direction=screen_ray(self.camera,(500.,280.),viewport)
        self.assertVector(origin,(0,0,0));self.assertVector(direction,(0,0,-1))
        _,direction=screen_ray(self.camera,(700.,280.),viewport)
        self.assertVector(direction,(1/math.sqrt(2),0,-1/math.sqrt(2)))
        _,direction=screen_ray(self.camera,(500.,180.),viewport)
        self.assertVector(direction,(0,1/math.sqrt(5),-2/math.sqrt(5)))
        for point in ((99,280),(900,280),(500,79),(500,480)):
            self.assertIsNone(screen_ray(self.camera,point,viewport))
        self.assertFalse(contains((0,0,0,200),(0,50)))

    def test_orthographic_rays_are_parallel_with_shifted_origins(self):
        self.camera.update(position=[3.,2.,8.],target=[3.,2.,0.],fovy=10.,projection=1)
        origin,direction=screen_ray(self.camera,(700.,180.),(100.,80.,800.,400.))
        self.assertVector(origin,(8.,4.5,8.));self.assertVector(direction,(0,0,-1))
        origin2,direction2=screen_ray(self.camera,(300.,380.),(100.,80.,800.,400.))
        self.assertVector(origin2,(-2.,-.5,8.));self.assertVector(direction2,direction)

    def test_degenerate_camera_fails_explicitly(self):
        self.camera['target']=self.camera['position'][:]
        with self.assertRaisesRegex(ValueError,'Degenerate'):
            screen_ray(self.camera,(50,50),(0,0,100,100))

    def test_atomic_write_keeps_previous_record_if_replacement_fails(self):
        original={'selected':[picked('old')],'text':'湖心亭'}
        atomic_write(self.path,original)
        before=self.path.read_bytes()
        with patch('codex_selection.os.replace',side_effect=PermissionError('test lock')):
            with self.assertRaises(PermissionError):
                atomic_write(self.path,{'selected':[picked('new')]})
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')),[])
        self.assertNotIn(b'\r\n',before)
        self.assertEqual(json.loads(before),original)
        with self.assertRaises(ValueError):
            atomic_write(self.path,{'bad':math.nan})
        self.assertEqual(self.path.read_bytes(),before)

    def test_multiselect_toggle_clear_and_context_are_saved_locally(self):
        session=self.session
        self.assertFalse(self.path.exists())
        session.camera=copy.deepcopy(self.camera);session.viewport=[100,80,800,400]
        session.context={'world':'canals','player_position':[1,.325,2]}
        session.select_hit(picked('a'))
        session.select_hit(picked('b',2),additive=True)
        self.assertEqual([v['id'] for v in json.loads(self.path.read_text())['selected']],['a','b'])
        session.select_hit(picked('a'),additive=True)
        self.assertEqual([v['id'] for v in session.selected],['b'])
        session.select_hit(None,additive=True)
        self.assertEqual([v['id'] for v in session.selected],['b'])
        session.clear();self.assertTrue(session.save())
        record=json.loads(self.path.read_text())
        self.assertEqual(record['selected'],[])
        self.assertEqual(record['camera'],self.camera)
        self.assertEqual(record['viewport'],[100,80,800,400])
        self.assertEqual(record['context']['world'],'canals')
        self.assertEqual(record['scene'],'test_scene')
        self.assertEqual(record['session_id'],session.session_id)
        self.assertEqual(record['process_id'],os.getpid())
        session.select_hit(picked('c'));session.select_hit(None)
        self.assertEqual(json.loads(self.path.read_text())['selected'],[])

    def test_limit_and_save_error_preserve_existing_selection(self):
        session=self.session;session.selected=[picked(str(i)) for i in range(MAX_SELECTION)]
        session.select_hit(picked('overflow'),additive=True)
        self.assertEqual(len(session.selected),MAX_SELECTION)
        self.assertIn('limit',session.status.lower())
        session.selected=[picked('good')];session._dirty=True
        self.assertTrue(session.save());before=self.path.read_bytes()
        session.selected=[picked('new')];session._dirty=True
        with patch('codex_selection.atomic_write',side_effect=PermissionError('test lock')):
            self.assertFalse(session.save())
        self.assertTrue(session._dirty);self.assertIn('test lock',session.error)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(session.save());self.assertIsNone(session.error)
        self.assertEqual(json.loads(self.path.read_text())['selected'][0]['id'],'new')


class SelectionNativeTests(unittest.TestCase):
    """Small real Raylib meshes, with neither asset loading nor audio startup."""
    @classmethod
    def setUpClass(cls):
        cls.environment=patch.dict(os.environ,{'HAUNTED_MUTE_AUDIO':'1'})
        cls.environment.start()
        import pyray as pr
        cls.pr=pr
        pr.set_trace_log_level(pr.LOG_ERROR)
        pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
        pr.init_window(64,64,'Codex selection native tests (muted)')
        if not pr.is_window_ready():
            cls.environment.stop()
            raise unittest.SkipTest('Native hidden graphics context is unavailable')
        pr.begin_drawing();pr.clear_background(pr.BLACK);pr.end_drawing()

    @classmethod
    def tearDownClass(cls):
        cls.pr.enable_cursor();cls.pr.close_window();cls.environment.stop()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'selection.json'
        self.session=SelectionSession('test_scene',__file__,self.path)
        self.session.enabled=True
        self.owned=[]

    def model(self, quads, transform=None):
        # Keep CPU arrays alive, and never hand borrowed buffers to UnloadModel.
        # Raylib collision/bounds functions operate on these same Mesh structs
        # used by loaded GLBs; no mocked intersections are involved.
        pr=self.pr;points=[]
        for a,b,c,d in quads:
            points.extend((a,b,c,a,c,d))
        vertices=pr.ffi.new('float[]',[v for point in points for v in point])
        mesh=pr.ffi.new('Mesh *');mesh.vertexCount=len(points);mesh.triangleCount=len(points)//3;mesh.vertices=vertices
        model=pr.ffi.new('Model *');model.meshCount=1;model.meshes=mesh
        model.transform=transform if transform is not None else pr.matrix_identity()
        self.owned.append((model,mesh,vertices))
        return model[0]

    @staticmethod
    def wall(z,left=-2.,right=2.,bottom=-2.,top=2.):
        return ((left,bottom,z),(right,bottom,z),(right,top,z),(left,top,z))

    def register(self, model, name, **kwargs):
        self.session.register_model(model,name,asset_path='art/'+name+'.glb',identity=name,**kwargs)

    def test_hidden_context_opens_no_audio_and_mode_is_opt_in(self):
        pr=self.pr
        self.assertTrue(pr.is_window_state(pr.FLAG_WINDOW_HIDDEN))
        self.assertFalse(pr.is_audio_device_ready())
        self.session.enabled=False
        self.register(self.model([self.wall(-3)]),'ignored')
        self.assertEqual(self.session.instances,[])
        self.assertFalse(self.path.exists())
        pr.disable_cursor();self.session.set_enabled(True)
        self.assertFalse(pr.is_cursor_hidden())
        self.session.set_enabled(False)
        self.assertTrue(pr.is_cursor_hidden())
        self.assertFalse(json.loads(self.path.read_text())['mode_enabled'])
        pr.enable_cursor()

    def test_projected_native_camera_points_roundtrip_through_viewport_ray(self):
        pr=self.pr
        for projection,fovy in ((pr.CAMERA_PERSPECTIVE,63.),(pr.CAMERA_ORTHOGRAPHIC,12.)):
            camera=pr.Camera3D(pr.Vector3(3,2,8),pr.Vector3(0,1,-2),pr.Vector3(0,1,0),fovy,projection)
            point=pr.Vector3(1,1,0);pixel=pr.get_world_to_screen_ex(point,camera,800,450)
            origin,direction=screen_ray(camera,(pixel.x+200,pixel.y+80),(200,80,800,450))
            delta=[getattr(point,a)-origin[i] for i,a in enumerate(('x','y','z'))]
            distance=sum(a*b for a,b in zip(delta,direction))
            self.assertGreater(distance,0.)
            self.assertLess(math.dist(delta,[distance*v for v in direction]),1e-5)

    def test_nearest_surface_wins_independently_of_registration_order(self):
        far=self.model([self.wall(-6)]);near=self.model([self.wall(-2)])
        for ordered in (((far,'far'),(near,'near')),((near,'near'),(far,'far'))):
            self.session.begin_frame()
            for model,name in ordered:self.register(model,name)
            result=self.session.pick_ray((0,0,0),(0,0,-1))
            self.assertEqual(result['id'],'near')
            self.assertAlmostEqual(result['distance'],2.,places=5)
            self.assertAlmostEqual(result['hit_position'][2],-2.,places=5)
            self.assertEqual(result['mesh_index'],0)
            self.assertEqual(result['pick_method'],'mesh_triangles')

    def test_one_authored_object_spanning_material_batches_has_union_bounds(self):
        left=self.model([self.wall(-3,left=-3,right=-1)])
        right=self.model([self.wall(-4,left=1,right=4)])
        self.session.register_model(left,'left_material',identity='whole_arch')
        self.session.register_model(right,'right_material',identity='whole_arch')
        result=self.session.pick_ray((-2,0,0),(0,0,-1))
        self.assertEqual(result['id'],'whole_arch')
        self.assertEqual(result['model_name'],'left_material')
        self.assertEqual(result['bounds'],{'min':[-3.,-2.,-4.],'max':[4.,2.,-3.]})
        self.assertEqual(result['hit_position'],[-2.,0.,-3.])
        self.session.select_hit(result)
        right_hit=self.session.pick_ray((2,0,0),(0,0,-1))
        self.session.select_hit(right_hit,additive=True)
        self.assertEqual(self.session.selected,[])

    def test_hollow_doorway_does_not_pick_its_enclosing_box(self):
        frame=self.model([self.wall(-2,left=-2,right=-.6),self.wall(-2,left=.6,right=2),
                          self.wall(-2,left=-.6,right=.6,bottom=.9),self.wall(-2,left=-.6,right=.6,top=-.9)])
        rear=self.model([self.wall(-5)])
        self.register(frame,'open_frame');self.register(rear,'room_back_wall')
        through=self.session.pick_ray((0,0,0),(0,0,-1))
        self.assertEqual(through['id'],'room_back_wall')
        self.assertAlmostEqual(through['distance'],5.,places=5)
        jamb=self.session.pick_ray((1,0,0),(0,0,-1))
        self.assertEqual(jamb['id'],'open_frame')

    def test_rejected_hidden_face_continues_to_visible_face_in_same_mesh(self):
        merged=self.model([self.wall(-2),self.wall(-4)])
        self.register(merged,'clipped_batch',metadata={'_reject_hit':lambda p:p[2]>-3.,'label':'visible back'})
        result=self.session.pick_ray((0,0,0),(0,0,-1))
        self.assertIsNotNone(result)
        self.assertEqual(result['id'],'clipped_batch')
        self.assertAlmostEqual(result['distance'],4.,places=4)
        self.assertAlmostEqual(result['hit_position'][2],-4.,places=4)
        self.assertNotIn('_reject_hit',result['metadata'])
        json.dumps(result,allow_nan=False)

    def test_root_transform_is_applied_once_to_bounds_and_ray_geometry(self):
        pr=self.pr
        vertices=[(x,y,z) for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                                       (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
        quads=[tuple(vertices[i] for i in face) for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))]
        model=self.model(quads,pr.matrix_translate(2,1,0))
        matrix=compose_transform(model,(10,3,-5),(2,3,1),90.)
        center=pr.vector3_transform(pr.Vector3(0,0,0),matrix)
        for actual,expected in zip((center.x,center.y,center.z),(10.,6.,-9.)):
            self.assertAlmostEqual(actual,expected,places=5)
        self.register(model,'transformed_cube',position=(10,3,-5),scale=(2,3,1),yaw=90.)
        item=self.session.instances[0]
        for actual,expected in zip(item['bounds']['min'],(9.,3.,-11.)):
            self.assertAlmostEqual(actual,expected,places=5)
        for actual,expected in zip(item['bounds']['max'],(11.,9.,-7.)):
            self.assertAlmostEqual(actual,expected,places=5)
        result=self.session.pick_ray((10,15,-9),(0,-1,0))
        self.assertIsNotNone(result)
        self.assertEqual(result['id'],'transformed_cube')
        self.assertAlmostEqual(result['distance'],6.,places=5)
        self.assertAlmostEqual(result['hit_position'][1],9.,places=5)
        self.assertEqual(item['transform'],matrix_values(matrix))
        # A renderer may restore/change model.transform after its draw call.
        # The registered instance owns the matrix value it actually rendered.
        model.transform=pr.matrix_translate(100,100,100)
        self.assertEqual(self.session.instances[0]['transform'],matrix_values(matrix))
        self.assertEqual(self.session.pick_ray((10,15,-9),(0,-1,0))['id'],'transformed_cube')

    def test_inside_bounds_and_unpickable_decoration_do_not_hide_nearer_hit(self):
        enclosure=self.model([self.wall(-5),self.wall(3)])
        middle=self.model([self.wall(-2)])
        decoration=self.model([self.wall(-1)])
        self.register(enclosure,'enclosure');self.register(middle,'middle')
        self.register(decoration,'effect',metadata={'pickable':False})
        result=self.session.pick_ray((0,0,0),(0,0,-1))
        self.assertEqual(result['id'],'middle')
        self.assertAlmostEqual(result['distance'],2.,places=5)


if __name__=='__main__':
    unittest.main()
