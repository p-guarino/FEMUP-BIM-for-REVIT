# -*- coding: utf-8 -*-
from pyrevit import forms, revit, script
from Autodesk.Revit.DB import *
from System.Collections.Generic import List
from Autodesk.Revit.Creation import FamilyInstanceCreationData
import os

# === CONFIGURATION ===
# "M" = Meters (x 3.28084). Use this if the obj file has small coordinates (e.g., 1.5, 2.0)
# "MM" = Millimeters (/ 304.8). Use this if the obj file has large coordinates (e.g., 1500, 2000)
# "FEET" = Feet (No conversion needed for Revit internal units).
obj_file_units = "M"

family_point_mesh = "Point"

batch_size = 2000   # points created per call (batch creation)

# === FUNCTION: Show message and stop the script ===
def abort(msg):
    forms.alert(msg)
    script.exit()

# === FUNCTION: Select OBJ file ===
def get_mesh_file_path():
    return forms.pick_file(file_ext='obj', title="Select OBJ file")

# === FUNCTION: Load OBJ vertices and edges ===
def load_obj_data(file_path):
    vertices = []
    edges = set()
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith('v '):  # Vertex data
                    clean_line = line.replace(',', '.')
                    parts = clean_line.strip().split()

                    try:
                        x, y, z = map(float, parts[1:4])

                        # --- UNIT CONVERSION LOGIC ---
                        if obj_file_units == "M":
                            x = x * 3.28084
                            y = y * 3.28084
                            z = z * 3.28084
                        elif obj_file_units == "MM":
                            x = x / 304.8
                            y = y / 304.8
                            z = z / 304.8

                        vertices.append(XYZ(x, y, z))
                    except ValueError:
                        pass

                elif line.startswith('f '):  # Face data
                    parts = line.strip().split()
                    indices = []
                    for p in parts[1:]:
                        v_idx_str = p.split('/')[0]
                        if v_idx_str.isdigit():
                            indices.append(int(v_idx_str) - 1)

                    for i in range(len(indices)):
                        idx1 = indices[i]
                        idx2 = indices[(i + 1) % len(indices)]
                        edge = tuple(sorted((idx1, idx2)))
                        edges.add(edge)

    except Exception as e:
        abort("Error reading OBJ file:\n{}".format(e))
    return vertices, list(edges)

# === FUNCTION: Load Families from the Script Folder ===
def load_families_from_folder(doc, folder_path):
    required_families = ["X axis.rfa", "Y axis.rfa", "Z axis.rfa", "Point.rfa", "Z axis_neg.rfa", "Femup_sheet.rfa"]
    loaded_symbols = {}

    with Transaction(doc, "Load Families") as t:
        t.Start()
        for fname in required_families:
            name_only = fname.replace(".rfa", "")
            full_path = os.path.join(folder_path, fname)

            if os.path.exists(full_path):
                doc.LoadFamily(full_path)
            else:
                print("Warning: File '{}' is missing in the script folder.".format(fname))

            found_sym = None
            for sym in FilteredElementCollector(doc).OfClass(FamilySymbol):
                if sym.FamilyName == name_only:
                    found_sym = sym
                    if not sym.IsActive:
                        sym.Activate()
                    break

            if found_sym:
                loaded_symbols[name_only] = found_sym
            else:
                print("Error: Unable to find or load symbol for '{}'.".format(name_only))

        t.Commit()
    return loaded_symbols

# === FUNCTION: Create geometry in Revit ===
def create_geometry(doc, vertices, edges, symbols_map):

    # --- SETUP BLUE COLOR FOR MESH LINES ---
    blue_color = Color(0, 0, 255)
    blue_override = OverrideGraphicSettings()
    blue_override.SetProjectionLineColor(blue_color)
    blue_override.SetProjectionLineWeight(3)

    # --- SETUP RED COLOR FOR AXES ---
    red_color = Color(255, 0, 0)
    red_override = OverrideGraphicSettings()
    red_override.SetProjectionLineColor(red_color)

    # Find Solid Fill Pattern in the project for the red surfaces
    solid_pattern_id = None
    for fp in FilteredElementCollector(doc).OfClass(FillPatternElement):
        if fp.GetFillPattern().IsSolidFill:
            solid_pattern_id = fp.Id
            break

    if solid_pattern_id:
        try:
            red_override.SetSurfaceForegroundPatternId(solid_pattern_id)
            red_override.SetSurfaceForegroundPatternColor(red_color)
        except AttributeError:
            pass  # Failsafe for very old Revit versions

    total_verts = len(vertices)
    if total_verts < 4:
        abort("File has too few vertices (needs mesh + 3 axis tips).")

    mesh_end_index = total_verts - 3

    with Transaction(doc, "Import OBJ Geometry") as t:
        t.Start()

        # 1. PLACE MESH VERTICES (batch creation)
        sym_point = symbols_map.get(family_point_mesh)
        if sym_point:
            with forms.ProgressBar(title="Placing OBJ Points...", cancellable=True) as pb:
                for start in range(0, mesh_end_index, batch_size):
                    if pb.cancelled:
                        t.RollBack()
                        abort("Operation cancelled by user.")

                    end = min(start + batch_size, mesh_end_index)
                    batch = List[FamilyInstanceCreationData]()
                    for i in range(start, end):
                        batch.Add(FamilyInstanceCreationData(vertices[i], sym_point, Structure.StructuralType.NonStructural))
                    doc.Create.NewFamilyInstances2(batch)

                    pb.update_progress(end, mesh_end_index)
        else:
            print("Warning: family '{}' not available, mesh points not placed.".format(family_point_mesh))

        # 2. PLACE AXIS TIPS AND COLOR THEM RED
        axes = [("X axis", vertices[-3]),
                ("Y axis", vertices[-2]),
                ("Z axis", vertices[-1])]
        for fam_name, pt in axes:
            sym = symbols_map.get(fam_name)
            if sym:
                inst = doc.Create.NewFamilyInstance(pt, sym, Structure.StructuralType.NonStructural)
                doc.ActiveView.SetElementOverrides(inst.Id, red_override)

        # 3. CREATE MESH EDGES (one by one: no batch API for 3D model lines)
        created_lines_ids = []
        total_edges = len(edges)

        with forms.ProgressBar(title="Creating Mesh Edges...", cancellable=True) as pb:
            for i, edge in enumerate(edges):
                if pb.cancelled:
                    t.RollBack()
                    abort("Operation cancelled by user.")

                idx1, idx2 = edge
                if idx1 < mesh_end_index and idx2 < mesh_end_index:
                    p1 = vertices[idx1]
                    p2 = vertices[idx2]

                    if p1.DistanceTo(p2) >= 0.005:
                        try:
                            line = Line.CreateBound(p1, p2)

                            direction = (p2 - p1).Normalize()
                            up = XYZ.BasisZ
                            if abs(direction.DotProduct(up)) > 0.99:
                                up = XYZ.BasisX
                            normal = direction.CrossProduct(up).Normalize()

                            try:
                                plane = Plane.CreateByNormalAndOrigin(normal, p1)
                            except AttributeError:
                                plane = Plane.Create(p1, normal)

                            sketch_plane = SketchPlane.Create(doc, plane)
                            model_curve = doc.Create.NewModelCurve(line, sketch_plane)
                            created_lines_ids.append(model_curve.Id)
                        except Exception:
                            pass

                if i % 500 == 0:
                    pb.update_progress(i, total_edges)

            pb.update_progress(total_edges, total_edges)

        # 4. COLOR ALL MESH LINES BLUE
        view = doc.ActiveView
        for curve_id in created_lines_ids:
            view.SetElementOverrides(curve_id, blue_override)

        t.Commit()

    forms.alert("Import Complete.\nMesh Points: {}\nMesh Edges: {}\nAxes Colored Red.".format(mesh_end_index, len(created_lines_ids)))


# === MAIN SCRIPT ===
mesh_path = get_mesh_file_path()

if mesh_path:
    # 1. Get the exact directory where this python script is located
    script_directory = os.path.dirname(__file__)

    # 2. Load families directly from the script's folder
    loaded_symbols = load_families_from_folder(revit.doc, script_directory)

    # 3. Read the OBJ file
    verts, edges = load_obj_data(mesh_path)

    # 4. Generate geometry in Revit
    if verts:
        create_geometry(revit.doc, verts, edges, loaded_symbols)
    else:
        abort("No vertices found in the OBJ file.")