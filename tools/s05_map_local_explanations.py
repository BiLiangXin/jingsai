"""Map fixed new per-modality windows onto verified text and estimated media time."""
import argparse,csv,hashlib,json,pickle,re,subprocess,sys
from collections import Counter
from pathlib import Path
import numpy as np
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from s04_clarified_map import WORDS,PTS,token_word_indices,window_mapping

def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def video_pts(ffmpeg,path):
    p=subprocess.run([str(ffmpeg),'-nostdin','-hide_banner','-loglevel','info','-copyts','-i',str(path),'-map','0:v:0','-an','-vf','showinfo','-f','null','-'],capture_output=True,timeout=60)
    need(p.returncode==0,'VIDEO_PTS_DECODE')
    out=np.asarray([float(x) for x in PTS.findall(p.stderr.decode('utf-8','replace'))],dtype=np.float64)
    need(len(out)>0 and np.all(np.diff(out)>0),'VIDEO_PTS_ORDER')
    return out
def main():
    p=argparse.ArgumentParser()
    for name in ('source','old-map','supplement','tokenizer','ffmpeg','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();out=Path(a.output);need(not out.exists(),'OUTPUT_EXISTS')
    sup=Path(a.supplement);need(sha(sup)=='e3279098f24317f7f0bf34bc67a8d01ed9ecdc4c85415b710897a2ae264324bd','SUPPLEMENT_BINDING')
    rows=list(csv.DictReader(sup.open(encoding='utf-8',newline='')));need(len(rows)==20,'ROW_COUNT')
    tokenizer=AutoTokenizer.from_pretrained(a.tokenizer,local_files_only=True,use_fast=True)
    need(sha(Path(a.tokenizer)/'vocab.txt')=='07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3','TOKENIZER_BINDING')
    source=Path(a.source).resolve();counter=Counter();mapped=[]
    for i,row in enumerate(rows):
        need(int(row['sample_index'])==i,'ROW_ORDER')
        prior=json.loads((Path(a.old_map)/f'row_{i:02d}.json').read_bytes())
        path=(source/row['source_file']).resolve();need(path.is_relative_to(source) and sha(path)==prior['source_sha256'],'SOURCE_BINDING')
        video=path.parent/'videos'/(path.stem+'.mp4');need(sha(video)==prior['video_sha256'],'VIDEO_BINDING')
        with path.open('rb') as f:item=pickle.load(f)
        raw=str(item['raw_text']);enc=tokenizer(raw,max_length=50,truncation=True,padding='max_length',return_offsets_mapping=True)
        need(all(list(item['text_bert'][j])==enc[key] for j,key in enumerate(('input_ids','attention_mask','token_type_ids'))),'TOKEN_REPLAY')
        spans=[m.span() for m in WORDS.finditer(raw.lower())]
        token_to_word=token_word_indices(enc['offset_mapping'],enc['attention_mask'],spans)
        times=[(float(w['start']),float(w['end'])) for w in prior['words']] if prior['words'] else None
        if times is not None:need(len(times)==len(spans),'WORD_TIME_LENGTH')
        pts=video_pts(a.ffmpeg,video);need(len(pts)==prior['video_pts_count'],'VIDEO_PTS_COUNT_CHANGED')
        addition=dict(row)
        for target in ('class','reg'):
            src=json.loads(row[target+'_per_modality_v1_json']);result={}
            for modality in ('text','audio','vision'):
                entry=src[modality];cards=[]
                for w in entry['windows']:
                    mapping=window_mapping(w,token_to_word,times,pts)
                    mapping['original_single_modality_effect']=w['signed_full_minus_single_modality_deleted']
                    mapping['feature_modality']=modality
                    mapping['text_char_spans']=[{'start':spans[j][0],'end':spans[j][1]} for j in mapping['word_indices']]
                    distances=[abs(t['nearest_video_pts']-(t['start']+t['end'])/2) for t in mapping['intervals']]
                    mapping['reference_status']='ALIGNED_REFERENCE_TIME_ESTIMATE' if distances and max(distances)<=.1 else 'REFERENCE_TIME_FRAME_GAP' if distances else 'TEXT_SPAN_ONLY'
                    mapping['official_av_feature_production_timing']='UNKNOWN'
                    counter[target+'_'+modality+'_'+mapping['reference_status']]+=1
                    cards.append(mapping)
                result[modality]={'status':entry['status'],'windows':cards}
            addition[target+'_per_modality_mapped_v1_json']=json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        mapped.append(addition)
    out.mkdir(parents=True)
    csv_path=out/'attachment4_predictions_explanations_WITH_LOCAL_MAPPED_PRIVATE.csv'
    with csv_path.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(mapped[0]));writer.writeheader();writer.writerows(mapped)
    check=list(csv.DictReader(csv_path.open(encoding='utf-8',newline='')))
    need(len(check)==20 and all(all(check[i][k]==v for k,v in row.items()) for i,row in enumerate(rows)),'SUPPLEMENT_CHANGED')
    report={'status':'PASS','rows':20,'old_original_and_supplement_columns_unchanged':True,'input_supplement_sha256':sha(sup),'mapped_csv_sha256':sha(csv_path),'quality_counts':dict(counter),'official_av_feature_production_timing':'UNKNOWN','human_checked':0}
    (out/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
