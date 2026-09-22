# -*- coding: utf-8 -*-
from pyrevit import forms, revit, script
from Autodesk.Revit.DB import *
import os
from collections import defaultdict
from System.Collections.Generic import List
from Autodesk.Revit.Creation import FamilyInstanceCreationData

# === CONFIGURATION ===
scale_to_mm = False    # Set to True if you want to scale coordinates (e.g., inches to millimeters)

# === FUNCTION: Select OBJ file ===
def get_mesh_file_path():
    return forms.pick_file(file_ext='obj', title="Select OBJ file")

# === FUNCTION: Load OBJ vertices and identify external nodes ===
def load_external_vertices(file_path):
    vertices = []
    edges = defaultdict(int)
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith('v '):  # Vertex data
                    # Replace commas with dots to avoid float conversion errors
                    clean_line = line.replace(',', '.')
                    parts = clean_line.strip().split()
                    x, y, z = map(float, parts[1:4])
                    
                    if scale_to_mm:
                        x, y, z = x * 25.4, y * 25.4, z * 25.4
                        
                    vertices.append(XYZ(x, y, z))
                    
                elif line.startswith('f '):  # Face data
                    # Extract vertex indices (OBJ uses 1-based indexing, Python uses 0-based)
                    parts = line.strip().split()
                    indices = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                    
                    for i in range(len(indices)):
                        idx1 = indices[i]
                        idx2 = indices[(i + 1) % len(indices)]
                        edge = tuple(sorted((idx1, idx2)))
                        edges[edge] += 1
                        
    except Exception as e:
        forms.alert("Error reading OBJ file:\n{}".format(e), exit=True)

    # Find boundary nodes: vertices involved in edges that appear exactly once
    boundary_nodes = set()
    for edge, count in edges.items():
        if count == 1:
            boundary_nodes.update(edge)

    external_indices = sorted(boundary_nodes)
    external_vertices = [vertices[i] for i in external_indices]

    return external_vertices, external_indices, vertices

# === FUNCTION: Save external vertices to TXT ===
def save_vertices_to_txt(obj_path, indices, all_vertices):
    base, _ = os.path.splitext(obj_path)
    txt_path = base + "_outer_points.txt"
    try:
        with open(txt_path, 'w') as f:
            for i in indices:
                pt = all_vertices[i]
                f.write("{:.6f}, {:.6f}, {:.6f}\n".format(pt.X, pt.Y, pt.Z))
    except Exception as e:
        forms.alert("Failed to save TXT file:\n{}".format(e))

# === FUNCTION: Load Families from Script Folder ===
def load_families_from_folder(doc):
    # Get the directory of this python script
    script_dir = os.path.dirname(__file__)
    required_families = ["X axis", "Y axis", "Z axis", "Point", "Z axis_neg", "Femup_sheet"]
    loaded_symbols = {}
    
    with Transaction(doc, "Load Families") as t:
        t.Start()
        
        for fam_name in required_families:
            file_name = fam_name + ".rfa"
            full_path = os.path.join(script_dir, file_name)
            
            # Check if file exists in the script directory and attempt to load
            if os.path.exists(full_path):
                doc.LoadFamily(full_path)
            else:
                print("Warning: File '{}' is missing from the script folder.".format(file_name))
                
            # Retrieve the FamilySymbol from the document
            collector = FilteredElementCollector(doc).OfClass(FamilySymbol)
            
            for sym in collector:
                if sym.FamilyName == fam_name:
                    if not sym.IsActive:
                        sym.Activate()
                    loaded_symbols[fam_name] = sym
                    break
                    
        t.Commit()
        
    return loaded_symbols

# === FUNCTION: Create geometry in Revit ===
def create_points_and_axes(doc, ext_vertices, all_vertices, symbols):
    total_ext_verts = len(ext_vertices)
    batch_size = 2000   # points created per call

    # --- SETUP RED COLOR ONLY FOR AXES ---
    red_color = Color(255, 0, 0)
    red_override = OverrideGraphicSettings()
    red_override.SetProjectionLineColor(red_color)

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
            pass  # Failsafe for older Revit versions

    with Transaction(doc, "Import Nodes and Axes") as t:
        t.Start()

        # 1. PLACE BOUNDARY POINTS (batch creation)
        sym_point = symbols.get("Point")
        if sym_point:
            with forms.ProgressBar(title="Placing Boundary Points...", cancellable=True) as pb:
                for start in range(0, total_ext_verts, batch_size):
                    if pb.cancelled:
                        t.RollBack()
                        abort("Operation cancelled by user.")

                    batch = List[FamilyInstanceCreationData]()
                    for pt in ext_vertices[start:start + batch_size]:
                        batch.Add(FamilyInstanceCreationData(pt, sym_point, Structure.StructuralType.NonStructural))
                    doc.Create.NewFamilyInstances2(batch)

                    pb.update_progress(min(start + batch_size, total_ext_verts), total_ext_verts)

        # 2. PLACE AXES (Last 3 vertices of the OBJ) AND COLOR THEM RED
        if len(all_vertices) >= 3:
            axes = [("X axis", all_vertices[-3]),
                    ("Y axis", all_vertices[-2]),
                    ("Z axis", all_vertices[-1])]
            for fam_name, pt in axes:
                sym = symbols.get(fam_name)
                if sym:
                    inst = doc.Create.NewFamilyInstance(pt, sym, Structure.StructuralType.NonStructural)
                    doc.ActiveView.SetElementOverrides(inst.Id, red_override)

        t.Commit()

    forms.alert("Import completed:\n{} boundary points placed.\nAxes placed and colored red.".format(total_ext_verts))


# === MAIN SCRIPT ===
mesh_path = get_mesh_file_path()
if not mesh_path:
    forms.alert("No file selected.", exit=True)

# 1. Parse OBJ to find external boundary vertices and get all vertices
external_verts, external_indices, all_verts = load_external_vertices(mesh_path)
if not external_verts:
    forms.alert("No external/boundary vertices found in the selected OBJ file.", exit=True)

# 2. Save the extracted coordinates to a text file
save_vertices_to_txt(mesh_path, external_indices, all_verts)

# 3. Load all required families (Point + Axes) from the script's folder
symbols_map = load_families_from_folder(revit.doc)
if not symbols_map.get("Point"):
    forms.alert("Family 'Point' could not be loaded. Please ensure 'Point.rfa' is in the script folder.", exit=True)

# 4. Create the instances and axes in Revit
create_points_and_axes(revit.doc, external_verts, all_verts, symbols_map)