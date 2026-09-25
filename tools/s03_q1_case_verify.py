"""Repair a missing preview asset without recomputing features or alignments."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
import numpy as np
import cv2,imageio_ffmpeg
from s03_q1 import vision_features,guard
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--q1',required=True);p.add_argument('--alignment',required=True);p.add_argument('--report',required=True);a=p.parse_args();guard()
 q=Path(a.q1);page=Path(a.alignment)/'ALIGNMENT_CASE.html'
 match=re.search(r'src="../q1/(\d{3})/frame.png"',page.read_text(encoding='utf-8'));need(match is not None,'Case image binding')
 folder=q/match.group(1);trace=json.loads((folder/'trace.json').read_bytes());source=(Path(a.source)/trace['video_relative']).resolve()
 need(source.is_relative_to(Path(a.source).resolve()) and sha(source)==trace['video_sha256'],'Original Q1 source binding')
 need(not (folder/'frame.png').exists(),'Do not overwrite preview')
 cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','info','-copyts','-i',str(source),'-map','0:v:0','-an','-vf','scale=64:64,showinfo','-frames:v','1','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
 run=subprocess.run(cmd,capture_output=True);need(run.returncode==0 and len(run.stdout)==64*64*3,'Actual frame extraction')
 frame=np.frombuffer(run.stdout,np.uint8).reshape(64,64,3)
 with np.load(folder/'features.npz',allow_pickle=False) as data:
  error=float(np.max(np.abs(vision_features(frame)-data['vision'][0])))
  pts=float(re.findall(r'pts_time:([-+\d.eE]+)',run.stderr.decode(errors='replace'))[0])
  need(error==0 and abs(pts-float(data['video_pts'][0]))<1e-6,'Saved first-frame descriptor/PTS mismatch')
 ok,encoded=cv2.imencode('.png',cv2.cvtColor(frame,cv2.COLOR_RGB2BGR));need(ok,'PNG encoder')
 (folder/'frame.png').write_bytes(encoded.tobytes())
 decoded=cv2.imdecode(np.frombuffer((folder/'frame.png').read_bytes(),np.uint8),cv2.IMREAD_COLOR)
 need(np.array_equal(decoded,cv2.cvtColor(frame,cv2.COLOR_RGB2BGR)),'PNG round trip')
 result=dict(status='PASS',failure_found='cv2.imwrite to Unicode path silently returned false; preview asset absent',repair='imencode plus pathlib byte write',case_assets_exist=True,descriptor_max_abs_error=error,original_features_unchanged=sha(folder/'features.npz')==trace['features_sha256'],audio_exists=(folder/'audio.wav').is_file(),frame_sha256=sha(folder/'frame.png'),human_word_alignment_verified=0,official_time_mapping='UNVERIFIED',special_sources_opened=False)
 Path(a.report).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()

