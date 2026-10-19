"""Windows replacement contention must preserve resumable view checkpoints."""
from pathlib import Path
import json,os,tempfile,unittest
from unittest.mock import patch
from bake_all_views import atomic,replace_file,generation_window
from pack_format import shared_open,shared_read

class GenerationIOTests(unittest.TestCase):
 def test_reader_allows_atomic_replacement_and_keeps_coherent_old_contents(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'state.json';atomic(path,{'generation':1})
   with shared_open(path) as reader:
    atomic(path,{'generation':2})
    self.assertEqual(json.loads(reader.read()),{'generation':1})
   self.assertEqual(json.loads(shared_read(path)),{'generation':2})
 def test_temporary_permission_contention_is_retried(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'state.json';atomic(path,{'generation':1});replace=replace_file;attempts=[]
   def contended(source,target):
    attempts.append(1)
    if len(attempts)<3:raise PermissionError('Simulated transient sharing conflict')
    replace(source,target)
   with patch('bake_all_views.replace_file',side_effect=contended),patch('bake_all_views.time.sleep'):
    atomic(path,{'generation':2})
   self.assertEqual(len(attempts),3);self.assertEqual(json.loads(shared_read(path)),{'generation':2})
 def test_persistent_denial_is_bounded_and_preserves_previous_checkpoint(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'state.json';atomic(path,{'generation':1})
   with patch('bake_all_views.replace_file',side_effect=PermissionError('Simulated persistent denial')),patch('bake_all_views.time.monotonic',side_effect=[0,6]),self.assertRaises(PermissionError):atomic(path,{'generation':2})
   self.assertEqual(json.loads(shared_read(path)),{'generation':1})
 def test_unrelated_io_errors_are_not_retried(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch('bake_all_views.replace_file',side_effect=FileNotFoundError('Simulated missing file')) as replace,self.assertRaises(FileNotFoundError):atomic(Path(folder)/'state.json',{})
   self.assertEqual(replace.call_count,1)
 def test_resume_cannot_extend_the_original_time_window(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch('bake_all_views.time.time',return_value=1000),patch('bake_all_views.time.monotonic',return_value=50):self.assertEqual(generation_window(folder,'identity',30,16),(50,80))
   with patch('bake_all_views.time.time',return_value=1010),patch('bake_all_views.time.monotonic',return_value=60):self.assertEqual(generation_window(folder,'identity',300,16),(50,80))
 def test_expired_original_window_blocks_resume(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch('bake_all_views.time.time',return_value=1000):generation_window(folder,'identity',30,16)
   with patch('bake_all_views.time.time',return_value=1031),self.assertRaises(RuntimeError):generation_window(folder,'identity',300,16)
 def test_resume_cannot_silently_increase_storage_budget(self):
  with tempfile.TemporaryDirectory() as folder:
   generation_window(folder,'identity',30,16)
   with self.assertRaises(RuntimeError):generation_window(folder,'identity',30,32)

if __name__=='__main__':unittest.main()
