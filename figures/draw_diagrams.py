"""Vector drawing primitives; copied into each independent project generator."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)

def generate(out):
    from fractions import Fraction as F
    out.mkdir(parents=True, exist_ok=True)
    def rn(x):
        n=x.numerator//x.denominator
        r=x-n
        return n if r<F(1,2) or (r==F(1,2) and n%2==0) else n+1
    xs=(F(161,16),F(177,16));first=tuple(rn(x+F(7,16)) for x in xs)
    final=tuple(rn(x+F(1,2)) for x in first)
    if first!=final or final!=(10,12):
        raise ValueError('Rounded witness outputs differ.')
    if tuple(abs(y-x-F(7,16)-F(1,2)) for x,y in zip(xs,final))!=(1,0):
        raise ValueError('Witness errors differ.')
    d=Drawing((-0.9,-.8,8.4,1.8))
    d.box('x',0,0,1.3,.95,'$161/16$\n$177/16$')
    d.box('a',2.2,0,1.15,.95,'$+$\nRN')
    d.box('b',5.3,0,1.15,.95,'$+$\nRN')
    d.box('y',7.5,0,1.1,.95,'$10$\n$12$')
    d.edge('x','a','e','w');d.edge('a','b','e','w');d.edge('b','y','e','w')
    d.text(3.75,.5,'$10$\n$12$')
    d.text(2.2,1.4,'$7/16$');d.text(5.3,1.4,'$1/2$')
    d.arrow((2.2,1.12),(2.2,.475));d.arrow((5.3,1.12),(5.3,.475))
    d.save(out,'two-addition')
    d=Drawing((-1.8,-2.65,8.5,.75))
    d.text(0,0,'$(v,D)$');d.text(6,0,r"$(v',D+\ell)$")
    d.text(0,-1.75,r'$(\phi_B(v),D)$')
    d.text(6,-1.75,r"$(\phi_B(v'),D+\ell)$")
    d.arrow((.8,0),(4.85,0));d.text(3,.42,'concrete gate')
    d.arrow((1.35,-1.75),(4.4,-1.75));d.text(3,-2.17,'phase transfer')
    d.arrow((0,-.3),(0,-1.4));d.text(-.12,-.87,'projection',ha='right')
    d.arrow((6,-.3),(6,-1.4));d.text(6.12,-.87,'projection',ha='left')
    d.save(out,'commutation')

def main():
    import tempfile
    p=argparse.ArgumentParser(description='Direct Python diagrams for residual-phase contracts.')
    p.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as t:
            x,y=Path(t)/'a',Path(t)/'b';generate(x);generate(y)
            for name in ('commutation','two-addition'):
                if (x/(name+'.pdf')).read_bytes()!=(y/(name+'.pdf')).read_bytes():
                    raise ValueError('Fresh vector redraws differ: '+name)
        print('Rational witness and deterministic vector redraw checks passed.')
    else:generate(a.output_dir)
if __name__=='__main__':main()
