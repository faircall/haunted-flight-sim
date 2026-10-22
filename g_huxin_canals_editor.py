"""Undoable direction edits and deterministic timeline transport, without a GPU."""
from copy import deepcopy
import math

from g_huxin_canals_direction import (
    CUES, DEFAULT_PATH, default_document, load_direction, save_direction,
    validate_document, profile_from_document, sample_camera,
)


class DirectionEditor:
    def __init__(self, document=None, path=DEFAULT_PATH):
        self.path = path
        self.document = validate_document(document if document is not None else load_direction(path))
        self.saved = deepcopy(self.document)
        self.selected = CUES[0]
        self.band = 'near'
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
    def profile(self):
        if self._profile_document != self.document:
            self._profile = profile_from_document(self.document)
            self._profile_document = deepcopy(self.document)
        return self._profile

    def checkpoint(self):return deepcopy(self.document)

    def _record(self, document):
        return dict(document=document, selected=self.selected, band=self.band, elapsed=self.elapsed)

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
        result = self.change(lambda:self.document['cues'].__setitem__(cue, value))
        self.select(cue)
        return result

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
        self.change(lambda:setattr(self, 'document', default_document()))
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
