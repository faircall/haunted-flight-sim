"""Run inside the saved .blend to check packed resources and render portability."""
from pathlib import Path
import bpy

root=Path(__file__).resolve().parent
scene=bpy.context.scene
assert scene.camera.data.type=='ORTHO'
assert scene.camera.name=='Orthographic '+str(scene['selected_angle'])+' degrees'
assert len([obj for obj in scene.objects if obj.type=='CAMERA'])==3
meshes=[obj for obj in scene.objects if obj.type=='MESH']
assert len(meshes)==18
images=[im for im in bpy.data.images if im.source=='FILE']
assert len(images)==4
assert all(im.packed_file is not None for im in images)
assert all(obj.data.materials and obj.data.materials[0].use_nodes for obj in meshes)
assert scene.view_settings.view_transform=='Standard'
scene.render.filepath=str(root/'renders'/'reopened.png')
bpy.ops.render.render(write_still=True)
print('SAVED_ROOF_VERIFIED: packed textures, colour materials, orthographic camera and render')
