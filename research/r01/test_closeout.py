"""Synthetic regression checks for substantive local-closeout findings; no training."""
import copy
import math
import unittest
import reference as r
from test_reference import grid,report

class CloseoutTests(unittest.TestCase):
    def test_equal_huge_logits_ce(self):
        self.assertAlmostEqual(r.joint_loss([1e20]*3,0.,0.),math.log(3))
    def test_equal_negative_huge_logits_ce(self):
        self.assertAlmostEqual(r.joint_loss([-1e20]*3,0.,0.),math.log(3))
    def test_unrepresentable_ce_fails_closed(self):
        with self.assertRaises(ValueError):r.joint_loss([1e308,-1e308,0.],0.,0.)
    def test_common_checkpoint_objective_removes_selector_difference(self):
        clean=[(.8,.5),(.7,.5)];robust=[(.3,.8),(.6,.6)]
        self.assertNotEqual(r.choose_checkpoint(clean)['best_epoch'],r.choose_checkpoint(robust)['best_epoch'])
        self.assertEqual(r.choose_checkpoint(robust),r.choose_checkpoint(list(robust)))
    def test_single_run_checkpoint_uses_one_seed_only(self):
        self.assertEqual(r.checkpoint_score(grid()[17]),{'macro_F1':.5,'MAE':1.})
    def test_same_counts_different_eligibility_set_rejected(self):
        g=grid()
        for seed,runs in g.items():
            for cid,reps in runs.items():
                for i,x in enumerate(reps):
                    x['eligible_count']=1
                    x['pairing']=r.pairing_stamp([0,1],[True,False] if seed==17 else [False,True],'0'*64,i)
        with self.assertRaisesRegex(ValueError,'eligibility set'):r.aggregate(g)
    def test_same_counts_different_order_rejected(self):
        g=grid();g[29]['T:0.1:front'][0]['pairing']=r.pairing_stamp([1,0],[True,True],'0'*64,0)
        with self.assertRaisesRegex(ValueError,'ordered population'):r.aggregate(g)
    def test_same_replica_different_corruption_rejected(self):
        g=grid();g[43]['T:0.1:random'][1]['pairing']['view']='1'*64
        with self.assertRaisesRegex(ValueError,'corruption view'):r.aggregate(g)
    def test_distinct_paired_replicates_allowed(self):
        g=grid()
        for runs in g.values():
            for cid,reps in runs.items():
                for i,x in enumerate(reps):x['pairing']['view']=str(i)*64
        self.assertEqual(r.aggregate(g)['across_seeds']['macro_F1'],.5)
    def test_duplicate_replicate_rejected(self):
        g=grid();g[17]['T:0.1:random'][1]['pairing']['replicate']=0
        with self.assertRaisesRegex(ValueError,'replicate identity'):r.aggregate(g)
    def test_final_fixed_seed_guard_after_mean_pass(self):
        cfg=dict(id='winner',F=.9,MAE=.1,clean_F=(.6+.9+.9)/3,clean_MAE=(.8+.35+.35)/3,parameters=1)
        self.assertEqual(r.rank_configs([cfg],dict(F=.8,MAE=.5))[0]['id'],'winner')
        winner=dict(configuration='winner',seed=17,clean_F=.6,clean_MAE=.8)
        ref=dict(configuration='B*',seed=17,clean_F=.8,clean_MAE=.5)
        self.assertEqual(r.select_final(winner,ref)['configuration'],'B*')
    def test_final_fixed_seed_guard_accepts(self):
        ref=dict(configuration='B*',seed=17,clean_F=.8,clean_MAE=.5)
        winner=dict(configuration='winner',seed=17,clean_F=.8,clean_MAE=.5)
        self.assertEqual(r.select_final(winner,ref)['configuration'],'winner')
    def test_final_does_not_substitute_lucky_seed(self):
        ref=dict(configuration='B*',seed=17,clean_F=.8,clean_MAE=.5)
        winner=dict(configuration='winner',seed=29,clean_F=.9,clean_MAE=.1)
        with self.assertRaises(ValueError):r.select_final(winner,ref)
    def test_fingerprint_produced_from_actual_attempted_inputs(self):
        v=r.attempted_report([0,2],[-1.,1.],[0,2],[-1.,1.],[2,None],[1.,None],[True,False],ordered_rows=[4,8],view_fingerprint='f'*64)
        self.assertEqual(v['pairing'],r.pairing_stamp([4,8],[True,False],'f'*64,0))
    def test_duplicate_ordinal_rejected(self):
        with self.assertRaises(ValueError):r.pairing_stamp([0,0],[True,False],'0'*64,0)

if __name__=='__main__':unittest.main()
