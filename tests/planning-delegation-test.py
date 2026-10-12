#!/usr/bin/env python3
"""Public command checks: authorization, independent fidelity, drift and bounds.

The fake tracker models persistence only; actual doors/outline/map checks run.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'bin/planning-delegation'
MAIN = runpy.run_path(str(TOOL))['main']
FAKE = ROOT / 'tests/fixtures/spec-approve/bd'
BODY = '## User Stories\n1. As an operator, I want a probe, so that I see failure.\n'
KEY, REQUEST = 'gc.planning_delegation', 'gc.planning_derivation'


class DelegationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix='planning-delegation-test-'))
        cls.profile = cls.base / 'profile'
        cls.profile.write_text('#!/usr/bin/env python3\nprint(\'{"ok":true,"human_approver":"benjamin"}\')\n')
        cls.profile.chmod(0o755)
        cls.graph = cls.base / 'graph'
        cls.graph.write_text("#!/usr/bin/env python3\nimport os,json,hashlib\n"
            "state=json.load(open(os.environ['SPEC_APPROVE_BD_STATE']))\n"
            "d='sha256:'+hashlib.sha256(state['beads']['spec']['description'].encode()).hexdigest()\n"
            "print(os.environ.get('GRAPH_TEST_RESULT',json.dumps({'ok':True,'decisions':{},'derived_spec_digest':d})))\n")
        cls.graph.chmod(0o755)
        def bead(id, body, **meta):
            return {'id': id, 'title': id, 'description': body, 'metadata': {'gc.plane': 'planning', 'gc.project_id': 'acme', **meta},
                    'labels': [], 'parent': None, 'status': 'open'}
        cls.seed = {'beads': {
            'map': bead('map', 'Validated purpose'),
            'map.1': bead('map.1', 'Validated decision'),
            'spec': bead('spec', BODY, planning_map='map'),
            'graph': bead('graph', 'flow_contract: new-flow/v1\ntickets: []\n', spec_id='spec'),
        }, 'next_id': 1}
        cls.seed['beads']['map']['labels'] = ['wayfinder:map']
        cls.seed['beads']['map.1'].update(parent='map', status='closed', labels=['wayfinder:task'])
        decor = cls()
        decor.setUp()
        decor.seal()
        cls.prepared_request = decor.prepare()['request']
        cls.prepared_state = decor.state()
        decor.doCleanups()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=self.base))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state_path = self.tmp / 'state.json'
        self.state_path.write_text(json.dumps(copy.deepcopy(self.seed)))
        self.env = {'BD_BIN': str(FAKE), 'SPEC_APPROVE_BD_STATE': str(self.state_path),
                    'PROJECT_PLANNING_PROFILE_BIN': str(self.profile), 'GRAPH_REVIEW_BIN': str(self.graph),
                    'DELIVERY_ROLE_READ_ONLY': '1', 'GC_SESSION_NAME': 'independent-reviewer'}

    def invoke(self, *args, cli=False, expected=0):
        with patch.dict(os.environ, self.env):
            if cli:
                p = subprocess.run([str(TOOL), *args], text=True, capture_output=True)
                code, out = p.returncode, p.stdout
            else:
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    code = MAIN(args)
                out = stream.getvalue()
        self.assertEqual(expected, code, out)
        return json.loads(out)

    def state(self):
        return json.loads(self.state_path.read_text())

    def change(self, callback):
        state = self.state(); callback(state['beads']); self.state_path.write_text(json.dumps(state))

    def seal(self):
        return self.invoke('authorize', '--map', 'map', '--project', 'acme', '--by', 'benjamin', '--evidence', 'Delegate derivation, live chat')

    def prepare(self, kind='spec', expected=0):
        return self.invoke('prepare', '--map', 'map', '--artifact', kind, '--kind', kind, '--project', 'acme', '--author-session', 'author', expected=expected)

    def ready(self):
        self.state_path.write_text(json.dumps(copy.deepcopy(self.prepared_state)))
        return copy.deepcopy(self.prepared_request)

    def record(self, request, **changes):
        verdict = {'digest': request['digest'], 'authorization': request['authorization'],
                   'source_coverage': [{'source': source, 'stories': ['1'], 'reason': 'Retained decision'} for source in ('map', 'map.1')],
                   'story_basis': [{'story': '1', 'sources': ['map', 'map.1'], 'reason': 'Probe preserves the validated intent'}],
                   'all_decisions_preserved': True, 'no_new_sensitive_effect': True,
                   'no_unsourced_product_choice': True, 'reason': 'Compared every decision and story', **changes}
        path = self.tmp / 'verdict.json'; path.write_text(json.dumps(verdict))
        return path

    def favorable(self):
        request = self.ready()
        self.invoke('record', '--artifact', 'spec', '--verdict-file', str(self.record(request)))
        return request

    def test_cli_authorizes_and_refuses_another_human(self):
        result = self.invoke('authorize', '--map', 'map', '--project', 'acme', '--by', 'benjamin', '--evidence', 'Delegate', cli=True)
        self.assertEqual(['map', 'map.1'], result['authorization']['source_ids'])
        before = self.state()
        self.invoke('authorize', '--map', 'map', '--project', 'acme', '--by', 'agent', '--evidence', 'Delegate', cli=True, expected=1)
        self.assertEqual(before, self.state())

    def test_favorable_review_is_distinct_from_human_approval(self):
        self.favorable()
        proof = self.invoke('check', '--artifact', 'spec', '--project', 'acme')
        self.assertEqual(('derived/v1', 'author', 'benjamin', 'spec'), (proof['mode'], proof['derived_by'], proof['delegated_by'], proof['kind']))
        self.assertNotIn('approved_by', self.state()['beads']['spec']['metadata'])

    def test_self_review_and_missing_coverage_are_refused_without_writes(self):
        request = self.ready(); path = self.record(request)
        before = self.state()
        self.env['GC_SESSION_NAME'] = 'author'
        self.invoke('record', '--artifact', 'spec', '--verdict-file', str(path), expected=1)
        self.env['GC_SESSION_NAME'] = 'reviewer'
        path = self.record(request, source_coverage=[])
        self.invoke('record', '--artifact', 'spec', '--verdict-file', str(path), expected=1)
        self.assertEqual(before, self.state())

    def test_new_sensitive_effect_refuses_derivation(self):
        request = self.ready()
        self.invoke('record', '--artifact', 'spec', '--verdict-file', str(self.record(request, no_new_sensitive_effect=False)))
        self.invoke('check', '--artifact', 'spec', '--project', 'acme', expected=1)

    def test_source_comment_title_project_and_reopening_invalidate(self):
        self.favorable(); good = self.state()
        for field, value in [('comments', [{'text': 'Changed decision'}]), ('title', 'Another purpose'), ('status', 'open')]:
            with self.subTest(field=field):
                self.state_path.write_text(json.dumps(good))
                self.change(lambda beads: beads['map.1'].update({field: value}))
                self.invoke('check', '--artifact', 'spec', '--project', 'acme', expected=1)
        self.state_path.write_text(json.dumps(good))
        self.change(lambda beads: beads['map']['metadata'].update({'gc.project_id': 'other'}))
        self.invoke('check', '--artifact', 'spec', '--project', 'acme', expected=1)

    def test_artifact_edit_and_revocation_invalidate(self):
        self.favorable(); good = self.state()
        self.change(lambda beads: beads['spec'].update(description=BODY + 'changed'))
        self.invoke('check', '--artifact', 'spec', '--project', 'acme', expected=1)
        self.state_path.write_text(json.dumps(good))
        self.invoke('revoke', '--map', 'map', '--by', 'benjamin')
        self.invoke('check', '--artifact', 'spec', '--project', 'acme', expected=1)

    def test_bounds_survive_source_comment_renewal_and_reuse_last_favorable(self):
        request = self.ready()
        self.invoke('record', '--artifact', 'spec', '--verdict-file', str(self.record(request, all_decisions_preserved=False)))
        self.change(lambda beads: beads['spec'].update(description=BODY + '\nCorrected detail'))
        request = self.prepare()['request']
        self.invoke('record', '--artifact', 'spec', '--verdict-file', str(self.record(request)))
        self.assertTrue(self.prepare()['unchanged'])
        self.change(lambda beads: beads['map'].update(comments=[{'text': 'New context'}]))
        renewed = self.seal()['authorization']
        self.assertEqual((2, 'spec'), (renewed['spec_reviews'], renewed['spec']))
        self.prepare(expected=1)

    def test_graph_is_bound_to_spec_and_refuses_review_override(self):
        self.favorable(); self.prepare('graph')
        proof = self.invoke('derive-graph', '--artifact', 'graph', '--project', 'acme')
        self.assertEqual('graph', proof['kind'])
        self.assertEqual('author', self.state()['beads']['graph']['metadata']['approved_by'])
        self.env['GRAPH_TEST_RESULT'] = json.dumps({'ok': True, 'decisions': {'T1': 'publish'}})
        self.invoke('derive-graph', '--artifact', 'graph', '--project', 'acme', expected=1)

    def test_review_dispatch_is_routed_once_and_a_closed_missing_verdict_is_not_success(self):
        self.ready()
        dispatcher = self.tmp / 'dispatch'
        log = self.tmp / 'dispatch.json'
        dispatcher.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n'
                              + 'Path(' + repr(str(log)) + ').write_text(json.dumps(sys.argv[1:]))\n')
        dispatcher.chmod(0o755)
        self.env['DISPATCH_DOOR_BIN'] = str(dispatcher)
        first = self.invoke('request-review', '--artifact', 'spec')
        review_id = first['request']['review_bead']
        self.assertEqual('spec: spec', self.state()['beads'][review_id]['description'])
        self.assertNotEqual('planning', self.state()['beads'][review_id]['metadata'].get('gc.plane'))
        self.assertEqual([review_id, '--rig', 'agent-factory', '--formula', 'mol-planning-fidelity', '--role', 'reviewer'], json.loads(log.read_text()))
        self.assertEqual(review_id, self.invoke('request-review', '--artifact', 'spec')['request']['review_bead'])
        self.assertEqual(5, len(self.state()['beads']))
        self.change(lambda beads: beads[review_id].update(status='closed'))
        self.invoke('request-review', '--artifact', 'spec', expected=1)

    def test_publication_seal_allows_retry_but_not_another_digest(self):
        self.favorable(); request = self.prepare('graph')['request']
        args = ('seal-publication', '--artifact', 'graph', '--project', 'acme', '--expected-digest', request['digest'])
        self.invoke(*args)
        self.invoke(*args)
        self.change(lambda beads: beads['graph'].update(description='changed graph'))
        self.prepare('graph', expected=1)
        self.invoke(*args, expected=1)

    def test_real_spec_freeze_transmits_derivation_without_human_signature(self):
        self.favorable()
        with patch.dict(os.environ, self.env):
            proc = subprocess.run([str(ROOT / 'bin/spec-approve'), 'bd-derive', '--spec', 'spec', '--project', 'acme',
                '--repo-root', str(self.tmp), '--config-dir', str(ROOT / 'tests/fixtures/spec-approve/projects')], capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        state = self.state()
        self.assertEqual('derived/v1', state['beads']['spec']['metadata']['approval_mode'])
        self.assertEqual('author', state['beads']['spec']['metadata']['approved_by'])
        self.assertEqual('closed', state['beads']['map']['status'])
        self.invoke('check', '--artifact', 'spec', '--project', 'acme')


if __name__ == '__main__':
    unittest.main()
