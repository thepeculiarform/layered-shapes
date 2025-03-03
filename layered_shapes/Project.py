import Rhino as rh
import Rhino.Geometry as rg
import scriptcontext as sc

import io
import projectpy as pjct






class BaffleRow:
    instances = []
    def __init__(self, name: str, curve: rh.DocObjects.ObjectType.Curve, max_baffle_length=2800):
        self.name = name
        self.curve = curve
        self.max_baffle_length = max_baffle_length
        #
        BaffleRow.instances.append(self)

class BaffleLayout:
    def __init__(self, name: str):
        self.name = name
        #
        BaffleLayout.instances.append(self)

    @property
    def baffle_rows(self) -> list:
        return []








class Cloud:
    def __init__(self, block: rh.DocObjects.InstanceDefinition, name=""):
        self.name = name
        self.block = block
        self.info = {}

        parts = self.block.Explode(True)[0]
        xform = rg.Transform.Translation(rg.Vector3d(self.block.InsertionPoint))

        circle = parts[0].Geometry.TryGetCircle()[-1]
        circle.Transform(xform)
        self.boundary = circle
        self.center = circle.Center
        self.baffle_curves = []

    # xy surface
    def boundary_surface(self):
        for obj in self.block.GetSubObjects():
            if type(obj.Geometry) == rh.Geometry.NurbsCurve:
                return rh.Geometry.Brep.CreatePlanarBreps([obj.Geometry], .01)[0]

    # xz baffle surfaces
    def cloud_surfaces(self):
        surfaces = []
        depth = self.block.Attributes.GetUserString("depth")
        for curve in self.baffle_curves: 
            if len(self.baffle_curves) > 0:
                extrude = rg.Extrusion.Create(curve, -(float(depth)), False)
                if extrude is not None:
                    print(extrude)
                    extrude.ToBrep()
                surfaces.append(extrude)
        return surfaces

    # xz cloud baffle surfaces
    def cloud_baffle_surfaces(self):
        surfaces = []
        height = self.block.Attributes.GetUserString("height")
        srfs = self.cloud_surfaces()
        print(srfs)
        for srf in srfs:
            srf.Translate(0,0,float(height))
            surfaces.append(srf)
        return surfaces

    # xz cloud baffle curves
    def cloud_surface_curves(self):
        curves = []
        for srf in self.cloud_surfaces():
            edge_curve = rg.Curve.JoinCurves(srf.Edges)
            # print(edge_curve[0])

            # filletA = rg.Curve.CreateFillet(edge_curve[1], edge_curve[0], 10,5,5)
            curves.append(edge_curve[0])
            # print(curves)
        return curves


















""" BAFFLE CENTERLINE CLASS """
class BaffleCenterline:
    #
    instances = []
    def __init__(self, name: str, centerline: rh.DocObjects.ObjectType.Curve, max_baffle_length=2800, extend=54, break_gap=20):
        self.name = name
        self.centerline = centerline
        self.max_baffle_length = max_baffle_length
        self.extend = extend
        self.break_gap= break_gap
        #
        BaffleCenterline.instances.append(self)

    # Centerline Thickness Offset
    def get_offset(self, offset):
        #
        right = self.centerline.Geometry.Offset(rg.Plane.WorldXY, -offset, 0.001, rg.CurveOffsetCornerStyle.NONE)[0]
        left = self.centerline.Geometry.Offset(rg.Plane.WorldXY, offset, 0.001, rg.CurveOffsetCornerStyle.NONE)[0]
        #
        return [right, left]

    # All Centerline Arcs
    def get_arcs(self):
        return [
            crv for crv in self.centerline.Geometry.GetSubCurves() if type(crv) == rg.ArcCurve
        ]

    # All Centerline Lines
    def get_lines(self):
        return [
            crv.Line for crv in self.centerline.Geometry.GetSubCurves() if type(crv) == rg.LineCurve
        ]

    @property
    def hanging_points(self):
        hanging_points = []
        for i, line in enumerate(self.connection_lines()):
            hanging_points.append(line.PointAtMid)
        return hanging_points


    # All Centerline Lines
    def connection_lines(self):
        lines = []
        for i, baffle in enumerate(self.baffles):

            if self.centerline.Geometry.IsClosed:
                try:
                    if i < len(self.baffles) - 1:
                        ptA = baffle.baffle_curve.ToNurbsCurve().PointAtEnd
                        ptB = self.baffles[i+1].baffle_curve.ToNurbsCurve().PointAtStart
                        a_line = rg.Line(ptA, ptB).ToNurbsCurve()
                        lines.append(a_line)
                    #
                    elif i == len(self.baffles) - 1:
                        ptA = baffle.baffle_curve.ToNurbsCurve().PointAtEnd
                        ptB = self.baffles[0].baffle_curve.ToNurbsCurve().PointAtStart
                        a_line = rg.Line(ptA, ptB).ToNurbsCurve()
                        lines.append(a_line)
                except:
                    pass
                # 
            else:
                #
                if i < len(self.baffles) - 1:
                    try:
                        ptA = baffle.baffle_curve.ToNurbsCurve().PointAtEnd
                        ptB = self.baffles[i+1].baffle_curve.ToNurbsCurve().PointAtStart
                        a_line = rg.Line(ptA, ptB).ToNurbsCurve()
                        lines.append(a_line)
                    except:
                        pass

        return lines
    
    @property
    def baffles(self):
        #
        baffle_listing = []
        #
        baffle_curves = [crv for crv in self.get_inset_lines() if type(crv) == rg.LineCurve or rg.ArcCurve]
        #
        for i, baffle_curve in enumerate(baffle_curves):
            baffle = Baffle(f"{self.name} - {i}",self, baffle_curve)
            baffle_listing.append(baffle)
        #
        return baffle_listing

    # The Baffle Curves with their extension and subtraction of the
    # Rhino Curve Geometry
    # Default extension and break_length is 0 unless value is passed
    def get_inset_lines(self):
        curve_list = []
        sub_curves = self.centerline.Geometry.GetSubCurves()
        #
        for i, crv in enumerate(sub_curves):

            if type(crv) == rg.LineCurve:
                # 
                if self.centerline.Geometry.IsClosed:
                        ptA = crv.PointAtLength((self.extend) + self.break_gap)
                        ptB = crv.PointAtLength((crv.GetLength() - self.extend) - self.break_gap)
                else:
                    #
                    if  i == 0:
                        ptA = crv.PointAtStart
                        ptB = crv.PointAtLength((crv.GetLength() - self.extend) - self.break_gap)
                    #
                    elif 0 < i < len(sub_curves) - 1:
                        ptA = crv.PointAtLength((self.extend) + self.break_gap)
                        ptB = crv.PointAtLength((crv.GetLength() - self.extend) - self.break_gap)
                    #
                    elif i == len(sub_curves) - 1:
                        ptA = crv.PointAtLength((self.extend) + self.break_gap)
                        ptB = crv.PointAtEnd
                #
                inset_line = rg.Line(ptA, ptB).ToNurbsCurve()
                #
                if inset_line.GetLength() > self.max_baffle_length:
                    baffle_count = int(inset_line.GetLength()/self.max_baffle_length)
                    baffle_count = 2 if baffle_count == 1 else baffle_count
                    #
                    a_length = round((inset_line.GetLength()/baffle_count),0)
                    #
                    for j in range(baffle_count):
                        #
                        if j == 0:
                            new_baffle_line = rg.Line(
                                inset_line.PointAtStart, 
                                inset_line.PointAtLength(a_length-(self.break_gap/2))).ToNurbsCurve()
                        #    
                        elif 0 < j < baffle_count-1:
                            new_baffle_line = rg.Line(
                                inset_line.PointAtLength((a_length*j)+(self.break_gap/2)), 
                                inset_line.PointAtLength((a_length*(j+1))-(self.break_gap/2))).ToNurbsCurve()
                        #
                        else:
                            new_baffle_line = rg.Line(
                                inset_line.PointAtLength((a_length*j)+(self.break_gap/2)),
                                inset_line.PointAtEnd).ToNurbsCurve()
                            
                        curve_list.append(new_baffle_line)
                else:
                    curve_list.append(inset_line)


            elif type(crv) == rg.ArcCurve:

                if self.centerline.Geometry.IsClosed:
                    #
                    if i == 0:
                        #
                        ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                        ptC = sub_curves[-1].PointAtLength(sub_curves[-1].GetLength() - self.extend)
                        ptD = sub_curves[i + 1].PointAtLength(self.extend)
                        crvA = rg.Line(ptA, ptC).ToNurbsCurve()
                        crvB = rg.Line(ptB, ptD).ToNurbsCurve()
                        a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                        curve_list.append(a_corner)

                    if 0 < i < len(sub_curves) - 1:
                        ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                        ptC = sub_curves[i - 1].PointAtLength(
                            sub_curves[i - 1].GetLength() - self.extend
                        )
                        ptD = sub_curves[i + 1].PointAtLength(self.extend)
                        crvA, crvB = (
                            rg.Line(ptA, ptC).ToNurbsCurve(),
                            rg.Line(ptB, ptD).ToNurbsCurve(),
                        )
                        a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                        curve_list.append(a_corner)
                    #
                    if i == len(sub_curves) - 1:
                        ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                        ptC = sub_curves[i - 1].PointAtLength(
                            sub_curves[i - 1].GetLength() - self.extend
                        )
                        ptD = sub_curves[0].PointAtLength(self.extend)
                        crvA, crvB = (
                            rg.Line(ptA, ptC).ToNurbsCurve(),
                            rg.Line(ptB, ptD).ToNurbsCurve(),
                        )
                        a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                        curve_list.append(a_corner)
                else:
                    #
                    if i == 0:
                        #
                        ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                        # ptC = sub_curves[i-1].PointAtLength(sub_curves[i-1].GetLength() - extend)
                        ptD = sub_curves[i + 1].PointAtLength(self.extend)
                        crvA = rg.Line(ptB, ptD).ToNurbsCurve()
                        a_corner = rg.Curve.JoinCurves([crv, crvA])[0]
                        curve_list.append(a_corner)
                    #
                    if 0 < i < len(sub_curves) - 1:
                        #
                        ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                        ptC = sub_curves[i - 1].PointAtLength(sub_curves[i - 1].GetLength() - self.extend)   
                        ptD = sub_curves[i + 1].PointAtLength(self.extend)
                        crvA, crvB = (
                            rg.Line(ptA, ptC).ToNurbsCurve(),
                            rg.Line(ptB, ptD).ToNurbsCurve(),
                        )
                        a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                        curve_list.append(a_corner)
                    #
                    if i == len(sub_curves) - 1:
                        #
                        ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                        ptC = sub_curves[i - 1].PointAtLength(sub_curves[i - 1].GetLength() - self.extend)
                        # ptD = sub_curves[0].PointAtLength(extend)
                        crvA = rg.Line(ptA, ptC).ToNurbsCurve()
                        a_corner = rg.Curve.JoinCurves([crv, crvA])[0]
                        curve_list.append(a_corner)
        return curve_list

    # The Arc Baffles with extensions
    def get_corners(self):
        corners = []
        sub_curves = self.centerline.Geometry.GetSubCurves()
        #
        for i, crv in enumerate(sub_curves):
            # Check and see if the curve is closed
            if self.centerline.Geometry.IsClosed:
                #
                if type(crv) == rg.ArcCurve and i == 0:
                    #
                    ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                    ptC = sub_curves[-1].PointAtLength(sub_curves[-1].GetLength() - self.extend)
                    ptD = sub_curves[i + 1].PointAtLength(self.extend)
                    crvA = rg.Line(ptA, ptC).ToNurbsCurve()
                    crvB = rg.Line(ptB, ptD).ToNurbsCurve()
                    a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                    corners.append(a_corner)

                if type(crv) == rg.ArcCurve and 0 < i < len(sub_curves) - 1:
                    ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                    ptC = sub_curves[i - 1].PointAtLength(
                        sub_curves[i - 1].GetLength() - self.extend
                    )
                    ptD = sub_curves[i + 1].PointAtLength(self.extend)
                    crvA, crvB = (
                        rg.Line(ptA, ptC).ToNurbsCurve(),
                        rg.Line(ptB, ptD).ToNurbsCurve(),
                    )
                    a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                    corners.append(a_corner)
                #
                if type(crv) == rg.ArcCurve and i == len(sub_curves) - 1:
                    ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                    ptC = sub_curves[i - 1].PointAtLength(
                        sub_curves[i - 1].GetLength() - self.extend
                    )
                    ptD = sub_curves[0].PointAtLength(self.extend)
                    crvA, crvB = (
                        rg.Line(ptA, ptC).ToNurbsCurve(),
                        rg.Line(ptB, ptD).ToNurbsCurve(),
                    )
                    a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                    corners.append(a_corner)
            else:
                #
                if type(crv) == rg.ArcCurve and i == 0:
                    #
                    ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                    # ptC = sub_curves[i-1].PointAtLength(sub_curves[i-1].GetLength() - extend)
                    ptD = sub_curves[i + 1].PointAtLength(self.extend)
                    crvA = rg.Line(ptB, ptD).ToNurbsCurve()
                    a_corner = rg.Curve.JoinCurves([crv, crvA])[0]
                    corners.append(a_corner)
                #
                if type(crv) == rg.ArcCurve and 0 < i < len(sub_curves) - 1:
                    #
                    ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                    ptC = sub_curves[i - 1].PointAtLength(
                        sub_curves[i - 1].GetLength() - self.extend
                    )
                    ptD = sub_curves[i + 1].PointAtLength(self.extend)
                    crvA, crvB = (
                        rg.Line(ptA, ptC).ToNurbsCurve(),
                        rg.Line(ptB, ptD).ToNurbsCurve(),
                    )
                    a_corner = rg.Curve.JoinCurves([crvA, crv, crvB])[0]
                    corners.append(a_corner)
                #
                if type(crv) == rg.ArcCurve and i == len(sub_curves) - 1:
                    #
                    ptA, ptB = crv.PointAtStart, crv.PointAtEnd
                    ptC = sub_curves[i - 1].PointAtLength(
                        sub_curves[i - 1].GetLength() - self.extend
                    )
                    # ptD = sub_curves[0].PointAtLength(extend)
                    crvA = rg.Line(ptA, ptC).ToNurbsCurve()
                    a_corner = rg.Curve.JoinCurves([crv, crvA])[0]
                    corners.append(a_corner)

        return corners



""" BAFFLE CLASS """
class Baffle:

    def __init__(self, name: str, baffle_centerline, baffle_curve):
        self.name = name
        self.baffle_centerline = baffle_centerline
        self.baffle_curve = baffle_curve

    def surface(self, depth=-100):
        vec = rg.Vector3d(0,0,depth)
        extrusion = rg.Extrusion.CreateExtrusion(self.baffle_curve.ToNurbsCurve(), vec)
        return extrusion
    
    def solid(self, thickness=12, depth = -100):
        offset = rg.Brep.CreateOffsetBrep(self.surface(depth=depth).ToBrep(), -thickness, False, True, 0.01)[0][0]
        solid = rg.Brep.CreateOffsetBrep(offset, thickness*2, True, True, 0.01)[0][0]
        return solid



""" OVERLAY CLASS """
class Overlay:
    pass


class Area:
    pass


class Floor(Area, Overlay):
    pass


class Cluster(Area):
    pass



""" CUTFILE CLASS """
class CutFile:

    def __init__(self,
                baffle,
                baffle_length: float, 
                baffle_height: float, 
                origin_point: rg.Point3d, 
                blocking_shoulder: float, 
                blocking_hip: float,
                blocking_inset: float,
                blocking_spacing: float,
                material_thickness: float):

        self.baffle = baffle
        self.height = baffle_height
        self.length = baffle_length
        self.origin_point = origin_point
        self.blocking_shoulder=blocking_shoulder
        self.blocking_hip = blocking_hip
        self.blocking_inset = blocking_inset
        self.blocking_spacing = blocking_spacing
        self.material_thickness = material_thickness


    def centerline(self):
        #
        centerline_start = rg.Point3d(self.origin_point)
        #
        centerline_start.Y = centerline_start.Y + self.length
        #
        centerline = rg.Line(self.origin_point, centerline_start).ToNurbsCurve()
        #
        return centerline

    #
    def sidecut(self):
        #
        centerline = self.centerline()
        print(centerline)
        #
        top_crv = centerline.Offset(rg.Plane.WorldXY, -self.height, 0.001, rg.CurveOffsetCornerStyle.NONE)[0]
        #
        sideL = rg.Line(centerline.PointAtStart, top_crv.PointAtStart).ToNurbsCurve()
        #
        sideR = rg.Line(centerline.PointAtEnd, top_crv.PointAtEnd).ToNurbsCurve()
        #
        joined = rg.Curve.JoinCurves([sideL, top_crv, sideR])[0]
        #
        a_plane = rg.Plane(rg.Point3d(centerline.PointAtMid), rg.Vector3d(0,1,0), rg.Vector3d(0,0, 1))
        xform_plane = rg.Transform.Mirror(a_plane)
        #
        flipped = joined.Duplicate()
        flipped.Transform(xform_plane)
        #
        rejoined = rg.Curve.JoinCurves([joined, flipped])[0]
        #
        return rejoined


    def centerline_inset(self):
        #
        centerline = self.centerline()
        #
        centerline_inset = rg.Line(centerline.PointAtLength(self.blocking_inset), centerline.PointAtLength((centerline.GetLength() - self.blocking_inset)),).ToNurbsCurve()
        #
        return centerline_inset


    def blocking_centerlines(self):
        #
        blocking_count = int(self.centerline_inset().GetLength()/self.blocking_spacing)
        #
        blocking_points = [self.centerline_inset().PointAt(loc) for loc in self.centerline_inset().DivideByCount(blocking_count, True)]
        #
        blocking_centerlines = []
        #
        for pt in blocking_points:
            new_pt = rg.Point3d(pt)
            new_pt.X = new_pt.X-self.height
            blocking_centerlines.append(rg.Line(pt, new_pt).ToNurbsCurve())
        #
        return blocking_centerlines


    def blocking_curves(self):
        #
        blocking_centerlines = self.blocking_centerlines()
        #
        blocking_curves = []
        #
        for line in blocking_centerlines:
            #
            c_pt = line.ToNurbsCurve().PointAtMid
            #
            ptA, ptB = rg.Point3d(c_pt), rg.Point3d(c_pt)
            #
            ptA.X, ptA.Y = ptA.X - ((line.GetLength()/2)-self.blocking_shoulder), ptA.Y- (self.material_thickness/2)
            # ptA.Y = ptA.Y- (material_thickness/2)
            ptB.X, ptB.Y = ptB.X + ((line.GetLength()/2)-self.blocking_hip), ptB.Y + (self.material_thickness/2)
            # ptB.Y = ptB.Y + (material_thickness/2)
            a_plane = line.FrameAt(line.GetLength()/2)
            #
            a_rect = rg.Rectangle3d(a_plane[1], ptA, ptB)
            #
            blocking_curves.append(a_rect)
        #
        mirror_plane = rg.Plane(rg.Point3d(self.centerline().PointAtMid), rg.Vector3d(0,1,0), rg.Vector3d(0,0, 1))
        xform_plane = rg.Transform.Mirror(mirror_plane)
        #
        blocking_mirrored = []
        for curve in blocking_curves:
            a_crv = curve.ToNurbsCurve().Duplicate()
            a_crv.Transform(xform_plane)
            blocking_mirrored.append(a_crv)

        return blocking_curves + blocking_mirrored



