import unittest
import torch
from mosei.s01.contracts import synthetic_batch,MODS
from mosei.s01.normalization import Normalizer
from mosei.s03.core import adapter,coalition,shapley,content_window,mapped_interval,disjoint_top,paired_random

class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.b=synthetic_batch(6,17);self.n=Normalizer('zscore').fit([self.b],split='train')
    def test_clean_v0_matches_frozen_normalizer(self):
        a=adapter(self.b.features,self.b.support,self.n,'V0');b=self.n.transform(self.b)
        for m in MODS:
            self.assertTrue(torch.equal(a['available'][m],b.observed[m]))
            self.assertTrue(torch.equal(a['features'][m][b.observed[m]],b.features[m][b.observed[m]]))
    def test_proxy_before_normalization_and_no_truth(self):
        v={m:x.clone() for m,x in self.b.features.items()}
        v['text'][:,0]=0
        a=adapter(v,self.b.support,self.n,'V1');b=adapter(v,self.b.support,self.n,'V0')
        self.assertFalse(a['available']['text'][:,0].any())
        self.assertTrue(b['available']['text'][:,0].all())
        with self.assertRaises(TypeError):adapter(v,self.b.support,self.n,'V1',corruption={})
        with self.assertRaises(ValueError):adapter({**v,'label':torch.zeros(6)},self.b.support,self.n,'V1')
    def test_padding_and_zero_variance(self):
        for m in MODS:self.n.statistics[m]['std']=[0]*len(self.n.statistics[m]['std'])
        a=adapter(self.b.features,self.b.support,self.n,'V1')
        for m in MODS:
            self.assertFalse((a['available'][m]&~self.b.support).any())
            self.assertTrue(torch.isfinite(a['features'][m]).all())
    def test_coalition_keeps_masks(self):
        a=self.n.transform(self.b).inputs()
        for bits in range(8):
            c=coalition(a,bits)
            self.assertIs(c['available'],a['available']);self.assertIs(c['support'],a['support'])
            for i,m in enumerate(MODS):self.assertTrue(torch.equal(c['features'][m],a['features'][m] if bits&(1<<i) else torch.zeros_like(a['features'][m])))
    def test_exact_additive_and_interaction_shapley(self):
        v=torch.tensor([[sum([2,3,7][i] for i in range(3) if bits&(1<<i))+6*int(bits==7)] for bits in range(8)],dtype=torch.float64).unsqueeze(-1)
        p=shapley(v);self.assertTrue(torch.allclose(p[0,:,0],torch.tensor([4,5,9],dtype=torch.float64)))
        self.assertTrue(torch.allclose(p.sum(1),v[7]-v[0]))
    def test_zero_effect(self):self.assertEqual(shapley(torch.ones(8,2,2)).abs().sum().item(),0)
    def test_windows_preserve_inactive_and_masks(self):
        a=self.n.transform(self.b).inputs();r=content_window(a,[0,1,2])
        self.assertIs(r['available'],a['available'])
        for m in MODS:
            self.assertTrue(torch.equal(a['features'][m][:,3:],r['features'][m][:,3:]))
            self.assertFalse(r['features'][m][:,:3][a['available'][m][:,:3]].any())
    def test_unverified_mapping_never_invents_time(self):
        self.assertIsNone(mapped_interval(0,3)['timestamp'])
        with self.assertRaises(ValueError):mapped_interval(0,3,{'verified_official_correspondence':False})
    def test_disjoint_and_equal_length_random(self):
        import random
        self.assertEqual(disjoint_top([3,3,2,1,5,4,2]),[4,0])
        for n in range(3,51):
            for k in range(1,min(n//3,3)+1):
                starts=paired_random(n,k,random.Random(3103))
                positions=[i for s in starts for i in range(s,s+3)]
                self.assertEqual(len(positions),len(set(positions)));self.assertTrue(max(positions)<n)

if __name__=='__main__':unittest.main()
