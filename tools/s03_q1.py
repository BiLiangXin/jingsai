"""Q1 local feature/forced-alignment extraction. Private sample data only."""
import argparse,csv,datetime,hashlib,html,json,re,subprocess,sys,wave
from pathlib import Path
import numpy as np
from scipy.fft import dct
import cv2,openpyxl,pocketsphinx,imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
def guard():
    c=json.loads((ROOT/'configs/s03_execution.json').read_bytes())
    if c['status']!='ACTIVE_AUTHORIZED' or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(c['compute_deadline']):raise RuntimeError('S03 closed/deadline')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def tokenize(text):return re.findall(r"[a-z]+(?:'[a-z]+)*|[0-9]+",text.lower())
def text_features(words):
    x=np.zeros((len(words),128),np.float32)
    for i,w in enumerate(words):
        h=hashlib.sha256(w.encode()).digest();x[i,int.from_bytes(h[:4],'little')%128]=1 if h[4]%2 else -1
    return x
def audio_features(y):
    if len(y)<400:raise ValueError('Audio shorter than25ms')
    frames=np.lib.stride_tricks.sliding_window_view(y,400)[::160].copy()
    power=np.abs(np.fft.rfft(frames*np.hanning(400),512))**2
    mel=lambda hz:2595*np.log10(1+hz/700)
    hz=700*(10**(np.linspace(mel(0),mel(8000),28)/2595)-1);freq=np.fft.rfftfreq(512,1/16000)
    filters=np.stack([np.maximum(0,np.minimum((freq-hz[i])/(hz[i+1]-hz[i]),(hz[i+2]-freq)/(hz[i+2]-hz[i+1]))) for i in range(26)])
    mfcc=dct(np.log(np.maximum(power@filters.T,1e-12)),type=2,norm='ortho',axis=1)[:,:13]
    rms=np.log(np.sqrt(np.mean(frames**2,axis=1))+1e-12)
    zcr=np.mean(np.diff(np.signbit(frames),axis=1),axis=1)
    cent=(power*freq).sum(1)/np.maximum(power.sum(1),1e-12)
    return np.column_stack([mfcc,rms,zcr,cent]).astype(np.float32)
def vision_features(frame):
    rgb=frame.astype(np.float32)/255;hsv=cv2.cvtColor(frame,cv2.COLOR_RGB2HSV)
    hist=np.concatenate([np.histogram(hsv[:,:,i],bins=8,range=(0,180 if i==0 else 256))[0]/4096 for i in range(3)])
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);dx=cv2.Sobel(gray,cv2.CV_32F,1,0);dy=cv2.Sobel(gray,cv2.CV_32F,0,1)
    mag=np.hypot(dx,dy);angle=np.mod(np.arctan2(dy,dx),np.pi)
    hog=np.histogram(angle,bins=9,range=(0,np.pi),weights=mag)[0];hog=hog/max(float(hog.sum()),1e-12)
    return np.concatenate([rgb.mean((0,1)),rgb.std((0,1)),hist,hog]).astype(np.float32)
def ffmpeg(args,log):
    guard();r=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-hide_banner',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
    log.write_bytes(r.stderr)
    if r.returncode:raise RuntimeError('FFmpeg failed; private log retained')
    return r.stdout,r.stderr.decode('utf-8',errors='replace')
def align_pcm(pcm,words,offset,continuous,at,vt,model):
    segments=[];status='UNALIGNED';reason=None
    try:
        dec=pocketsphinx.Decoder(hmm=str(model/'en-us/en-us'),dict=str(model/'en-us/cmudict-en-us.dict'),lm=None,samprate=16000,loglevel='ERROR')
        if not words:raise ValueError('NO_TOKENS')
        if not continuous:raise ValueError('AUDIO_PTS_DISCONTINUITY')
        if any(dec.lookup_word(w) is None for w in words):raise ValueError('DICTIONARY_OOV')
        dec.set_align_text(' '.join(words));dec.start_utt();dec.process_raw(pcm,full_utt=True);dec.end_utt()
        pieces=[s for s in dec.seg() if s.word not in ['<sil>','<s>','</s>','[SPEECH]','[NOISE]']]
        canonical=lambda w:re.sub(r'\(\d+\)$','',w)
        if [canonical(s.word) for s in pieces]!=words:raise ValueError('TOKEN_SEQUENCE_MISMATCH')
        for i,s in enumerate(pieces):
            start=offset+s.start_frame/100;end=offset+(s.end_frame+1)/100
            if end<=start or start<offset-.011 or end>offset+len(pcm)/32000+.02:raise ValueError('INVALID_WORD_BOUNDS')
            if segments and start<segments[-1]['end']:raise ValueError('NONMONOTONIC_WORDS')
            ai=np.flatnonzero((at<end)&(at+.025>start)).tolist();vi=int(np.argmin(np.abs(vt-(start+end)/2)))
            segments.append(dict(token_index=i,word=words[i],start=start,end=end,audio_feature_indices=ai,video_feature_index=vi,video_pts=float(vt[vi])))
        status='COMPUTED_TEMPORAL_CHECKS_PASS'
    except (ValueError,RuntimeError,TypeError) as e:reason=str(e);segments=[]
    return dict(status=status,reason=reason,words=segments)

def extract(video,folder,words,model):
    pcm,log=ffmpeg(['-copyts','-i',str(video),'-map','0:a:0','-vn','-af','aresample=16000,ashowinfo','-ac','1','-ar','16000','-f','s16le','pipe:1'],folder/'audio_decode.log')
    # ashowinfo samples follow aresample; output downmix preserves sample counts.
    events=[(float(t),int(n)) for t,n in re.findall(r'pts_time:([-+\d.eE]+).*?nb_samples:(\d+)',log)]
    if not events:raise ValueError('No audio PTS evidence')
    offset=events[0][0];continuous=all(abs(t-(prev+n/16000))<.002 for (prev,n),(t,_) in zip(events,events[1:]))
    y=np.frombuffer(pcm,dtype='<i2').astype(np.float64)/32768
    with wave.open(str(folder/'audio.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm)
    af=audio_features(y);at=offset+np.arange(len(af))*.01
    raw,vlog=ffmpeg(['-copyts','-i',str(video),'-map','0:v:0','-an','-vf',"select='isnan(prev_selected_t)+gte(t-prev_selected_t,0.2)',scale=64:64,showinfo",'-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],folder/'video_decode.log')
    vt=np.array([float(v) for v in re.findall(r'pts_time:([-+\d.eE]+)',vlog)])
    frames=np.frombuffer(raw,np.uint8).reshape(-1,64,64,3)
    if not len(frames) or len(frames)!=len(vt) or np.any(np.diff(vt)<=0):raise ValueError('Video PTS/frame mismatch')
    vf=np.stack([vision_features(f) for f in frames]);cv2.imwrite(str(folder/'frame.png'),cv2.cvtColor(frames[0],cv2.COLOR_RGB2BGR))
    quality=[]
    if not continuous:quality.append('AUDIO_PTS_DISCONTINUITY')
    if np.max(np.abs(y))<1e-4:quality.append('NEAR_SILENCE')
    alignment=align_pcm(pcm,words,offset,continuous,at,vt,model)
    return dict(text=text_features(words),audio=af,vision=vf,audio_pts=at,video_pts=vt),dict(**alignment,audio_start=offset,audio_end=offset+len(y)/16000,audio_contiguous=continuous,quality=quality,manual_word_accuracy='UNKNOWN')
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--acoustic-model',required=True);a=p.parse_args();source=Path(a.source);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    if (out/'SUMMARY.json').exists():raise RuntimeError('Existing terminal Q1 output; verify instead of overwrite')
    books=list(source.glob('*.xlsx'))
    if len(books)!=1:raise ValueError('Expected one official workbook')
    wb=openpyxl.load_workbook(books[0],read_only=True,data_only=True);rows=list(wb.active.values);header=[str(v).lower().strip() for v in rows[0]]
    records=[dict(zip(header,r)) for r in rows[1:] if any(v is not None for v in r)]
    if len(records)!=100:raise ValueError('Expected exactly100 official rows')
    videos=list(source.rglob('*.mp4'));summary=[];example=None
    for i,row in enumerate(records):
        guard();folder=out/f'{i:03d}';folder.mkdir(exist_ok=False);save(folder/'official_row.json',row)
        text=str(row['text']);words=tokenize(text);vid=str(row['video_id']);clip=str(row['clip_id']);clip=clip[:-2] if clip.endswith('.0') else clip
        matches=[v for v in videos if v.parent.name==vid and v.stem==clip]
        trace=dict(row=i,status='FAILED',word_alignment='UNALIGNED',reason=None,text_tokens=len(words),feature_file=None)
        try:
            if len(matches)!=1:raise ValueError('ROW_TO_VIDEO_MAPPING_NOT_UNIQUE')
            video=matches[0];features,align=extract(video,folder,words,Path(a.acoustic_model))
            # Non-ASCII letters prevent claiming reliable English word alignment.
            if any(c.isalpha() and not c.isascii() for c in text):align.update(status='UNALIGNED',reason='NON_ASCII_TRANSCRIPT',words=[])
            np.savez_compressed(folder/'features.npz',**features);save(folder/'alignment.json',align)
            trace.update(status='EXTRACTED',word_alignment=align['status'],reason=align['reason'],feature_file=f'{i:03d}/features.npz',video_relative=video.relative_to(source).as_posix(),video_sha256=sha(video),features_sha256=sha(folder/'features.npz'),duration=align['audio_end']-align['audio_start'],audio_frames=len(features['audio']),video_frames=len(features['vision']),text_dim=128,audio_dim=16,vision_dim=39,quality=';'.join(align['quality']))
            if example is None and align['status']=='COMPUTED_TEMPORAL_CHECKS_PASS':example=i
        except Exception as e:
            trace['reason']=type(e).__name__+': '+str(e)
        save(folder/'trace.json',trace);summary.append(trace)
        print(json.dumps({'processed':i+1,'extracted':sum(r['status']=='EXTRACTED' for r in summary),'computed_alignments':sum(r['word_alignment']=='COMPUTED_TEMPORAL_CHECKS_PASS' for r in summary)}),flush=True) if (i+1)%10==0 else None
    keys=list(dict.fromkeys(k for r in summary for k in r))
    with (out/'TRACE_100.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,keys);w.writeheader();w.writerows(summary)
    if example is not None:
        folder=out/f'{example:03d}';align=json.loads((folder/'alignment.json').read_bytes())
        body=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r['token_index'],r['word'],r['start'],r['end'],r['video_pts']])+'</tr>' for r in align['words'])
        page=f'<!doctype html><meta charset="utf-8"><title>Q1 acoustic alignment evidence</title><h1>Computed forced alignment, not manually verified ground truth</h1><audio controls src="{example:03d}/audio.wav"></audio><img src="{example:03d}/frame.png"><table><tr><th>index</th><th>word</th><th>start PTS</th><th>end PTS</th><th>nearest video PTS</th></tr>{body}</table>'
        (out/'ALIGNMENT_CASE.html').write_text(page,encoding='utf-8')
    result=dict(status='COMPLETED' if all(r['status']=='EXTRACTED' for r in summary) else 'PARTIAL',sample_count=100,extracted=sum(r['status']=='EXTRACTED' for r in summary),computed_temporal_checks_pass=sum(r['word_alignment']=='COMPUTED_TEMPORAL_CHECKS_PASS' for r in summary),human_verified_word_alignments=0,failures={reason:sum(r['reason']==reason for r in summary) for reason in sorted(set(r['reason'] for r in summary if r['reason']))},example_available=example is not None,official_workbook_sha256=sha(books[0]),trace_sha256=sha(out/'TRACE_100.csv'),dimensions={'text':128,'audio':16,'vision':39},official_Q3_mapping='UNVERIFIED')
    save(out/'SUMMARY.json',result);save(ROOT/'reports/s03_readiness/Q1_SUMMARY.json',result);print(json.dumps(result))
if __name__=='__main__':main()
