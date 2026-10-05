"""An editable first encounter, added beside the original temple approach."""
import g_temple_layout as layout


def install_terrace(scene):
    if scene.get('terrace-trigger'):return False
    layout.paint(scene,(496,320),(559,351),'wood',16,'x')
    layout.paint(scene,(560,304),(655,383),'wood',16,'x')
    layout.paint(scene,(656,336),(703,367),'wood',16,'x')
    for record in (
        dict(id='terrace-trigger',kind='encounter',label='Terrace encounter',position=[568,320],end=[596,368],rotation=0,group='temple-terrace',camera_offset=[-180,151,140],camera_span=130),
        dict(id='terrace-redhead',kind='enemy_spawn',label='Pale chorus spawn',position=[624,336],rotation=270,group='temple-terrace'),
        dict(id='terrace-gate',kind='gate',label='Terrace gate',position=[664,352],rotation=90,group='temple-terrace'),
        dict(id='terrace-ammo',kind='ammo',label='Pistol ammunition',position=[684,352],rotation=0),
        dict(id='terrace-medicine',kind='medicine',label='Medicine',position=[600,376],rotation=0),
    ):scene.add(record)
    bowl=next(o for o in scene.document['objects'] if o['kind']=='prop' and o['template']['kind']=='brazier')
    for identity,position in (('terrace-fire-west',[568,308]),('terrace-fire-east',[640,376])):
        scene.add(dict(id=identity,kind='prop',label='Terrace fire bowl',position=position,rotation=0,template=bowl['template']))
    return True
