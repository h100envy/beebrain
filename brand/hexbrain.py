"""
brand art: avatar 800x800, banner 1500x500 and the readme cover 1500x600, the honeycomb
brain with the BeeBrain wordmark. rendered with headless chromium into web/assets/brand/.

  python brand/hexbrain.py

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import os

from common import BRAND_OUT, font_css, shoot

JS = r"""
function rng(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;}}
// realistic lateral view of a brain in a 1000 x 760 box, frontal lobe on the left
function cerebrum(c){c.beginPath();c.moveTo(120,400);
 c.bezierCurveTo(88,280,170,158,300,118);c.bezierCurveTo(420,68,600,58,722,108);
 c.bezierCurveTo(832,150,902,262,886,362);c.bezierCurveTo(876,430,832,470,772,480);
 c.bezierCurveTo(722,488,690,472,650,482);c.bezierCurveTo(612,560,522,592,432,572);
 c.bezierCurveTo(352,556,300,512,300,472);c.bezierCurveTo(292,446,262,446,242,460);
 c.bezierCurveTo(182,482,132,462,120,400);c.closePath();}
function cerebellum(c){c.beginPath();c.moveTo(640,500);
 c.bezierCurveTo(680,478,780,470,835,500);c.bezierCurveTo(880,525,870,585,810,605);
 c.bezierCurveTo(740,628,660,612,628,575);c.bezierCurveTo(612,550,615,515,640,500);c.closePath();}
function stem(c){c.beginPath();c.moveTo(575,492);c.bezierCurveTo(600,520,612,600,600,700);
 c.lineTo(548,700);c.bezierCurveTo(552,620,540,545,520,512);c.closePath();}
const SULCI=[
 [[300,468],[380,430],[470,405],[560,378],[610,360]],          // lateral fissure
 [[520,86],[500,170],[470,250],[448,330],[440,372]],           // central sulcus
 [[455,96],[430,180],[400,260],[385,330]],                      // precentral
 [[175,225],[260,180],[340,150],[420,128]],                     // superior frontal
 [[150,322],[230,300],[300,290],[372,300]],                     // inferior frontal
 [[560,160],[600,250],[680,290],[790,300]],                     // intraparietal
 [[770,150],[758,230],[742,300]],                               // parieto occipital
 [[360,520],[450,500],[560,470],[660,440]],                     // superior temporal
 [[420,560],[520,545],[610,520]]                                // inferior temporal
];
function segDist(x,y,lines){let d=1e9;for(const f of lines){for(let i=0;i<f.length-1;i++){const [x1,y1]=f[i],[x2,y2]=f[i+1];const vx=x2-x1,vy=y2-y1;let t=((x-x1)*vx+(y-y1)*vy)/(vx*vx+vy*vy);t=Math.max(0,Math.min(1,t));d=Math.min(d,Math.hypot(x-(x1+vx*t),y-(y1+vy*t)));}}return d;}
function hexPath(c,x,y,r){c.beginPath();for(let k=0;k<6;k++){const a=Math.PI/3*k;const px=x+r*Math.cos(a),py=y+r*Math.sin(a);k?c.lineTo(px,py):c.moveTo(px,py);}c.closePath();}
function cellsIn(shape,r){const off=document.createElement('canvas');off.width=1000;off.height=760;const oc=off.getContext('2d');shape(oc);
 const w=r*1.5,h=Math.sqrt(3)*r,out=[];for(let col=-2;col<1000/w+2;col++)for(let row=-2;row<760/h+2;row++){const x=col*w,y=row*h+(col%2?h/2:0);
 let ok=true;for(const [dx,dy] of [[0,0],[r*.55,0],[-r*.55,0],[0,r*.55],[0,-r*.55]]) if(!oc.isPointInPath(x+dx,y+dy)) ok=false; if(ok) out.push([x,y]);}return out;}
function drawBrain(c, ox, oy, s, seed, opts){
  const R=rng(seed);
  c.save(); c.translate(ox,oy); c.scale(s,s);
  const g=c.createRadialGradient(500,360,40,500,360,560); g.addColorStop(0,"rgba(255,79,163,.24)"); g.addColorStop(1,"rgba(255,79,163,0)");
  c.fillStyle=g; c.fillRect(-150,-150,1300,1100);
  // antennae from the top of the head
  c.lineCap="round"; c.strokeStyle="rgba(243,239,230,.92)"; c.lineWidth=8; c.shadowColor="rgba(255,176,74,.6)"; c.shadowBlur=16;
  c.beginPath(); c.moveTo(330,112); c.bezierCurveTo(300,30,240,-15,178,-45); c.stroke();
  c.beginPath(); c.moveTo(430,82); c.bezierCurveTo(432,0,402,-58,352,-102); c.stroke();
  c.fillStyle="#ffb04a"; c.beginPath(); c.arc(174,-47,18,0,7); c.fill(); c.beginPath(); c.arc(348,-105,18,0,7); c.fill(); c.shadowBlur=0;
  const light=(x,y)=>{const d=Math.hypot(x-360,y-170);return Math.max(0,Math.min(1,1.15-d/620));};
  function paint(cells,r,kind){
    for(const [x,y] of cells){
      const L=light(x,y); let fill,glow=0;
      const sd=kind==='cer'?segDist(x,y,SULCI):1e9;
      const folia=kind==='cbl'?(Math.abs(((y-500)%22+22)%22-11)<3.2):false;
      const roll=R();
      if(kind==='stem'){fill=`rgba(255,120,180,${0.10+0.18*L})`;}
      else if(sd<r*0.95 || folia){fill=`rgba(24,6,18,.95)`;}
      else if(roll<0.10){fill='#ff4fa3';glow=18;}
      else if(roll<0.15){fill='#ffafd7';glow=14;}
      else if(roll<0.19){fill='#ffb04a';glow=12;}
      else{const a=0.10+0.55*L*(0.75+0.25*R()); fill=`rgba(255,${Math.round(90+80*L)},${Math.round(160+50*L)},${a})`;}
      hexPath(c,x,y,r*0.88); c.shadowColor=fill; c.shadowBlur=glow; c.fillStyle=fill; c.fill(); c.shadowBlur=0;
      hexPath(c,x,y,r*0.88); c.strokeStyle=`rgba(255,175,215,${0.12+0.3*L})`; c.lineWidth=1.2; c.stroke();
    }
  }
  const r=opts.r||18;
  paint(cellsIn(stem,r*0.8),r*0.8,'stem');
  paint(cellsIn(cerebellum,r*0.7),r*0.7,'cbl');
  paint(cellsIn(cerebrum,r),r,'cer');
  // sulci as soft dark grooves, clipped to the cerebrum
  c.save(); cerebrum(c); c.clip(); c.lineCap="round"; c.lineJoin="round";
  for(const f of SULCI){ c.beginPath(); c.moveTo(f[0][0],f[0][1]);
    for(let i=1;i<f.length-1;i++){ const mx=(f[i][0]+f[i+1][0])/2, my=(f[i][1]+f[i+1][1])/2; c.quadraticCurveTo(f[i][0],f[i][1],mx,my); }
    c.lineTo(f[f.length-1][0],f[f.length-1][1]);
    c.strokeStyle="rgba(8,2,6,.9)"; c.lineWidth=11; c.stroke();
    c.strokeStyle="rgba(255,175,215,.18)"; c.lineWidth=2; c.stroke(); }
  c.restore();
  // rim light and outlines
  c.lineWidth=3.5; c.shadowColor="#ff4fa3"; c.shadowBlur=18; c.strokeStyle="rgba(255,175,215,.55)";
  cerebrum(c); c.stroke(); cerebellum(c); c.stroke(); c.shadowBlur=0;
  c.restore();
}
"""

AVATAR = """<html><head><meta charset=utf-8><style>FONTS*{margin:0}body{background:#000;width:800px;height:800px}</style></head><body>
<canvas id=c width=800 height=800></canvas><script>%s
const c=document.getElementById('c').getContext('2d'); c.fillStyle='#000'; c.fillRect(0,0,800,800);
drawBrain(c, 32, 200, 0.74, 11, {r:17});
</script></body></html>""" % JS

BANNER = """<html><head><meta charset=utf-8><style>FONTS*{margin:0;padding:0}body{background:#000;width:1500px;height:500px;position:relative;overflow:hidden}
.w{position:absolute;left:92px;top:118px;font-family:'Cinzel';font-weight:700;font-size:118px;line-height:1;letter-spacing:2px;
background:linear-gradient(100deg,#f3efe6 0%%,#d9d6e2 45%%,#ffafd7 75%%,#ff4fa3 100%%);-webkit-background-clip:text;color:transparent}
.t{position:absolute;left:100px;top:262px;font-family:'JetBrains Mono';font-size:21px;letter-spacing:9px;color:#b9b6c6}
.r{position:absolute;right:46px;bottom:28px;font-family:'JetBrains Mono';font-size:15px;color:#4a5060}
</style></head><body>
<canvas id=c width=1500 height=500 style="position:absolute;left:0;top:0"></canvas>
<div class=w>BeeBrain</div><div class=t>INSIDE THE HIVE MIND</div><div class=r>github.com/h100envy/beebrain</div>
<script>%s
const c=document.getElementById('c').getContext('2d'); c.fillStyle='#000'; c.fillRect(0,0,1500,500);
const R=rng(4); for(let i=0;i<140;i++){const x=R()*1500,y=R()*500,s=R()<0.1?3:1.2; c.fillStyle=R()<0.3?'rgba(255,79,163,.7)':'rgba(236,235,242,.35)'; c.beginPath(); c.arc(x,y,s,0,7); c.fill();}
drawBrain(c, 875, 95, 0.50, 11, {r:17});
</script></body></html>""" % JS


COVER = """<html><head><meta charset=utf-8><style>FONTS*{margin:0;padding:0}body{background:#000;width:1500px;height:600px;position:relative;overflow:hidden}
.w{position:absolute;left:96px;top:170px;font-family:'Cinzel';font-weight:700;font-size:132px;line-height:1;letter-spacing:2px;
background:linear-gradient(100deg,#f3efe6 0%%,#d9d6e2 45%%,#ffafd7 75%%,#ff4fa3 100%%);-webkit-background-clip:text;color:transparent}
.n{position:absolute;left:104px;top:322px;font-family:'JetBrains Mono';font-size:20px;letter-spacing:9px;color:#b9b6c6}
.d{position:absolute;left:104px;top:376px;font-family:'JetBrains Mono';font-size:20px;line-height:1.6;color:#8a8fa2}
.d b{color:#ff4fa3;font-weight:500}
.r{position:absolute;left:104px;bottom:52px;font-family:'JetBrains Mono';font-size:15px;color:#4a5060}
</style></head><body>
<canvas id=c width=1500 height=600 style="position:absolute;left:0;top:0"></canvas>
<div class=w>BeeBrain</div><div class=n>INSIDE THE HIVE MIND</div>
<div class=d>a honeybee brain inside the <b>nerve</b> memecoin desk.<br>five lobes. one waggle vector. you click.</div>
<div class=r>github.com/h100envy/beebrain</div>
<script>%s
const c=document.getElementById('c').getContext('2d'); c.fillStyle='#000'; c.fillRect(0,0,1500,600);
const R=rng(9); for(let i=0;i<170;i++){const x=R()*1500,y=R()*600,s=R()<0.1?3:1.2; c.fillStyle=R()<0.3?'rgba(255,79,163,.7)':'rgba(236,235,242,.35)'; c.beginPath(); c.arc(x,y,s,0,7); c.fill();}
drawBrain(c, 820, 95, 0.62, 11, {r:17});
</script></body></html>""" % JS


if __name__ == "__main__":
    css = font_css()
    shoot([(AVATAR.replace("FONTS", css), 800, 800, os.path.join(BRAND_OUT, "avatar.png")),
           (BANNER.replace("FONTS", css), 1500, 500, os.path.join(BRAND_OUT, "banner.png")),
           (COVER.replace("FONTS", css), 1500, 600, os.path.join(BRAND_OUT, "cover.png"))], wait=700)
