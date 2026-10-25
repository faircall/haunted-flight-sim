"""Undoable direction edits and deterministic timeline transport, without a GPU."""
from copy import deepcopy
import math
from pathlib import Path

from g_huxin_canals_direction import (
    CUES, DEFAULT_PATH, default_document, load_direction,
    validate_document, profile_from_document, sample_camera, building_document,
)
from g_huxin_canals_targets import target_groups
from g_huxin_canals_volumes import (MAX_VOLUMES, default_volume_document,
    default_region_document, demo_volume_document)
from g_huxin_canals_surface_settings import default_surface_document, fit_surface_times, fit_water_settle_times
from g_huxin_canals_live import (DirectionWatcher, DirectionConflictError,
    merge_directions, read_direction_snapshot, save_direction_checked)


def pick_target_bounds(origin, direction, targets=None):
    """Pick the nearest positive ray/AABB hit in the semantic target catalog.

    This is independent of draw batching, visible fog cards, and F8 selection.
    The boxes describe architecture; fog offsets never move the pick target.
    """
    if not all(math.isfinite(v) for v in (*origin, *direction)):
        raise ValueError('Picking ray must be finite.')
    if sum(v*v for v in direction) < 1e-16:return None
    hits=[]
    for target in target_groups() if targets is None else targets:
        lo,hi=0.,float('inf')
        for axis in range(3):
            minimum=target.center[axis]-target.half_extents[axis]
            maximum=target.center[axis]+target.half_extents[axis]
            if abs(direction[axis])<1e-10:
                if not minimum<=origin[axis]<=maximum:hi=-1.;break
            else:
                a=(minimum-origin[axis])/direction[axis]
                b=(maximum-origin[axis])/direction[axis]
                lo=max(lo,min(a,b));hi=min(hi,max(a,b))
        if hi>=lo:hits.append((lo,target.id))
    return min(hits)[1] if hits else None


class DirectionEditor:
    def __init__(self, document=None, path=DEFAULT_PATH):
        self.path = path
        self.document = validate_document(document if document is not None else load_direction(path))
        self.saved = deepcopy(self.document)
        self.selected = CUES[0]
        self.band = 'near'
        self.targets = tuple(target_groups())
        self._targets = {target.id:target for target in self.targets}
        self.target_id = self.targets[0].id
        self.volume_id = next(iter(self.document.get('volumes',{}).get('regions',{})),None)
        self.elapsed = 0.
        self.playing = False
        self.loop = False
        self.undo_stack, self.redo_stack = [], []
        self._profile_document = None
        self._profile = None
        self.watcher=DirectionWatcher(path,self.document)
        self._file_was_present=Path(path).exists()
        self._pending_external=None
        self.external_conflicts=()
        self.live_status='Live direction updates ready.'

    @property
    def duration(self):return self.document['cues']['end']
    @property
    def dirty(self):return self.document != self.saved
    @property
    def external_pending(self):return bool(self._pending_external is not None or self.external_conflicts or self.watcher.error)
    @property
    def frame(self):
        frame=self.document['cameras']['keys'].get(self.selected)
        if frame is not None:return frame
        pose=sample_camera(self.profile,self.document['cues'][self.selected],include_disabled=True)
        if pose is None:return default_document()['cameras']['keys'][self.selected]
        return dict(eye=list(pose.eye),target=list(pose.target),fov=pose.fov)
    @property
    def bank(self):return self.document['banks'][self.band]
    @property
    def fog_mode(self):return self.document.get('fog',{}).get('mode','banks')
    @property
    def target(self):return self._targets[self.target_id]
    @property
    def group(self):return self.document['fog']['groups'][self.target_id]
    @property
    def placement(self):return self.group if self.fog_mode=='buildings' else self.bank
    @property
    def volume_settings(self):return self.document.get('volumes',default_volume_document())
    @property
    def volumes(self):return self.volume_settings
    @property
    def volume_regions(self):return self.volume_settings['regions']
    @property
    def volume(self):return self.volume_regions.get(self.volume_id)
    @property
    def surface_settings(self):return self.document.get('surface_fog',default_surface_document(self.document['cues']))
    @property
    def profile(self):
        if self._profile_document != self.document:
            self._profile = profile_from_document(self.document)
            self._profile_document = deepcopy(self.document)
        return self._profile

    def checkpoint(self):return deepcopy(self.document)

    def _record(self, document):
        return dict(document=document, selected=self.selected, band=self.band,
                    target_id=self.target_id, volume_id=self.volume_id, elapsed=self.elapsed)

    def commit(self, before):
        try:self.document = validate_document(self.document)
        except (ValueError, TypeError, KeyError):
            self.document = before
            raise
        if before == self.document:return False
        self.undo_stack.append(self._record(before))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()
        self.elapsed = min(self.elapsed, self.duration)
        self._repair_volume_selection()
        return True

    def change(self, operation):
        before = self.checkpoint()
        record = self._record(before)
        try:
            operation()
            changed=self.commit(before)
            if changed:self.undo_stack[-1]=record
            return changed
        except Exception:
            self.document = before
            self.volume_id=record['volume_id']
            raise

    def _restore(self, record):
        self.document = deepcopy(record['document'])
        self.selected, self.band = record['selected'], record['band']
        self.target_id=record.get('target_id',self.target_id)
        self.volume_id=record.get('volume_id',self.volume_id)
        self._repair_volume_selection()
        self.seek(record['elapsed'])

    def undo(self):
        if not self.undo_stack:return False
        self.redo_stack.append(self._record(self.checkpoint()))
        self._restore(self.undo_stack.pop())
        return True

    def redo(self):
        if not self.redo_stack:return False
        self.undo_stack.append(self._record(self.checkpoint()))
        self._restore(self.redo_stack.pop())
        return True

    def seek(self, value):
        if not math.isfinite(value):raise ValueError('Playhead must be a finite time.')
        self.elapsed = max(0., min(self.duration, float(value)))
        self.playing = False

    def select(self, cue):
        if cue not in CUES:raise ValueError('Unknown timeline point.')
        self.selected = cue
        self.seek(self.document['cues'][cue])

    def clamp_time(self, cue, value):
        if not math.isfinite(value):raise ValueError('Time must be finite.')
        index = CUES.index(cue)
        if index == 0:return 0.
        lo = self.document['cues'][CUES[index-1]] + .1
        hi = self.document['cues'][CUES[index+1]] - .1 if index+1 < len(CUES) else 1800.
        return max(lo, min(hi, value))

    def set_time(self, cue, value):
        def apply():
            self.document['cues'][cue]=value
            self.fit_group_times()
        result = self.change(apply)
        self.select(cue)
        return result

    def fit_group_times(self):
        """Keep absolute group times unless a global edit makes them invalid.

        Called within the cue's transaction, including each live drag update.
        Undo restores both the cue and every affected group together.
        """
        low=self.document['cues']['blend_end'];high=self.duration
        if not all(math.isfinite(v) for v in (low,high)) or high-low<.1:return
        for group in self.document.get('fog',{}).get('groups',{}).values():
            start=max(low,min(high-.1,group['reveal_start']))
            end=max(start+.1,min(high,group['reveal_end']))
            group['reveal_start'],group['reveal_end']=start,end
        self.fit_volume_times()
        if 'surface_fog' in self.document:fit_surface_times(self.document['surface_fog'],self.document['cues'])

    def set_surface(self,prop,value,axis=None):
        def apply():
            settings=self.document.setdefault('surface_fog',default_surface_document(self.document['cues']))
            if prop=='build_end':
                cues=self.document['cues'];span=cues['blend_end']-cues['build_end']
                low=settings['build_start']+.1;high=self.duration-span-.1
                if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
                    raise ValueError(f'Surface build end must be between {low:g} and {high:g} seconds.')
            if axis is None:settings[prop]=deepcopy(value)
            else:settings[prop][axis]=value
            if prop=='build_end':fit_surface_times(settings,self.document['cues'])
            if prop=='water_settle' and value is True:fit_water_settle_times(settings,self.document['cues'],author=True)
        return self.change(apply)

    def _repair_volume_selection(self):
        if self.volume_id not in self.volume_regions:
            self.volume_id=next(iter(self.volume_regions),None)

    def _ensure_volumes(self):
        return self.document.setdefault('volumes',default_volume_document(self.document['cues']))

    def select_volume(self,identity):
        if identity not in self.volume_regions:raise ValueError('Unknown fog volume.')
        self.volume_id=identity;self.playing=False

    def set_volume_global(self,prop,value):
        if prop not in ('enabled','mix','particle_mix','quality'):raise ValueError('Unknown volume setting.')
        return self.change(lambda:self._ensure_volumes().__setitem__(prop,value))

    set_volume_setting=set_volume_global

    def set_volume(self,prop,value,axis=None):
        if self.volume is None:raise ValueError('Select or add a fog volume first.')
        def apply():
            if axis is None:self.volume[prop]=deepcopy(value)
            else:self.volume[prop][axis]=value
        return self.change(apply)

    def _new_volume_id(self):
        for number in range(1,10000):
            ident=f'volume-{number:03d}'
            if ident not in self.volume_regions:return ident
        raise ValueError('Cannot allocate a unique fog volume ID.')

    def add_volume(self,shape='box',target_id=None,region=None):
        if len(self.volume_regions)>=MAX_VOLUMES:raise ValueError(f'At most {MAX_VOLUMES} fog volumes are supported.')
        value=deepcopy(region) if region is not None else default_region_document(self.document['cues'],shape=shape)
        if target_id is not None:
            if target_id not in self._targets:raise ValueError('Unknown fog target.')
            target=self._targets[target_id]
            value.update(label=target.label+' / volume',center=list(target.center),
                half_extents=[h+.8 for h in target.half_extents],hollow=.55 if target.kind=='house' else 0.)
        identity=self._new_volume_id()
        def apply():
            volumes=self._ensure_volumes()
            volumes['enabled']=True
            volumes['regions'][identity]=value
            self.volume_id=identity
        self.change(apply)
        return identity

    def duplicate_volume(self):
        if self.volume is None:raise ValueError('Select a fog volume first.')
        value=deepcopy(self.volume)
        value['label']=(value['label'][:89]+' / copy')[:96]
        value['center'][0]+=1.
        return self.add_volume(region=value)

    def delete_volume(self):
        if self.volume is None:return False
        return self.change(lambda:self.volume_regions.pop(self.volume_id))

    remove_volume=delete_volume

    def set_volume_demo(self):
        def apply():
            self.document['volumes']=demo_volume_document(self.document['cues'])
            self.volume_id=next(iter(self.volume_regions),None)
        return self.change(apply)

    def fit_volume_times(self):
        """Keep each region's authored window valid when global cues move."""
        high=self.duration;blend=self.document['cues']['blend_end']
        for region in self.document.get('volumes',{}).get('regions',{}).values():
            start=max(0.,min(high-.3,region['fade_in_start']))
            end=max(start+.1,min(high-.2,region['fade_in_end']))
            reveal=max(blend,end,min(high-.1,region['reveal_start']))
            clear=max(reveal+.1,min(high,region['reveal_end']))
            region.update(fade_in_start=start,fade_in_end=end,reveal_start=reveal,reveal_end=clear)

    def select_target(self, identity):
        if identity not in self._targets:raise ValueError('Unknown fog target.')
        self.target_id=identity;self.playing=False

    def set_fog_mode(self, mode):
        if mode not in ('banks','buildings'):raise ValueError('Unknown fog mode.')
        def apply():
            if mode=='buildings':self.document=building_document(self.document)
            elif 'fog' in self.document:self.document['fog']['mode']='banks'
        return self.change(apply)

    def clamp_group_time(self, prop, value):
        if not math.isfinite(value):raise ValueError('Reveal time must be finite.')
        if prop=='reveal_start':return max(self.document['cues']['blend_end'],min(self.group['reveal_end']-.1,value))
        if prop=='reveal_end':return max(self.group['reveal_start']+.1,min(self.duration,value))
        raise ValueError('Unknown reveal time.')

    def set_group(self, prop, value, axis=None):
        def apply():
            if axis is None:self.group[prop]=value
            else:self.group[prop][axis]=value
        return self.change(apply)

    def set_placement(self, prop, value, axis=None):
        return (self.set_group if self.fog_mode=='buildings' else self.set_bank)(prop,value,axis)

    def reset_group(self):
        base=deepcopy(self.document);base.pop('fog',None)
        group=building_document(base)['fog']['groups'][self.target_id]
        return self.change(lambda:self.document['fog']['groups'].__setitem__(self.target_id,group))

    def set_camera(self, frame):
        def apply():
            self.document['cameras']['keys'][self.selected] = deepcopy(frame)
            self.document['cameras']['enabled'] = True
        return self.change(apply)

    def set_bank(self, prop, value, axis=None):
        def apply():
            if axis is None:self.bank[prop] = value
            else:self.bank[prop][axis] = value
        return self.change(apply)

    def _live_message(self,message):
        changed=message!=self.live_status
        self.live_status=message
        return message if changed else None

    def _apply_external(self,document,remote):
        # Commit is undoable but, unlike seek(), does not pause transport or
        # change the selected cue/target. A shorter timeline clamps its end.
        self.change(lambda:setattr(self,'document',deepcopy(document)))
        self.saved=deepcopy(remote);self._pending_external=None;self.external_conflicts=()
        self._file_was_present=True
        self.watcher.acknowledge(remote)

    def _merge_external(self,remote):
        combined,conflicts=merge_directions(self.saved,self.document,remote)
        if conflicts:
            self._pending_external=deepcopy(remote);self.external_conflicts=conflicts
            message='File changes need a choice: '+', '.join(conflicts[:3])+'. Use file or keep mine.'
            self._live_message(message)
            return False
        dirty=combined!=remote
        self._apply_external(combined,remote)
        self._live_message('Merged file changes; your unsaved edits are retained.' if dirty else 'Applied direction file changes.')
        return True

    def poll_external(self,now=None,busy=False):
        previous=self.live_status
        previous_error=self.watcher.error
        remote=self.watcher.poll(now)
        if remote is not None:
            self._pending_external=deepcopy(remote);self._file_was_present=True
        if self.watcher.error:
            self._live_message(self.watcher.error)
        elif self._pending_external is not None:
            if busy:self._live_message('File changes waiting until the current edit finishes.')
            else:self._merge_external(self._pending_external)
        elif self.external_conflicts:
            # A previously conflicting write may have been reverted on disk.
            current=self.watcher.document
            if current==self.saved:self.external_conflicts=()
        if previous_error and not self.watcher.error and self._pending_external is None:
            self._live_message('Direction file is valid again; current edits are retained.')
        return self.live_status if self.live_status!=previous else None

    def _read_for_save(self):
        try:return read_direction_snapshot(self.path)
        except FileNotFoundError as exc:
            if not self._file_was_present:return None,None
            error='Direction file is missing; keeping your edits. Use keep mine to recreate it.'
            self.watcher.error=error;self._live_message(error)
            raise DirectionConflictError(error) from exc
        except (OSError,ValueError) as exc:
            error='Direction file cannot be safely replaced: '+str(exc)
            self.watcher.error=error;self._live_message(error)
            raise DirectionConflictError(error) from exc

    def save(self):
        # Always inspect disk, even when UI polling is disabled or has not yet
        # reached its settle interval. Never silently lose unseen remote edits.
        validate_document(self.document)
        expected,remote=self._read_for_save()
        if remote is not None and remote!=self.saved:
            if not self._merge_external(remote):raise DirectionConflictError(self.live_status)
        try:save_direction_checked(self.document,self.path,expected)
        except DirectionConflictError as exc:
            self.external_conflicts=(str(exc),);self._live_message(str(exc));raise
        self.saved=self.checkpoint();self._file_was_present=True
        self._pending_external=None;self.external_conflicts=()
        self.watcher.acknowledge(self.saved)
        self._live_message('Saved direction; live updates are ready.')

    def reload(self):
        _,document=read_direction_snapshot(self.path)
        self._apply_external(document,document)
        self._live_message('Loaded direction file; undo restores your prior edits.')

    def discard(self):
        """Drop local edits without requiring a readable live file or writing it.

        A running editor can encounter a newer schema, a partial external
        write, or a deleted file. None of those should prevent leaving it.
        Prefer valid disk changes; otherwise keep the last valid saved state
        so an embedded editor can safely return to gameplay.
        """
        try:_,document=read_direction_snapshot(self.path)
        except (OSError,ValueError):document=self.saved
        self.document=deepcopy(document);self.saved=deepcopy(document)
        self._pending_external=None;self.external_conflicts=()
        self.undo_stack.clear();self.redo_stack.clear()
        self._repair_volume_selection();self.seek(self.elapsed)

    def resolve_external(self,choice):
        if choice=='file':
            self.reload()
            return self.live_status
        if choice!='mine':raise ValueError('Choose file or mine for external edits.')
        # This explicit choice is also the recovery path for an invalid file.
        validate_document(self.document)
        try:expected=Path(self.path).read_bytes()
        except FileNotFoundError:expected=None
        save_direction_checked(self.document,self.path,expected)
        self.saved=self.checkpoint();self._file_was_present=True
        self._pending_external=None;self.external_conflicts=()
        self.watcher.acknowledge(self.saved)
        self._live_message('Kept your edits and saved them over the file version.')
        return self.live_status

    def defaults(self):
        document=building_document() if self.fog_mode=='buildings' else default_document()
        self.change(lambda:setattr(self, 'document', document))
        self.seek(self.elapsed)

    def tick(self, dt):
        if not self.playing:return
        index = CUES.index(self.selected)
        start = self.document['cues'][self.selected] if self.loop else 0.
        end = self.document['cues'][CUES[index+1]] if self.loop and index+1 < len(CUES) else self.duration
        if end <= start:start = 0.
        self.elapsed += max(0., min(.1, dt))
        if self.elapsed >= end:
            if self.loop:self.elapsed = start + (self.elapsed-start) % (end-start)
            else:self.elapsed = end;self.playing = False
