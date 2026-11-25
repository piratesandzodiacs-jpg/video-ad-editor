#!/usr/bin/env bash
# قالب ريل الخدمات المعتمد (15 ثانية، 9:16، بدون صوت، انتقالات ناعمة، كرت نهاية المستخدم).
#
# الاستخدام:
#   IMG=صورة.jpg EC=مجلد_طبقات_النهاية OUT=out.mp4 bash garage/services_reel.sh
#   (طبقات النهاية من: python3 garage/endcard.py --out $EC --logo ... --phone ... --address ...)
# المتغيرات:
#   IMG  صورة اللوحة أو أي صورة عريضة (اللقطات تتحرك عليها بالقص)
#   EC   مجلد فيه ec_logo/ec_head/ec_sub/ec_line/ec_phone/ec_addr/ec_handle .png
#   OUT  ملف الخرج (1080x1920). لـ4K: ffmpeg -i OUT -vf "scale=2160:3840:flags=lanczos,unsharp=5:5:0.6" ...
#   HOOK1/HOOK2 نص الهوك، و SERVICES أربع كلمات مفصولة بمسافة
set -euo pipefail
: "${IMG:?IMG}" "${EC:?EC}" "${OUT:?OUT}"
HOOK1=${HOOK1:-BREAKDOWN?}; HOOK2=${HOOK2:-WE FIX IT.}
read -r S1 S2 S3 S4 <<<"${SERVICES:-ELECTRICAL RADIATOR AXLES BRAKES}"
FB=/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf
FS=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
RED=0xE5091A
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
G="eq=contrast=1.15:saturation=1.25:brightness='-0.03+0.03*sin(37*t)':eval=frame,colorbalance=rs=.18:rm=.12:bs=-.12,vignette=PI/4,setsar=1,fps=30,format=yuv420p"
T() { echo "drawtext=fontfile=$8:text='$1':fontsize=$6:fontcolor=$7:borderw=5:bordercolor=black@0.8:x=(w-text_w)/2:y=$5:alpha='min(1,max(0,(t-$2)/0.2))':enable='between(t,$2,$3)'"; }

# 1) الجزء الرئيسي: هوك + 4 خدمات + كرت «ONE SIGN. ONE GARAGE.» (11.4 ث)
ffmpeg -y -hide_banner -loglevel error \
 -loop 1 -framerate 30 -i "$IMG" \
 -f lavfi -i "color=c=black:s=1080x1920:r=30:d=2.4" \
 -f lavfi -i "color=c=black@0:s=1080x1920:r=30:d=12,format=rgba,drawbox=x=90:y=380:w=900:h=900:color=red@1:t=10:replace=1" \
 -filter_complex "
[0:v]split=5[a][b][c][d][e];
[a]trim=duration=2.15,setpts=PTS-STARTPTS,scale=-2:2100:flags=lanczos,crop=1080:1920:'400+500*t/2.15':90,$G[s0];
[b]trim=duration=2.1,setpts=PTS-STARTPTS,scale=-2:2300:flags=lanczos,crop=1080:1920:'2565-600*t/2.1':380,$G[s1];
[c]trim=duration=2.1,setpts=PTS-STARTPTS,scale=-2:2600:flags=lanczos,crop=1080:1920:'1400+700*t/2.1':680,$G[s2];
[d]trim=duration=2.1,setpts=PTS-STARTPTS,scale=-2:2400:flags=lanczos,crop=1080:1920:'400+900*t/2.1':480,$G[s3];
[e]trim=duration=2.1,setpts=PTS-STARTPTS,scale=-2:2700:flags=lanczos,crop=1080:1920:'3200-500*t/2.1':780,$G[s4];
[1:v]format=yuv420p,setsar=1[s5];
[s0][s1]xfade=transition=fade:duration=0.3:offset=1.85[x1];
[x1][s2]xfade=transition=fade:duration=0.3:offset=3.65[x2];
[x2][s3]xfade=transition=fade:duration=0.3:offset=5.45[x3];
[x3][s4]xfade=transition=fade:duration=0.3:offset=7.25[x4];
[x4][s5]xfade=transition=fade:duration=0.3:offset=9.05[base];
[2:v]split[b1][b2];[b1]gblur=sigma=24[glow];
[base][glow]overlay=enable='between(t,9.4,11.4)'[o1];
[o1][b2]overlay=enable='between(t,9.4,11.4)'[o2];
[o2]$(T "$HOOK1" 0.2 2.0 0 1100 140 $RED $FB),$(T "$HOOK2" 0.5 2.0 0 1290 80 white $FS),$(T 'WE FIX' 2.1 3.8 0 1030 60 white $FS),$(T "$S1" 2.2 3.8 0 1100 135 $RED $FB),$(T 'WE FIX' 3.9 5.6 0 1030 60 white $FS),$(T "$S2" 4.0 5.6 0 1100 170 $RED $FB),$(T 'WE FIX' 5.7 7.4 0 1030 60 white $FS),$(T "$S3" 5.8 7.4 0 1100 190 $RED $FB),$(T 'WE FIX' 7.5 9.2 0 1030 60 white $FS),$(T "$S4" 7.6 9.2 0 1100 190 $RED $FB),$(T 'ONE SIGN.' 9.6 11.4 0 640 90 white $FS),$(T 'ONE GARAGE.' 9.75 11.4 0 770 105 $RED $FB)[v]" \
 -map "[v]" -t 11.4 -an -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p "$TMP/main.mp4"

# 2) كرت النهاية: تغبيش + الشعار بحد أبيض + نص بالتتابع (3.9 ث) ويندمج مع الرئيسي
CUT=11.4; TOTAL=15; LE=3.9; OFF=11.1
L() { echo "[$1:v]format=rgba,fade=t=in:st=$2:d=0.35:alpha=1[l$1]"; }
ffmpeg -y -hide_banner -loglevel error -i "$TMP/main.mp4" -loop 1 -framerate 30 -t $LE -i "$IMG" \
 -loop 1 -framerate 30 -t $LE -i "$EC/ec_logo.png" -loop 1 -framerate 30 -t $LE -i "$EC/ec_head.png" -loop 1 -framerate 30 -t $LE -i "$EC/ec_sub.png" \
 -loop 1 -framerate 30 -t $LE -i "$EC/ec_line.png" -loop 1 -framerate 30 -t $LE -i "$EC/ec_phone.png" -loop 1 -framerate 30 -t $LE -i "$EC/ec_addr.png" -loop 1 -framerate 30 -t $LE -i "$EC/ec_handle.png" \
 -filter_complex "
[0:v]trim=duration=$CUT,setpts=PTS-STARTPTS,fps=30,format=yuv420p,setsar=1[m];
[1:v]scale=-2:2100:flags=lanczos,crop=1080:1920:1000:90,gblur=sigma=34,eq=brightness=-0.12:saturation=0.85,vignette=PI/4,fps=30,trim=duration=$LE,setpts=PTS-STARTPTS,format=yuv420p[bg];
$(L 2 0.35);$(L 3 0.8);$(L 4 1.0);$(L 5 1.15);$(L 6 1.35);$(L 7 1.6);$(L 8 1.85);
[bg][l2]overlay=y='if(lt(t,0.8),-90*(1-(t-0.35)/0.45),0)'[e1];
[e1][l3]overlay=y='if(lt(t,1.15),50*(1-(t-0.8)/0.35),0)'[e2];
[e2][l4]overlay=y='if(lt(t,1.35),50*(1-(t-1.0)/0.35),0)'[e3];
[e3][l5]overlay=y='if(lt(t,1.5),50*(1-(t-1.15)/0.35),0)'[e4];
[e4][l6]overlay=y='if(lt(t,1.7),50*(1-(t-1.35)/0.35),0)'[e5];
[e5][l7]overlay=y='if(lt(t,1.95),50*(1-(t-1.6)/0.35),0)'[e6];
[e6][l8]overlay=y='if(lt(t,2.2),50*(1-(t-1.85)/0.35),0)',format=yuv420p[e];
[m][e]xfade=transition=fade:duration=0.3:offset=$OFF,format=yuv420p[v]" \
 -map "[v]" -t $TOTAL -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p -movflags +faststart "$OUT"
echo "تم: $OUT"
