"""
point cloud stills for the article figures: cover brain, lobes and reward channels, plus the
projected label anchors that brand/figs.py uses. writes to build/art/.
idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import json
import os

import numpy as np
from PIL import Image

import cloud as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "build", "art")
os.makedirs(ART, exist_ok=True)
rng=np.random.default_rng(5)
b=B.Brain()
# cover: calm brain with a sparse code lit and a pool mid flight
m=b.mask('mushroom'); b.excite('mushroom', np.where(rng.random(m.sum())<0.05, 1.25, 0.15))
b.excite('antennal', 0.3+0.5*rng.random(b.mask('antennal').sum()))
pul=[(b.tracts['al_mbL'],0.55,(255,245,250)),(b.tracts['al_mbR'],0.7,(255,245,250)),(b.tracts['ol_cxR'],0.5,(255,245,250))]
img,_=B.render(b,1100,600,yaw=0.42,pitch=0.2,dist=3.3,scale=600*1.75,pulses=pul)
Image.fromarray(img).save(os.path.join(ART, 'brain_cover.png'))
# lobes figure: everything gently lit, front three quarter view
b2=B.Brain()
for k,v in (('optic',0.25),('mushroom',0.45),('central',0.6),('antennal',0.5),('motor',0.45)): b2.excite(k,v)
img,xy=B.render(b2,1600,900,yaw=0.32,pitch=0.22,dist=3.4,scale=900*1.7)
Image.fromarray(img).save(os.path.join(ART, 'brain_lobes.png'))
# reward figure: sugar to calyces + antennal lobes, punishment on its own channel
b3=B.Brain()
m=b3.mask('motor'); b3.act[m]=0.8; b3.tint[m]=np.array([204,255,60])/255; b3.tint_amt[m]=0.9
b3.excite('mushroom',0.35); b3.excite('antennal',0.45)
pul=[]
for s in 'LR':
    for u in (0.35,0.62,0.9): pul.append((b3.tracts['reward_mb'+s],u,(204,255,60)))
    for u in (0.45,0.85): pul.append((b3.tracts['reward_al'+s],u,(204,255,60)))
img,_=B.render(b3,1600,900,yaw=0.32,pitch=0.22,dist=3.4,scale=900*1.7,pulses=pul)
Image.fromarray(img).save(os.path.join(ART, 'brain_reward.png'))
# projected label anchors for the lobes figure
anch={}
for k,c in {'optic lobes':(0.84,0.32,0.0),'mushroom bodies':(-0.23,0.44,-0.06),'central complex':(0.0,0.03,0.0),'antennal lobes':(0.15,-0.2,0.26),'subesophageal ganglion':(0.0,-0.42,0.08)}.items():
    x,y,z,f=B.project(np.array([c]),1600,900,0.32,0.22,3.4,900*1.7); anch[k]=[float(x[0]),float(y[0])]
for k,c in {'calyx':(0.23,0.38,-0.06),'al':(0.15,-0.2,0.26),'seg':(0.0,-0.40,0.08)}.items():
    x,y,z,f=B.project(np.array([c]),1600,900,0.32,0.22,3.4,900*1.7); anch['r_'+k]=[float(x[0]),float(y[0])]
json.dump(anch,open(os.path.join(ART, 'anchors.json'),'w'))
print(anch)
