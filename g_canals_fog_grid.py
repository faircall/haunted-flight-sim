"""Persistent, local fog discovery on the canals' horizontal world plane.

There are no clocks, graphics calls or file operations here. Each update paints
the maximum clearance reached by a visited point or short walked segment.
Row zero is negative world Z; RGBA pixels store clearance, arrival lag, spatial
resistance and 255. The latter two channels are deterministic smooth fields.
"""
import math
import numbers
import numpy as np


FOG_GRID_BOUNDS=(-96.,-96.,96.,96.)
FOG_GRID_SIZE=192
CLEAR_CORE_RADIUS=7.
MIN_FEATHER_RADIUS=17.
MAX_FEATHER_RADIUS=23.
MAX_INTERPOLATED_DISTANCE=12.
ATMOSPHERE_CLEAR_AREA=3500.


def _smooth(t):
    """Quintic interpolation with zero slope at both ends."""
    return t*t*t*(t*(t*6.-15.)+10.)


def _noise(x,z,seed):
    """Smooth value noise in world coordinates, independent of grid resolution."""
    ix=np.floor(x);iz=np.floor(z);fx=_smooth(x-ix);fz=_smooth(z-iz)
    def lattice(a,b):
        # Reduce before integer conversion, so even distant finite bounds are
        # supported without overflowing a platform-sized integer conversion.
        a=np.remainder(a,65521.).astype(np.uint64)
        b=np.remainder(b,65521.).astype(np.uint64)
        h=a*np.uint64(374761393)+b*np.uint64(668265263)+np.uint64(seed*2246822519)
        h=(h^(h>>np.uint64(13)))*np.uint64(1274126177)
        h=h^(h>>np.uint64(16))
        return (h&np.uint64(0xffffff)).astype(np.float64)/float(0xffffff)
    a=lattice(ix,iz);b=lattice(ix+1.,iz)
    c=lattice(ix,iz+1.);d=lattice(ix+1.,iz+1.)
    return (a+(b-a)*fx)*(1.-fz)+(c+(d-c)*fx)*fz


def _field(x,z,seed,scale):
    # Rotate each field relative to the grid and layer unlike wavelengths. The
    # feather consequently follows broad irregular banks, not cell rows/rings.
    u=x*.819152+z*.573576;v=-x*.573576+z*.819152
    return np.clip(.63*_noise(u*scale,v*scale,seed)
                   +.27*_noise((u+17.1)*scale*2.17,(v-9.4)*scale*2.17,seed+11)
                   +.10*_noise((u-31.6)*scale*4.73,(v+26.3)*scale*4.73,seed+29),0.,1.)


class CanalFogGrid:
    """Remember local clearance; waiting or repeated visits cannot erode it.

    A seven-metre core is fully clear at strength one. Its feather varies from
    seventeen to twenty-three metres using the same lag/resistance channels
    exported to the shader. Short movements paint an analytic swept segment;
    jumps over twelve metres paint only the destination, never a teleport trail.
    """

    def __init__(self,bounds=FOG_GRID_BOUNDS,size=FOG_GRID_SIZE):
        try:bounds=tuple(float(v) for v in bounds)
        except (TypeError,ValueError,OverflowError) as exc:raise ValueError('Fog bounds must contain four finite coordinates') from exc
        if len(bounds)!=4 or not all(math.isfinite(v) for v in bounds):
            raise ValueError('Fog bounds must contain four finite coordinates')
        span_x=bounds[2]-bounds[0];span_z=bounds[3]-bounds[1]
        if not all(math.isfinite(v) and v>0. for v in (span_x,span_z)):
            raise ValueError('Fog bounds must have finite positive X and Z spans')
        if isinstance(size,bool) or not isinstance(size,numbers.Integral) or size<2:
            raise ValueError('Fog size must be an integer of at least two cells')
        self.bounds=bounds;self.size=int(size);self.width=self.height=self.size
        self.cell_size=(span_x/self.size,span_z/self.size)
        self._cell_area=self.cell_size[0]*self.cell_size[1]
        if not math.isfinite(self._cell_area) or self._cell_area<=0.:
            raise ValueError('Fog cells must have a finite positive area')
        self._x=bounds[0]+(np.arange(self.size,dtype=np.float64)+.5)*self.cell_size[0]
        self._z=bounds[1]+(np.arange(self.size,dtype=np.float64)+.5)*self.cell_size[1]
        xx,zz=np.meshgrid(self._x,self._z)
        lag=np.rint(_field(xx,zz,7,.038)*255.).astype(np.uint8)
        resistance=np.rint(_field(xx,zz,43,.071)*255.).astype(np.uint8)
        self._rgba=np.zeros((self.size,self.size,4),dtype=np.uint8)
        self._rgba[:,:,1]=lag;self._rgba[:,:,2]=resistance;self._rgba[:,:,3]=255
        # CPU and shader consume the exact same quantized spatial channels.
        lag=lag.astype(np.float64)/255.;resistance=resistance.astype(np.float64)/255.
        self._reach=MAX_FEATHER_RADIUS-(MAX_FEATHER_RADIUS-MIN_FEATHER_RADIUS)*resistance
        self._response=.8+1.1*resistance+.3*lag
        self._last_position=None;self._last_strength=0.;self._total=0
        self._revision=0;self._pixel_bytes=None

    @property
    def revision(self):return self._revision

    @property
    def coverage_fraction(self):
        """Effective cleared fraction of the entire grid, including feathers."""
        return self._total/(255.*self.size*self.size)

    @property
    def clear_fraction(self):
        """Area-based atmosphere grade; it does not drive local fog visibility."""
        return min(1.,self._total/255.*self._cell_area/ATMOSPHERE_CLEAR_AREA)

    def pixels(self):
        """RGBA8 bytes, row zero at min Z and column zero at min X."""
        if self._pixel_bytes is None:self._pixel_bytes=self._rgba.tobytes()
        return self._pixel_bytes

    def _profile(self,distance,reach,response):
        t=np.clip((distance-CLEAR_CORE_RADIUS)/(reach-CLEAR_CORE_RADIUS),0.,1.)
        return np.clip(1.-_smooth(t),0.,1.)**response

    def update(self,x,y,z,strength=1.):
        """Paint a visit and return the area-based ``clear_fraction`` summary.

        Strength is an explicit 0..1 handoff gate, not elapsed time. Height is
        checked for validity but the remembered field is a horizontal grid.
        """
        try:x,y,z,strength=(float(v) for v in (x,y,z,strength))
        except (TypeError,ValueError,OverflowError) as exc:raise ValueError('Fog visit must contain finite coordinates and strength') from exc
        if not all(math.isfinite(v) for v in (x,y,z,strength)) or not 0.<=strength<=1.:
            raise ValueError('Fog visit must be finite and strength must be in [0, 1]')
        previous=self._last_position;previous_strength=self._last_strength
        if previous==(x,z) and strength<=previous_strength:return self.clear_fraction
        self._last_position=(x,z);self._last_strength=strength
        if strength==0.:return self.clear_fraction
        segment=False
        if previous is not None:
            length=math.hypot(x-previous[0],z-previous[1])
            segment=0.<length<=MAX_INTERPOLATED_DISTANCE
        ax,az=previous if segment else (x,z)
        min_x,min_z,max_x,max_z=self.bounds;dx,dz=self.cell_size
        # Work only on the touched cell rectangle. No arrays are rebuilt during
        # idle updates, and off-map visits are harmless.
        left=max(min_x,min(ax,x)-MAX_FEATHER_RADIUS);right=min(max_x,max(ax,x)+MAX_FEATHER_RADIUS)
        top=max(min_z,min(az,z)-MAX_FEATHER_RADIUS);bottom=min(max_z,max(az,z)+MAX_FEATHER_RADIUS)
        if left>=right or top>=bottom:return self.clear_fraction
        x0=max(0,int(math.floor((left-min_x)/dx)));x1=min(self.size,int(math.ceil((right-min_x)/dx)))
        z0=max(0,int(math.floor((top-min_z)/dz)));z1=min(self.size,int(math.ceil((bottom-min_z)/dz)))
        xx=self._x[None,x0:x1];zz=self._z[z0:z1,None]
        reach=self._reach[z0:z1,x0:x1];response=self._response[z0:z1,x0:x1]
        painted=self._profile(np.hypot(xx-x,zz-z),reach,response)*strength
        if segment:
            vx,vz=x-ax,z-az
            along=np.clip(((xx-ax)*vx+(zz-az)*vz)/(vx*vx+vz*vz),0.,1.)
            distance=np.hypot(xx-(ax+along*vx),zz-(az+along*vz))
            local_strength=previous_strength+(strength-previous_strength)*along
            painted=np.maximum(painted,self._profile(distance,reach,response)*local_strength)
        old=self._rgba[z0:z1,x0:x1,0]
        new=np.maximum(old,np.rint(np.clip(painted,0.,1.)*255.).astype(np.uint8))
        if np.any(new!=old):
            self._total+=int(new.sum(dtype=np.int64)-old.sum(dtype=np.int64))
            old[:]=new;self._revision+=1;self._pixel_bytes=None
        return self.clear_fraction

    def sample(self,x,z):
        """Bilinearly sample remembered clearance; outside the grid stays foggy."""
        try:x,z=float(x),float(z)
        except (TypeError,ValueError,OverflowError) as exc:raise ValueError('Fog sample position must be finite') from exc
        if not math.isfinite(x) or not math.isfinite(z):raise ValueError('Fog sample position must be finite')
        a,b,c,d=self.bounds
        if x<a or x>c or z<b or z>d:return 0.
        u=max(0.,min(self.size-1.,(x-a)/self.cell_size[0]-.5))
        v=max(0.,min(self.size-1.,(z-b)/self.cell_size[1]-.5))
        i,j=int(math.floor(u)),int(math.floor(v));ii=min(self.size-1,i+1);jj=min(self.size-1,j+1)
        tx,tz=u-i,v-j;r=self._rgba[:,:,0]
        upper=float(r[j,i])*(1.-tx)+float(r[j,ii])*tx
        lower=float(r[jj,i])*(1.-tx)+float(r[jj,ii])*tx
        return (upper*(1.-tz)+lower*tz)/255.

    def reveal_all(self):
        """Explicit debug preview: fill clearance without touching spatial noise."""
        total=255*self.size*self.size
        if self._total!=total:
            self._rgba[:,:,0]=255;self._total=total;self._revision+=1;self._pixel_bytes=None
        return self.clear_fraction
