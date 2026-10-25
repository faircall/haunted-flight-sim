"""Borrow the surface field for the actual canal materials' late reveal.

Raylib binds material maps on every mesh draw. Assigning the two field maps to
unused metalness/roughness slots avoids fragile global texture-unit bindings,
while leaving diffuse and the existing secondary stone atlas untouched.
"""
import pyray as pr


def material_reveal_weight(progress,settle_fraction=.65):
    """CPU counterpart of the material shader's final-third smooth reveal."""
    t=max(0.,min(1.,(float(progress)-settle_fraction)/max(.001,1.-settle_fraction)))
    return t*t*t*(10.+t*(-15.+6.*t))


class SurfaceMaterialReveal:
    """Non-owning material bindings; close before the models are unloaded."""
    def __init__(self,shader,models):
        self.shader=shader
        self.models={name:model for name,model in models.items()
            if name.startswith('canal_') and name not in ('canal_water','canal_annulus')}
        names=('surfaceResolveActive','surfaceResolveElapsed','surfaceResolveAmount','surfaceResolveSettle','surfaceMaterialOrigin',
               'surfaceMaterialShape','surfaceMaterialSpacing','surfaceMaterialColumns',
               'surfaceCondense','surfacePullDuration','surfaceNoiseSize','surfacePatternAmount')
        self.locations={name:pr.get_shader_location(shader,name) for name in names}
        self.slots=((pr.MATERIAL_MAP_METALNESS,pr.SHADER_LOC_MAP_METALNESS,'surfaceMaterialField'),
                    (pr.MATERIAL_MAP_ROUGHNESS,pr.SHADER_LOC_MAP_ROUGHNESS,'surfaceMaterialTiming'))
        self._old_locations={location:shader.locs[location] for _,location,_ in self.slots}
        for _,location,name in self.slots:
            shader.locs[location]=pr.get_shader_location(shader,name)
        self._saved=[];self._bound=None;self.last_active=False;self.last_elapsed=0.
        self._uniform('surfaceResolveActive',0.)

    def _uniform(self,name,value):
        location=self.locations[name]
        if location<0:return
        values=value if isinstance(value,(tuple,list)) else (value,)
        kind={1:pr.SHADER_UNIFORM_FLOAT,3:pr.SHADER_UNIFORM_VEC3}[len(values)]
        pr.set_shader_value(self.shader,location,pr.ffi.new('float[]',values),kind)

    def _bind(self,renderer):
        pair=(renderer.field_texture.id,renderer.timing_texture.id)
        if self._bound==pair:return
        if not self._saved:
            for model in self.models.values():
                for i in range(model.materialCount):
                    material=model.materials[i]
                    for slot,_,_ in self.slots:
                        saved=pr.ffi.new('Texture2D *',material.maps[slot].texture)
                        self._saved.append((material,slot,saved))
        for model in self.models.values():
            for i in range(model.materialCount):
                maps=model.materials[i].maps
                maps[pr.MATERIAL_MAP_METALNESS].texture=renderer.field_texture
                maps[pr.MATERIAL_MAP_ROUGHNESS].texture=renderer.timing_texture
        self._bound=pair

    def sync(self,renderer,sequence):
        """Call before opaque geometry, including the reflected geometry pass.

        The renderer's profile synchronization prepares both textures before
        a scrub or live timing edit can draw materials using stale owner rows.
        Old erosion mode and disabled profiles keep the original shader path.
        """
        settings=sequence.direction.surface_fog
        active=(renderer is not None and settings.enabled and settings.amount>0. and
                getattr(settings,'evolution','erode') in ('rise_resolve','condense') and
                sequence.state in ('entering','canals'))
        self.last_elapsed=sequence.elapsed
        if active:
            synchronize=getattr(renderer,'sync_profile',None)
            if synchronize is not None:synchronize(sequence.direction)
            else:renderer.prepare()
            active=(renderer.field is not None and renderer.field_texture is not None and
                    renderer.timing_texture is not None and renderer.last_rows is not None)
        if active:
            self._bind(renderer)
            field=renderer.field
            # Atlas dimensions are saved in the baked metadata, keeping this
            # cheap on every frame; no atlas allocation is needed here.
            atlas=field.metadata['atlas']
            self._uniform('surfaceMaterialOrigin',tuple(field.origin))
            self._uniform('surfaceMaterialShape',tuple(field.shape))
            self._uniform('surfaceMaterialSpacing',float(field.spacing))
            self._uniform('surfaceMaterialColumns',float(atlas['columns']))
            self._uniform('surfaceResolveElapsed',float(sequence.elapsed))
            self._uniform('surfaceResolveAmount',float(settings.amount))
            self._uniform('surfaceResolveSettle',float(getattr(settings,'settle_fraction',.65)))
            self._uniform('surfaceCondense',float(getattr(settings,'evolution','erode')=='condense'))
            self._uniform('surfacePullDuration',float(getattr(settings,'pull_duration',1.15)))
            self._uniform('surfaceNoiseSize',float(getattr(settings,'noise_size',2.8)))
            self._uniform('surfacePatternAmount',float(getattr(settings,'pattern_amount',.75)))
        self.last_active=bool(active)
        self._uniform('surfaceResolveActive',float(active))
        return self.last_active

    def close(self):
        self._uniform('surfaceResolveActive',0.)
        for material,slot,texture in self._saved:material.maps[slot].texture=texture[0]
        for location,value in self._old_locations.items():self.shader.locs[location]=value
        self._saved.clear();self._bound=None;self.last_active=False
