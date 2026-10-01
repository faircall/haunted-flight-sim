"""Run inside the saved kit to verify it is editable and self-contained."""
from pathlib import Path
import json,sys
import bpy
from mathutils import Vector

root=Path(__file__).resolve().parent
records=json.loads((root/'bakes.json').read_text())
for index,name in enumerate(records):
    collection=bpy.data.collections[name]
    assert len(collection.objects)>0,name
    assert all(obj.type=='MESH' for obj in collection.objects),name
images=[im for im in bpy.data.images if im.source=='FILE']
assert images and all(im.packed_file is not None for im in images)
assert bpy.context.scene.camera.data.type=='ORTHO'
if '--reframe' in sys.argv:
    scene=bpy.context.scene;old=scene.get('kit_spacing',[145,110])
    for index,name in enumerate(records):
        for obj in bpy.data.collections[name].objects:
            obj.location.x+=(index%5)*(170-old[0]);obj.location.y+=(index//5)*(150-old[1])
    scene['kit_spacing']=[170,150]
    scene.camera.location=(400,-660,700);target=Vector((400,225,0))
    scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=940
    bpy.context.preferences.filepaths.save_version=0
    preview=bpy.context.preferences.filepaths.bl_rna.properties.get('file_preview_type')
    if preview and 'NONE' in preview.enum_items.keys():bpy.context.preferences.filepaths.file_preview_type='NONE'
    bpy.ops.wm.save_as_mainfile(filepath=str(root/'water_temple_kit.blend'))
    scene.render.filepath=str(root/'renders'/'kit_overview.png');bpy.ops.render.render(write_still=True)
print('Packed editable kit verified:',len(records),'model collections,',len(images),'packed photo images')
