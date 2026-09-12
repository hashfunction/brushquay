"""Fixed release identities and fail-closed reviewed input boundary."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import manifest_identity as identity

class ReleaseContractTests(unittest.TestCase):
    def test_fixed_modes_are_available(self):
        self.assertTrue(callable(getattr(identity,'identity_for_mode',None)), 'fixed mode resolver is missing')
        store=identity.identity_for_mode('store')
        self.assertEqual(store['PackageName'],'1659hashfunction.BrushQuay')
        self.assertEqual(store['Version'],'1.0.1.0')
        self.assertNotEqual(store,identity.identity_for_mode('qualification'))
        for mode in ('Store','anything','',None):
            with self.assertRaises(ValueError):identity.identity_for_mode(mode)
        changed=copy.deepcopy(store);changed['Publisher']='CN=foreign'
        with self.assertRaises(ValueError):identity.require_mode(changed,'store')
        with self.assertRaises(ValueError):identity.require_mode(store,'qualification')
        store['Version']='9.0.0.0'
        self.assertEqual(identity.identity_for_mode('store')['Version'],'1.0.1.0')

if __name__=='__main__':unittest.main()
