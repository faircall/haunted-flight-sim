"""Validated, settled live direction files and non-destructive runtime updates.

No renderer, audio, or platform watcher is involved. Reading the small file's
bytes detects atomic replacements and edits that preserve size and timestamps.
"""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
import time

from g_huxin_canals_direction import DEFAULT_PATH, DirectionError, validate_document


CHECK_INTERVAL = .25
SETTLE_TIME = .20


class DirectionConflictError(DirectionError):
    """Saving requires an explicit local/file choice."""


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError(f'duplicate field {key!r}')
        result[key]=value
    return result


def decode_direction(data, path):
    try:
        return validate_document(json.loads(data.decode('utf-8'),object_pairs_hook=_unique_object))
    except (UnicodeError,ValueError,TypeError) as exc:
        raise DirectionError(f'Cannot load direction from {path}: {exc}') from exc


def read_direction_snapshot(path):
    """Read and validate one exact byte snapshot; callers can guard a save."""
    path=Path(path)
    data=path.read_bytes()
    return data,decode_direction(data,path)


def save_direction_checked(document,path,expected_bytes):
    """Atomic replacement with a final optimistic check against the read file."""
    document=validate_document(document);path=Path(path);temporary=None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='\n',dir=path.parent,
                                         prefix='.'+path.name+'.',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(document,stream,indent=2,ensure_ascii=False,allow_nan=False)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        try:current=path.read_bytes()
        except FileNotFoundError:current=None
        if current!=expected_bytes:
            raise DirectionConflictError('The direction file changed while saving. Review the latest file changes first.')
        os.replace(temporary,path);temporary=None
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


class DirectionWatcher:
    def __init__(self,path=DEFAULT_PATH,document=None):
        self.path=Path(path).expanduser().resolve()
        self.document=validate_document(document) if document is not None else None
        self.error=None
        self._accepted=None;self._candidate=None;self._candidate_since=None
        self._last_check=-math.inf
        if self.document is not None:self.acknowledge(self.document)

    def acknowledge(self,document):
        """Suppress our own write only if the file actually contains it.

        A concurrent, different file is left unacknowledged for the next poll.
        No missing/invalid file replaces the last known-good document.
        """
        document=validate_document(document)
        try:data,current=read_direction_snapshot(self.path)
        except (OSError,ValueError):return False
        if current!=document:return False
        self.document=deepcopy(document);self._accepted=data
        self._candidate=None;self._candidate_since=None;self.error=None
        return True

    def poll(self,now=None):
        now=time.monotonic() if now is None else float(now)
        if not math.isfinite(now):raise ValueError('Watcher time must be finite.')
        if now<self._last_check:
            self._last_check=-math.inf;self._candidate_since=now if self._candidate is not None else None
        if now-self._last_check<CHECK_INTERVAL-1e-9:return None
        self._last_check=now
        try:data=self.path.read_bytes()
        except OSError as exc:
            self.error=f'Live direction unavailable; keeping current scene. {exc}'
            self._candidate=None;self._candidate_since=None
            return None
        if data==self._accepted:
            self.error=None;self._candidate=None;self._candidate_since=None
            return None
        if data!=self._candidate:
            self._candidate=data;self._candidate_since=now
            return None
        if now-self._candidate_since<SETTLE_TIME-1e-9:return None
        try:document=decode_direction(data,self.path)
        except ValueError as exc:
            self.error=f'Live direction invalid; keeping current scene. {exc}'
            return None
        self._accepted=data;self._candidate=None;self._candidate_since=None;self.error=None
        changed=document!=self.document
        self.document=deepcopy(document)
        return document if changed else None


_MISSING=object()


def merge_directions(base,local,remote):
    """Merge independent leaf edits, then validate the combined document.

    Lists of equal length are merged per component, allowing independent XYZ
    edits. A conflicting delete/edit or unsafe combined timing remains pending.
    """
    conflicts=[]
    def clone(value):return _MISSING if value is _MISSING else deepcopy(value)
    def merge(before,mine,theirs,path):
        if mine==theirs:return clone(mine)
        if mine==before:return clone(theirs)
        if theirs==before:return clone(mine)
        if isinstance(mine,dict) and isinstance(theirs,dict) and (before is _MISSING or isinstance(before,dict)):
            before={} if before is _MISSING else before
            result={}
            for key in sorted(before.keys()|mine.keys()|theirs.keys()):
                value=merge(before.get(key,_MISSING),mine.get(key,_MISSING),theirs.get(key,_MISSING),path+(key,))
                if value is not _MISSING:result[key]=value
            return result
        if isinstance(before,list) and isinstance(mine,list) and isinstance(theirs,list) and len(before)==len(mine)==len(theirs):
            return [merge(a,b,c,path+(str(index),)) for index,(a,b,c) in enumerate(zip(before,mine,theirs))]
        conflicts.append('.'.join(path) or 'document')
        return clone(mine)
    document=merge(base,local,remote,())
    if conflicts:return None,tuple(conflicts)
    try:return validate_document(document),()
    except (ValueError,TypeError,KeyError) as exc:return None,('Combined edits are invalid: '+str(exc),)


def apply_live_direction(sequence,profile):
    """Replace only direction/state needed at its threshold; never seek/reset.

    Inventory, event queues, world ambience time, actor locks and released
    cameras survive. A committed world cannot be reversed by retiming its cue.
    """
    if sequence.direction==profile:return False
    committed=bool(sequence.revealed or sequence.state=='canals')
    sequence.direction=profile
    if committed:
        sequence.state='canals';sequence.revealed=True
        sequence._live_world_committed=True
    elif sequence.state=='entering' and sequence.elapsed>=sequence.entry_duration:
        sequence.state='canals';sequence.revealed=True
        sequence._live_world_committed=True
    return True
