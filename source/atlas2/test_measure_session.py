import unittest
from measure_session import distribution
class StatisticsTests(unittest.TestCase):
    def test_known_intervals(self):
        r=distribution([10,20,30]);self.assertEqual(r['samples'],3);self.assertEqual(r['mean_ms'],20);self.assertEqual(r['fps_from_interval_mean'],50);self.assertAlmostEqual(r['population_variance_ms2'],200/3);self.assertEqual(r['sample_stddev_ms'],10);self.assertEqual(r['p95_ms'],29)
    def test_empty_closed_cpu_scope(self):self.assertEqual(distribution([]),{'samples':0})
    def test_warm_boundary_discard(self):
        r=distribution([1000,500,10,10],2);self.assertEqual(r['samples'],2);self.assertEqual(r['mean_ms'],10);self.assertEqual(r['sample_stddev_ms'],0)
if __name__=='__main__':unittest.main()
