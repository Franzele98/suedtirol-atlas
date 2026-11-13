import sys, io, math, json, urllib.request, urllib.parse, warnings
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
warnings.simplefilter('ignore'); Image.MAX_IMAGE_PIXELS=None
out=sys.argv[1]
O=20037508.343; T=2*O/1024
BB=(-O+541*T, O-364*T, -O+548*T, O-359*T)   # minx,miny,maxx,maxy of the main map (EPSG:3857)
def get(url):
    import subprocess
    for i in range(4):
        r=subprocess.run(['curl','-s','-f','-m','180','-A','map-prototype/0.1',url],capture_output=True)
        if r.returncode==0 and r.stdout: return r.stdout
    raise RuntimeError('download failed: '+url[:120])
def wms(base,layer,bb,w,h,ver='1.1.1'):
    q=dict(SERVICE='WMS',VERSION=ver,REQUEST='GetMap',LAYERS=layer,STYLES='',SRS='EPSG:3857',BBOX=','.join(f'{v:.3f}' for v in bb),WIDTH=w,HEIGHT=h,FORMAT='image/jpeg')
    return Image.open(io.BytesIO(get(base+'?'+urllib.parse.urlencode(q)))).convert('RGB')
def mosaic(base,layer,bb,W,H,chunk):
    nx=math.ceil(W/chunk); ny=math.ceil(H/chunk); img=Image.new('RGB',(W,H)); jobs=[]
    for i in range(nx):
        for j in range(ny):
            x0=i*chunk; y0=j*chunk; w=min(chunk,W-x0); h=min(chunk,H-y0)
            b=(bb[0]+(bb[2]-bb[0])*x0/W, bb[3]-(bb[3]-bb[1])*(y0+h)/H, bb[0]+(bb[2]-bb[0])*(x0+w)/W, bb[3]-(bb[3]-bb[1])*y0/H)
            jobs.append((x0,y0,b,w,h))
    with ThreadPoolExecutor(4) as ex:
        for (x0,y0,b,w,h),im in zip(jobs,ex.map(lambda j: wms(base,layer,j[2],j[3],j[4]),jobs)): img.paste(im,(x0,y0))
    return img
what=sys.argv[2]
if what=='manifest':
    # town photos and school close-ups listed by places.py
    import os
    ORTHO='https://geoservices.buergernetz.bz.it/mapproxy/ows'; L='p_bz-Orthoimagery:Aerial-2023-RGB'
    todo=[p for p in json.load(open(sys.argv[3])) if not os.path.exists(f"{out}/{p['f']}")]
    def one(p):
        wms(ORTHO,L,p['bb'],p['px'],p['px']).save(f"{out}/{p['f']}",quality=76); return p['f']
    with ThreadPoolExecutor(4) as ex:
        for i,f in enumerate(ex.map(one,todo)):
            if i%40==0: print(i,len(todo),flush=True)
    print('done',len(todo))
elif what=='stops':
    # two nested aerial photos per stop: 24 km wide surroundings and a 7 km centre, 3000 px each
    import os
    ORTHO='https://geoservices.buergernetz.bz.it/mapproxy/ows'; L='p_bz-Orthoimagery:Aerial-2023-RGB'
    for part in sys.argv[3:]:
        name,lon,lat=part.split(','); lon=float(lon); lat=float(lat)
        cx=lon*O/180; cy=math.log(math.tan(math.pi/4+math.radians(lat)/2))*O/math.pi; k=1/math.cos(math.radians(lat))
        for key,km in (('a',24.0),('b',7.0)):
            f=f'{out}/stop_{name}_{key}.jpg'
            if os.path.exists(f): continue
            hm=km*1000*k/2
            mosaic(ORTHO,L,(cx-hm,cy-hm,cx+hm,cy+hm),3000,3000,1500).save(f,quality=82)
        print(name,flush=True)
elif what=='sat':
    W=8192; H=round(W*(BB[3]-BB[1])/(BB[2]-BB[0]))
    mosaic('https://tiles.maps.eox.at/wms','s2cloudless-2020_3857',BB,W,H,2048).save(f'{out}/sat.jpg',quality=84)
    print('sat',W,H)
else:
    lon,lat,name=float(sys.argv[3]),float(sys.argv[4]),sys.argv[5]
    cx=lon*O/180; cy=math.log(math.tan(math.pi/4+math.radians(lat)/2))*O/math.pi
    k=1/math.cos(math.radians(lat))
    ORTHO='https://geoservices.buergernetz.bz.it/mapproxy/ows'; L='p_bz-Orthoimagery:Aerial-2023-RGB'
    rects={}
    for key,km in (('mid',8.0),('close',1.6)):
        hm=km*1000*k/2; bb=(cx-hm,cy-hm,cx+hm,cy+hm)
        mosaic(ORTHO,L,bb,4000,4000,2000).save(f'{out}/{name}_{key}.jpg',quality=86)
        rects[key]=[(bb[0]-BB[0])/(BB[2]-BB[0]),(BB[3]-bb[3])/(BB[3]-BB[1]),(bb[2]-BB[0])/(BB[2]-BB[0]),(BB[3]-bb[1])/(BB[3]-BB[1])]
        midbb = bb if key=='mid' else midbb
    # fine terrain for the mid rect from terrarium z14
    Z=14; n=2**Z; t=2*O/n
    x0=int((midbb[0]+O)//t); x1=int((midbb[2]+O)//t); y0=int((O-midbb[3])//t); y1=int((O-midbb[1])//t)
    F=Image.new('F',((x1-x0+1)*256,(y1-y0+1)*256))
    for x in range(x0,x1+1):
        for y in range(y0,y1+1):
            im=Image.open(io.BytesIO(get(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png'))).convert('RGB')
            tl=Image.new('F',(256,256)); tl.putdata([r*256+g+b/256-32768 for r,g,b in im.getdata()]); F.paste(tl,((x-x0)*256,(y-y0)*256))
    px=lambda mx: (mx+O)/t*256-x0*256; py=lambda my: (O-my)/t*256-y0*256
    F=F.crop((round(px(midbb[0])),round(py(midbb[3])),round(px(midbb[2])),round(py(midbb[1])))).resize((1024,1024),Image.BICUBIC)
    P=Image.new('RGB',(1024,1024)); P.putdata([((q:=max(0,min(65535,round(v*10))))>>8,q&255,0) for v in F.getdata()]); P.save(f'{out}/{name}_h.png',optimize=True)
    print(json.dumps({'mid':rects['mid'],'close':rects['close']}))
