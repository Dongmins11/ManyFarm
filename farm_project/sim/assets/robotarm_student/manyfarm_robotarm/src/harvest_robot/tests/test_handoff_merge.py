import tempfile
import unittest
from pathlib import Path
import torch
from merge_handoff_banks import merge

class HandoffMerge(unittest.TestCase):
    def test_provenance_and_reject_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            states={'target_index':torch.zeros(2,dtype=torch.long),'q':torch.ones(2,6)}
            for name in ('a','b'):
                torch.save({'metadata':{'checkpoint':'same'},'states':states},root/f'{name}.pt')
            result=merge([root/'a.pt',root/'b.pt'],root/'merged.pt')
            self.assertEqual(result['count'],4)
            self.assertEqual(len(result['sources']),2)
            with self.assertRaises(FileExistsError):merge([root/'a.pt'],root/'merged.pt')
            torch.save({'metadata':{'checkpoint':'different'},'states':states},root/'b.pt')
            with self.assertRaises(ValueError):merge([root/'a.pt',root/'b.pt'],root/'bad.pt')
            self.assertFalse((root/'bad.pt').exists())
