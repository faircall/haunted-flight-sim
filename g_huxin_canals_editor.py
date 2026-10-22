"""Undoable direction edits and deterministic timeline transport, without a GPU."""
from copy import deepcopy
import math

from g_huxin_canals_direction import (
    CUES, DEFAULT_PATH, default_document, load_direction, save_direction,
    validate_document, profile_from_document, sample_camera, building_document,
)
from g_huxin_canals_targets import target_groups


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
        self.elapsed = 0.
        self.playing = False
        self.loop = False
        self.undo_stack, self.redo_stack = [], []
        self._profile_document = None
        self._profile = None

    @property
    def duration(self):return self.document['cues']['end']
    @property
    def dirty(self):return self.document != self.saved
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
    def profile(self):
        if self._profile_document != self.document:
            self._profile = profile_from_document(self.document)
            self._profile_document = deepcopy(self.document)
        return self._profile

    def checkpoint(self):return deepcopy(self.document)

    def _record(self, document):
        return dict(document=document, selected=self.selected, band=self.band,
                    target_id=self.target_id, elapsed=self.elapsed)

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
        return True

    def change(self, operation):
        before = self.checkpoint()
        try:
            operation()
            return self.commit(before)
        except Exception:
            self.document = before
            raise

    def _restore(self, record):
        self.document = deepcopy(record['document'])
        self.selected, self.band = record['selected'], record['band']
        self.target_id=record.get('target_id',self.target_id)
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

    def save(self):
        save_direction(self.document, self.path)
        self.saved = self.checkpoint()

    def reload(self):
        document = load_direction(self.path)
        self.change(lambda:setattr(self, 'document', document))
        self.saved = deepcopy(document)
        self.seek(self.elapsed)

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
