"""Reject native raster aliasing before timing; no image upload or display."""
from pathlib import Path
import argparse,hashlib,json
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);a=p.parse_args();s=a.session.resolve();pairs=json.loads((s/'matching-view-comparisons.json').read_text());pixels=json.loads((s/'private-pixel-comparison.json').read_text());metrics={r['preset']:r for r in pixels['comparisons']};rows=[]
 limits={'default':2.,'maximum_scaled':2.,'minimum_scaled':.5,'fit':3.}
 for pair in pairs['comparisons']:
  state=pair['static'];preset=pair['preset'];assert pair['status']=='matched_view_pending_visual_review';assert state['composite'] and state['detail_ppu']==16 and state['integrity_failures']==0 and state['resident_slots']==state['distinct_backend_textures'] and state['visible_tiles']==state['backend_ready_tiles'];mae=metrics[preset]['map_canvas']['rgb_mae_0_255'];assert mae<=limits[preset];images=[]
  for mode in ('static','reference'):
   image=pair['private_images'][mode][0];assert image['capture_kind']=='final_swapchain_including_atlas';path=Path(image['path']).resolve();path.relative_to(s);assert hashlib.sha256(path.read_bytes()).hexdigest()==image['sha256'];images.append(dict(mode=mode,path=str(path),sha256=image['sha256']))
  rows.append(dict(preset=preset,rgb_mae=mae,acceptance_limit=limits[preset],images=images))
 assert {r['preset'] for r in rows}==set(limits)
 report=dict(schema=1,texture_binding_accepted=True,session=str(s),same_pose_views=4,comparisons=rows,pixel_identity_claimed=False,navigation_readability_accepted=False,scope='Operational rejection of repeated/missing raster tiles at four sampled views; RGB limits are regression thresholds, not perceptual or semantic equivalence',images_uploaded=False);(s/'raster-correctness-verification.json').write_text(json.dumps(report,indent=2));print('NATIVE_RASTER_BINDING_CHECK_PASS views=4 pixel_identity=false')
if __name__=='__main__':main()
