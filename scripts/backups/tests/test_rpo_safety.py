import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rpo


class MarkerSafetyTest(unittest.TestCase):
    def test_postgresql_text_oid_can_be_cleaned(self):
        with patch.object(rpo,'sql',side_effect=['16480','']) as sql:
            rpo.cleanup_marker('fixture','app-dev','fixture-primary',{'table':'rpo_probe_123456abcdef','table_oid':'16480'})
            self.assertEqual(sql.call_count,2);self.assertTrue(sql.call_args.args[-1].startswith('DROP TABLE public.rpo_probe_'))
    def test_reused_table_is_preserved(self):
        with patch.object(rpo,'sql',return_value='16481') as sql:
            with self.assertRaises(AssertionError):rpo.cleanup_marker('fixture','app-dev','fixture-primary',{'table':'rpo_probe_123456abcdef','table_oid':'16480'})
            self.assertEqual(sql.call_count,1)
    def test_unrelated_table_name_is_never_queried(self):
        with patch.object(rpo,'sql') as sql:
            with self.assertRaises(AssertionError):rpo.cleanup_marker('fixture','app-dev','fixture-primary',{'table':'user','table_oid':'16480'})
            sql.assert_not_called()


if __name__=='__main__':unittest.main()
