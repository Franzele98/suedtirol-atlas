# Sorts every school into its municipality and valley district; writes places.js for the page.
import json, sys, math, re, collections
src, out = sys.argv[1], sys.argv[2]
O=20037508.343; T=2*O/1024
BB=(-O+541*T, O-364*T, -O+548*T, O-359*T)
def uv(lon,lat):
    x=lon*O/180; y=math.log(math.tan(math.pi/4+math.radians(lat)/2))*O/math.pi
    return [round((x-BB[0])/(BB[2]-BB[0]),5), round((BB[3]-y)/(BB[3]-BB[1]),5)]
def rings(rel):
    # stitch outer ways into closed rings
    ways=[[(g['lon'],g['lat']) for g in m['geometry']] for m in rel['members'] if m['type']=='way' and m.get('role')!='inner' and 'geometry' in m]
    out=[]
    while ways:
        r=ways.pop()
        while r[0]!=r[-1]:
            for i,w in enumerate(ways):
                if w[0]==r[-1]: r+=w[1:]; ways.pop(i); break
                if w[-1]==r[-1]: r+=w[-2::-1]; ways.pop(i); break
            else: break
        out.append(r)
    return out
def inside(p,rs):
    x,y=p; c=False
    for r in rs:
        for (x1,y1),(x2,y2) in zip(r,r[1:]):
            if (y1>y)!=(y2>y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
GERMAN={'Bolzano':'Bozen'}
def short(name):          # "Brixen - Bressanone" -> "Brixen"
    n=re.split(r'\s+[-–/]\s+', name)[0].strip()
    return GERMAN.get(n,n)
def names(t):
    return {k:t[f'name:{k}'] for k in ('de','it','lld') if t.get(f'name:{k}')}
def kind(name,fallback):
    n=name.lower()
    for words,label in ((('grundschule','volksschule','elementare','primaria','scola elementara'),'primary'),(('mittelschule','scuola media','secondaria di primo'),'middle'),
        (('gymnasium','oberschule','lyzeum','liceo','istituto','fachoberschule','oberschulzentrum','fachschule','berufsschule','landesberufsschule','professionale','hotelfachschule'),'upper'),
        (('musikschule','scuola di musica'),'music'),(('universit','hochschule','conservatorio','konservatorium'),'university')):
        if any(w in n for w in words): return label
    return fallback
adm=json.load(open(f'{src}/admin_geom.json'))['elements']
dist=[]; gem=[]
for r in adm:
    rs=rings(r); xs=[p[0] for q in rs for p in q]; ys=[p[1] for q in rs for p in q]
    e={'name':short(r['tags']['name']),'full':r['tags']['name'],'names':names(r['tags']),'rings':rs,'bbox':(min(xs),min(ys),max(xs),max(ys)),'c':((min(xs)+max(xs))/2,(min(ys)+max(ys))/2)}
    (dist if r['tags']['admin_level']=='7' else gem).append(e)
dist.append({'name':'Bozen','full':'Bozen - Bolzano','names':{'de':'Bozen','it':'Bolzano','lld':'Bulsan'},'rings':[],'bbox':None})
for g in gem:
    d=next((d for d in dist if d['rings'] and inside(g['c'],d['rings'])),None)
    if d is None: d=next((d for d in dist if d['rings'] and any(inside(p,d['rings']) for p in g['rings'][0][::20])),dist[-1])
    g['district']='Bozen' if 'Bozen' in g['full'].split(' - ') else d['name']; g['schools']=[]
# --- school shapes: grounds outline and buildings ---
def uv6(lon,lat):
    x=lon*O/180; y=math.log(math.tan(math.pi/4+math.radians(lat)/2))*O/math.pi
    return [round((x-BB[0])/(BB[2]-BB[0]),6), round((BB[3]-y)/(BB[3]-BB[1]),6)]
def load(name):
    try: return json.load(open(f'{src}/{name}.json'))['elements']
    except Exception: return []
def way_ring(e):
    if e['type']=='way': return [(g['lon'],g['lat']) for g in e.get('geometry',[])]
    rs=rings(e); return max(rs,key=len) if rs else []
grounds={(e['type'],e['id']):e for e in load('school_geom')}
blds={}
for e in load('bld_in')+load('bld_node')+load('bld_tag'):
    r=way_ring(e)
    if len(r)<4 or r[0]!=r[-1]: continue
    t=e['tags']
    try: h=float(str(t.get('height','')).replace('m','').strip())
    except ValueError:
        try: h=float(t.get('building:levels',''))*3.2
        except ValueError: h=9.0
    blds[e['id']]={'ring':r,'c':(sum(p[0] for p in r)/len(r),sum(p[1] for p in r)/len(r)),'h':min(max(h,4),40)}
def metres(a,b): return math.hypot((a[0]-b[0])*111320*math.cos(math.radians(a[1])),(a[1]-b[1])*110540)
OVERRIDES=json.load(open(f'{src}/../overrides.json'))
def shape(e,lon,lat):
    out=osm_shape(e,lon,lat)
    for b in OVERRIDES.get(f"{e['type']}/{e['id']}",{}).get('add_buildings',[]):      # hand-traced buildings missing in OpenStreetMap
        out.setdefault('b',[]).append({'r':[uv6(*p) for p in b['ring']],'h':b['h']})
    return out
def osm_shape(e,lon,lat):
    g=grounds.get((e['type'],e['id'])); out={}
    if g:
        r=way_ring(g)
        if len(r)>=4 and r[0]==r[-1]:
            if 'building' in g['tags']: mine=[{'ring':r,'h':blds.get(g['id'],{}).get('h',9.0)}]
            else:
                out['g']=[uv6(*p) for p in r]
                mine=[b for b in blds.values() if inside(b['c'],[r])]
            if mine: out['b']=[{'r':[uv6(*p) for p in b['ring']],'h':b['h']} for b in mine]
            return out
    mine=[b for b in blds.values() if abs(b['c'][0]-lon)<0.003 and abs(b['c'][1]-lat)<0.003 and inside((lon,lat),[b['ring']])]
    if not mine:
        near=sorted((metres(b['c'],(lon,lat)),i) for i,b in blds.items() if abs(b['c'][0]-lon)<0.002 and abs(b['c'][1]-lat)<0.002)
        if near and near[0][0]<60: mine=[blds[near[0][1]]]
    if mine: out['b']=[{'r':[uv6(*p) for p in b['ring']],'h':b['h']} for b in mine]
    return out
FOUNDED=json.load(open(f'{src}/founded.json'))
MONTHS='Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
def founded(t):
    if t.get('start_date'): return t['start_date']
    f=FOUNDED.get(t.get('wikidata'))
    if not f: return ''
    y,m,d=f['t'][1:11].split('-')
    return f'{int(d)} {MONTHS[int(m)-1]} {y}' if f['p']>=11 else y
def extras(t):
    e={'founded':founded(t),'op':t.get('operator',''),'lang':','.join(x.strip() for x in t.get('school:language','').split(';') if x.strip()),
       'phone':t.get('phone') or t.get('contact:phone') or '','email':t.get('email') or t.get('contact:email') or ''}
    return {k:v for k,v in e.items() if v}
KIND={'school':'school','college':'college','university':'university','music_school':'music'}
LEVEL={'0':'school','1':'primary','2':'middle','3':'upper'}
lost=0; noname=0
for s in json.load(open(f'{src}/schools.json'))['elements']:
    t=s['tags']; lon=s.get('lon',s.get('center',{}).get('lon')); lat=s.get('lat',s.get('center',{}).get('lat'))
    name=t.get('name') or t.get('name:de') or t.get('name:it')
    if lon is None: lost+=1; continue
    if not name: name=''; noname+=1
    g=next((g for g in gem if g['bbox'][0]<=lon<=g['bbox'][2] and g['bbox'][1]<=lat<=g['bbox'][3] and inside((lon,lat),g['rings'])),None)
    if g is None: lost+=1; continue
    lv=(t.get('isced:level') or '').split(';')[0]
    addr=' '.join(x for x in [t.get('addr:street'),t.get('addr:housenumber')] if x)
    g['schools'].append({'name':name,'names':names(t),'ll':(lon,lat),'uv':uv(lon,lat),'type':kind(name,LEVEL.get(lv,KIND[t['amenity']])),'addr':addr,'web':t.get('website') or t.get('contact:website') or '',**extras(t),**shape(s,lon,lat)})
def box(b): a=uv(b[0],b[3]); c=uv(b[2],b[1]); return a+c
def merc(lon,lat): return (lon*O/180, math.log(math.tan(math.pi/4+math.radians(lat)/2))*O/math.pi)
def rect(bb): return [round((bb[0]-BB[0])/(BB[2]-BB[0]),5), round((BB[3]-bb[3])/(BB[3]-BB[1]),5), round((bb[2]-BB[0])/(BB[2]-BB[0]),5), round((BB[3]-bb[1])/(BB[3]-BB[1]),5)]
res=[]
for d in dist:
    gs=[g for g in gem if g['district']==d['name'] and g['schools']]
    if not gs: continue
    xs=[v for g in gs for v in (g['bbox'][0],g['bbox'][2])]; ys=[v for g in gs for v in (g['bbox'][1],g['bbox'][3])]
    towns=[]
    for g in sorted(gs,key=lambda g:g['name']):
        pts=[merc(*s['ll']) for s in g['schools']]; k=1/math.cos(math.radians(g['schools'][0]['ll'][1]))
        cx=(min(p[0] for p in pts)+max(p[0] for p in pts))/2; cy=(min(p[1] for p in pts)+max(p[1] for p in pts))/2
        ext=max(max(p[0] for p in pts)-min(p[0] for p in pts), max(p[1] for p in pts)-min(p[1] for p in pts))/k   # ground metres
        for sc in g['schools']: del sc['ll']
        towns.append({'name':g['name'],'names':g['names'],'c':rect((cx,cy,cx,cy))[:2],'ext':round(ext/1000,2),'schools':sorted(g['schools'],key=lambda s:s['name'])})
    res.append({'name':d['name'],'names':d['names'],'box':box((min(xs),min(ys),max(xs),max(ys))),'towns':towns})
open(out,'w').write('window.PLACES='+json.dumps(res,ensure_ascii=False,separators=(',',':'))+';')
al=[s for d in res for t in d['towns'] for s in t['schools']]
print('shapes: building',sum(1 for s in al if s.get('b')),'grounds only',sum(1 for s in al if s.get('g') and not s.get('b')),'point only',sum(1 for s in al if not s.get('g') and not s.get('b')),'| buildings known',len(blds))
n=sum(len(t['schools']) for d in res for t in d['towns'])
print('schools placed',n,'dropped',lost,'of which unnamed',noname)
for d in res: print(d['name'],len(d['towns']),'towns',sum(len(t['schools']) for t in d['towns']),'schools', sum(1 for t in d['towns'] if t['schools']),'with schools')
print(collections.Counter(s['type'] for d in res for t in d['towns'] for s in t['schools']))
