"""Behavioral tests for event-driven cameras and safe document migration."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from g_camera_rules import CameraRuleEngine
from g_huxin_moon_direction import CameraDocument, CameraWatcher, default_document, validate_document
from g_scene_cameras import CameraValidationError, resolve_shot


def setup_document():
    doc=default_document();base=doc['shots'][0];base['id']='base';base['label']='Base'
    doc['shots']=[base];return doc


def add_rule(doc,identity='special',priority=10,**rule):
    shot=deepcopy(doc['shots'][0]);shot['id']=identity;shot['label']=identity;shot['enabled']=True
    shot['activation']=dict(type='rule',phase='any',priority=priority)
    shot['rule'].update(rule);doc['shots'].append(shot);return shot


def marker(identity='gate',phase='any'):
    return dict(id=identity,label=identity,phase=phase,bounds={'min':[-.1,0,-1],'max':[.1,2,1]})


def pick(engine,doc,time,events=(),facts=None,point=(0,1,0),trigger=None,include_zones=True):
    shot=engine.choose(doc,trigger or {'type':'lake','index':0},point,
                       {'world.phase':'lake',**(facts or {})},time,events,include_zones)
    return None if shot is None else shot['id']


class RuleLifecycleTests(unittest.TestCase):
    def test_event_start_is_a_pulse_but_active_camera_is_continuous(self):
        doc=setup_document();add_rule(doc,start_event='puzzle.solved',conditions=[dict(fact='ready',op='eq',value=True)])
        engine=CameraRuleEngine()
        self.assertEqual(pick(engine,doc,0,facts={'ready':True}),'base')
        self.assertEqual(pick(engine,doc,1,['puzzle.solved'],{'ready':True}),'special');start=engine.started
        self.assertEqual(pick(engine,doc,2,facts={'ready':True}),'special');self.assertEqual(engine.started,start)
        self.assertEqual(pick(engine,doc,3,facts={'ready':False}),'base')
        self.assertEqual(pick(engine,doc,4,facts={'ready':True}),'base')
        self.assertTrue(engine.facts['event.puzzle.solved.seen'])

    def test_missing_facts_fail_including_not_equal_and_boolean_is_not_number(self):
        doc=setup_document();shot=add_rule(doc,conditions=[dict(fact='not-yet-known',op='ne',value=True)])
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0),'base')
        self.assertIn('Missing fact',engine.diagnostics[-1]['reason'])
        self.assertEqual(pick(engine,doc,1,facts={'not-yet-known':False}),'special')
        shot['rule']['conditions']=[dict(fact='ready',op='eq',value=1)]
        self.assertEqual(pick(engine,doc,2,facts={'ready':True}),'base')
        shot['rule']['conditions']=[dict(fact='amount',op='gte',value=2),dict(fact='amount',op='lte',value=4)]
        self.assertEqual(pick(engine,doc,3,facts={'amount':3}),'special')
        self.assertEqual(pick(engine,doc,4,facts={'amount':'3'}),'base')

    def test_release_ignores_activation_pulse_then_waits_for_minimum_hold(self):
        doc=setup_document();add_rule(doc,start_event='bell',release_event='bell',hold='event',min_hold=3)
        engine=CameraRuleEngine();engine.emit('bell')
        self.assertEqual(pick(engine,doc,1,['bell','bell']),'special')
        self.assertEqual(engine.events,('bell',));self.assertEqual(len([h for h in engine.history if h['type']=='event']),1)
        self.assertEqual(pick(engine,doc,2,['bell']),'special')
        self.assertEqual(pick(engine,doc,3),'special')
        self.assertEqual(pick(engine,doc,4),'base')
        self.assertEqual(pick(engine,doc,5),'base')
        self.assertEqual(pick(engine,doc,6,['bell']),'special')

    def test_event_hold_survives_condition_loss_but_releases_on_future_event(self):
        doc=setup_document();add_rule(doc,hold='event',release_event='finished',conditions=[dict(fact='ready',op='eq',value=True)])
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0,facts={'ready':True}),'special')
        self.assertEqual(pick(engine,doc,1,facts={'ready':False}),'special')
        self.assertEqual(pick(engine,doc,2,['finished'],{'ready':False}),'base')

    def test_duration_and_minimum_hold_end_once_without_infinite_replay(self):
        doc=setup_document();shot=add_rule(doc,hold='duration',min_hold=3);shot['duration']=2
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0),'special')
        self.assertEqual(pick(engine,doc,2.5),'special');self.assertEqual(pick(engine,doc,3),'base')
        self.assertEqual(pick(engine,doc,4),'base')
        shot['rule']['conditions']=[dict(fact='ready',op='eq',value=True)]
        self.assertEqual(pick(engine,doc,5,facts={'ready':False}),'base')
        self.assertEqual(pick(engine,doc,6,facts={'ready':True}),'special')

    def test_minimum_hold_survives_trigger_loss_then_hands_back(self):
        doc=setup_document();shot=add_rule(doc,min_hold=2);shot['activation']=dict(type='lake',index=1,priority=10)
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0,trigger={'type':'lake','index':1}),'special')
        self.assertEqual(pick(engine,doc,1),'special');self.assertEqual(pick(engine,doc,2),'base')

    def test_only_higher_priority_explicit_interrupt_preempts_a_hold(self):
        doc=setup_document();add_rule(doc,hold='event',release_event='done')
        other=add_rule(doc,'interrupt',priority=20,conditions=[dict(fact='emergency',op='eq',value=True)])
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0),'special')
        self.assertEqual(pick(engine,doc,1,facts={'emergency':True}),'special')
        other['rule']['interrupt']=True;other['activation']['priority']=10
        self.assertEqual(pick(engine,doc,2,facts={'emergency':True}),'special')
        other['activation']['priority']=20
        self.assertEqual(pick(engine,doc,3,facts={'emergency':True}),'interrupt')

    def test_equal_priority_keeps_current_then_document_order(self):
        doc=setup_document();first=add_rule(doc,'first',conditions=[dict(fact='first',op='eq',value=True)])
        add_rule(doc,'second');engine=CameraRuleEngine()
        self.assertEqual(pick(engine,doc,0),'second')
        self.assertEqual(pick(engine,doc,1,facts={'first':True}),'second')
        engine.reset();self.assertEqual(pick(engine,doc,2,facts={'first':True}),'first')

    def test_disabled_removed_or_reserved_context_releases_immediately(self):
        doc=setup_document();shot=add_rule(doc,hold='event',min_hold=99)
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0),'special')
        shot['enabled']=False;self.assertEqual(pick(engine,doc,1),'base')
        self.assertEqual(engine.diagnostics[-1]['reason'],'Disabled')
        shot['enabled']=True;self.assertEqual(pick(engine,doc,2),'special')
        doc['shots'].pop();self.assertEqual(pick(engine,doc,3),'base')
        add_rule(doc,hold='event',min_hold=99)
        focus=deepcopy(doc['shots'][0]);focus['id']='focus';focus['activation']={'type':'focus','priority':-100};doc['shots'].append(focus)
        self.assertEqual(pick(engine,doc,4),'special')
        self.assertEqual(pick(engine,doc,5,trigger={'type':'focus'}),'focus')
        self.assertEqual(pick(engine,doc,6),'special')

    def test_once_per_run_and_visit_have_distinct_reset_scopes(self):
        for scope in ('run','visit'):
            with self.subTest(scope=scope):
                doc=setup_document();shot=add_rule(doc,start_event='go',hold='duration',repeat=scope);shot['duration']=1
                engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0,['go']),'special')
                self.assertEqual(pick(engine,doc,1),'base');engine.reset()
                self.assertEqual(pick(engine,doc,2,['go']),'base');engine.new_visit()
                self.assertEqual(pick(engine,doc,3,['go']),'special' if scope=='visit' else 'base')
                engine.reset(clear_memory=True);self.assertEqual(pick(engine,doc,4,['go']),'special')

    def test_cooldown_starts_on_release_and_losing_shots_are_not_consumed(self):
        doc=setup_document();add_rule(doc,cooldown=3,conditions=[dict(fact='ready',op='eq',value=True)])
        loser=add_rule(doc,'loser',priority=5,repeat='run',start_event='go')
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0,['go'],{'ready':True}),'special')
        self.assertNotIn('loser',engine.export_memory()['seen_run'])
        self.assertEqual(pick(engine,doc,1,facts={'ready':False}),'base')
        self.assertEqual(pick(engine,doc,2,facts={'ready':True}),'base')
        self.assertEqual(pick(engine,doc,4,facts={'ready':True}),'special')

    def test_zone_exit_margin_is_only_for_the_active_zone(self):
        doc=setup_document();shot=add_rule(doc);shot['activation']=dict(type='zone',phase='lake',priority=10,bounds={'min':[-1,0,-1],'max':[1,2,1]})
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0,point=(1.1,1,0)),'base')
        self.assertEqual(pick(engine,doc,1,point=(.9,1,0)),'special')
        self.assertEqual(pick(engine,doc,2,point=(1.2,1,0)),'special')
        self.assertEqual(pick(engine,doc,3,point=(1.26,1,0)),'base')

    def test_manual_override_does_not_consume_a_deferred_rule_event(self):
        doc=setup_document();add_rule(doc,start_event='solved',repeat='run')
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0,['solved'],include_zones=False),'base')
        self.assertNotIn('special',engine.export_memory()['seen_run'])
        self.assertEqual(pick(engine,doc,1,include_zones=False),'base')
        self.assertEqual(pick(engine,doc,2),'special')

    def test_manual_index_change_breaks_hold_but_matching_index_keeps_clock(self):
        doc=setup_document();held=doc['shots'][0];held['rule'].update(min_hold=99,hold='event')
        other=deepcopy(held);other['id']='second';other['activation']['index']=1;doc['shots'].append(other)
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,10),'base')
        self.assertEqual(pick(engine,doc,11,trigger={'type':'lake','index':1},include_zones=False),'second')
        self.assertEqual(engine.started,11)
        self.assertEqual(pick(engine,doc,13,trigger={'type':'lake','index':1},include_zones=False),'second')
        self.assertEqual(engine.started,11)

    def test_deferred_manual_event_waits_through_protected_cinematic_context(self):
        doc=setup_document();add_rule(doc,start_event='solved',repeat='run');engine=CameraRuleEngine()
        pick(engine,doc,0,['solved'],include_zones=False)
        self.assertIsNone(pick(engine,doc,1,trigger={'type':'reveal'}))
        self.assertEqual(pick(engine,doc,2),'special')

    def test_empty_base_slot_sentinel_still_allows_rules_or_none(self):
        doc=setup_document();doc['shots'][0]['enabled']=False;engine=CameraRuleEngine()
        self.assertIsNone(pick(engine,doc,0,trigger={'type':'lake','index':-1}))
        add_rule(doc);self.assertEqual(pick(engine,doc,1,trigger={'type':'lake','index':-1}),'special')
        with self.assertRaises(CameraValidationError):pick(engine,doc,2,trigger={'type':'lake','index':-2})


class MarkerTests(unittest.TestCase):
    def test_initial_inside_records_visited_without_fake_entry(self):
        doc=setup_document();doc['markers']=[marker()];engine=CameraRuleEngine()
        pick(engine,doc,0);self.assertEqual(engine.events,());self.assertTrue(engine.facts['marker.gate.inside'])
        self.assertTrue(engine.facts['marker.gate.visited'])
        pick(engine,doc,1,point=(2,1,0));self.assertEqual(engine.events,('marker.gate.exited',))
        pick(engine,doc,2);self.assertEqual(engine.events,('marker.gate.entered',))

    def test_swept_marker_catches_a_narrow_gate_and_emits_both_edges(self):
        doc=setup_document();doc['markers']=[marker()];add_rule(doc,start_event='marker.gate.entered')
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0,point=(-2,1,0)),'base')
        self.assertEqual(pick(engine,doc,1,point=(2,1,0)),'special')
        self.assertEqual(engine.events,('marker.gate.entered','marker.gate.exited'))
        self.assertTrue(engine.facts['marker.gate.visited']);self.assertFalse(engine.facts['marker.gate.inside'])

    def test_sweep_does_not_trigger_above_or_tangent_to_a_marker(self):
        doc=setup_document();doc['markers']=[marker()]
        for y in (2,3):
            engine=CameraRuleEngine();pick(engine,doc,0,point=(-2,y,0));pick(engine,doc,1,point=(2,y,0))
            self.assertEqual(engine.events,())

    def test_phase_and_edited_marker_rebase_without_fake_entry(self):
        doc=setup_document();doc['markers']=[marker(phase='teahouse')];engine=CameraRuleEngine()
        pick(engine,doc,0);self.assertFalse(engine.facts['marker.gate.visited'])
        pick(engine,doc,1,facts={'world.phase':'teahouse'});self.assertEqual(engine.events,());self.assertTrue(engine.facts['marker.gate.visited'])
        pick(engine,doc,2,facts={'world.phase':'lake'});self.assertEqual(engine.events,('marker.gate.exited',))
        doc['markers'][0]['bounds']['min'][0]=-4
        pick(engine,doc,3,facts={'world.phase':'teahouse'});self.assertEqual(engine.events,())

    def test_visit_reset_clears_occupancy_but_retains_run_visited_memory(self):
        doc=setup_document();doc['markers']=[marker()];engine=CameraRuleEngine();pick(engine,doc,0)
        engine.new_visit();pick(engine,doc,1,point=(2,1,0))
        self.assertEqual(engine.events,());self.assertTrue(engine.facts['marker.gate.visited'])
        engine.reset(clear_memory=True);pick(engine,doc,2,point=(2,1,0));self.assertFalse(engine.facts['marker.gate.visited'])

    def test_removed_marker_condition_fails_closed_but_undo_retains_visit_memory(self):
        doc=setup_document();doc['markers']=[marker()]
        add_rule(doc,conditions=[dict(fact='marker.gate.visited',op='eq',value=True)])
        engine=CameraRuleEngine();self.assertEqual(pick(engine,doc,0),'special')
        doc['markers']=[];self.assertEqual(pick(engine,doc,1),'base')
        self.assertTrue(engine.export_memory()['remembered']['marker.gate.visited'])
        doc['markers']=[marker()];self.assertEqual(pick(engine,doc,2,point=(2,1,0)),'special')


class PersistenceAndValidationTests(unittest.TestCase):
    def test_reload_preserves_active_hold_clock_and_run_consumption(self):
        doc=setup_document();shot=add_rule(doc,hold='event',release_event='finish',repeat='run')
        engine=CameraRuleEngine();pick(engine,doc,5);modified=deepcopy(doc);modified['shots'][-1]['label']='Edited live'
        self.assertEqual(pick(engine,modified,9),'special');self.assertEqual(engine.started,5)
        self.assertEqual(pick(engine,modified,10,['finish']),'base')
        modified['shots'][-1]['duration']=8
        self.assertEqual(pick(engine,modified,11),'base')

    def test_memory_round_trip_preserves_once_scopes_without_replaying_pulses(self):
        doc=setup_document();add_rule(doc,identity='3d-shot',start_event='go',repeat='run',hold='duration')
        engine=CameraRuleEngine();engine.remember('inventory.key',True);pick(engine,doc,0,['go'])
        saved=json.loads(json.dumps(engine.export_memory()));restored=CameraRuleEngine();restored.import_memory(saved)
        self.assertEqual(restored.export_memory(),saved);self.assertIsNone(restored.active_id)
        self.assertEqual(pick(restored,doc,1,['go']),'base');self.assertTrue(restored.facts['inventory.key'])
        self.assertTrue(restored.facts['event.go.seen'])
        before=restored.export_memory();bad=deepcopy(saved);bad['remembered']['x']=float('nan')
        with self.assertRaises(CameraValidationError):restored.import_memory(bad)
        self.assertEqual(restored.export_memory(),before)

    def test_invalid_document_or_inputs_do_not_advance_pending_event_or_memory(self):
        doc=setup_document();add_rule(doc,start_event='go');engine=CameraRuleEngine();engine.emit('go')
        invalid=deepcopy(doc);invalid['shots'][-1]['rule']['cooldown']=-1
        with self.assertRaises(CameraValidationError):pick(engine,invalid,0)
        self.assertEqual(engine.export_memory()['seen_run'],[])
        self.assertEqual(pick(engine,doc,0),'special')
        before=engine.export_memory()
        with self.assertRaises(CameraValidationError):pick(engine,doc,1,facts={'unsafe()':True})
        self.assertEqual(engine.export_memory(),before)

    def test_event_capacity_rejects_atomically_and_existing_memory_round_trips(self):
        doc=setup_document();doc['markers']=[marker()];engine=CameraRuleEngine()
        pick(engine,doc,0,[f'event-{i}' for i in range(512)],point=(-2,1,0))
        before=engine.export_memory();history=deepcopy(engine.history);started=engine.started
        engine.emit('one-too-many')
        with self.assertRaisesRegex(CameraValidationError,'event memory is full'):
            pick(engine,doc,1,point=(2,1,0))
        self.assertEqual(engine.export_memory(),before);self.assertEqual(engine.history,history);self.assertEqual(engine.started,started)
        restored=CameraRuleEngine();restored.import_memory(before);self.assertEqual(restored.export_memory(),before)
        engine.reset(clear_memory=True);pick(engine,doc,2,point=(-2,1,0));pick(engine,doc,3,point=(2,1,0))
        self.assertIn('marker.gate.entered',engine.events)

    def test_seen_history_capacity_rejects_new_documents_without_consumption(self):
        engine=CameraRuleEngine();memory=engine.export_memory();memory['seen_run']=[f'shot-{i}' for i in range(4096)]
        engine.import_memory(memory);before=engine.export_memory();engine.emit('still-pending')
        with self.assertRaisesRegex(CameraValidationError,'shot history is full'):pick(engine,setup_document(),1)
        self.assertEqual(engine.export_memory(),before);self.assertEqual(engine.history,[])

    def test_rule_and_marker_schema_rejects_unknown_nonfinite_or_executable_data(self):
        mutations=(lambda d:d['shots'][0]['rule'].update(min_hold=float('inf')),
                   lambda d:d['shots'][0]['rule'].update(start_event='__import__("os")'),
                   lambda d:d['shots'][0]['rule'].update(conditions=[dict(fact='a',op='gte',value=True)]),
                   lambda d:d['shots'][0]['rule'].update(conditions=[dict(fact='a',op='eval',value='anything')]),
                   lambda d:d['shots'][0]['rule'].update(interrupt=1),
                   lambda d:d.update(markers=[marker(),marker()]),
                   lambda d:d.update(markers=[{**marker(),'bounds':{'min':[0,0,0],'max':[0,2,2]}}]),
                   lambda d:d['shots'][0].update(activation={'type':'rule','phase':'lake','priority':0,'index':0}))
        for mutate in mutations:
            doc=setup_document();mutate(doc)
            with self.subTest(mutation=mutate),self.assertRaises(CameraValidationError):validate_document(doc)

    def test_legacy_migration_is_read_only_and_default_selection_is_unchanged(self):
        legacy=default_document();legacy.pop('markers')
        for shot in legacy['shots']:shot.pop('rule')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'cameras.json';path.write_text(json.dumps(legacy),encoding='utf-8');before=path.read_bytes()
            watcher=CameraWatcher(path);editor=CameraDocument(path)
            self.assertFalse(editor.dirty);self.assertEqual(watcher.document['markers'],[]);self.assertEqual(path.read_bytes(),before)
            engine=CameraRuleEngine()
            for index in range(9):
                actor=[0,.325,0];trigger={'type':'lake','index':index}
                expected=resolve_shot(legacy,trigger,actor,'lake')['id']
                self.assertEqual(engine.choose(watcher.document,trigger,actor,{'world.phase':'lake'},index)['id'],expected)
            editor.save();self.assertIn('markers',json.loads(path.read_text(encoding='utf-8')))

    def test_marker_and_document_changes_are_atomic_and_undoable(self):
        with tempfile.TemporaryDirectory() as directory:
            state=CameraDocument(Path(directory)/'cameras.json');created=state.add_marker();identity=created['id'];label=created['label']
            state.change_document(lambda d:d['markers'][0].update(label='Doorway'))
            self.assertEqual(state.document['markers'][0]['label'],'Doorway');state.undo()
            self.assertEqual(state.document['markers'][0]['label'],label)
            state.remove_marker(identity);self.assertEqual(state.document['markers'],[]);state.undo()
            self.assertEqual(state.document['markers'][0]['id'],identity)
            before=deepcopy(state.document)
            with self.assertRaises(CameraValidationError):state.change_document(lambda d:d['markers'][0].update(phase='unknown'))
            self.assertEqual(state.document,before)
            self.assertFalse(state.path.exists())


if __name__=='__main__':unittest.main()
