import copy,unittest
from visual_pair import same_view

class MatchingViewTests(unittest.TestCase):
    def setUp(self):self.a=dict(region_id='generic',layer=3,v1_layer=3,ui_scale=1.5,canvas_size=[1252.5,807],viewport_size=[1920,1080],feature_settings=dict(fog=True,items=True,travel=True),zoom=13.5,center=[1.,2.],pose=dict(valid=True,block=1,x=1.,y=0.,z=2.,yaw=0.))
    def test_identical(self):self.assertTrue(same_view(self.a,copy.deepcopy(self.a))[0])
    def test_rejects_zoom_pan_floor_flags(self):
        for key,value in [('zoom',14),('center',[2.,2.]),('layer',4),('feature_settings',dict(fog=False))]:
            b=copy.deepcopy(self.a);b[key]=value;self.assertFalse(same_view(self.a,b)[0],key)
    def test_rejects_missing_telemetry(self):
        b=copy.deepcopy(self.a);del b['center'];self.assertFalse(same_view(self.a,b)[0])
    def test_rejects_player_motion(self):
        b=copy.deepcopy(self.a);b['pose']['x']+=1;self.assertFalse(same_view(self.a,b)[0])
    def test_rejects_subtle_motion_at_large_zoom(self):
        a=copy.deepcopy(self.a);a['zoom']=75;b=copy.deepcopy(a);b['pose']['x']+=.01;self.assertFalse(same_view(a,b)[0])
    def test_rejects_unavailable_reference(self):
        b=copy.deepcopy(self.a);del b['v1_layer'];self.assertFalse(same_view(self.a,b)[0])
if __name__=='__main__':unittest.main()
