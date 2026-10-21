import argparse,ast,sys,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P))
from input_timing import timing,summarize

class TimingTests(unittest.TestCase):
    def test_existing_boundary_preserved(self):
        for age,expected in [(-.100000001,'future_stamp'),(-.1,''),(0,''),(.5,''),(.500000001,'stamp_expired')]:
            with self.subTest(age=age):
                value=timing('footprint',10**9,10**9,10**9+round(age*10**9),.01)
                self.assertEqual(value['reason'],expected)
    def test_receipt_boundary(self):
        self.assertEqual(timing('odom',10**9,10**9,10**9,.5)['reason'],'')
        self.assertEqual(timing('odom',10**9,10**9,10**9,.500000001)['reason'],'receipt_expired')
    def test_arrival_delay_separate_from_callback_age(self):
        row=timing('footprint',10**9,1600000000,1610000000,.01)
        self.assertAlmostEqual(row['age_at_receive_s'],.6)
        self.assertEqual(row['reason'],'stamp_expired')
    def test_executor_delay_visible(self):
        row=timing('footprint',10**9,1100000000,1610000000,.51)
        self.assertAlmostEqual(row['age_at_receive_s'],.1)
        self.assertEqual(row['reason'],'receipt_expired')
    def test_future_clock_visible(self):
        row=timing('footprint',1600000000,1000000000,1100000000,.1)
        self.assertAlmostEqual(row['measurement_age_s'],-.5)
        self.assertEqual(row['reason'],'future_stamp')
    def test_summary_empty_and_distinct(self):
        self.assertEqual(summarize([]),{})
        rows=[timing('footprint',10**9,1100000000,t,.01) for t in (1200000000,1600000000)]
        result=summarize(rows)['footprint']
        self.assertEqual(result['checks'],2);self.assertEqual(result['distinct_stamps'],1)
        self.assertEqual(len(result['failures']),1)
    def parser(self,filename,args):
        tree=ast.parse((P/filename).read_text())
        if filename=='arc_trial.py':
            body=next(n for n in tree.body if isinstance(n,ast.If)).body
        else:
            body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main').body
        start=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='parser' for t in n.targets))
        end=next(i for i,n in enumerate(body) if isinstance(n,ast.If) and 'args.input_trace' in ast.unparse(n))
        code=compile(ast.fix_missing_locations(ast.Module(body=body[start:end+1],type_ignores=[])),'parser','exec')
        scope=dict(argparse=argparse,Path=Path,__doc__='test')
        with patch.object(sys,'argv',[filename,*args]):exec(code,scope)
        return scope['args']
    def test_runtime_rejects_execute_trace(self):
        with self.assertRaises(SystemExit):self.parser('arc_trial.py',['trial','--align-from','x','--input-trace','--execute'])
    def test_supervisor_rejects_execute_trace(self):
        with self.assertRaises(SystemExit):self.parser('arc_isolated.py',['execute','--align-from','x','--input-trace'])
    def test_trace_requires_align(self):
        for file,args in [('arc_trial.py',['trial','--input-trace']),('arc_isolated.py',['plan','--input-trace'])]:
            with self.subTest(file=file),self.assertRaises(SystemExit):self.parser(file,args)
    def test_readonly_trace_arguments(self):
        self.assertFalse(self.parser('arc_trial.py',['trial','--align-from','x','--input-trace']).execute)
        self.assertEqual(self.parser('arc_isolated.py',['plan','--align-from','x','--input-trace']).mode,'plan')
if __name__=='__main__':unittest.main(verbosity=2)
