import unittest
from unittest.mock import Mock,patch
from measure_session import distribution,settle
from live_protocol import ProtocolError
class StatisticsTests(unittest.TestCase):
    def test_known_intervals(self):
        r=distribution([10,20,30]);self.assertEqual(r['samples'],3);self.assertEqual(r['mean_ms'],20);self.assertEqual(r['fps_from_interval_mean'],50);self.assertAlmostEqual(r['population_variance_ms2'],200/3);self.assertEqual(r['sample_stddev_ms'],10);self.assertEqual(r['p95_ms'],29)
    def test_empty_closed_cpu_scope(self):self.assertEqual(distribution([]),{'samples':0})
    def test_warm_boundary_discard(self):
        r=distribution([1000,500,10,10],2);self.assertEqual(r['samples'],2);self.assertEqual(r['mean_ms'],10);self.assertEqual(r['sample_stddev_ms'],0)
    def test_settle_requires_requested_native_world_state(self):
        pose=dict(valid=True,block=1,x=0,y=0,z=0,yaw=0)
        for required in [False,True]:
            channel=Mock();channel.read.return_value=dict(pose=pose,menu_top=required)
            with patch('measure_session.time.monotonic',side_effect=[0,0,1]),patch('measure_session.time.sleep'):
                settle(channel,.5,pose,native_menu_paused=required)
    def test_paused_samples_cannot_be_reported_as_active_gameplay(self):
        pose=dict(valid=True,block=1,x=0,y=0,z=0,yaw=0);channel=Mock();channel.read.return_value=dict(pose=pose,menu_top=True)
        with patch('measure_session.time.monotonic',side_effect=[0,0]),self.assertRaises(ProtocolError):settle(channel,.5,pose,native_menu_paused=False)
    def test_active_gameplay_samples_cannot_be_reported_as_paused(self):
        pose=dict(valid=True,block=1,x=0,y=0,z=0,yaw=0);channel=Mock();channel.read.return_value=dict(pose=pose,menu_top=False)
        with patch('measure_session.time.monotonic',side_effect=[0,0]),self.assertRaises(ProtocolError):settle(channel,.5,pose)
if __name__=='__main__':unittest.main()
