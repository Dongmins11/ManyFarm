import ast
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_runtime import Executor, Request, Target, Feedback
from harvest_runtime.demo import build_demo
from harvest_runtime.adapters import Observation


class ExecutorTests(unittest.TestCase):
    def start(self, fail=None):
        ex,world=build_demo(fail)
        ex.start([Request('r1','red'),Request('r2','yellow')],0.)
        return ex,world

    def finish(self, ex, start=1, end=1000):
        for i in range(start,end):
            ex.tick(i*.05)
            if ex.done:return
        self.fail('Executor did not terminate')

    def test_two_targets_world_preserved_and_final_return(self):
        ex,w=self.start();self.finish(ex)
        self.assertEqual(ex.state,'SUCCEEDED')
        self.assertEqual(w.deposited,{'red','yellow'})
        self.assertEqual([r['target_id'] for r in ex.results],['red','yellow'])
        self.assertEqual([e['state'] for e in ex.events].count('RETURNING'),3)
        count=dict(w.commands);ex.tick(200.);ex.cancel(200.)
        self.assertEqual(w.commands,count)

    def test_failure_stops_without_starting_next(self):
        ex,w=self.start('red');self.finish(ex)
        self.assertEqual(ex.state,'FAILED');self.assertTrue(ex.stop_confirmed)
        self.assertNotIn('yellow',w.commands)

    def test_cancel_waits_for_ack_and_sends_no_more_actions(self):
        ex,w=self.start();ex.tick(.2);ex.tick(.25)
        count=dict(w.commands);ex.cancel(.3)
        self.assertEqual(ex.state,'STOPPING')
        ex.tick(.35);self.assertEqual(ex.state,'CANCELLED')
        self.assertEqual(w.commands,count)

    def test_missing_stop_ack_is_not_cancel_success(self):
        ex,w=self.start();w.tick_stop=lambda now:False
        ex.cancel(.1);ex.tick(2.2)
        self.assertEqual(ex.state,'FAILED');self.assertFalse(ex.stop_confirmed)
        self.assertIn('stop_unconfirmed',ex.reason)

    def test_stale_target_blocks_policy(self):
        ex,w=self.start();ex.observe=lambda t,n:Target(t,'arm_base',(0,0,0),n-2)
        self.finish(ex)
        self.assertEqual(w.commands,{})
        self.assertEqual(ex.state,'FAILED')

    def test_wrong_frame_blocks_policy(self):
        ex,w=self.start();ex.observe=lambda t,n:Target(t,'camera_optical',(0,0,0),n)
        self.finish(ex);self.assertEqual(w.commands,{})

    def test_invalid_live_observation_stops_before_action(self):
        ex,w=self.start()
        ex.backend.read_observation=lambda r,n:Observation(r.request_id,r.target_id,'arm_base',n-2,{})
        self.finish(ex);self.assertEqual(w.commands,{})

    def test_wrong_completion_id_stops_before_action(self):
        ex,w=self.start()
        ex.backend.completion=lambda r,n:Feedback('old-request',r.target_id,'SUCCEEDED','old deposit')
        self.finish(ex);self.assertEqual(w.commands,{})
        self.assertEqual(ex.completed,set())

    def test_action_validation_blocks_nan(self):
        ex,w=self.start();ex.backend.policy.act=lambda obs:float('nan')
        self.finish(ex);self.assertEqual(w.commands,{})

    def test_target_timeout_does_not_advance(self):
        ex,w=build_demo();ex.start([Request('r1','red',.1),Request('r2','yellow')],0.)
        self.finish(ex);self.assertEqual(ex.state,'TIMED_OUT')
        self.assertNotIn('yellow',w.commands)

    def test_return_timeout_does_not_start_policy(self):
        ex,w=self.start()
        w.tick_return=lambda r,n:Feedback(r.request_id,r.target_id,'RUNNING')
        ex.tick(21.);ex.tick(21.1)
        self.assertEqual(ex.state,'TIMED_OUT');self.assertEqual(w.commands,{})

    def test_target_success_does_not_override_return_failure(self):
        ex,w=self.start()
        original=w.tick_return
        def poll(r,n):
            if w.deposited:return Feedback(r.request_id,r.target_id,'FAILED','blocked path')
            return original(r,n)
        w.tick_return=poll;self.finish(ex)
        self.assertEqual(ex.completed,{'red'});self.assertEqual(ex.state,'FAILED')
        self.assertNotIn('yellow',w.commands)

    def test_each_target_reobserved_after_return(self):
        ex,w=self.start();seen=[]
        def observe(t,n):seen.append((t,n));return w.observe(t,n)
        ex.observe=observe;self.finish(ex)
        self.assertEqual([t for t,n in seen],['red','yellow'])
        self.assertGreater(seen[1][1],seen[0][1])

    def test_duplicate_and_previously_completed_rejected(self):
        ex,w=build_demo()
        with self.assertRaises(ValueError):ex.start([Request('r','a'),Request('r','b')],0.)
        with self.assertRaises(ValueError):ex.start([Request('r','a'),Request('s','a')],0.)
        ex.completed.add('a')
        with self.assertRaises(ValueError):ex.start([Request('r','a')],0.)

    def test_clock_backwards_stops_policy(self):
        ex,w=self.start();ex.tick(.2);ex.tick(.1)
        self.assertEqual(ex.state,'STOPPING');ex.tick(.3)
        self.assertEqual(ex.state,'FAILED');self.assertTrue(ex.stop_confirmed)

    def test_exception_requests_stop(self):
        ex,w=self.start()
        def broken(obs):raise RuntimeError('sensor failed')
        ex.backend.policy.act=broken;self.finish(ex)
        self.assertTrue(w.stopped);self.assertEqual(ex.state,'FAILED')

    def test_external_timeout_resets_per_target(self):
        # Exercise actual method without importing Isaac Sim.
        tree=ast.parse((Path(__file__).resolve().parents[1]/'harvest_rl/env.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='HarvestEnv')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_target_elapsed_steps')
        namespace={'target_elapsed':lambda elapsed,start,per_target:elapsed-start if per_target else elapsed}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'env method','exec'),namespace)
        from types import SimpleNamespace
        obj=SimpleNamespace(episode_length_buf=500,target_start_step=480,
            settings=SimpleNamespace(target_mode='external',sequence=False,timeout_scope='episode'))
        self.assertEqual(namespace['_target_elapsed_steps'](obj),20)
        obj.settings.target_mode='nearest'
        self.assertEqual(namespace['_target_elapsed_steps'](obj),500)


if __name__=='__main__':unittest.main()
