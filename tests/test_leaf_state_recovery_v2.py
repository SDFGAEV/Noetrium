from pathlib import Path
import tempfile, unittest
from noetrium_platform.capabilities.environment.specification.schema.composition import compose
class LeafStateRecoveryTests(unittest.TestCase):
 def test_leaf_checkpoint_restore_is_atomic_and_generation_bound(self):
  with tempfile.TemporaryDirectory() as td:
   runtime=compose(lambda op,payload:{'ok':True},Path(td)/'state.json')
   first=runtime.checkpoint({'value':1}); self.assertEqual(first.generation,1)
   self.assertEqual(runtime.read_state().values['value'],1)
   second=runtime.checkpoint({'value':2},expected_generation=1)
   self.assertEqual(second.generation,2)
   restored=runtime.restore(first); self.assertEqual(restored.values['value'],1)
if __name__=='__main__': unittest.main()
