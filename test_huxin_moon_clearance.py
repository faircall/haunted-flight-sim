"""Check the exported teahouse, not only its separate walking collision map."""
import unittest
import numpy as np
from g_huxin_moon import DECK
from test_huxin_moon import geometry
from test_santana_car import intersections


def clipped_polygon(points, planes):
    """Clip a triangle to a convex volume; a remainder means an intrusion."""
    poly=list(points)
    for normal,offset in planes:
        out=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            da=float(np.dot(a,normal)-offset)
            db=float(np.dot(b,normal)-offset)
            if da>=0:out.append(a)
            if (da>=0)!=(db>=0):out.append(a+(b-a)*(da/(da-db)))
        poly=out
        if not poly:break
    return poly


class CausewayClearanceTests(unittest.TestCase):
    def test_actual_causeway_width_has_no_piers_posts_or_braces_through_it(self):
        path=geometry('causeway')[1]
        normal=np.cross(path[:,1]-path[:,0],path[:,2]-path[:,0])
        # Exact triangles of the curved paving, extruded below its surface and
        # above a tall player. This also catches a submerged stone pile poking
        # into the path; sparse centre-line rays would miss that case.
        path=path[(normal[:,1]>1e-7)&(path[:,:,2].min(axis=1)<9.)&
                  (path[:,:,2].max(axis=1)>6.4)]
        self.assertGreater(len(path),10)
        bounds=[(np.array((0,1,0)),DECK-.30),
                (np.array((0,-1,0)),-(DECK+2.6)),
                (np.array((0,0,1)),6.4),(np.array((0,0,-1)),-9.)]
        parts=('tea_frame','tea_foundation','tea_walls','tea_lattice','tea_floors',
               'tea_stairs','tea_roofs','tea_ceiling','tea_furniture')
        for name in parts:
            triangles=geometry(name)[1]
            lo,hi=triangles.min(axis=1),triangles.max(axis=1)
            for paving in path:
                center=paving.mean(axis=0);planes=list(bounds)
                for a,b in zip(paving,np.roll(paving,-1,axis=0)):
                    edge=b-a;n=np.array((edge[2],0,-edge[0]))
                    if np.dot(center-a,n)<0:n=-n
                    planes.append((n,np.dot(a,n)))
                candidates=triangles[(hi[:,0]>=paving[:,0].min())&
                    (lo[:,0]<=paving[:,0].max())&
                    (hi[:,2]>=max(6.4,paving[:,2].min()))&
                    (lo[:,2]<=min(9.,paving[:,2].max()))&
                    (hi[:,1]>=DECK-.30)&(lo[:,1]<=DECK+2.6)]
                intrusions=[tri.mean(axis=0).round(3).tolist() for tri in candidates
                            if clipped_polygon(tri,planes)]
                self.assertEqual(intrusions,[],f'{name} penetrates causeway: {intrusions[:3]}')

    def test_doorway_remains_open_and_balcony_remains_overhead(self):
        parts=('tea_frame','tea_walls','tea_lattice','tea_floors','tea_ceiling')
        tri=np.concatenate([geometry(name)[1] for name in parts])
        # Test a broad body-height entrance corridor rather than a single ray
        # that might pass through an accidental gap between timbers.
        planes=[(np.array((1,0,0)),-.92),(np.array((-1,0,0)),-.92),
                (np.array((0,1,0)),DECK+.04),(np.array((0,-1,0)),-(DECK+2.55)),
                (np.array((0,0,1)),5.8),(np.array((0,0,-1)),-6.7)]
        lo,hi=tri.min(axis=1),tri.max(axis=1)
        near=tri[(hi[:,0]>=-.92)&(lo[:,0]<=.92)&(hi[:,2]>=5.8)&(lo[:,2]<=6.7)&
                 (hi[:,1]>=DECK+.04)&(lo[:,1]<=DECK+2.55)]
        self.assertFalse(any(clipped_polygon(t,planes) for t in near))
        for x in (-.85,0.,.85):
            origin=np.array((x,DECK+.05,7.9))
            hits=intersections(tri,origin,np.array((0.,1.,0.)))
            self.assertTrue(len(hits),'Balcony above the passage was removed')
            self.assertGreater(hits.min(),3.)
            self.assertLess(hits.min(),3.8)


if __name__=='__main__':unittest.main()
