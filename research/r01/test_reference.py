"""Only hand-created synthetic arrays; no model fitting, no official imports."""
import copy
import math
import unittest
import reference as r

def masks(length=5,a=None,v=None,pad=0):
    s=[True]*length+[False]*pad
    return s,{'T':list(s),'A':(a if a is not None else [True]*length)+[False]*pad,'V':(v if v is not None else [True]*length)+[False]*pad}

def report(f=.5,mae=1.,eligible=2):
    return {'attempted':{'macro_F1':f,'MAE':mae,'n':2},'eligible_count':eligible,'total_count':2,'pairing':r.pairing_stamp([0,1],[True]*eligible+[False]*(2-eligible),'0'*64,0)}

def rep_report(i,f=.5,mae=1.):
    v=report(f,mae);v['pairing']['replicate']=i;return v

def grid():
    return {seed:{r.condition_id(c):[rep_report(i) for i in range(3 if c[2]=='random' else 1)] for c in r.conditions()} for seed in r.MODEL_SEEDS}

class GeneratorTests(unittest.TestCase):
    def test_01_grid_96_nominal_144_views(self):
        self.assertEqual(len(r.conditions()),96);self.assertEqual(sum(3 if c[2]=='random' else 1 for c in r.conditions()),144)
    def test_02_short_support_fallback(self):
        z=r.generate(*masks(1),('T','0.7','front'));self.assertEqual((z['status'],z['reason'],z['fallback']),('INELIGIBLE','short_support','CLEAN_ONCE'))
    def test_03_empty_observed(self):
        z=r.generate(*masks(a=[False]*5),('A','0.3','front'));self.assertEqual(z['reason'],'insufficient_observed')
    def test_04_single_observation(self):
        z=r.generate(*masks(a=[True,False,False,False,False]),('A','0.3','front'));self.assertEqual(z['status'],'INELIGIBLE')
    def test_05_no_common_window(self):
        z=r.generate(*masks(4,a=[True,True,False,False],v=[False,False,True,True]),('AV','0.1','front'));self.assertEqual(z['reason'],'no_common_legal_window')
    def test_06_middle_migration_tie_lower_start(self):
        z=r.generate(*masks(a=[False,True,False,True,False]),('A','0.1','middle'));self.assertEqual((z['requested_start'],z['start'],z['moved']),(2,1,True))
    def test_07_structural_hole_within_continuous_window(self):
        z=r.generate(*masks(a=[True,False,True,True,True]),('A','0.5','front'));self.assertEqual(z['C']['A'],[True,False,True,False,False])
    def test_08_no_padding_corruption(self):
        z=r.generate(*masks(pad=3),('TV','0.7','back'));self.assertFalse(any(z['C']['T'][5:]))
    def test_09_all_selected_modalities_retain_observation(self):
        s,o=masks()
        for c in r.conditions():
            z=r.generate(s,o,c)
            for m in c[0]:self.assertTrue(0<sum(z['C'][m])<sum(o[m]))
    def test_10_unselected_modality_unchanged(self):
        s,o=masks();z=r.generate(s,o,('T','0.3','front'));self.assertEqual(z['A']['A'],o['A'])
    def test_11_exact_fraction_width(self):
        z=r.generate(*masks(10),('T','0.1','front'));self.assertEqual(z['width'],1)
    def test_12_realized_rates_differ(self):
        z=r.generate(*masks(a=[True,False,True,True,True]),('A','0.5','front'));self.assertEqual(z['realized_observed_rate']['A'],.5);self.assertEqual(z['realized_support_rate']['A'],.4)
    def test_13_deterministic_random_key(self):
        self.assertEqual(r.generate(*masks(20),('TA','0.3','random'),ordinal=8,replicate=2),r.generate(*masks(20),('TA','0.3','random'),ordinal=8,replicate=2))
    def test_14_nonrandom_extra_replicate_rejected(self):
        with self.assertRaises(ValueError):r.generate(*masks(),('T','0.1','front'),replicate=1)
    def test_15_train_ineligible_kept_once(self):
        found=[r.train_attempt(*masks(1),17,e,0) for e in range(40)]
        eligible=[z for z in found if z['status']=='INELIGIBLE'];self.assertTrue(eligible)
        self.assertTrue(all(z['weight']==1. and z['A']['T']==[True] and z['fallback']=='CLEAN_ONCE' for z in eligible))
    def test_16_train_architecture_pairing(self):
        self.assertEqual(r.train_attempt(*masks(),29,3,9),r.train_attempt(*masks(),29,3,9))
    def test_17_source_immutable(self):
        s,o=masks();saved=copy.deepcopy((s,o));r.generate(s,o,('AV','0.3','random'));self.assertEqual((s,o),saved)
    def test_18_invalid_support_rejected(self):
        s,o=masks();s[1]=False
        with self.assertRaises(ValueError):r.generate(s,o,('A','0.3','front'))
    def test_19_text_observed_equality_rejected(self):
        s,o=masks();o['T'][0]=False
        with self.assertRaises(ValueError):r.generate(s,o,('A','0.3','front'))
    def test_20_full_generator_exhaustive_dual_masks(self):
        cases=0
        for length in range(1,6):
            for av in range(2**length):
                for vv in range(2**length):
                    a=[bool(av&(1<<t)) for t in range(length)];v=[bool(vv&(1<<t)) for t in range(length)]
                    s,o=masks(length,a,v)
                    for q in r.RATES:
                        z=r.generate(s,o,('AV',q,'middle'));width=z['width']
                        legal=[j for j in range(length-width+1) if width>0 and all(0<sum(o[m][j:j+width])<sum(o[m]) for m in 'AV')]
                        self.assertEqual(z['legal_starts'],legal)
                        if legal:
                            target=(length-width)//2;self.assertEqual(z['start'],min(legal,key=lambda j:(abs(j-target),j)))
                        else:self.assertEqual(z['A'],o)
                        cases+=1
        self.assertEqual(cases,5456)

class AggregationTests(unittest.TestCase):
    def test_21_fixed_classes_absent_class(self):
        z=r.metrics([2],[1.],[2],[1.]);self.assertEqual(z['macro_F1'],1/3);self.assertEqual([x['support'] for x in z['per_class']],[0,0,1])
    def test_22_strict_neutral(self):
        with self.assertRaises(ValueError):r.metrics([1],[1e-12],[1],[0.])
    def test_23_pearson_constant_target(self):self.assertEqual(r.pearson([1.,1.],[1.,2.]),(None,'zero_target_variance'))
    def test_24_pearson_constant_prediction(self):self.assertEqual(r.pearson([1.,2.],[1.,1.]),(None,'zero_prediction_variance'))
    def test_25_pearson_insufficient(self):self.assertEqual(r.pearson([1.],[1.]),(None,'insufficient_n'))
    def test_26_attempted_fallback_is_clean_prediction(self):
        z=r.attempted_report([0,2],[-1.,1.],[0,2],[-1.,1.],[2,None],[1.,None],[True,False],ordered_rows=[0,1],view_fingerprint='0'*64);self.assertEqual(z['attempted']['Accuracy'],.5);self.assertEqual(z['attempted']['MAE'],1.);self.assertEqual(z['coverage'],.5)
    def test_27_all_ineligible_no_deletion(self):
        z=r.attempted_report([0,2],[-1.,1.],[0,2],[-1.,1.],[None,None],[None,None],[False,False],ordered_rows=[0,1],view_fingerprint='0'*64);self.assertIsNone(z['eligible_only']);self.assertEqual(z['attempted']['n'],2)
    def test_28_random_replicates_no_extra_condition_weight(self):
        g=grid()
        for runs in g.values():
            for cid in runs:
                if cid.endswith('random'):runs[cid]=[rep_report(i,1.,0.) for i in range(3)]
                else:runs[cid]=[report(0.,0.)]
        self.assertEqual(r.aggregate(g)['across_seeds']['macro_F1'],.25)
    def test_29_replica_then_condition_then_seed(self):
        g=grid()
        for seed,runs in g.items():
            for cid in runs:runs[cid]=[rep_report(i,(seed%10)/10,1.) for i in range(len(runs[cid]))]
        self.assertAlmostEqual(r.aggregate(g)['across_seeds']['macro_F1'],(.7+.9+.3)/3)
    def test_30_wrong_replica_count_rejected(self):
        g=grid();g[17]['T:0.1:front']*=3
        with self.assertRaises(ValueError):r.aggregate(g)
    def test_31_missing_condition_rejected(self):
        g=grid();del g[17]['T:0.1:front']
        with self.assertRaises(ValueError):r.aggregate(g)
    def test_32_model_dependent_eligibility_rejected(self):
        g=grid();g[17]['T:0.1:front'][0]['eligible_count']=0
        with self.assertRaises(ValueError):r.aggregate(g)

class LossSelectionTests(unittest.TestCase):
    def test_33_joint_mae_numeric(self):self.assertAlmostEqual(r.joint_loss([0.,0.,0.],2.,0.),math.log(3)+2/3)
    def test_34_joint_huber_numeric(self):self.assertAlmostEqual(r.joint_loss([0.,0.,0.],2.,0.,kind='huber'),math.log(3)+.5)
    def test_35_ce_stability_large_logits(self):self.assertTrue(math.isfinite(r.joint_loss([1000.,-1000.,0.],1.,1.)))
    def test_36_reconstruction_nonempty_per_modality_dimension_mean(self):
        self.assertEqual(r.reconstruction_loss({'T':[[3.,5.]],'A':[[4.]]},{'T':[[1.,3.]],'A':[[0.]]},{'T':[True],'A':[True]},{'T':[True],'A':[True]}),3.)
    def test_37_actual_reconstruction_empty_supervision(self):
        self.assertEqual(r.reconstruction_loss({'A':[[float('nan')]]},{'A':[[float('inf')]]},{'A':[False]},{'A':[False]}),0.)
    def test_38_reconstruction_rejects_structural_unobserved_target(self):
        with self.assertRaises(ValueError):r.reconstruction_loss({'A':[[1.]]},{'A':[[0.]]},{'A':[False]},{'A':[True]})
    def test_39_reconstruction_active_nonfinite_rejected(self):
        with self.assertRaises(ValueError):r.reconstruction_loss({'A':[[float('nan')]]},{'A':[[0.]]},{'A':[True]},{'A':[True]})
    def test_40_checkpoint_earliest_exact_tie(self):self.assertEqual(r.choose_checkpoint([(.5,1.)]*12)['best_epoch'],1)
    def test_41_early_stopping_patience(self):self.assertEqual(r.choose_checkpoint([(.5,1.)]*12)['stop_epoch'],11)
    def test_42_tiny_improvement_saves_without_reset(self):
        z=r.choose_checkpoint([(.5,1.),(.50001,1.),(.50002,1.),(.50003,1.)],patience=2);self.assertEqual((z['best_epoch'],z['stop_epoch']),(3,3))
    def test_43_secondary_progress_resets_patience(self):
        z=r.choose_checkpoint([(.5,1.),(.5,.999),(.5,.999),(.5,.999)],patience=2);self.assertEqual((z['best_epoch'],z['stop_epoch']),(2,4))
    def test_44_config_clean_guard(self):
        cfg=[dict(id='bad',F=.9,MAE=.1,clean_F=.1,clean_MAE=1.,parameters=1),dict(id='ok',F=.6,MAE=.5,clean_F=.8,clean_MAE=.5,parameters=2)]
        self.assertEqual(r.rank_configs(cfg,dict(F=.8,MAE=.5))[0]['id'],'ok')
    def test_45_config_ties_parameter_then_id(self):
        cs=[dict(id=name,F=.5,MAE=.5,clean_F=.5,clean_MAE=.5,parameters=p) for name,p in [('z',2),('b',1),('a',1)]]
        self.assertEqual([c['id'] for c in r.rank_configs(cs)],['a','b','z'])
    def test_46_no_feasible_config_explicit_empty(self):
        cs=[dict(id='bad',F=.9,MAE=.1,clean_F=.1,clean_MAE=1.,parameters=1)];self.assertEqual(r.rank_configs(cs,dict(F=.8,MAE=.5)),[])
    def test_47_maximum_epochs(self):
        z=r.choose_checkpoint([(i/1000,1.) for i in range(120)])
        self.assertEqual((z['best_epoch'],z['evaluated_epochs']),(100,100))
    def test_48_attempted_population_must_not_change(self):
        g=grid()
        for seed in g:g[seed]['T:0.1:front'][0]['total_count']=3
        with self.assertRaises(ValueError):r.aggregate(g)

if __name__=='__main__':unittest.main()
