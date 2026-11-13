# Stitches the z12 elevation tiles into one 4096 px wide height image (decimetres in R*256+G).
import sys, warnings
from PIL import Image, ImageMath
warnings.simplefilter('ignore'); Image.MAX_IMAGE_PIXELS=None
tiles, out = sys.argv[1], sys.argv[2]
X0,X1,Y0,Y1 = 2164,2191,1436,1455
F=Image.new('F',((X1-X0+1)*256,(Y1-Y0+1)*256))
for x in range(X0,X1+1):
    for y in range(Y0,Y1+1):
        r,g,b=Image.open(f'{tiles}/{x}_{y}.png').convert('RGB').split()
        e=ImageMath.lambda_eval(lambda a: a['convert'](a['r'],'F')*256+a['convert'](a['g'],'F')+a['convert'](a['b'],'F')/256-32768, r=r,g=g,b=b)
        F.paste(e,((x-X0)*256,(y-Y0)*256))
W=4096; H=round(F.height*W/F.width)
F=F.resize((W,H),Image.LANCZOS)
q=ImageMath.lambda_eval(lambda a: a['convert'](a['max'](a['f']*10+0.5,0),'I'), f=F)
hi=ImageMath.lambda_eval(lambda a: a['convert'](a['q']/256,'L'), q=q)
lo=ImageMath.lambda_eval(lambda a: a['convert'](a['q']%256,'L'), q=q)
Image.merge('RGB',(hi,lo,Image.new('L',(W,H)))).save(out,optimize=True)
p=(W//2,H//2); print(W,H,'check',F.getpixel(p),(hi.getpixel(p)*256+lo.getpixel(p))/10, F.getextrema())
