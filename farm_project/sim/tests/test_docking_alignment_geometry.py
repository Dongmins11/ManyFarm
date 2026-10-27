"""바구니 겹침 면적의 기하 계산 검사. 합격 임계값은 별도 정책으로 적용한다."""
import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from analyze_docking_alignment import polygon, intersection, area


class AlignmentGeometryTests(unittest.TestCase):
    def test_contained_partial_and_separated(self) -> None:
        h=polygon(np.eye(4),dict(center_local_m=[0,0,0],opening_size_m=[.19,.19]))[:,:2]
        for shift,expected in [(0,1),(.1,(.147-.005)/.19),(.5,0)]:
            t=polygon(np.eye(4),dict(center_local_m=[shift,0,0],opening_size_m=[.294,.294]))[:,:2]
            self.assertAlmostEqual(area(intersection(h,t))/area(h),expected,places=9)

    def test_world_rotation_preserves_overlap(self) -> None:
        m=np.array([[0,-1,0,2],[1,0,0,-3],[0,0,1,.4],[0,0,0,1]])
        h=polygon(m,dict(center_local_m=[0,0,.1],opening_size_m=[.19,.19]))
        t=polygon(m,dict(center_local_m=[0,0,0],opening_size_m=[.294,.294]))
        self.assertAlmostEqual(area(intersection(h[:,:2],t[:,:2])),.19**2)
        self.assertAlmostEqual(h[:,2].min()-t[:,2].max(),.1)


if __name__=='__main__':unittest.main()
