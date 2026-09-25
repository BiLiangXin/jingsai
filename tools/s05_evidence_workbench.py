"""Private A4 evidence cards from immutable predictions and prior source mapping."""
import argparse,csv,hashlib,html,json,pickle,re
from collections import Counter
from pathlib import Path
from transformers import AutoTokenizer

WORDS=re.compile(r"[a-z]+(?:'[a-z]+)*|[0-9]+")
def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1<<20),b''):h.update(part)
    return h.hexdigest()
def classify(token,position,support,offset,raw,special_ids):
    if not support:return 'PADDING'
    if token in special_ids:return 'SPECIAL_TOKEN_NO_DIRECT_WORD_SPAN'
    a,b=offset
    if a==b:return 'ZERO_LENGTH_OFFSET'
    piece=raw[a:b]
    if piece and not any(c.isalnum() for c in piece):return 'PUNCTUATION_NO_WORD_SPAN'
    if position==49:return 'POSSIBLE_TRUNCATION_EDGE'
    return 'TOKEN_WORD_SPAN_MISMATCH'
def main():
    parser=argparse.ArgumentParser()
    for key in ('csv','source','prior-map','tokenizer','output','q1-case'):parser.add_argument('--'+key,required=True)
    a=parser.parse_args();source=Path(a.source).resolve();out=Path(a.output)
    need(not out.exists(),'OUTPUT_EXISTS');need(sha(a.csv)=='9f1846d9ad4a1ab9d8a7d968503b87ff5e7f675b9b721855cc7c7eeccfcde3e0','FROZEN_A4_CSV')
    token=AutoTokenizer.from_pretrained(a.tokenizer,local_files_only=True,use_fast=True)
    need(token.unk_token_id==100 and sha(Path(a.tokenizer)/'vocab.txt')=='07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3','TOKENIZER_BINDING')
    rows=list(csv.DictReader(Path(a.csv).open(encoding='utf-8-sig',newline='')));need(len(rows)==20,'ROW_COUNT')
    cards=[];windows=[];count=Counter();groups={};prior_row_hashes=[]
    for ordinal,row in enumerate(rows):
        need(int(row['sample_index'])==ordinal and row['human_checked']=='false','OLD_ROW_ORDER_HUMAN')
        old_path=Path(a.prior_map)/f'row_{ordinal:02d}.json'
        old=json.loads(old_path.read_bytes());prior_row_hashes.append(sha(old_path))
        path=(source/row['source_file']).resolve()
        need(path.is_relative_to(source) and path.is_file() and sha(path)==old['source_sha256'],'SOURCE_BINDING')
        video=path.parent/'videos'/(path.stem+'.mp4')
        need(video.is_file() and sha(video)==old['video_sha256'],'VIDEO_BINDING')
        with path.open('rb') as stream:item=pickle.load(stream)
        need(type(item)==dict and 'raw_text' in item and 'text_bert' in item,'OFFICIAL_TEXT_FIELDS')
        raw=str(item['raw_text']);enc=token(raw,max_length=50,truncation=True,padding='max_length',return_offsets_mapping=True)
        stored=item['text_bert'];need(stored.shape==(3,50),'TOKEN_SHAPE')
        need(all(list(stored[i])==enc[key] for i,key in enumerate(('input_ids','attention_mask','token_type_ids'))),'TOKEN_REPLAY')
        word_spans=[m.span() for m in WORDS.finditer(raw.lower())]
        word_text=[raw[x:y] for x,y in word_spans]
        reasons=[]
        for target in ('class','reg'):
            main=row[target+'_main_modality'];need(main in ('text','audio','vision'),'MAIN_MODALITY')
            orig=json.loads(row[target+'_windows_json']);mapped=json.loads(row[target+'_mapped_windows_json']);need(len(orig)==len(mapped)==3,'WINDOW_COUNT')
            for rank,(w,m) in enumerate(zip(orig,mapped),1):
                lo,hi=w['feature_start'],w['feature_end_exclusive']
                need((lo,hi)==(m['token_start'],m['token_end_exclusive']) and 0<=lo<hi<=50,'WINDOW_BOUNDING')
                word_ids=m['word_indices'];need(all(0<=x<len(word_spans) for x in word_ids),'WORD_INDEX')
                text_spans=[{'word_index':x,'text':word_text[x],'char_start':word_spans[x][0],'char_end':word_spans[x][1]} for x in word_ids]
                unmapped=[]
                for pos in m['unmapped_token_positions']:
                    need(lo<=pos<hi,'UNMAPPED_BOUNDS')
                    reason=classify(int(stored[0,pos]),pos,int(stored[1,pos]),enc['offset_mapping'][pos],raw,set(token.all_special_ids))
                    unmapped.append({'position':pos,'token':token.convert_ids_to_tokens(int(stored[0,pos])),'reason':reason})
                    reasons.append(reason);count['unmapped_'+reason]+=1
                intervals=[]
                for it in m['intervals']:
                    start,end,pts=float(it['start']),float(it['end']),float(it['nearest_video_pts'])
                    need(old['audio_start_pts']-.02<=start<end<=old['audio_end_pts']+.02,'AUDIO_INTERVAL_BOUNDARY')
                    distance=abs(pts-(start+end)/2)
                    intervals.append({'start':start,'end':end,'word_indices':it['word_indices'],'nearest_actual_video_pts':pts,'pts_distance_from_word_midpoint':distance,'pts_quality':'NEAR_100MS' if distance<=.1 else 'DISTANT_GT_100MS'})
                    count['pts_near_100ms' if distance<=.1 else 'pts_far_gt_100ms']+=1
                quality=('ALIGNED_REFERENCE_TIME_ESTIMATE' if all(it['pts_quality']=='NEAR_100MS' for it in intervals) else 'REFERENCE_TIME_ESTIMATE_WITH_FRAME_GAP') if intervals else 'TEXT_SPAN_ONLY'
                windows.append({'ordinal':ordinal,'target':target,'main_modality':main,'rank':rank,'original':w,'mapped_text_spans':text_spans,'unmapped':unmapped,'intervals':intervals,'reference_quality':quality,'official_av_feature_production_timing':'UNKNOWN'})
                count['windows']+=1;count['text_located_windows']+=bool(text_spans);count['with_unmapped_token_windows']+=bool(unmapped);count['estimated_time_windows']+=bool(intervals)
        nontext=row['class_main_modality']!='text' or row['reg_main_modality']!='text'
        no_acoustic=row['mapping_quality']!='ESTIMATED_ACOUSTIC_ALIGNMENT'
        anomaly=bool(reasons)
        group=[g for g,v in [('NON_TEXT_PRIMARY',nontext),('NO_ACOUSTIC_ESTIMATE',no_acoustic),('UNMAPPED_TOKENS',anomaly)] if v]
        groups[ordinal]=group
        cards.append({'ordinal':ordinal,'source_file':row['source_file'],'sample_id':row['sample_id'],'polarity':row['polarity'],'intensity':row['intensity'],
            'class_main_modality':row['class_main_modality'],'reg_main_modality':row['reg_main_modality'],
            'class_phi':{m:row['class_phi_'+m] for m in ('T','A','V')},'reg_phi':{m:row['reg_phi_'+m] for m in ('T','A','V')},
            'mapping_quality':row['mapping_quality'],'original_text':raw,'video_uri':video.as_uri(),'source_video_sha256':old['video_sha256'],'prior_mapping_row_sha256':prior_row_hashes[-1],
            'priority_reasons':group,'windows':[w for w in windows if w['ordinal']==ordinal],
            'reviewer_role_code':'','reviewed_at':'','checked_scope':'','source_interval_checked':'','observed_issue':'','disposition':'','media_reference':'','correction_basis':'',
            'human_checked':False,'official_av_feature_production_timing':'UNKNOWN'})
        count['records']+=1;count['records_estimated_acoustic']+=not no_acoustic;count['records_text_only']+=no_acoustic
        count['class_main_'+row['class_main_modality']]+=1;count['reg_main_'+row['reg_main_modality']]+=1
    priority=sorted(range(20),key=lambda i:(0 if 'NON_TEXT_PRIMARY' in groups[i] else 1,0 if 'NO_ACOUSTIC_ESTIMATE' in groups[i] else 1,0 if 'UNMAPPED_TOKENS' in groups[i] else 1,i))
    priority_union={i for i in range(20) if groups[i]};count['priority_union']=len(priority_union)
    count['nontext_primary_union']=sum('NON_TEXT_PRIMARY' in g for g in groups.values())
    count['no_acoustic_union']=sum('NO_ACOUSTIC_ESTIMATE' in g for g in groups.values())
    count['unmapped_record_union']=sum('UNMAPPED_TOKENS' in g for g in groups.values())
    need(count['records']==20 and count['windows']==120 and count['text_located_windows']==120 and count['with_unmapped_token_windows']==39 and count['estimated_time_windows']==72,'HISTORICAL_AGGREGATE')
    out.mkdir(parents=True)
    (out/'EVIDENCE_COVERAGE.json').write_text(json.dumps({'cards':cards,'priority_order':priority,'counts':dict(count)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (out/'EVIDENCE_COVERAGE.csv').open('x',encoding='utf-8',newline='') as f:
        field=['ordinal','sample_id','polarity','intensity','class_main_modality','reg_main_modality','mapping_quality','priority_reasons','class_phi','reg_phi','windows_json','human_checked','reviewer_role_code','reviewed_at','checked_scope','source_interval_checked','observed_issue','disposition','media_reference','correction_basis']
        writer=csv.DictWriter(f,fieldnames=field);writer.writeheader()
        for card in cards:
            writer.writerow({k:(json.dumps(card['windows'],ensure_ascii=False) if k=='windows_json' else json.dumps(card[k],ensure_ascii=False) if isinstance(card.get(k),(dict,list)) else card.get(k,'')) for k in field})
    (out/'WINDOW_COVERAGE.json').write_text(json.dumps(windows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'COVERAGE_AGGREGATE.json').write_text(json.dumps({'status':'READY_FOR_TEAM_REVIEW','counts':dict(count),'shared_index':'SPECIFIED','token_to_word':'VERIFIED_WITH_REPLAY','word_to_audio':'ESTIMATED_FOR_12_RECORDS','nearby_video_pts':'MEASURED_FRAME_NEAR_ESTIMATE','official_av_feature_production_timing':'UNKNOWN','human_checked':0,'old_csv_sha256':sha(a.csv),'historical_mapping_row_hashes_sha256':hashlib.sha256(('\n'.join(prior_row_hashes)+'\n').encode()).hexdigest()},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    blocks=[]
    for i in priority:
        c=cards[i];whtml=[]
        for w in c['windows']:
            spans=', '.join(f"{html.escape(s['text'])} [{s['char_start']}:{s['char_end']}]" for s in w['mapped_text_spans'])
            times=', '.join(f"{x['start']:.3f}–{x['end']:.3f}s; frame PTS {x['nearest_actual_video_pts']:.3f}s; Δ{x['pts_distance_from_word_midpoint']:.3f}s ({x['pts_quality']})" for x in w['intervals']) or '无声学估计'
            unmap=', '.join(f"{u['position']}:{html.escape(u['token'])} ({u['reason']})" for u in w['unmapped']) or '无'
            whtml.append(f"<li>{w['target']} / 原主模态 {w['main_modality']} / 窗口#{w['rank']} / index {w['original']['feature_start']}–{w['original']['feature_end_exclusive']-1} / 原联合效应 {w['original']['signed_full_minus_deleted']:.5f}<br>文本: {spans}<br>未定位token: {unmap}<br>估计音轨与实际帧: {times}</li>")
        first_pts=next((it['nearest_actual_video_pts'] for w in c['windows'] for it in w['intervals']),None)
        media_src=c['video_uri']+(f'#t={first_pts:.3f}' if first_pts is not None else '')
        blocks.append(f"<section data-ordinal='{i}' data-sample-id='{html.escape(c['sample_id'],quote=True)}' data-source-video-sha256='{c['source_video_sha256']}'><h2>案例 {i+1:02d}　{html.escape(c['mapping_quality'])}</h2><p>优先原因：{', '.join(c['priority_reasons']) or '常规核验'}</p><p>样本键：{html.escape(c['sample_id'])}</p><p>预测：{c['polarity']} / {c['intensity']}；分类主模态：{c['class_main_modality']}，贡献 {html.escape(str(c['class_phi']))}；回归主模态：{c['reg_main_modality']}，贡献 {html.escape(str(c['reg_phi']))}</p><p>官方原文：{html.escape(c['original_text'])}</p><video controls preload='metadata' width='480' src='{html.escape(media_src,quote=True)}'></video><p>来源视频 SHA256：{c['source_video_sha256']}。播放器在有估计时从首个真实邻近PTS帧开始，需队员实际播放；官方音视频特征生产时间仍 UNKNOWN。</p><ol>{''.join(whtml)}</ol><label>审核角色代码 <input data-field='reviewer_role_code'></label><label>核验时间 <input data-field='reviewed_at' placeholder='填写实际时间'></label><label>实际查看范围 <input data-field='checked_scope'></label><label>是否实际检查源时段 <select data-field='source_interval_checked'><option value=''></option><option>YES</option><option>NO</option></select></label><label>发现问题 <textarea data-field='observed_issue'></textarea></label><label>结论 <select data-field='disposition'><option value=''></option><option>ACCEPTED</option><option>CORRECTED</option><option>UNRESOLVED</option></select></label><label>媒体引用 <input data-field='media_reference'></label><label>更正依据 <textarea data-field='correction_basis'></textarea></label></section>")
    template="""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>S05 附件4人工核验入口</title><style>body{font:16px/1.5 system-ui;margin:2rem auto;max-width:980px;background:#f4f6f9;color:#172134}section{background:#fff;margin:1.3rem 0;padding:1.4rem;border:1px solid #ccd4df;border-radius:12px}li{margin:1rem 0}label{display:block;margin:.5rem 0}input,textarea,select{display:block;width:95%;padding:.4rem}textarea{height:3.5rem}video{max-width:100%}</style><h1>附件4：20条逐条人工核验</h1><p>按非文本主模态、无声学估计、映射异常的并集优先排列，所有20条均保留。文本位置、声学估计与实际视频PTS不等于官方音视频特征精确时标。以下审核栏初始均为空；只有队员实际听看后填写并导出。</p><p><a href='EVIDENCE_COVERAGE.csv'>下载覆盖表</a>　<a href='Q1_REVIEW_ENTRY.html'>Q1典型案例入口</a></p><button onclick='exportReview()'>导出已填写的人工核验JSON</button>"""+''.join(blocks)+"""<script>function exportReview(){let out=[];document.querySelectorAll('section').forEach((s,i)=>{let v={priority_position:i+1,ordinal:Number(s.dataset.ordinal),sample_id:s.dataset.sampleId,source_video_sha256:s.dataset.sourceVideoSha256};s.querySelectorAll('[data-field]').forEach(x=>v[x.dataset.field]=x.value);if(v.reviewer_role_code||v.reviewed_at||v.checked_scope||v.observed_issue||v.disposition||v.media_reference||v.correction_basis)out.push(v)});let b=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});let a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='TEAM_REVIEW_FILLED.json';a.click();URL.revokeObjectURL(a.href)}</script></html>"""
    (out/'REVIEW_INDEX.html').write_text(template,encoding='utf-8')
    q1=Path(a.q1_case)
    need(q1.is_file(),'Q1_CASE_MISSING')
    (out/'Q1_REVIEW_ENTRY.html').write_text("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><h1>Q1典型案例人工入口</h1><p>已有100条特征、66条程序检查通过、34条异常；人工核验仍为0。请先打开原典型案例，实际播放音轨及帧，再记录词序、粗时间、异常和证据。不得将程序检查代签为人工。</p><p><a href='"+html.escape(q1.as_uri(),quote=True)+"'>打开已有典型案例工作页</a></p><label>审核角色代码 <input id='role'></label><label>实际核验时间 <input id='when'></label><label>核验范围 <input id='scope'></label><label>发现问题 <textarea id='issue'></textarea></label><label>结论 <select id='decision'><option value=''></option><option>ACCEPTED</option><option>CORRECTED</option><option>UNRESOLVED</option></select></label><label>媒体与更正依据 <textarea id='basis'></textarea></label><button onclick='save()'>导出人工记录</button><script>function save(){let x={reviewer_role_code:role.value,reviewed_at:when.value,checked_scope:scope.value,observed_issue:issue.value,disposition:decision.value,correction_basis:basis.value,case_source_sha256:'"+sha(q1)+"'};let b=new Blob([JSON.stringify(x,null,2)],{type:'application/json'});let a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='Q1_TEAM_REVIEW_FILLED.json';a.click();URL.revokeObjectURL(a.href)}</script></html>",encoding='utf-8')
    print(json.dumps({'status':'PASS','counts':dict(count),'review_index':str(out/'REVIEW_INDEX.html')},ensure_ascii=False))
if __name__=='__main__':main()
