from pathlib import Path
import csv,tempfile,unittest
from capture_presentmon import summarize
class PresentMonTests(unittest.TestCase):
    def test_pid_swapchain_and_units(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'frames.csv'
            with path.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['ProcessID','SwapChainAddress','MsBetweenPresents','MsGPUBusy']);w.writeheader()
                for n in range(6):w.writerow(dict(ProcessID=7,SwapChainAddress='a',MsBetweenPresents=20,MsGPUBusy='NA'))
                w.writerow(dict(ProcessID=7,SwapChainAddress='b',MsBetweenPresents=1000,MsGPUBusy=4));w.writerow(dict(ProcessID=8,SwapChainAddress='a',MsBetweenPresents=5000,MsGPUBusy=4))
            out=summarize(path,7);self.assertEqual(out['selected_rows'],4);self.assertEqual(out['swapchain_count'],2);self.assertEqual(out['metrics']['MsBetweenPresents']['fps_from_interval_mean'],50);self.assertEqual(out['metrics']['MsGPUBusy']['samples'],0)
    def test_empty_capture_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'frames.csv';path.write_text('ProcessID,SwapChainAddress,MsBetweenPresents\n')
            with self.assertRaises(RuntimeError):summarize(path,7)
if __name__=='__main__':unittest.main()
