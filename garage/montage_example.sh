#!/usr/bin/env bash
# مثال مونتاج بلقطات حقيقية (4K مباشرة): هوك + 3 خطوات + النتيجة + لوحة الكراج + كرت النهاية.
# يتوقع مجلد clips/ فيه المقاطع الخام (IMG_6158 و IMG_5812 و IMG_6150 و IMG_6155 و IMG_5824 .mov) ومجلد ec/ من garage/endcard.py.
# غيّر أسماء المقاطع ومددها بالأمر الأول من ffmpeg، والباقي يبقى.
set -euo pipefail
C=clips; EC=ec; K=2
FB=/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf
FS=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
RED=0xE5091A
T() { echo "drawtext=fontfile=$8:text='$1':fontsize=$(( $6*K )):fontcolor=$7:borderw=$(( 5*K )):bordercolor=black@0.85:x=(w-text_w)/2:y=$(( $5*K )):alpha='min(1,max(0,(t-$2)/0.2))':enable='between(t,$2,$3)'"; }
# clip: ss duration
cl() { # idx drift_dur
  echo "[$1:v]fps=30,scale=$((1166*K)):-2,crop=$((1080*K)):$((1920*K)):'(iw-ow)*t/$2':'(ih-oh)/2',eq=contrast=1.08:saturation=1.12,vignette=PI/5,setsar=1,format=yuv420p[c$1]"
}
ffmpeg -y -hide_banner -loglevel error \
 -ss 0   -t 2.6  -i $C/IMG_6158.mov \
 -ss 2.6 -t 2.95 -i $C/IMG_6158.mov \
 -ss 2.0 -t 3.35 -i $C/IMG_5812.mov \
 -ss 1.0 -t 3.35 -i $C/IMG_6150.mov \
 -ss 8.0 -t 3.35 -i $C/IMG_6155.mov \
 -ss 2.5 -t 2.85 -i $C/IMG_5824.mov \
 -filter_complex "
$(cl 0 2.6);$(cl 1 2.95);$(cl 2 3.35);$(cl 3 3.35);$(cl 4 3.35);$(cl 5 2.85);
[c0][c1]xfade=transition=fade:duration=0.25:offset=2.275[x1];
[x1][c2]xfade=transition=fade:duration=0.25:offset=4.875[x2];
[x2][c3]xfade=transition=fade:duration=0.25:offset=7.875[x3];
[x3][c4]xfade=transition=fade:duration=0.25:offset=10.875[x4];
[x4][c5]xfade=transition=fade:duration=0.25:offset=13.875[base];
[base]$(T 'THEY SAID IT' 0.2 2.3 0 1000 70 white $FS),$(T "COULDN’T BE" 0.35 2.3 0 1080 70 white $FS),$(T 'REPAIRED.' 0.5 2.3 0 1150 150 $RED $FB),$(T 'STEP 1' 2.6 4.9 0 1030 60 white $FS),$(T 'INSPECT' 2.7 4.9 0 1100 190 $RED $FB),$(T 'STEP 2' 5.2 7.9 0 1030 60 white $FS),$(T 'REPAIR' 5.3 7.9 0 1100 190 $RED $FB),$(T 'STEP 3' 8.2 10.9 0 1030 60 white $FS),$(T 'PAINT' 8.3 10.9 0 1100 190 $RED $FB),$(T 'THE RESULT' 11.2 13.9 0 1030 60 white $FS),$(T 'DONE RIGHT.' 11.3 13.9 0 1100 150 $RED $FB),$(T 'ONE SIGN.' 14.3 16.6 0 700 90 white $FS),$(T 'ONE GARAGE.' 14.45 16.6 0 820 105 $RED $FB)[v]" \
 -map "[v]" -t 16.6 -an -c:v libx264 -preset fast -crf 17 -pix_fmt yuv420p main_m.mp4
CUT=16.6; TOTAL=20; LE=$(python3 -c "print(round($TOTAL-$CUT+0.3,3))"); OFF=$(python3 -c "print(round($CUT-0.3,3))")
L() { echo "[$1:v]scale=2160:3840:flags=lanczos,format=rgba,fade=t=in:st=$2:d=0.35:alpha=1[l$1]"; }
ffmpeg -y -hide_banner -loglevel error -i main_m.mp4 -ss 8 -t $LE -i $C/IMG_6155.mov \
 -loop 1 -framerate 30 -t $LE -i $EC/ec_logo.png -loop 1 -framerate 30 -t $LE -i $EC/ec_head.png -loop 1 -framerate 30 -t $LE -i $EC/ec_sub.png \
 -loop 1 -framerate 30 -t $LE -i $EC/ec_line.png -loop 1 -framerate 30 -t $LE -i $EC/ec_phone.png -loop 1 -framerate 30 -t $LE -i $EC/ec_addr.png -loop 1 -framerate 30 -t $LE -i $EC/ec_handle.png \
 -filter_complex "
[0:v]trim=duration=$CUT,setpts=PTS-STARTPTS,fps=30,format=yuv420p,setsar=1[m];
[1:v]fps=30,scale=2160:3840,gblur=sigma=60,eq=brightness=-0.15:saturation=0.85,vignette=PI/4,trim=duration=$LE,setpts=PTS-STARTPTS,format=yuv420p[bg];
$(L 2 0.35);$(L 3 0.8);$(L 4 1.0);$(L 5 1.15);$(L 6 1.35);$(L 7 1.6);$(L 8 1.85);
[bg][l2]overlay=y='if(lt(t,0.8),-180*(1-(t-0.35)/0.45),0)'[e1];
[e1][l3]overlay=y='if(lt(t,1.15),100*(1-(t-0.8)/0.35),0)'[e2];
[e2][l4]overlay=y='if(lt(t,1.35),100*(1-(t-1.0)/0.35),0)'[e3];
[e3][l5]overlay=y='if(lt(t,1.5),100*(1-(t-1.15)/0.35),0)'[e4];
[e4][l6]overlay=y='if(lt(t,1.7),100*(1-(t-1.35)/0.35),0)'[e5];
[e5][l7]overlay=y='if(lt(t,1.95),100*(1-(t-1.6)/0.35),0)'[e6];
[e6][l8]overlay=y='if(lt(t,2.2),100*(1-(t-1.85)/0.35),0)',format=yuv420p[e];
[m][e]xfade=transition=fade:duration=0.3:offset=$OFF,format=yuv420p[v]" \
 -map "[v]" -t $TOTAL -an -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart montage_4k.mp4
