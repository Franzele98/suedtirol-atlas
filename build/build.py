import json, math, sys, base64, io
from PIL import Image
data, out = sys.argv[1], sys.argv[2]
Z=10; X0,X1,Y0,Y1=541,547,359,363
W=(X1-X0+1)*256; H=(Y1-Y0+1)*256
# stitch to float elevation
F=Image.new('F',(W,H))
for x in range(X0,X1+1):
    for y in range(Y0,Y1+1):
        im=Image.open(f'{data}/tiles/{x}_{y}.png').convert('RGB')
        px=list(im.getdata())
        t=Image.new('F',(256,256)); t.putdata([r*256+g+b/256-32768 for r,g,b in px])
        F.paste(t,((x-X0)*256,(y-Y0)*256))
OW=1024; OH=round(H*OW/W)
F=F.resize((OW,OH),Image.LANCZOS)
vals=list(F.getdata()); lo=min(vals); hi=max(vals)
enc=[]
for v in vals:
    q=max(0,min(65535,round(v))) if v>0 else 0
    enc.append((q>>8,q&255,0))
P=Image.new('RGB',(OW,OH)); P.putdata(enc)
buf=io.BytesIO(); P.save(buf,'PNG',optimize=True)
n=2**Z
def lon(x): return x/n*360-180
def lat(y): return math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n))))
bbox=[lon(X0),lat(Y1+1),lon(X1+1),lat(Y0)]  # w,s,e,n
# mercator-normalised coords: u,v in 0..1 over the stitched area
def uv(lo_,la):
    x=(lo_+180)/360*n; y=(1-math.asinh(math.tan(math.radians(la)))/math.pi)/2*n
    return [round((x-X0)/(X1-X0+1),5), round((y-Y0)/(Y1-Y0+1),5)]
def thin(pts,step):
    o=[pts[0]]
    for p in pts[1:]:
        if abs(p[0]-o[-1][0])+abs(p[1]-o[-1][1])>=step: o.append(p)
    if o[-1]!=pts[-1]: o.append(pts[-1])
    return o
b=json.load(open(f'{data}/border.json'))[0]['geojson']
polys=b['coordinates'] if b['type']=='MultiPolygon' else [b['coordinates']]
ring=max((p[0] for p in polys),key=len)
border=[uv(*c) for c in ring]
trails={}
for r in json.load(open(f'{data}/trails.json'))['elements']:
    ways=[]
    for m in r['members']:
        if m['type']=='way' and 'geometry' in m:
            pts=thin([uv(g['lon'],g['lat']) for g in m['geometry']],0.0006)
            if len(pts)>1: ways.append(pts)
    trails[r['id']]={'name':r['tags'].get('name'),'ways':ways}
    print(r['id'],r['tags'].get('name'),len(ways),'ways',sum(map(len,ways)),'pts',file=sys.stderr)
js='window.MAPDATA='+json.dumps({'w':OW,'h':OH,'min':lo,'max':hi,'bbox':bbox,'kmW':(bbox[2]-bbox[0])*111.32*math.cos(math.radians(46.66)),
  'height':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),'border':border,'trails':trails},separators=(',',':'))+';'
open(out,'w').write(js)
print(OW,OH,lo,hi,bbox,len(border),len(js),file=sys.stderr)
print(json.dumps({k:uv(*v) for k,v in {'bozen':(11.3548,46.4983),'meran':(11.1594,46.6713),'brixen':(11.657,46.715),'bruneck':(11.938,46.7963),'sterzing':(11.431,46.893),'ortler':(10.545,46.5089),'zinnen':(12.3024,46.6187),'schlern':(11.5744,46.5117),'reschen':(10.53,46.81),'prags':(12.0853,46.6944),'kaltern':(11.264,46.378)}.items()}))
