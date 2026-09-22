# Copyright 2026 Trieflow LLC. CC0-1.0.
"""Original Moonlit Garden illustration; generates demo input, never screenshots.
Pillow is needed only to regenerate the committed artwork, not by capture CI.
"""
from PIL import Image,ImageDraw
from pathlib import Path
import math,io,zipfile,json,hashlib
W,H,S=512,384,3
size=(W*S,H*S)
def canvas():return Image.new('RGBA',size,(0,0,0,0))
def poly(draw,points,fill):draw.polygon([(int(x*S),int(y*S)) for x,y in points],fill=fill)
def ellipse(draw,box,fill):draw.ellipse(tuple(int(v*S) for v in box),fill=fill)
sky=canvas();d=ImageDraw.Draw(sky)
for y in range(H*S):
 t=y/(H*S-1);a=(28,42,74);b=(126,147,161);c=tuple(round(x+(z-x)*t) for x,z in zip(a,b));d.line((0,y,W*S,y),fill=c,width=1)
for baseline,amp,phase,color in [(244,24,0,(83,102,124)),(272,30,1.5,(52,81,98)),(310,19,3,(28,63,77))]:
 points=[(x,baseline+amp*math.sin(x/95+phase)) for x in range(-5,W+6,4)]+[(W,H),(0,H)];poly(d,points,color)
moon=canvas();d=ImageDraw.Draw(moon)
ellipse(d,(329,60,409,140),(242,211,155));ellipse(d,(350,48,424,119),(0,0,0,0))
# Each star is deliberately placed, with a quiet arc around the moon.
for x,y,r in [(72,69,1),(125,111,1.5),(198,55,1),(267,97,1.5),(305,39,1),(442,77,1.2),(462,153,1),(211,155,1),(75,166,1),(164,193,1)]:
 ellipse(d,(x-r,y-r,x+r,y+r),(239,215,172))
for x,y in [(236,62),(432,178),(93,123)]:
 poly(d,[(x,y-4),(x+1,y-1),(x+4,y),(x+1,y+1),(x,y+4),(x-1,y+1),(x-4,y),(x-1,y-1)],(239,215,172))
plants=canvas();d=ImageDraw.Draw(plants)
for base,height,lean,color in [(32,127,18,(176,183,146)),(78,170,-20,(213,187,132)),(115,100,14,(132,172,158)),(448,163,-17,(119,160,152)),(482,210,-28,(207,186,137)),(400,91,12,(163,176,142))]:
 pts=[(base+lean*t*t,H-height*t) for t in [i/35 for i in range(36)]]
 d.line([(int(x*S),int(y*S)) for x,y in pts],fill=color,width=2*S)
 for j in range(3,10):
  t=j/11;x=base+lean*t*t;y=H-height*t;direction=-1 if j%2 else 1
  length=18+(1-t)*13;tip=(x+direction*length,y-15)
  poly(d,[(x,y),(x+direction*length*.30,y-13),tip,(x+direction*length*.55,y+1)],color)
for x,y,r in [(154,327,3),(354,334,3),(372,312,2),(174,353,2),(294,352,2)]:
 for i in range(5):
  a=i*math.tau/5;cx=x+math.cos(a)*4;cy=y+math.sin(a)*4;ellipse(d,(cx-r,cy-r,cx+r,cy+r),(220,188,139))
 ellipse(d,(x-1.5,y-1.5,x+1.5,y+1.5),(95,83,67))
layers=[('Moon and stars',moon),('Botanical silhouettes',plants),('Evening landscape',sky)]
# Stack XML and the merged preview use these same original authored layers.
merged=sky.copy();merged.alpha_composite(plants);merged.alpha_composite(moon)
def png(image):
 out=io.BytesIO();image.resize((W,H),Image.Resampling.LANCZOS).save(out,format='PNG');return out.getvalue()
root=Path(__file__).resolve().parent
entries={'mimetype':b'image/openraster','mergedimage.png':png(merged)}
xml='<image version="0.0.3" w="512" h="384" name="Moonlit Garden"><stack>'
for i,(name,im) in enumerate(layers):
 entries[f'data/layer{i}.png']=png(im);xml+=f'<layer name="{name}" src="data/layer{i}.png" opacity="1.0" visibility="visible" composite-op="svg:src-over" x="0" y="0"/>'
entries['stack.xml']=(xml+'</stack></image>').encode()
path=root/'Moonlit Garden.ora'
with zipfile.ZipFile(path,'w') as z:
 for name,data in entries.items():
  info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED if name=='mimetype' else zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)
(root/'artwork-preview.png').write_bytes(entries['mergedimage.png'])
manifest={'schema':1,'title':'Moonlit Garden','license':'CC0-1.0','purpose':'Original generated layered demo artwork, not application screenshot','width':W,'height':H,'layerNames':[n for n,_ in layers],'archive':{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},'members':{n:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in entries.items()}}
(root/'artwork.json').write_text(json.dumps(manifest,indent=2)+'\n')
