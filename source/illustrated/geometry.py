"""Shared bounded paths and reference metadata for offline all-map baking."""
from config import ROOT,WORK,REF,MAP_ID,MAP,FEATURES,ASSET
import sys
import numpy as np
import shapely as sh
from PIL import Image,ImageDraw

def components(g):
    if g.geom_type=='Polygon': yield g
    elif hasattr(g,'geoms'):
        for q in g.geoms: yield from components(q)

def union(tri):
    parts=[]
    for i in range(0,len(tri),4000):
        parts.append(sh.union_all(sh.polygons(tri[i:i+4000,:,[0,2]]),grid_size=.015))
    return sh.make_valid(sh.union_all(parts,grid_size=.015))

def packed(g):
    g=sh.make_valid(sh.simplify(g,.035,preserve_topology=True))
    try: t=sh.constrained_delaunay_triangles(g)
    except Exception:
        # Robust inward-only fallback for rare GEOS convex-corner failures.
        candidate=sh.delaunay_triangles(g)
        t=sh.GeometryCollection([p for p in components(candidate) if g.covers(p)])
    return {'triangles':[[round(v,3) for xy in list(p.exterior.coords)[:3] for v in xy] for p in components(t)],'outlines':[[[round(x,3),round(z,3)] for x,z in ring.coords] for p in components(g) for ring in (p.exterior,*p.interiors)]}
