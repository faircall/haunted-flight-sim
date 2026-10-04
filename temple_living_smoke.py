"""Actual GPU skinning, contact/clearance validation and multi-angle art review."""
from setup_temple_3d import ensure_runtime


def surface_distance(points, triangles):
    """Distances to triangle interiors and edges, rather than joint capsules."""
    import numpy as np
    a,b,c=triangles[:,0],triangles[:,1],triangles[:,2]
    ab,ac=b-a,c-a
    normal=np.cross(ab,ac);normal_squared=np.sum(normal*normal,axis=1)
    delta=points[:,None,:]-a
    plane=np.einsum('ptd,td->pt',delta,normal)
    d00=np.sum(ab*ab,axis=1);d01=np.sum(ab*ac,axis=1);d11=np.sum(ac*ac,axis=1)
    d20=np.einsum('ptd,td->pt',delta,ab);d21=np.einsum('ptd,td->pt',delta,ac)
    divisor=np.maximum(d00*d11-d01*d01,1e-20)
    u=(d11*d20-d01*d21)/divisor;v=(d00*d21-d01*d20)/divisor
    interior=(u>=0)&(v>=0)&(u+v<=1)&(normal_squared>1e-16)
    best=np.where(interior,plane*plane/np.maximum(normal_squared,1e-20),np.inf)
    for start,end in ((a,b),(b,c),(c,a)):
        edge=end-start;relative=points[:,None,:]-start
        t=np.clip(np.einsum('ptd,td->pt',relative,edge)/np.maximum(np.sum(edge*edge,axis=1),1e-20),0,1)
        difference=relative-t[:,:,None]*edge
        best=np.minimum(best,np.sum(difference*difference,axis=2))
    return np.sqrt(np.min(best,axis=1))


def points_inside_mesh(points, triangles):
    """Odd ray crossings on each closed trouser component identify penetration."""
    import numpy as np
    direction=np.array([.381,.173,1.])
    a,b,c=triangles[:,0],triangles[:,1],triangles[:,2]
    e1,e2=b-a,c-a;h=np.cross(direction,e2)
    determinant=np.sum(e1*h,axis=1);valid=np.abs(determinant)>1e-10
    inverse=np.where(valid,1/np.where(valid,determinant,1),0)
    relative=points[:,None,:]-a
    u=np.einsum('ptd,td->pt',relative,h)*inverse
    q=np.cross(relative,e1)
    v=np.einsum('ptd,d->pt',q,direction)*inverse
    t=np.einsum('ptd,td->pt',q,e2)*inverse
    hits=valid&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-7)
    return np.count_nonzero(hits,axis=1)%2==1


def triangle_components(vertices, triangles):
    """Weld export seams to keep separate closed seat and trouser-leg volumes."""
    keys=[tuple(point.round(5)) for point in vertices]
    parent={key:key for key in keys}
    def root(key):
        while parent[key]!=key:
            parent[key]=parent[parent[key]];key=parent[key]
        return key
    for triangle in triangles:
        first=root(keys[triangle[0]])
        for index in triangle[1:]:parent[root(keys[index])]=first
    components={}
    for triangle in triangles:components.setdefault(root(keys[triangle[0]]),[]).append(triangle)
    return list(components.values())


def paired_leg_metrics(points):
    """Side-view coordination from measured joints, in lateral/forward/up."""
    import math
    h,k,a=(points[key] for key in ('hip','knee','ankle'))
    u=[x-y for x,y in zip(h,k)];v=[x-y for x,y in zip(a,k)]
    cosine=sum(x*y for x,y in zip(u,v))/math.dist(h,k)/math.dist(a,k)
    return dict(points,knee_flex_degrees=180-math.degrees(math.acos(max(-1.,min(1.,cosine)))),
        thigh_angle_degrees=math.degrees(math.atan2(k[1]-h[1],h[2]-k[2])),
        hip_ankle_angle_degrees=math.degrees(math.atan2(a[1]-h[1],h[2]-a[2])),
        forward_knee_offset=k[1]-h[1],forward_ankle_offset=a[1]-h[1],
        knee_height_from_hip=k[2]-h[2])


def main():
    import hashlib
    import json
    from pathlib import Path
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    import pyray as pr
    from g_temple_living import LivingScene, ANIMATION_SAMPLE_SECONDS
    from photo_asset_pipeline.temple3d.living import gait
    from animation_viewer_3d import sample_pose

    output = Path(__file__).resolve().parent/'artifacts'/'temple3d-living'
    output.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(512,512,'GPU living-asset verification')
    target = pr.load_render_texture(256,256)
    assets = None
    try:
        assets = LivingScene()

        def cpu_vertices(model):
            buffers=[]
            for index in range(model.meshCount):
                mesh=model.meshes[index]
                for name in ('vertices','normals','animVertices','animNormals'):
                    pointer=getattr(mesh,name)
                    if pointer!=pr.ffi.NULL:
                        buffers.append(bytes(pr.ffi.buffer(pointer,mesh.vertexCount*12)))
            return b''.join(buffers)

        def bones():
            mesh=assets.player.meshes[0]
            return bytes(pr.ffi.buffer(mesh.boneMatrices,mesh.boneCount*pr.ffi.sizeof('Matrix')))

        def render(kind,name,angle=0.,phase=0.,now=.5,clip='walk',inspection=True,dt=None,view=None):
            assets.environment(now,inspection,[])
            assets.pose(clip,phase,dt)
            if kind=='head':
                camera=pr.Camera3D(pr.Vector3(0,24,55),pr.Vector3(0,23.8,0),pr.Vector3(0,1,0),7.4,pr.CAMERA_ORTHOGRAPHIC)
            elif kind=='legs':
                camera=pr.Camera3D(pr.Vector3(0,8,55),pr.Vector3(0,6.5,0),pr.Vector3(0,1,0),15,pr.CAMERA_ORTHOGRAPHIC)
            elif kind=='upper':
                camera=pr.Camera3D(pr.Vector3(0,21,55),pr.Vector3(0,18,0),pr.Vector3(0,1,0),18,pr.CAMERA_ORTHOGRAPHIC)
            elif view=='above':
                camera=pr.Camera3D(pr.Vector3(0,70,0),pr.Vector3(0,13,0),pr.Vector3(0,0,-1),24,pr.CAMERA_ORTHOGRAPHIC)
            elif view=='level-side':
                camera=pr.Camera3D(pr.Vector3(0,16,55),pr.Vector3(0,16,0),pr.Vector3(0,1,0),32,pr.CAMERA_ORTHOGRAPHIC)
            elif kind=='player':
                camera=pr.Camera3D(pr.Vector3(0,26,55),pr.Vector3(0,15,0),pr.Vector3(0,1,0),38,pr.CAMERA_ORTHOGRAPHIC)
            else:
                camera=pr.Camera3D(pr.Vector3(0,99,220),pr.Vector3(0,61,0),pr.Vector3(0,1,0),145,pr.CAMERA_ORTHOGRAPHIC)
            pr.begin_texture_mode(target)
            pr.clear_background(pr.Color(25,31,36,255))
            pr.begin_mode_3d(camera)
            if kind in ('player','head','legs','upper'):
                assets.yaw=angle
                assets.draw_player(0,0,0)
            else:assets.draw_willow(0,0,angle)
            pr.end_mode_3d();pr.end_texture_mode()
            im=pr.load_image_from_texture(target.texture)
            pr.image_flip_vertical(im)
            path=output/(name+'.png')
            pr.export_image(im,str(path));pr.unload_image(im)
            return np.asarray(Image.open(path).convert('RGB')).copy()

        player_before=cpu_vertices(assets.player)
        tree_before=cpu_vertices(assets.willow)
        first=render('player','walk-0',phase=0.)
        first_bones=bones()
        middle=render('player','walk-quarter',phase=.25)
        assert first_bones!=bones(),'Native bone matrices did not change'
        assert np.count_nonzero(np.any(first!=middle,axis=2))>100,'Skinning did not change rendered pixels'
        assert player_before==cpu_vertices(assets.player),'Character vertices were deformed on the CPU'
        transition=render('player','idle-transition-start',phase=.1,clip='idle',dt=0.)
        assert np.count_nonzero(np.any(middle!=transition,axis=2))<20,'Clip transition snapped the pose'
        halfway=render('player','idle-transition-half',phase=.1,clip='idle',dt=.07)
        end=render('player','idle-transition-end',phase=.1,clip='idle',dt=.14)
        assert not np.array_equal(halfway,end),'Pose blend did not advance'
        still=render('tree','wind-0',now=0.)
        gust=render('tree','wind-3',now=3.)
        assert np.count_nonzero(np.any(still!=gust,axis=2))>100,'Wind did not change rendered pixels'
        assert tree_before==cpu_vertices(assets.willow),'Tree vertices were deformed on the CPU'

        # Inspect the exported/native skeleton too: an authoring-only test would
        # miss reversed local axes, mismatched joint indices or GLB start delays.
        joint_ids={pr.ffi.string(assets.player.bones[i].name).decode():i for i in range(assets.player.boneCount)}
        from test_temple_living import glb,accessor
        document,binary=glb('player');skin=document['skins'][0]
        joint_names=[document['nodes'][node]['name'] for node in skin['joints']]
        native_ids=np.array([joint_ids[name] for name in joint_names])
        rest_vertices=[];skin_joints=[];skin_weights=[];pants_faces=[];hand_faces=[];hand_vertices=[];offset=0
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                attrs=primitive['attributes'];v=accessor(document,binary,attrs['POSITION'])
                j=accessor(document,binary,attrs['JOINTS_0']);w=accessor(document,binary,attrs['WEIGHTS_0'])
                uv=accessor(document,binary,attrs['TEXCOORD_0'])*256
                faces=accessor(document,binary,primitive['indices']).reshape(-1,3)
                pants=(uv[:,0]>0)&(uv[:,0]<64)&(uv[:,1]>64)&(uv[:,1]<192)
                hand=np.any(np.isin(j,[joint_names.index('hand.L'),joint_names.index('hand.R')])&(w>.3),axis=1)
                pants_faces.extend(faces[np.all(pants[faces],axis=1)]+offset)
                hand_faces.extend(faces[np.all(hand[faces],axis=1)]+offset)
                hand_vertices.extend(np.flatnonzero(hand)+offset)
                rest_vertices.extend(v);skin_joints.extend(native_ids[j]);skin_weights.extend(w);offset+=len(v)
        rest_vertices=np.asarray(rest_vertices);skin_joints=np.asarray(skin_joints);skin_weights=np.asarray(skin_weights)
        hand_faces=np.asarray(hand_faces);hand_vertices=np.asarray(hand_vertices)
        pants_components=[np.asarray(component) for component in triangle_components(rest_vertices,np.asarray(pants_faces))]
        assert len(hand_vertices)>20 and pants_components,'Clearance review failed to find hand and trouser geometry'
        # Ray parity is meaningful only for closed volumes. Atlas seams must
        # not leave holes in the geometry selected for the collision review.
        for component in pants_components:
            edges={}
            for triangle in component:
                keys=[tuple(point.round(5)) for point in rest_vertices[triangle]]
                for a,b in zip(keys,keys[1:]+keys[:1]):
                    edge=tuple(sorted((a,b)));edges[edge]=edges.get(edge,0)+1
            assert all(count==2 for count in edges.values()),'Trouser geometry review selected an open surface'
        homogeneous=np.column_stack((rest_vertices,np.ones(len(rest_vertices))))
        mesh_clearance={clip:dict(minimum_surface_gap=float('inf'),maximum_penetration=0.,worst_phase=None,closest_phase=None)
                        for clip in ('idle','walk','run')}

        def review_deformed_hands(clip,phase):
            # Evaluate the same weighted bone transforms as the GPU in local
            # temporary arrays. The model's CPU vertex buffers remain untouched.
            matrices=np.frombuffer(bones(),dtype=np.float32).reshape(assets.player.boneCount,4,4)
            deformed=np.zeros((len(rest_vertices),3))
            for influence in range(4):
                transformed=np.einsum('nij,nj->ni',matrices[skin_joints[:,influence],:3],homogeneous)
                deformed+=transformed*skin_weights[:,influence,None]
            if phase==0.:
                index=int(hand_vertices[0]);native=np.zeros(3)
                for joint,weight in zip(skin_joints[index],skin_weights[index]):
                    point=pr.vector3_transform(pr.Vector3(*rest_vertices[index]),assets.player.meshes[0].boneMatrices[int(joint)])
                    native+=weight*np.array([point.x,point.y,point.z])
                np.testing.assert_allclose(deformed[index],native,atol=2e-5,err_msg='Geometry review used the wrong bone-matrix layout')
            triangles=deformed[hand_faces]
            samples=np.concatenate((deformed[hand_vertices],triangles.mean(axis=1),
                                    (triangles[:,0]+triangles[:,1])/2,(triangles[:,1]+triangles[:,2])/2,
                                    (triangles[:,2]+triangles[:,0])/2))
            samples=np.unique(samples.round(6),axis=0)
            distance=np.full(len(samples),np.inf);inside=np.zeros(len(samples),dtype=bool)
            for component in pants_components:
                trousers=deformed[component]
                distance=np.minimum(distance,surface_distance(samples,trousers))
                inside|=points_inside_mesh(samples,trousers)
            gap=float(np.min(distance))
            result=mesh_clearance[clip]
            if gap<result['minimum_surface_gap']:
                result.update(minimum_surface_gap=gap,closest_phase=phase)
            penetration=float(np.max(distance[inside])) if np.any(inside) else 0.
            if penetration>result['maximum_penetration']:
                deepest=np.flatnonzero(inside)[int(np.argmax(distance[inside]))]
                result.update(maximum_penetration=penetration,worst_phase=phase,
                              penetration_point=samples[deepest].tolist())
        contact_error=0.;plant_error=0.;lateral_error=0.;segment_error=0.;max_flex={};extension={};walking_timing=[];running_posture=[];run_flights=[]
        running_hips=[];running_necks=[];running_chest_banks=[];running_chest_tilts=[];running_landings=[];front_hands=[]
        walking_support=[];walking_hand_drift=[];running_arm_cycle=[]
        running_recovery=[];running_pairs=[];lateral_swing={};pelvis_travel={};running_rear_pump=[]
        running_leg_samples={side:[] for side in ('L','R')};running_arm_samples={side:[] for side in ('L','R')}
        walking_leg_samples={side:[] for side in ('L','R')}
        stance_tracks={clip:{side:[] for side in ('L','R')} for clip in ('walk','run')}
        bones_by_label={'hip':'thigh','knee':'shin','ankle':'foot',
                        'shoulder':'arm','elbow':'forearm','wrist':'hand'}
        import math
        for clip in ('walk','run'):
            animation=assets.animations[assets.clips[clip]]
            period=assets.clip_seconds[clip]
            flex=[];knees=[];hands=[];hand_swing=[];outward=[];hips=[]
            for frame in range(animation.frameCount):
                phase=frame*ANIMATION_SAMPLE_SECONDS/period
                assets.pose(clip,phase+1e-6)
                native_pose=sample_pose(pr,assets,joint_ids)
                hips.append(native_pose['points']['hip'])
                for side in ('L','R'):
                    for start,end in (('hip','knee'),('knee','ankle'),('shoulder','elbow'),('elbow','wrist')):
                        p=native_pose['points']
                        a=assets.player.bindPose[joint_ids[bones_by_label[start]+'.'+side]].translation
                        b=assets.player.bindPose[joint_ids[bones_by_label[end]+'.'+side]].translation
                        rest=math.dist((a.x,a.y,a.z),(b.x,b.y,b.z))
                        segment_error=max(segment_error,abs(math.dist(p[start+'.'+side],p[end+'.'+side])-rest))
                assert all(np.isfinite(p).all() for p in native_pose['points'].values()),'Non-finite native pose'
                review_deformed_hands(clip,phase)
                if clip=='run':
                    running_posture.append(native_pose['angles'])
                    run_flights.append((min(native_pose['sole_clearance'].values()),native_pose['points']['hip'][1]))
                    running_hips.append(native_pose['points']['hip'])
                    running_necks.append(native_pose['points']['neck'])
                    hip=native_pose['points']['hip'];neck=native_pose['points']['neck']
                    running_chest_banks.append(math.degrees(math.atan2(neck[0]-hip[0],neck[1]-hip[1])))
                    running_chest_tilts.append(math.degrees(math.atan2(math.hypot(neck[0]-hip[0],neck[2]-hip[2]),neck[1]-hip[1])))
                    legs={}
                    for suffix,offset in (('L',0.),('R',.5)):
                        local_phase=(phase+offset)%1.
                        points={key:tuple(native_pose['points'][key+'.'+suffix][axis] for axis in (0,2,1))
                                for key in ('hip','knee','ankle')}
                        legs[suffix]=paired_leg_metrics(dict(points,local_phase=local_phase,
                            stance=local_phase<gait.SETTINGS['run']['stance'],
                            clearance=native_pose['sole_clearance'][suffix]))
                    running_pairs.append(dict(phase=phase,native_frame=assets.animation_frame,legs=legs))
                for suffix,side in (('L',0.),('R',.5)):
                    points=[]
                    for name in ('thigh.','shin.','foot.'):
                        index=joint_ids[name+suffix]
                        points.append(pr.vector3_transform(assets.player.bindPose[index].translation,assets.player.meshes[0].boneMatrices[index]))
                    h,k,a=points
                    knees.append(k.z-h.z)
                    hands.append(native_pose['points']['hand.'+suffix][2]-h.z)
                    hand_swing.append(native_pose['points']['hand.'+suffix][2]-native_pose['points']['shoulder.'+suffix][2])
                    u=np.array([h.x-k.x,h.y-k.y,h.z-k.z]);v=np.array([a.x-k.x,a.y-k.y,a.z-k.z])
                    flex.append(180-math.degrees(math.acos(float(np.clip(np.dot(u,v)/(np.linalg.norm(u)*np.linalg.norm(v)),-1,1)))))
                    if clip=='walk':
                        p=(phase+side)%1.
                        walking_leg_samples[suffix].append((p,native_pose['points']['ankle.'+suffix],
                                                            native_pose['points']['knee.'+suffix],assets.animation_frame))
                        walking_timing.append((flex[-1],p,a.z-h.z))
                        if .05<p<.34:walking_support.append(flex[-1])
                        if .22<p<.28 or .72<p<.78:
                            sign=-1 if suffix=='L' else 1
                            hand=native_pose['points']['hand.'+suffix]
                            shoulder=native_pose['points']['shoulder.'+suffix]
                            walking_hand_drift.append(sign*(hand[0]-shoulder[0]))
                    else:
                        p=(phase+side)%1.
                        running_arm_cycle.append((native_pose['angles']['elbow.'+suffix],p,hands[-1]))
                        running_recovery.append((p,flex[-1],k.z-h.z,k.y-h.y,a.z-h.z))
                        sign=-1 if suffix=='L' else 1
                        running_leg_samples[suffix].append((p,flex[-1],sign*(k.x-h.x)))
                        running_arm_samples[suffix].append((p,native_pose['angles']['elbow.'+suffix],hands[-1]))
                        if hands[-1]<-.4:
                            running_rear_pump.append((native_pose['angles']['elbow.'+suffix],p,hands[-1]))
                        if p<.025:running_landings.append((flex[-1],a.z-h.z))
                        if .45<p<.55:
                            sign=-1 if suffix=='L' else 1
                            front_hands.append(sign*(native_pose['points']['hand.'+suffix][0]-native_pose['points']['hip'][0]))
                    foot=gait.foot(clip,phase+side)
                    sign=-1 if suffix=='L' else 1
                    track=gait.foot_lateral(clip,sign,0.)
                    if foot['stance']:
                        contact=gait.HEEL if foot['pitch']>=0 else gait.TOE
                        index=joint_ids['foot.'+suffix];rest=assets.player.bindPose[index].translation
                        point=pr.vector3_transform(pr.Vector3(rest.x,.1,contact),assets.player.meshes[0].boneMatrices[index])
                        contact_error=max(contact_error,abs(point.y))
                        expected=gait.SETTINGS[clip]['front']+contact
                        world=point.z+gait.SETTINGS[clip]['stride']*((phase+side)%1.)
                        plant_error=max(plant_error,abs(world-expected))
                        stance_tracks[clip][suffix].append(((phase+side)%1.,point.z-contact))
                        expected_lateral=gait.foot_lateral(clip,sign,(phase+side)%1.)
                        assert abs(expected_lateral-track)<1e-8,'Authored stance track moved sideways'
                        lateral_error=max(lateral_error,abs(point.x-track))
                    else:
                        outward.append(sign*(a.x-track))
            max_flex[clip]=max(flex)
            lateral_swing[clip]=dict(minimum=min(outward),maximum=max(outward),
                                      travel=max(outward)-min(outward))
            pelvis_travel[clip]=max(p[0] for p in hips)-min(p[0] for p in hips)
            assert .04<lateral_swing[clip]['travel']<.6,(clip,'Recovery foot arc lost its narrow natural track',lateral_swing[clip])
            assert max(abs(v) for v in outward)<.6,(clip,'Recovery foot opened too far from its planted track',lateral_swing[clip])
            assert pelvis_travel[clip]>.45,(clip,'Pelvis did not transfer weight laterally',pelvis_travel[clip])
            minimum,maximum=(40.,80.) if clip=='walk' else (80.,105.)
            assert minimum<max(flex)<maximum,(clip,'Knee recovery lost its natural range',max(flex))
            assert min(flex)<10,(clip,'Support leg remained crouched')
            assert min(knees)<(-gait.THIGH*.08 if clip=='walk' else -gait.THIGH*.25),(clip,'Thigh never extended behind hips')
            # Measure arm swing from its own shoulder so changing adult torso
            # proportions or the forward running lean does not alter the test.
            assert min(hand_swing)<-1.5,(clip,'Hands never swung behind shoulders')
            extension[clip]=dict(minimum_knee_flex=min(flex),rear_knee=min(knees),rear_hand=min(hands),
                                 rear_hand_from_shoulder=min(hand_swing))
        idle=assets.animations[assets.clips['idle']]
        for frame in range(idle.frameCount):
            phase=frame*ANIMATION_SAMPLE_SECONDS/assets.clip_seconds['idle']
            assets.pose('idle',phase+1e-6)
            review_deformed_hands('idle',phase)
        assert contact_error<.08,('Foot left the floor during stance',contact_error)
        assert plant_error<.08,('Foot slid during stance',plant_error)
        assert lateral_error<.025,('Weight shift dragged planted foot sideways',lateral_error)
        assert segment_error<.01,('Export changed limb lengths',segment_error)
        stride_calibration={}
        for clip,tracks in stance_tracks.items():
            stride_calibration[clip]={}
            for side,samples in tracks.items():
                phase,contact=np.asarray(samples).T
                slope,intercept=np.polyfit(phase,contact,1)
                measured=-float(slope)
                stride_calibration[clip][side]=dict(measured_stride=measured,
                    ground_stance_travel=measured*gait.SETTINGS[clip]['stance'],
                    ground_track_residual=float(np.max(np.abs(contact-(intercept+slope*phase)))),
                    samples=[dict(phase=p,contact_offset=z) for p,z in samples])
                assert abs(measured-gait.SETTINGS[clip]['stride'])<.1,('Exported ground stride disagrees with the locomotion cadence',clip,side,measured)
        measured_run_stride=np.mean([v['measured_stride'] for v in stride_calibration['run'].values()])
        assert 32.<measured_run_stride<36.,('Running ground stride remained short or became excessive',measured_run_stride)
        assert gait.SETTINGS['run']['speed']==42.,'Longer stride changed the requested running speed'
        # Measure phase progress with fixed world travel and wall-clock time;
        # compare against stride inferred from geometry, not the metadata alone.
        assets.phase=0.;travelled=0.
        for frame in range(120):
            dt=1/120.;distance=42.*dt;travelled+=distance
            assets.update(dt,True,(0.,1.),distance,running=True)
        runtime_stride=dict(seconds=1.,world_distance=travelled,phase_advanced=assets.phase,
            implied_world_distance=assets.phase*measured_run_stride,
            measured_cycle_seconds=measured_run_stride/42.,running_speed=42.)
        assert abs(runtime_stride['implied_world_distance']-travelled)<.08,('Runtime root travel and native foot stride disagree',runtime_stride)
        assert .75<runtime_stride['measured_cycle_seconds']<.90,('Longer ground stride retained the old rapid cadence',runtime_stride)
        (output/'mesh-clearance.json').write_text(json.dumps(mesh_clearance,indent=2)+'\n')
        for clip,result in mesh_clearance.items():
            clearance_phase=result['worst_phase'] if result['worst_phase'] is not None else result['closest_phase']
            render('player',clip+'-clearance-above',clip=clip,phase=clearance_phase,view='above')
            render('player',clip+'-clearance-back',clip=clip,phase=clearance_phase,angle=180)
        peak_flex,peak_phase,peak_forward=max(walking_timing)
        assert .66<peak_phase<.76 and peak_forward<-2.5,('Walk knee peak occurred in front swing',max(walking_timing))
        assert max(v[0] for v in walking_timing if v[1]>.90)<15.,'Walk did not extend into contact'
        assert walking_support and max(walking_support)<22.,('Walk support leg remained crouched',max(walking_support))
        assert walking_hand_drift and all(abs(x)<gait.THIGH*.18 for x in walking_hand_drift),('Walk hands flared excessively from the shoulders',walking_hand_drift)
        assert all(2.<p['lean']<=5. and 60<p['elbow.L']<175 and 60<p['elbow.R']<175 for p in running_posture),'Upright running posture did not survive export'
        assert all(2.<tilt<=5. for tilt in running_chest_tilts),('Imported torso exceeded five degrees from vertical including its sideways bank',min(running_chest_tilts),max(running_chest_tilts))
        paired_landmarks={}
        for side,opposite in (('L','R'),('R','L')):
            stance=[record for record in running_pairs if record['legs'][side]['stance']]
            under=min(stance,key=lambda record:abs(record['legs'][side]['hip_ankle_angle_degrees']))
            rear=min((record for record in stance if record['legs'][side]['local_phase']>gait.SETTINGS['run']['stance']*.65),
                     key=lambda record:record['legs'][side]['thigh_angle_degrees'])
            paired_landmarks[side]=dict(support_under_hip=under,rear_support=rear)
            support,recovery=under['legs'][side],under['legs'][opposite]
            assert abs(support['hip_ankle_angle_degrees'])<5. and 5.<support['knee_flex_degrees']<30.,('Under-hip support knee remained crouched',side,under)
            assert abs(recovery['thigh_angle_degrees'])<15. and 75.<recovery['knee_flex_degrees']<105.,('Opposite leg drove its thigh before under-hip heel recovery',side,under)
            assert recovery['forward_ankle_offset']<recovery['forward_knee_offset']-gait.THIGH*.5,('Recovering heel did not fold behind the knee',side,under)
            support,recovery=rear['legs'][side],rear['legs'][opposite]
            assert -45.<support['thigh_angle_degrees']<-25. and -45.<support['hip_ankle_angle_degrees']<-25. and 3.<support['knee_flex_degrees']<30.,('Rear support lost its soft extended push-off',side,rear)
            assert 65.<recovery['thigh_angle_degrees']<95. and 75.<recovery['knee_flex_degrees']<105.,('Forward thigh drive did not pair with rear support',side,rear)
        open_angle,open_phase,_=max(running_arm_cycle)
        rear_angles=[angle for angle,p,_ in running_arm_cycle if p<.025 or p>.98]
        assert 150<open_angle<175,('Running elbow did not extend during the down/back sweep',max(running_arm_cycle))
        elbow_range=max(v[0] for v in running_arm_cycle)-min(v[0] for v in running_arm_cycle)
        assert elbow_range>50.,'Running elbow did not close again after the backsweep'
        closed_elbow=min(running_arm_samples['L'],key=lambda sample:sample[1])
        assert 60.<closed_elbow[1]<75.,('Front running elbow did not tuck tightly',closed_elbow)
        assert running_rear_pump and max(v[0] for v in running_rear_pump)>145.,'Elbow extension never carried the hand behind the hip'
        extended_rear_fraction=sum(angle>150. and hand<-.4 for angle,_,hand in running_arm_cycle)/len(running_arm_cycle)
        assert extended_rear_fraction>.075,('Rear elbow extension ended before the hand completed its backsweep',extended_rear_fraction)
        knee_sequences={};returning_elbows=[]
        for side in ('L','R'):
            swing=sorted(v for v in running_leg_samples[side] if v[0]>gait.SETTINGS['run']['stance'])
            flexes=np.array([v[1] for v in swing]);peak=int(np.argmax(flexes))
            before=flexes[:peak+1];after=flexes[peak:]
            early_dip=float(np.max(np.maximum.accumulate(before)-before))
            late_rebend=float(np.max(after-np.minimum.accumulate(after)))
            maximum_splay=max(v[2] for v in swing)
            knee_sequences[side]=dict(early_dip=early_dip,late_rebend=late_rebend,final_airborne_flex=float(flexes[-1]),
                                      maximum_outward_knee=maximum_splay,peak_phase=swing[peak][0])
            assert early_dip<3. and late_rebend<3.,('Recovery knee bent twice while airborne',side,knee_sequences[side])
            assert 10.<flexes[-1]<25.,('Leg did not approach touchdown with slight flex',side,flexes[-1])
            assert maximum_splay<gait.THIGH*.12,('Recovering knee opened too far outside its hip',side,maximum_splay)
            arms=sorted(running_arm_samples[side])
            for index,(_,angle,hand) in enumerate(arms):
                before_hand=arms[index-1][2];after_hand=arms[(index+1)%len(arms)][2]
                if hand<-.25 and after_hand-before_hand>.02:returning_elbows.append(angle)
        assert returning_elbows and min(returning_elbows)>145.,('Elbow bent while returning hand was still behind the hip',returning_elbows)
        touchdowns={};touchdown_heights={}
        for side,phase in (('L',0.),('R',.5)):
            assets.pose('run',phase+1e-6)
            pose=sample_pose(pr,assets,joint_ids)
            touchdowns[side]=pose['angles']['knee.'+side]
            touchdown_heights[side]=pose['sole_clearance'][side]
        assert all(10.<flex<25. for flex in touchdowns.values()),('The running leg did not land with slight flex',touchdowns)
        assert all(abs(height)<.08 for height in touchdown_heights.values()),('The running foot missed the floor at touchdown',touchdown_heights)
        terminal_extension={}
        for side in ('L','R'):
            samples=[]
            for phase in (.90,.95,.98,.999):
                record=max((record for record in running_pairs if record['legs'][side]['local_phase']<=phase+1e-8),
                           key=lambda record:record['legs'][side]['local_phase'])
                leg=record['legs'][side]
                samples.append(dict(requested_phase=phase,native_phase=leg['local_phase'],native_frame=record['native_frame'],
                    flex=leg['knee_flex_degrees'],clearance=leg['clearance']))
            flexes=[sample['flex'] for sample in samples]
            assert all(a>b+1. for a,b in zip(flexes,flexes[1:])),('Terminal knee extension stopped before touchdown',side,samples)
            assert flexes[0]-touchdowns[side]>30. and flexes[1]-flexes[-1]>8.,('Late swing retained an extended-knee plateau',side,samples)
            assert flexes[-1]>=touchdowns[side]-.5,('Terminal extension reversed before landing',side,samples,touchdowns[side])
            terminal_extension[side]=dict(samples=samples,touchdown_flex=touchdowns[side],touchdown_clearance=touchdown_heights[side],
                late_flex_drop=flexes[0]-touchdowns[side])
        walk_period=gait.SETTINGS['walk']['stride']/gait.SETTINGS['walk']['speed']
        walking_speeds={}
        for side,samples in walking_leg_samples.items():
            walking_speeds[side]=[]
            samples=sorted(samples)
            for a,b in zip(samples,samples[1:]):
                seconds=(b[0]-a[0])*walk_period
                if .45<(a[0]+b[0])*.5<.76:
                    walking_speeds[side].append(dict(phase=(a[0]+b[0])*.5,
                        ankle_speed=math.dist(a[1],b[1])/seconds,knee_speed=math.dist(a[2],b[2])/seconds,
                        ankle_forward_speed=(b[1][2]-a[1][2])/seconds,
                        ankle_vertical_speed=(b[1][1]-a[1][1])/seconds,
                        knee_forward_speed=(b[2][2]-a[2][2])/seconds,
                        knee_vertical_speed=(b[2][1]-a[2][1])/seconds,
                        native_frames=[a[3],b[3]]))
        (output/'walk-toeoff-speed.json').write_text(json.dumps(walking_speeds,indent=2)+'\n')
        walking_toeoff={}
        for side,values in walking_speeds.items():
            early=[v for v in values if gait.SETTINGS['walk']['stance']+.01<v['phase']<gait.SETTINGS['walk']['stance']+.06]
            assert len(early)>=2 and all(v['native_frames'][0]!=v['native_frames'][1] for v in early),'Toe-off speed review repeated the same native frame'
            walking_toeoff[side]=dict(minimum_knee_speed=min(v['knee_speed'] for v in early),
                                      minimum_ankle_forward_speed=min(v['ankle_forward_speed'] for v in early),
                                      measured_intervals=len(early))
            assert walking_toeoff[side]['minimum_knee_speed']>.22*gait.SETTINGS['walk']['speed'],('Walking knee paused just after toe-off',side,walking_toeoff[side])
            assert walking_toeoff[side]['minimum_ankle_forward_speed']>0.,('Walking shoe continued backward after toe-off',side,walking_toeoff[side])
        raised_knees=[v for v in running_recovery if .70<v[0]<.95]
        high_knee=max(raised_knees,key=lambda v:v[2])
        assert high_knee[2]>gait.THIGH*.65,('Run did not visibly drive the forward knee',high_knee)
        highest_knee=max(running_recovery,key=lambda sample:sample[3])
        ankle_reach=max(running_recovery,key=lambda sample:sample[4])
        assert gait.THIGH*.8<ankle_reach[4]<gait.THIGH*1.1,('Terminal running reach was too short or excessive',ankle_reach)
        precontact=[v for v in running_recovery if .92<v[0]<1.]
        assert precontact and min(v[1] for v in precontact)<30.,('Run did not extend the lower leg before landing',precontact)
        assert max(v[1] for v in raised_knees)-min(v[1] for v in precontact)>50.,'Recovery knee stayed folded into contact'
        flight_clearance=max(clearance for clearance,_ in run_flights)
        flight_hip=max(height for clearance,height in run_flights if clearance>.3)
        flight_fraction=sum(clearance>.2 for clearance,_ in run_flights)/len(run_flights)
        assert flight_clearance>.5 and .3<flight_hip-run_flights[0][1]<.65 and flight_fraction>.1,('Run lost flight or bounced excessively for its longer stride',max(run_flights),flight_fraction)
        assert min(v[0] for v in run_flights)>-.08,('Run penetrated floor',min(run_flights))
        assert max(p['wrist.L'] for p in running_posture)-min(p['wrist.L'] for p in running_posture)>4.5,'Wrist remained rigid'
        hip_sway=max(p[0] for p in running_hips)-min(p[0] for p in running_hips)
        assert hip_sway>.55 and min(p[2] for p in running_hips)>.65,'Run did not move the pelvis'
        neck_sway=max(p[0] for p in running_necks)-min(p[0] for p in running_necks)
        bank_range=max(running_chest_banks)-min(running_chest_banks)
        bank_offset=[neck[0]-hip[0] for neck,hip in zip(running_necks,running_hips)]
        lean_range=max(p['lean'] for p in running_posture)-min(p['lean'] for p in running_posture)
        assert 1.25<neck_sway/hip_sway<1.8,('Chest cancelled the pelvis weight shift',neck_sway,hip_sway)
        assert 3.<bank_range<6. and np.corrcoef([p[0] for p in running_hips],bank_offset)[0,1]>.95,'Chest bank did not follow the loaded side'
        assert .4<lean_range<3.,('Running chest pitch remained fixed or rocked excessively',lean_range)
        assert all(5.<p['pelvis_lean']<7. for p in running_posture),'Pelvis lean was lost in export'
        assert running_landings and all(0<=flex<35 and forward<gait.THIGH*.85 for flex,forward in running_landings),('Run landing lost its extended recovery or reached too far ahead',running_landings)
        assert front_hands and all(.15<x<2.5 for x in front_hands),('Hands failed to approach chest or crossed its centre',front_hands)

        canvas=Image.new('RGB',(1024,570),(25,31,36))
        draw=ImageDraw.Draw(canvas)
        font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',16)
        stride_proof=dict(native_ground_tracks=stride_calibration['run'],runtime=runtime_stride,
            declared_stride=gait.SETTINGS['run']['stride'],measured_stride=measured_run_stride,
            measured_ground_stance_travel=measured_run_stride*gait.SETTINGS['run']['stance'],
            steps_per_minute=120./runtime_stride['measured_cycle_seconds'])
        baseline_path=output.parent/'temple3d-living-baseline-v6'/'gait.py'
        if baseline_path.exists():
            import runpy
            old_settings=runpy.run_path(str(baseline_path))['SETTINGS']['run']
            stride_proof.update(previous_stride=old_settings['stride'],
                stride_increase_percent=100*(measured_run_stride/old_settings['stride']-1),
                previous_cycle_seconds=old_settings['stride']/old_settings['speed'])
        (output/'run-stride-proof.json').write_text(json.dumps(stride_proof,indent=2)+'\n')
        stride_sheet=Image.new('RGB',(1000,510),(25,31,36));stride_draw=ImageDraw.Draw(stride_sheet)
        stride_draw.text((20,10),f'Native ground stride {measured_run_stride:.2f} units / cycle {runtime_stride["measured_cycle_seconds"]:.3f} s / speed 42',font=font,fill=(210,203,180))
        for index,(label,world) in enumerate((('Ground contact relative to travelling root',False),('Ground contact after adding root travel (foot lock)',True))):
            x0=70;y0=70+index*220;width=870;height=145
            stride_draw.text((x0,y0-25),label,font=font,fill=(210,203,180))
            lower,upper=(-7.,7.) if not world else (gait.SETTINGS['run']['front']-.1,gait.SETTINGS['run']['front']+.1)
            for tick in range(5):
                value=lower+(upper-lower)*tick/4;y=y0+height-tick*height/4
                stride_draw.line((x0,y,x0+width,y),fill=(53,59,63))
                stride_draw.text((8,y-8),f'{value:.2f}',font=font,fill=(180,177,165))
            for side,color in (('L',(90,190,216)),('R',(228,170,91))):
                samples=sorted(stride_calibration['run'][side]['samples'],key=lambda v:v['phase'])
                points=[]
                for sample in samples:
                    phase=sample['phase'];value=sample['contact_offset']+(phase*measured_run_stride if world else 0)
                    points.append((x0+phase/gait.SETTINGS['run']['stance']*width,y0+height-(value-lower)/(upper-lower)*height))
                stride_draw.line(points,fill=color,width=2)
                for x,y in points:stride_draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
            for phase in (0.,.1,.2,.3):
                x=x0+phase/gait.SETTINGS['run']['stance']*width
                stride_draw.text((x-15,y0+height+8),f'{phase:.2f}',font=font,fill=(180,177,165))
        stride_draw.text((650,485),'stance phase / L blue / R amber',font=font,fill=(210,203,180))
        stride_sheet.save(output/'run-stride-proof.png')
        for row,kind in enumerate(('tree','player')):
            for column,angle in enumerate((0,90,180,270)):
                image=render(kind,f'{kind}-{angle}',angle=angle,phase=.05)
                x,y=column*256,row*285
                canvas.paste(Image.fromarray(image),(x,y+26))
                draw.text((x+8,y+5),f'{kind} / {angle} degrees',font=font,fill=(210,203,180))
        canvas.save(output/'asset-turnaround.png')
        body_views=Image.new('RGB',(1024,570),(25,31,36));head_views=Image.new('RGB',(1024,285),(25,31,36))
        body_labels=ImageDraw.Draw(body_views);head_labels=ImageDraw.Draw(head_views)
        for index,angle in enumerate(range(0,360,45)):
            x=(index%4)*256;y=(index//4)*285
            body_views.paste(Image.fromarray(render('player',f'player-eight-{angle}',angle=angle,clip='idle')),(x,y+26))
            body_labels.text((x+8,y+5),f'body / {angle} degrees',font=font,fill=(210,203,180))
        for index,angle in enumerate((0,90,180,270)):
            x=index*256
            head_views.paste(Image.fromarray(render('head',f'head-{angle}',angle=angle,clip='idle')),(x,26))
            head_labels.text((x+8,5),f'head / {angle} degrees',font=font,fill=(210,203,180))
        body_views.save(output/'player-eight-view.png');head_views.save(output/'head-closeups.png')
        native_walk_count=assets.animations[assets.clips['walk']].frameCount
        native_walk_phases=[frame*ANIMATION_SAMPLE_SECONDS/assets.clip_seconds['walk'] for frame in range(native_walk_count)]
        slow_frames=[]
        for frame,phase in enumerate(native_walk_phases):
            pixels=render('player',f'walk-slow-side-{frame:02}',angle=90,phase=phase+1e-6,clip='walk')
            slow_frames.append(Image.fromarray(pixels))
        slow_boundaries=[round(100*walk_period*4*p)*10 for p in native_walk_phases+[1.]]
        slow_frames[0].save(output/'walk-side-slow.gif',save_all=True,append_images=slow_frames[1:],
            duration=[b-a for a,b in zip(slow_boundaries,slow_boundaries[1:])],loop=0)
        native_run_count=assets.animations[assets.clips['run']].frameCount
        native_run_phases=[frame*ANIMATION_SAMPLE_SECONDS/assets.clip_seconds['run'] for frame in range(native_run_count)]
        run_period=gait.SETTINGS['run']['stride']/gait.SETTINGS['run']['speed']
        run_slow_frames=[]
        for frame,phase in enumerate(native_run_phases):
            pixels=render('player',f'run-slow-side-{frame:02}',angle=90,phase=phase+1e-6,clip='run')
            run_slow_frames.append(Image.fromarray(pixels))
        boundaries=[round(100*run_period*4*p)*10 for p in native_run_phases+[1.]]
        run_slow_frames[0].save(output/'run-side-slow.gif',save_all=True,append_images=run_slow_frames[1:],
            duration=[b-a for a,b in zip(boundaries,boundaries[1:])],loop=0)
        extension_sheet=Image.new('RGB',(1024,680),(25,31,36));extension_labels=ImageDraw.Draw(extension_sheet)
        extension_frames=[]
        for index,phase in enumerate((.65,.70,.75,.80,.85,.90,.95)):
            x=(index%4)*256;y=(index//4)*340
            pixels=render('player',f'run-extension-{round(phase*100):02}',angle=90,phase=phase+1e-6,clip='run')
            info=sample_pose(pr,assets,joint_ids);points=info['points']
            reach=points['ankle.L'][2]-points['hip.L'][2]
            record=dict(requested_phase=phase,native_frame=assets.animation_frame,
                native_phase=assets.animation_frame*ANIMATION_SAMPLE_SECONDS/assets.clip_seconds['run'],
                knee_flex=info['angles']['knee.L'],ankle_forward=reach,
                knee_forward=points['knee.L'][2]-points['hip.L'][2],
                knee_relative_height=points['knee.L'][1]-points['hip.L'][1])
            extension_frames.append(record)
            extension_sheet.paste(Image.fromarray(pixels),(x,y+30))
            extension_labels.text((x+6,y+5),f'phase {phase:.2f} / frame {assets.animation_frame}',font=font,fill=(210,203,180))
            extension_labels.text((x+6,y+291),f"knee {record['knee_flex']:.1f} degrees",font=font,fill=(210,203,180))
            extension_labels.text((x+6,y+314),f'ankle {reach:+.2f} from hip',font=font,fill=(210,203,180))
        extension_sheet.save(output/'run-early-extension-contact.png')
        (output/'run-early-extension.json').write_text(json.dumps(extension_frames,indent=2)+'\n')
        paired_frames=[('Support under hip',paired_landmarks['L']['support_under_hip']),
                       ('Rear support',paired_landmarks['L']['rear_support'])]
        for phase in (.90,.95,.98,.999,0.):
            record=max((record for record in running_pairs if record['phase']<=phase+1e-8),key=lambda record:record['phase'])
            paired_frames.append((f'Terminal {phase:.3f}',record))
        paired_sheet=Image.new('RGB',(1024,730),(25,31,36));paired_labels=ImageDraw.Draw(paired_sheet)
        small_font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
        for index,(label,record) in enumerate(paired_frames):
            x=(index%4)*256;y=(index//4)*365
            pixels=render('player',f'run-paired-{index}',angle=90,phase=record['phase']+1e-6,clip='run',view='level-side')
            paired_sheet.paste(Image.fromarray(pixels),(x,y+45))
            paired_labels.text((x+6,y+5),label,font=font,fill=(210,203,180))
            paired_labels.text((x+6,y+26),f'phase {record["phase"]:.3f} / frame {record["native_frame"]}',font=small_font,fill=(210,203,180))
            for line,side in enumerate(('L','R')):
                leg=record['legs'][side]
                paired_labels.text((x+6,y+309+line*21),f'{side} thigh {leg["thigh_angle_degrees"]:+.1f} knee {leg["knee_flex_degrees"]:.1f}',font=small_font,fill=(90,190,216) if side=='L' else (228,170,91))
        paired_sheet.save(output/'run-paired-contact.png')
        elbows_sheet=Image.new('RGB',(1024,300),(25,31,36));elbows_labels=ImageDraw.Draw(elbows_sheet)
        for column,angle in enumerate((0,45,90,270)):
            pixels=render('upper',f'run-elbow-close-{angle}',angle=angle,phase=closed_elbow[0]+1e-6,clip='run')
            elbows_sheet.paste(Image.fromarray(pixels),(column*256,30))
            elbows_labels.text((column*256+6,5),f'elbow {closed_elbow[1]:.1f} / view {angle}',font=font,fill=(210,203,180))
        elbows_sheet.save(output/'run-peak-elbow-closeups.png')
        posture_sheet=Image.new('RGB',(1024,330),(25,31,36));posture_labels=ImageDraw.Draw(posture_sheet)
        posture_frames=[]
        for column,phase in enumerate((0.,.25,.5,.75)):
            pixels=render('player',f'run-posture-{column}',angle=90,phase=phase+1e-6,clip='run',view='level-side')
            info=sample_pose(pr,assets,joint_ids);hip=info['points']['hip'];neck=info['points']['neck']
            tilt=math.degrees(math.atan2(math.hypot(neck[0]-hip[0],neck[2]-hip[2]),neck[1]-hip[1]))
            record=dict(requested_phase=phase,native_frame=assets.animation_frame,
                        pitch_degrees=info['angles']['lean'],total_tilt_degrees=tilt)
            posture_frames.append(record);x=column*256
            posture_sheet.paste(Image.fromarray(pixels),(x,30))
            # Level orthographic view, with player yaw 90 degrees: forward Z
            # projects to screen X, and vertical Y projects directly upward.
            project=lambda p:(x+128+p[2]*8,30+128-(p[1]-16)*8)
            hx,hy=project(hip);nx,ny=project(neck)
            posture_labels.line((hx,hy,hx,ny),fill=(118,153,170),width=1)
            posture_labels.line((hx,hy,nx,ny),fill=(233,188,94),width=1)
            posture_labels.text((x+6,5),f'phase {phase:.2f} / frame {assets.animation_frame}',font=font,fill=(210,203,180))
            posture_labels.text((x+6,291),f'pitch {record["pitch_degrees"]:.2f} / tilt {tilt:.2f}',font=font,fill=(210,203,180))
        posture_sheet.save(output/'run-upright-posture-contact.png')
        (output/'run-upright-posture.json').write_text(json.dumps(dict(
            minimum_pitch_degrees=min(p['lean'] for p in running_posture),
            maximum_pitch_degrees=max(p['lean'] for p in running_posture),
            minimum_total_tilt_degrees=min(running_chest_tilts),
            maximum_total_tilt_degrees=max(running_chest_tilts),frames=posture_frames),indent=2)+'\n')
        toeoff_frames=[frame for frame,phase in enumerate(native_walk_phases) if .52<phase<.66]
        toeoff_sheet=Image.new('RGB',(1024,640),(25,31,36));toeoff_labels=ImageDraw.Draw(toeoff_sheet)
        for index,frame in enumerate(toeoff_frames):
            phase=native_walk_phases[frame];x=(index%4)*256;y=(index//4)*320
            pixels=render('legs',f'walk-toeoff-{frame:02}',angle=90,phase=phase+1e-6,clip='walk')
            toeoff_sheet.paste(Image.fromarray(pixels),(x,y+30))
            toeoff_labels.text((x+6,y+5),f'phase {phase:.3f} / frame {frame}',font=font,fill=(210,203,180))
            speed=next(value for value in walking_speeds['L'] if value['native_frames'][0]==frame)
            toeoff_labels.text((x+6,y+288),f"ankle {speed['ankle_speed']:.1f} knee {speed['knee_speed']:.1f} u/s",font=font,fill=(210,203,180))
        toeoff_sheet.save(output/'walk-toeoff-contact.png')
        speed_sheet=Image.new('RGB',(1000,480),(25,31,36));speed_draw=ImageDraw.Draw(speed_sheet)
        speed_draw.text((20,10),'Native walk motion / units per game second / toe-off at phase 0.56',font=font,fill=(210,203,180))
        for index,side in enumerate(('L','R')):
            values=[v for v in walking_speeds[side] if .48<v['phase']<.74]
            x0=70;y0=65+index*205;width=880;height=155
            ceiling=math.ceil(max(max(v['ankle_speed'],v['knee_speed']) for v in values)/10)*10
            def chart_point(phase,speed):return (x0+(phase-.48)/.26*width,y0+height-speed/ceiling*height)
            for tick in range(0,ceiling+1,10):
                y=y0+height-tick/ceiling*height
                speed_draw.line((x0,y,x0+width,y),fill=(53,59,63))
                speed_draw.text((25,y-9),str(tick),font=font,fill=(180,177,165))
            toeoff_x=chart_point(gait.SETTINGS['walk']['stance'],0)[0]
            speed_draw.line((toeoff_x,y0,toeoff_x,y0+height),fill=(120,125,128),width=2)
            for key,color in (('ankle_speed',(90,190,216)),('knee_speed',(228,170,91))):
                positions=[chart_point(v['phase'],v[key]) for v in values]
                speed_draw.line(positions,fill=color,width=3)
                for x,y in positions:speed_draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
            speed_draw.text((x0,y0-25),f'{side} leg: ankle (blue), knee (amber)',font=font,fill=(210,203,180))
            for phase in (.5,.56,.6,.66,.72):
                x=chart_point(phase,0)[0]
                speed_draw.text((x-17,y0+height+5),f'{phase:.2f}',font=font,fill=(180,177,165))
        speed_sheet.save(output/'walk-toeoff-speed.png')
        for clip in ('idle','walk','run'):
            cycle_seconds=2. if clip=='idle' else gait.SETTINGS[clip]['stride']/gait.SETTINGS[clip]['speed']
            # GIF duration is quantized to 10 ms. Distribute rounding so the
            # review loop matches the actual game cadence rather than speeding up.
            boundaries=[round(100*cycle_seconds*frame/24)*10 for frame in range(25)]
            durations=[b-a for a,b in zip(boundaries,boundaries[1:])]
            for frame in range(24):
                render('player',f'{clip}-{frame:02}',angle=30,phase=frame/24,clip=clip)
            images=[Image.open(output/f'{clip}-{frame:02}.png').convert('RGB') for frame in range(24)]
            images[0].save(output/(clip+'.gif'),save_all=True,append_images=images[1:],duration=durations,loop=0)
            if clip!='idle':
                for frame in range(24):render('player',f'{clip}-side-{frame:02}',angle=90,phase=frame/24,clip=clip)
                images=[Image.open(output/f'{clip}-side-{frame:02}.png').convert('RGB') for frame in range(24)]
                images[0].save(output/(clip+'-side.gif'),save_all=True,append_images=images[1:],duration=durations,loop=0)
                sheet=Image.new('RGB',(1024,256),(25,31,36))
                for index,frame in enumerate((0,6,12,18)):sheet.paste(images[frame],(index*256,0))
                sheet.save(output/(clip+'-side-contact.png'))
                if clip=='run':
                    recovery=Image.new('RGB',(1024,256),(25,31,36))
                    for index,frame in enumerate((16,18,20,23)):
                        recovery.paste(images[frame],(index*256,0))
                    recovery.save(output/'run-recovery-sequence.png')
                for frame in range(24):render('player',f'{clip}-front-{frame:02}',angle=0,phase=frame/24,clip=clip)
                images=[Image.open(output/f'{clip}-front-{frame:02}.png').convert('RGB') for frame in range(24)]
                images[0].save(output/(clip+'-front.gif'),save_all=True,append_images=images[1:],duration=durations,loop=0)
                sheet=Image.new('RGB',(1024,256),(25,31,36))
                for index,frame in enumerate((0,4,12,16)):sheet.paste(images[frame],(index*256,0))
                sheet.save(output/(clip+'-front-contact.png'))
                for view,angle in (('back',180),('above',0)):
                    for frame in range(24):
                        render('player',f'{clip}-{view}-{frame:02}',angle=angle,phase=frame/24,clip=clip,
                               view='above' if view=='above' else None)
                    images=[Image.open(output/f'{clip}-{view}-{frame:02}.png').convert('RGB') for frame in range(24)]
                    images[0].save(output/(clip+'-'+view+'.gif'),save_all=True,append_images=images[1:],duration=durations,loop=0)
                    sheet=Image.new('RGB',(1024,256),(25,31,36))
                    for index,frame in enumerate((0,6,12,18)):sheet.paste(images[frame],(index*256,0))
                    sheet.save(output/(clip+'-'+view+'-contact.png'))
        report=dict(binding='5.5.0.4',bones=assets.player.boneCount,clips=list(assets.clips),
                    skinning_changed_pixels=int(np.count_nonzero(np.any(first!=middle,axis=2))),
                    wind_changed_pixels=int(np.count_nonzero(np.any(still!=gust,axis=2))),
                    cpu_vertex_buffers_unchanged=True,
                    clip_transition_preserves_previous_pose=True,
                    maximum_knee_flex_degrees=max_flex,stance_height_error=contact_error,stance_slide_error=plant_error,
                    extension=extension,
                    walking_peak=dict(degrees=peak_flex,phase=peak_phase,ankle_forward=peak_forward),
                    walking_support_maximum_flex=max(walking_support),walking_hand_drift=walking_hand_drift,
                    walking_toeoff_speeds=walking_speeds,
                    walking_early_swing=walking_toeoff,
                    running_lean_degrees=running_posture[0]['lean'],
                    running_elbow_opening=dict(degrees=open_angle,phase=open_phase,rear_angles=rear_angles,range=elbow_range,
                                               extended_rear_cycle_fraction=extended_rear_fraction,
                                               extended_rear_seconds=extended_rear_fraction*gait.SETTINGS['run']['stride']/gait.SETTINGS['run']['speed']),
                    running_elbow_contraction=dict(phase=closed_elbow[0],degrees=closed_elbow[1]),
                    running_rear_elbow_pump=running_rear_pump,
                    returning_elbow_minimum=min(returning_elbows),running_knee_sequences=knee_sequences,
                    running_paired_landmarks=paired_landmarks,running_terminal_extension=terminal_extension,
                    paired_pose_samples=running_pairs,settings=gait.SETTINGS['run'],
                    running_touchdown_knee_flex=touchdowns,
                    running_touchdown_sole_height=touchdown_heights,
                    running_high_knee=dict(phase=high_knee[0],bend=high_knee[1],forward=high_knee[2],relative_height=high_knee[3]),
                    running_highest_knee=dict(phase=highest_knee[0],bend=highest_knee[1],forward=highest_knee[2],relative_height=highest_knee[3]),
                    running_forward_reach=dict(phase=ankle_reach[0],forward=ankle_reach[4],knee_flex=ankle_reach[1]),
                    running_precontact_extension=dict(minimum_knee_flex=min(v[1] for v in precontact),
                                                       maximum_knee_forward=max(v[2] for v in precontact)),
                    lateral_foot_swing=lateral_swing,pelvis_lateral_travel=pelvis_travel,
                    running_flight=dict(sole_clearance=flight_clearance,hip_rise=flight_hip-run_flights[0][1],
                                        airborne_cycle_fraction=flight_fraction),
                    running_pelvis=dict(lateral_travel=hip_sway,lean=running_posture[0]['pelvis_lean']),
                    running_chest=dict(lateral_travel=neck_sway,neck_to_hip_travel_ratio=neck_sway/hip_sway,
                                       bank_range_degrees=bank_range,lean_range_degrees=lean_range,
                                       minimum_pitch_degrees=min(p['lean'] for p in running_posture),
                                       maximum_pitch_degrees=max(p['lean'] for p in running_posture),
                                       minimum_total_tilt_degrees=min(running_chest_tilts),
                                       maximum_total_tilt_degrees=max(running_chest_tilts)),
                    running_landings=running_landings,front_hand_distance_from_centre=front_hands,
                    stance_lateral_error=lateral_error,
                    maximum_segment_length_error=segment_error,
                    hand_trouser_clearance=mesh_clearance,
                    stride_calibration=stride_calibration,runtime_stride_progression=runtime_stride,
                    player_vertices_sha256=hashlib.sha256(player_before).hexdigest(),
                    willow_vertices_sha256=hashlib.sha256(tree_before).hexdigest())
        (output/'gpu-check.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        # Keep evidence available when this fails: the affected clip's native
        # renders, geometry witness and all other gait checks still complete.
        assert all(result['maximum_penetration']<.02 for result in mesh_clearance.values()),('Deformed hands or cuffs penetrated the trousers',mesh_clearance)
    finally:
        if assets:assets.close()
        pr.unload_render_texture(target);pr.close_window()


if __name__=='__main__':
    ensure_runtime()
    main()
