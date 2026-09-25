import unittest
import torch
from mosei.s05.local import one_modality_window,explain_fixed

class Dummy:
    def __call__(self,x):
        t=x['features']['text'].sum((1,2));a=x['features']['audio'].sum((1,2));v=x['features']['vision'].sum((1,2))
        return {'logits':torch.stack((t+2*a+3*v,torch.zeros_like(t),-t-a-v),1),'regression':t-a+v}

def fixture(t=True,a=True,v=True):
    support=torch.tensor([[1,1,1,1,1,0]],dtype=torch.bool)
    active={'text':t,'audio':a,'vision':v}
    return {'support':support,'available':{m:support.clone() if yes else torch.zeros_like(support) for m,yes in active.items()},
            'features':{m:torch.arange(6,dtype=torch.float32).view(1,6,1).repeat(1,1,d) for m,d in [('text',2),('audio',1),('vision',1)]}}

class LocalS05Tests(unittest.TestCase):
    def test_only_one_modality_changes_and_masks_stay(self):
        x=fixture();y=one_modality_window(x,'audio',1)
        self.assertTrue(torch.equal(x['features']['text'],y['features']['text']))
        self.assertTrue(torch.equal(x['features']['vision'],y['features']['vision']))
        self.assertTrue(torch.equal(x['features']['audio'][:,1:4],torch.arange(1,4,dtype=torch.float32).view(1,3,1)))
        self.assertTrue(torch.equal(y['features']['audio'][:,1:4],torch.zeros(1,3,1)))
        self.assertTrue(torch.equal(x['support'],y['support']))
        for m in x['available']:self.assertTrue(torch.equal(x['available'][m],y['available'][m]))

    def test_fixed_target_and_nonoverlap(self):
        x=fixture();full=Dummy()(x);r=explain_fixed(Dummy(),x)
        self.assertEqual(r['predicted_class_index'],int(full['logits'][0].argmax()))
        self.assertEqual(r['full_class_logit'],float(full['logits'][0,r['predicted_class_index']]))
        for m in ('text','audio','vision'):
            for key in ('class','reg'):
                windows=r['modalities'][m][key]['windows'];self.assertLessEqual(len(windows),3)
                for i,w in enumerate(windows):
                    self.assertEqual(w['feature_end_exclusive']-w['feature_start'],3)
                    for q in windows[i+1:]:self.assertTrue({*range(w['feature_start'],w['feature_end_exclusive'])}.isdisjoint(range(q['feature_start'],q['feature_end_exclusive'])))

    def test_empty_modality_and_zero_effect(self):
        x=fixture(a=False);r=explain_fixed(Dummy(),x)
        self.assertEqual(r['modalities']['audio']['class']['status'],'NO_AVAILABLE_CONTENT_EFFECT')
        z=fixture();z['features']['vision'].zero_();r=explain_fixed(Dummy(),z)
        self.assertEqual(r['modalities']['vision']['reg']['status'],'ZERO_EFFECT')

    def test_reject_invalid_window(self):
        x=fixture()
        for start in (-1,3):
            with self.assertRaises(ValueError):one_modality_window(x,'text',start)

if __name__=='__main__':unittest.main()
