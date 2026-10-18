from pathlib import Path
import json,math,tempfile,unittest
from unittest.mock import patch
from live_protocol import Channel,ProtocolError,classify_comparison,matched_pose,verified_private_image

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'trace.json.atlas2.json';self.now=1000.
        self.state=dict(schema=2,sequence=1,utc_ms=1000000,process_id=17,ack={})
        self.write();self.c=Channel(self.path,clock=lambda:self.now,wall=lambda:self.now,sleep=self.advance)
    def write(self):self.path.write_text(json.dumps(self.state))
    def advance(self,t):self.now+=t
    def test_freshness(self):
        self.c.read();self.now+=6
        with self.assertRaises(ProtocolError):self.c.read()
    def test_process_change(self):
        self.c.read();self.state['process_id']=18;self.write()
        with self.assertRaises(ProtocolError):self.c.read()
    def test_no_stale_sequence_acceptance(self):
        with self.assertRaises(ProtocolError):self.c.wait(lambda s:True,after=1,timeout=.3)
    def test_pending_not_overwritten(self):
        self.c.control.write_text('pending')
        with self.assertRaises(ProtocolError):self.c.command('open')
        self.assertEqual(self.c.control.read_text(),'pending')
    def test_correlated_ack(self):
        def native(t):
            self.now+=t
            if self.c.control.exists():
                prefix,seq,command=self.c.control.read_text().strip().split(' ',2);self.assertEqual(prefix,'atlas2-request');self.c.control.unlink();self.state.update(sequence=2,utc_ms=int(self.now*1000),ack=dict(id=int(seq),command=command,state='consumed'));self.write()
        self.c.sleep=native;self.assertEqual(self.c.command('open')['ack']['command'],'open')
    def test_classification(self):
        pose=dict(valid=True,block=1,x=0.,y=0.,z=0.,yaw=math.pi)
        static=dict(render=dict(pose=pose,strict_layer=2,layer=2),visible_tiles=4);ref=dict(render=dict(pose={**pose,'yaw':-math.pi},v1_layer=2))
        self.assertTrue(matched_pose(pose,ref['render']['pose']));self.assertEqual(classify_comparison(static,ref)['status'],'pass')
        ref['render']['v1_layer']=3;self.assertEqual(classify_comparison(static,ref)['status'],'mismatch')
        ref['render']['pose']['x']=1;self.assertEqual(classify_comparison(static,ref)['status'],'inconclusive')
    def test_hidden_visual_is_not_visual_pass(self):
        p=dict(valid=True,block=1,x=0.,y=0.,z=0.,yaw=0.)
        result=classify_comparison(dict(render=dict(pose=p,strict_layer=1,layer=1),visible_tiles=0),dict(render=dict(pose=p,v1_layer=1)))
        self.assertEqual(result['status'],'pass');self.assertNotEqual(result['visual_acceptance'],'pass')
    def test_private_runner_copy_requires_matching_content_and_layout(self):
        expected=Path(self.temp.name)/'private/bin/bb-probe.exe';expected.parent.mkdir(parents=True);expected.write_bytes(b'verified build')
        actual=expected.parent.parent/'state/session-assets-test/bin/bb-probe.exe';actual.parent.mkdir(parents=True);actual.write_bytes(expected.read_bytes())
        with patch('live_protocol.process_image',return_value=actual.resolve()):self.assertEqual(verified_private_image(17,expected),actual.resolve())
        actual.write_bytes(b'other build')
        with patch('live_protocol.process_image',return_value=actual.resolve()):
            with self.assertRaises(ProtocolError):verified_private_image(17,expected)
        outside=Path(self.temp.name)/'unrelated/bin/bb-probe.exe';outside.parent.mkdir(parents=True);outside.write_bytes(expected.read_bytes())
        with patch('live_protocol.process_image',return_value=outside.resolve()):
            with self.assertRaises(ProtocolError):verified_private_image(17,expected)
if __name__=='__main__':unittest.main()
