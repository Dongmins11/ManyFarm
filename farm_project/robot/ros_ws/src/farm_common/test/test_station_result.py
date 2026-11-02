"""실제 execute 경로의 Result 계약 검증. ROS 노드/이동 없이 어댑터만 대체한다."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from farm_common.station_return import StationReturn
from farm_common.action_handoff import ActionInterrupted

class ResultTests(unittest.TestCase):
    def run_case(self, wall=True, mode='real', failure=None, cleanup=False):
        obj=StationReturn.__new__(StationReturn)
        obj._handoff=Mock();obj._node=Mock();obj._check=Mock();obj._feedback=Mock()
        obj._prepare=None;obj._navigator=Mock();obj._forward=Mock();obj._spin=Mock()
        obj._station=NS(options={},xy=(0.,0.));obj._graph=Mock();obj._poses=Mock()
        obj._motion=Mock();obj._settings=Mock();obj._wall_reverse=Mock() if wall else None
        obj._tag_control=None;obj._profile={'mode':mode};obj._block=Mock()
        if cleanup:obj._motion.wait_stopped.side_effect=RuntimeError('stop missing')
        handle=Mock();handle.request=NS(robot_id='scout_01',task_id='test',station_id='STATION_SCOUT_01')
        handle.is_cancel_requested=isinstance(failure,ActionInterrupted)
        with patch('farm_common.station_stages.run_stages',side_effect=failure):
            result=obj.execute(handle)
        return result,handle
    def test_wall_success_is_docked(self):
        r,h=self.run_case();self.assertEqual((r.result_code,r.error_code,r.docked),('SUCCESS','NONE',True));h.succeed.assert_called_once()
    def test_legacy_real_not_marked_docked(self):
        r,_=self.run_case(wall=False);self.assertFalse(r.docked)
    def test_sim_success_preserved(self):
        r,_=self.run_case(wall=False,mode='sim');self.assertTrue(r.docked)
    def test_failure_not_docked(self):
        r,h=self.run_case(failure=RuntimeError('wall missing'));self.assertEqual(r.result_code,'FAILED');self.assertFalse(r.docked);h.abort.assert_called_once()
    def test_cancel_not_docked(self):
        r,h=self.run_case(failure=ActionInterrupted('cancel'));self.assertEqual(r.result_code,'CANCELED');self.assertFalse(r.docked);h.canceled.assert_called_once()
    def test_cleanup_failure_not_docked(self):
        r,h=self.run_case(cleanup=True);self.assertEqual(r.error_code,'CANCEL_UNCONFIRMED');self.assertFalse(r.docked);h.abort.assert_called_once()

if __name__=='__main__':unittest.main()
