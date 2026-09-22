# -*- coding: utf-8 -*-
import os
import re
import sys
import clr
clr.AddReference("System.Drawing")
import System.Drawing

from pyrevit import forms, revit, DB

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

# --- GEOMETRIC FUNCTIONS AND SUPPORT ---

def get_custom_titleblock():
    tblocks = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_TitleBlocks).WhereElementIsElementType().ToElements()
    for t in tblocks:
        try:
            name = DB.Element.Name.__get__(t)
            if "Cartiglio" in name:
                return t.Id
        except: pass
    return tblocks[0].Id if tblocks else None

def get_medium_line_style():
    try:
        category = DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Lines)
        if not category: return None
        # Cerca linee medie invece di quelle spesse
        for subcat in category.SubCategories:
            if "medium" in subcat.Name.lower() or "med" in subcat.Name.lower():
                return subcat.GetGraphicsStyle(DB.GraphicsStyleType.Projection)
    except: pass
    return None

def draw_line(sheet, x1, y1, x2, y2, style=None):
    try:
        line = DB.Line.CreateBound(DB.XYZ(x1, y1, 0), DB.XYZ(x2, y2, 0))
        curve = doc.Create.NewDetailCurve(sheet, line)
        if style: curve.LineStyle = style
    except: pass

# --- TEXT AND IMAGES FUNCTIONS ---

def get_or_create_title_text_type(type_name, size_mm, is_bold=True):
    tnts = DB.FilteredElementCollector(doc).OfClass(DB.TextNoteType).ToElements()
    target_tnt = None
    for t in tnts:
        try:
            if DB.Element.Name.__get__(t) == type_name:
                target_tnt = t
                break
        except: pass
    if not target_tnt:
        if not tnts: return None
        target_tnt = tnts[0].Duplicate(type_name)
        
    font_param = target_tnt.get_Parameter(DB.BuiltInParameter.TEXT_FONT)
    size_param = target_tnt.get_Parameter(DB.BuiltInParameter.TEXT_SIZE)
    bold_param = target_tnt.get_Parameter(DB.BuiltInParameter.TEXT_STYLE_BOLD)
    
    if font_param and not font_param.IsReadOnly: font_param.Set("Arial")
    if size_param and not size_param.IsReadOnly: size_param.Set(size_mm / 304.8) 
    if bold_param and not bold_param.IsReadOnly: bold_param.Set(1 if is_bold else 0) 
    return target_tnt

def create_centered_text(sheet, x, y, text, tnt):
    if not tnt: return
    options = DB.TextNoteOptions(tnt.Id)
    options.HorizontalAlignment = DB.HorizontalTextAlignment.Center
    try: options.VerticalAlignment = DB.VerticalTextAlignment.Middle
    except: pass
    DB.TextNote.Create(doc, sheet.Id, DB.XYZ(x, y, 0), 1.0, str(text), options)

def place_image_with_border(sheet, image_path, x_coord, y_coord, width_ft, align="center", border_style=None):
    if not os.path.exists(image_path): return
    
    height_ft = 0
    try:
        img_file = System.Drawing.Image.FromFile(image_path)
        aspect_ratio = float(img_file.Height) / float(img_file.Width)
        img_file.Dispose()
        height_ft = width_ft * aspect_ratio
    except Exception as e:
        return

    cx = x_coord
    if align == "center":
        cy = y_coord
    elif align == "top":
        cy = y_coord - (height_ft / 2.0)
    elif align == "bottom":
        cy = y_coord + (height_ft / 2.0)
        
    location = DB.XYZ(cx, cy, 0)

    img_options = DB.ImageTypeOptions(image_path, False, DB.ImageTypeSource.Import)
    img_type = DB.ImageType.Create(doc, img_options)
    placement_options = DB.ImagePlacementOptions(location, DB.BoxPlacement.Center)
    img_inst = DB.ImageInstance.Create(doc, sheet, img_type.Id, placement_options)
    doc.Regenerate()
    
    scaled = False
    try:
        w_param = img_inst.get_Parameter(DB.BuiltInParameter.RASTER_SYMBOL_WIDTH)
        if w_param and not w_param.IsReadOnly:
            w_param.Set(width_ft)
            scaled = True
    except: pass
    if not scaled:
        for p in img_inst.Parameters:
            name = p.Definition.Name.lower()
            if name == "larghezza" or name == "width":
                if not p.IsReadOnly: p.Set(width_ft); break
                
    try:
        half_w = width_ft / 2.0
        half_h = height_ft / 2.0
        margin = width_ft * 0.005 
        
        p1_x, p1_y = cx - half_w - margin, cy - half_h - margin
        p2_x, p2_y = cx + half_w + margin, cy - half_h - margin
        p3_x, p3_y = cx + half_w + margin, cy + half_h + margin
        p4_x, p4_y = cx - half_w - margin, cy + half_h + margin
        
        draw_line(sheet, p1_x, p1_y, p2_x, p2_y, border_style)
        draw_line(sheet, p2_x, p2_y, p3_x, p3_y, border_style)
        draw_line(sheet, p3_x, p3_y, p4_x, p4_y, border_style)
        draw_line(sheet, p4_x, p4_y, p1_x, p1_y, border_style)
    except:
        pass

def draw_dynamic_table(sheet, center_x, start_y, title, headers, data_matrix, col_widths, row_height, tnt_id, tnt_bold_id):
    tot_w = sum(col_widths)
    start_x = center_x - (tot_w / 2.0)
    current_y = start_y
    
    create_centered_text(sheet, center_x, current_y, title, tnt_bold_id)
    current_y -= (row_height * 1.5)
    
    draw_line(sheet, start_x, current_y, start_x + tot_w, current_y)
    
    cx = start_x
    for i, header in enumerate(headers):
        create_centered_text(sheet, cx + col_widths[i]/2.0, current_y - (row_height/2.0), header, tnt_bold_id)
        cx += col_widths[i]
        
    current_y -= row_height
    draw_line(sheet, start_x, current_y, start_x + tot_w, current_y)
    
    for row in data_matrix:
        cx = start_x
        for i, val in enumerate(row):
            create_centered_text(sheet, cx + col_widths[i]/2.0, current_y - (row_height/2.0), val, tnt_id)
            cx += col_widths[i]
        current_y -= row_height
        draw_line(sheet, start_x, current_y, start_x + tot_w, current_y)
        
    return current_y


# --- 1. SELECT FOLDER AND MODEL PICTURE ---
folder_path = forms.pick_folder(title="Pick the folder with FEMUP results")
if not folder_path: sys.exit()

image_model_path = os.path.join(folder_path, "Reference_sheet.png")
try:
    options = DB.ImageExportOptions()
    options.FilePath = image_model_path
    options.HLRandWFViewsFileType = DB.ImageFileType.PNG
    options.ShadowViewsFileType = DB.ImageFileType.PNG
    options.ImageResolution = DB.ImageResolution.DPI_150 
    options.ExportRange = DB.ExportRange.VisibleRegionOfCurrentView 
    options.ZoomType = DB.ZoomFitType.Zoom
    options.Zoom = 100
    doc.ExportImage(options)
except Exception as e:
    pass

# --- 2. LETTURA DEI DATI ---
img_mac = os.path.join(folder_path, "MAC_Matrix_2D.png")
img_freq = os.path.join(folder_path, "Frequencies_Comparison.png")
img_part = os.path.join(folder_path, "Convergence_Particle_History.png")
img_cost = os.path.join(folder_path, "Convergence_Cost_History.png")

file_py = os.path.join(folder_path, "Launch_From_Python_Run.py")
file_res = os.path.join(folder_path, "Calibration_Results.txt")
file_calib = os.path.join(folder_path, "Calibrated_Parameters.txt")

nmodes, nparticles, max_iter, tol, alpha_val, beta_val = "-", "-", "-", "-", "-", "-"
py_content = ""
if os.path.exists(file_py):
    with open(file_py, 'r') as f:
        py_content = f.read()
        m1 = re.search(r'"nmodes":\s*(\d+)', py_content); nmodes = m1.group(1) if m1 else "-"
        m2 = re.search(r'"nparticles":\s*(\d+)', py_content); nparticles = m2.group(1) if m2 else "-"
        m3 = re.search(r'"max_iter":\s*(\d+)', py_content); max_iter = m3.group(1) if m3 else "-"
        m5 = re.search(r'"alpha":\s*([\d\.]+)', py_content); alpha_val = m5.group(1) if m5 else "-"
        m6 = re.search(r'"beta":\s*([\d\.]+)', py_content); beta_val = m6.group(1) if m6 else "-"
        m7 = re.search(r'"Tolnodes":\s*([\d\.]+)', py_content); tol = m7.group(1) if m7 else "-"

exp_freqs = []
results_data = []
if os.path.exists(file_res):
    with open(file_res, 'r') as f:
        lines = f.readlines()
        for line in lines[1:]: 
            parts = line.split()
            if len(parts) >= 7:
                exp_freqs.append(float(parts[0]))
                unc = str(round(float(parts[1]), 2))
                e_unc = str(round(float(parts[2]), 1))
                mac_unc = str(round(float(parts[3]), 3)) 
                cal = str(round(float(parts[4]), 2))
                e_cal = str(round(float(parts[5]), 1))
                mac_cal = str(round(float(parts[6]), 3))
                results_data.append([unc, e_unc, mac_unc, cal, e_cal, mac_cal])
n_modes_calib = len(exp_freqs)

grouped_variables = []
mat_match = re.search(r'"Material"\s*:\s*\[(.*?)\]', py_content, re.DOTALL)
prop_match = re.search(r'"PROP"\s*:\s*\[(.*?)\]', py_content, re.DOTALL)
xo_match = re.search(r'"xo"\s*:\s*\[(.*?)\]', py_content, re.DOTALL)
xmin_match = re.search(r'"xmin"\s*:\s*\[(.*?)\]', py_content, re.DOTALL)
xmax_match = re.search(r'"xmax"\s*:\s*\[(.*?)\]', py_content, re.DOTALL)

if mat_match and prop_match:
    materials_list = [m.strip(' "\'\n\r') for m in mat_match.group(1).split(',')]
    props_list = [p.strip(' "\'\n\r') for p in prop_match.group(1).split(',')]
    materials_list = [m for m in materials_list if m]
    props_list = [p for p in props_list if p]
    xo_list = [float(x.strip()) for x in xo_match.group(1).split(',')] if xo_match else []
    xmin_list = [float(x.strip()) for x in xmin_match.group(1).split(',')] if xmin_match else []
    xmax_list = [float(x.strip()) for x in xmax_match.group(1).split(',')] if xmax_match else []
    
    last_mat = None
    for i, (mat, prop) in enumerate(zip(materials_list, props_list)):
        xo_val = xo_list[i] if i < len(xo_list) else 0.0
        xmin_val = xmin_list[i] if i < len(xmin_list) else 1.0
        xmax_val = xmax_list[i] if i < len(xmax_list) else 1.0
        prop_data = {"nome": prop, "xo": xo_val, "xmin": xmin_val, "xmax": xmax_val}
        if mat != last_mat:
            grouped_variables.append({"nome": mat, "proprieta": [prop_data]})
            last_mat = mat
        else:
            grouped_variables[-1]["proprieta"].append(prop_data)

calib_data = []
if os.path.exists(file_calib):
    with open(file_calib, 'r') as f:
        content = "".join(f.readlines())
        matches = re.findall(r'MATERIAL:\s*([^:]+):\s*(E|Dens)_nom[^;]*;\s*(?:E|Dens)_calib\s*=\s*([\d\.]+)', content)
        for mat, prop, calib_val in matches:
            prop_str = u"ρ" if prop == "Dens" else "E"
            cal_val_num = float(calib_val)
            calib_str = "{:.0f}".format(cal_val_num) if prop == "E" else "{:.2f}".format(cal_val_num)
            calib_data.append([mat.strip(), prop_str, calib_str])

# --- 3. CREAZIONE TAVOLA ---
t_block_id = get_custom_titleblock()

with DB.Transaction(doc, "FEMUP Sheet generation") as t:
    t.Start()
    
    if not t_block_id:
        forms.alert("Blank sheet not found!")
        t.RollBack()
    else:
        existing_femup_nums = []
        for s in DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Sheets).ToElements():
            if s.SheetNumber.startswith("FEMUP-"):
                try:
                    num = int(s.SheetNumber.split("-")[1])
                    existing_femup_nums.append(num)
                except: pass
                
        next_num = max(existing_femup_nums) + 1 if existing_femup_nums else 1
        sheet_num_str = "FEMUP-{:02d}".format(next_num)
        
        new_sheet = DB.ViewSheet.Create(doc, t_block_id)
        new_sheet.SheetNumber = sheet_num_str
        new_sheet.Name = "Report Calibrazione"
        
        tblock_inst = DB.FilteredElementCollector(doc, new_sheet.Id).OfCategory(DB.BuiltInCategory.OST_TitleBlocks).FirstElement()
        bbox = tblock_inst.get_BoundingBox(new_sheet)
        W = bbox.Max.X - bbox.Min.X
        H = bbox.Max.Y - bbox.Min.Y
        min_x, min_y = bbox.Min.X, bbox.Min.Y
        
        margin = W * 0.02 
        tb_x = min_x + margin
        tb_y = min_y + margin
        tb_w = W - (2 * margin) 
        tb_h = H * 0.15 
        top_y = tb_y + tb_h
        
        # --- DISEGNO CARTIGLIO INFERIORE ---
        x0 = tb_x
        x1 = x0 + (tb_w * 0.15) 
        x2 = x1 + (tb_w * 0.30) 
        x3 = x2 + (tb_w * 0.35) 
        x4 = x0 + tb_w          
        
        # ORA USA LO STILE DI LINEA MEDIO (MENO SPESSO)
        medium_line = get_medium_line_style()
        draw_line(new_sheet, x0, tb_y, x4, tb_y, medium_line)
        draw_line(new_sheet, x0, top_y, x4, top_y, medium_line)
        draw_line(new_sheet, x0, tb_y, x0, top_y, medium_line)
        draw_line(new_sheet, x4, tb_y, x4, top_y, medium_line)
        draw_line(new_sheet, x1, tb_y, x1, top_y, medium_line) 
        draw_line(new_sheet, x2, tb_y, x2, top_y, medium_line) 
        draw_line(new_sheet, x3, tb_y, x3, top_y, medium_line) 
        
        title_y = tb_y + (tb_h * 0.80)
        draw_line(new_sheet, x1, title_y, x4, title_y, medium_line)
        x_split_report = x3 + ((x4 - x3) * 0.60)
        draw_line(new_sheet, x_split_report, tb_y, x_split_report, title_y)
        
        tnt_large = get_or_create_title_text_type("FEMUP_Titoli_4mm", 4.0, True)
        tnt_medium = get_or_create_title_text_type("FEMUP_Titoli_3_2mm", 3.2, True)
        mid_y = title_y + ((top_y - title_y) / 2.0)
        create_centered_text(new_sheet, x1 + ((x2 - x1)/2), mid_y, "PSO Parameters", tnt_large)
        create_centered_text(new_sheet, x2 + ((x3 - x2)/2), mid_y, "Variables", tnt_large)
        create_centered_text(new_sheet, x3 + ((x4 - x3)/2), mid_y, "REPORT CALIBRATION", tnt_medium)

        y_logo_split = tb_y + (tb_h * 0.20)
        draw_line(new_sheet, x0, y_logo_split, x1, y_logo_split)
        tnt_logo = get_or_create_title_text_type("FEMUP_Titoli_Logo", 4.0, True)
        create_centered_text(new_sheet, x0 + ((x1 - x0) / 2.0), tb_y + (tb_h * 0.10), "FEMUP-BIM", tnt_logo)

        x_pso_split = x1 + ((x2 - x1) * 0.65)
        draw_line(new_sheet, x_pso_split, tb_y, x_pso_split, title_y)
        data_h = title_y - tb_y      
        row_h_pso = data_h / 6.0     
        for i in range(1, 6):
            draw_line(new_sheet, x1, tb_y + (i * row_h_pso), x2, tb_y + (i * row_h_pso))
            
        tnt_regular = get_or_create_title_text_type("FEMUP_Testo_2_5mm", 2.5, False)
        pso_labels = [u"n of modes considered", u"tolerance of nodes pos.", u"n of particles", u"n of iterations", u"α", u"β"]
        pso_values = [nmodes, tol, nparticles, max_iter, alpha_val, beta_val]
        for i in range(6):
            cy = title_y - (i * row_h_pso) - (row_h_pso / 2.0)
            create_centered_text(new_sheet, x1 + ((x_pso_split - x1)/2), cy, pso_labels[i], tnt_regular)
            create_centered_text(new_sheet, x_pso_split + ((x2 - x_pso_split)/2), cy, pso_values[i], tnt_regular)

        vw = x3 - x2 
        vx1 = x2 + (vw * 0.35); vx2 = vx1 + (vw * 0.12); vx3 = vx2 + (vw * 0.15); vx4 = vx3 + (vw * 0.23) 
        draw_line(new_sheet, vx1, tb_y, vx1, title_y)
        draw_line(new_sheet, vx2, tb_y, vx2, title_y)
        draw_line(new_sheet, vx3, tb_y, vx3, title_y)
        draw_line(new_sheet, vx4, tb_y, vx4, title_y)
        
        var_header_y = title_y - row_h_pso
        draw_line(new_sheet, x2, var_header_y, x3, var_header_y)
        tnt_header_var = get_or_create_title_text_type("FEMUP_Titoli_2_0mm", 2.0, True) 
        header_cy = var_header_y + (row_h_pso / 2.0)
        create_centered_text(new_sheet, vx2 + ((vx3 - vx2)/2.0), header_cy, "- %", tnt_header_var)
        create_centered_text(new_sheet, vx3 + ((vx4 - vx3)/2.0), header_cy, "Nominal value", tnt_header_var)
        create_centered_text(new_sheet, vx4 + ((x3 - vx4)/2.0), header_cy, "+ %", tnt_header_var)
        
        var_data_h = var_header_y - tb_y
        total_props = sum([len(m["proprieta"]) for m in grouped_variables])
        if total_props == 0: total_props = 1 
        row_h_var = var_data_h / total_props
        current_y = var_header_y
        tnt_var = get_or_create_title_text_type("FEMUP_Testo_2_0mm", 2.0, False)
        
        for i, mat in enumerate(grouped_variables):
            num_props = len(mat["proprieta"])
            mat_cy = current_y - ((num_props * row_h_var) / 2.0)
            create_centered_text(new_sheet, x2 + ((vx1 - x2)/2.0), mat_cy, mat["nome"], tnt_var)
            for j, prop_data in enumerate(mat["proprieta"]):
                prop_cy = current_y - (row_h_var / 2.0)
                prop_txt = u"ρ" if prop_data["nome"].strip() == "Dens" else prop_data["nome"].strip()
                create_centered_text(new_sheet, vx1 + ((vx2 - vx1)/2.0), prop_cy, prop_txt, tnt_var)
                min_perc = str(int(round((1.0 - prop_data["xmin"]) * 100)))
                create_centered_text(new_sheet, vx2 + ((vx3 - vx2)/2.0), prop_cy, min_perc, tnt_var)
                xo_val = prop_data["xo"]
                xo_str = str(int(xo_val)) if xo_val.is_integer() else str(xo_val)
                create_centered_text(new_sheet, vx3 + ((vx4 - vx3)/2.0), prop_cy, xo_str, tnt_var)
                max_perc = str(int(round((prop_data["xmax"] - 1.0) * 100)))
                create_centered_text(new_sheet, vx4 + ((x3 - vx4)/2.0), prop_cy, max_perc, tnt_var)
                current_y -= row_h_var
                if j < num_props - 1: draw_line(new_sheet, vx1, current_y, x3, current_y)
            if i < len(grouped_variables) - 1: draw_line(new_sheet, x2, current_y, x3, current_y)

        tnt_huge = get_or_create_title_text_type("FEMUP_Titoli_4_5mm", 4.5, True)
        tnt_bold_modes = get_or_create_title_text_type("FEMUP_Titoli_2_6mm", 2.6, True)
        cy_horiz_report = tb_y + (data_h * 0.72)
        draw_line(new_sheet, x3, cy_horiz_report, x_split_report, cy_horiz_report)
        create_centered_text(new_sheet, x3 + ((x_split_report - x3)/2), cy_horiz_report + ((title_y - cy_horiz_report)/2), "Experimental Modes = {}".format(n_modes_calib), tnt_bold_modes)
        create_centered_text(new_sheet, x_split_report + ((x4 - x_split_report)/2), tb_y + (data_h/2), sheet_num_str, tnt_huge)

        tnt_freq = get_or_create_title_text_type("FEMUP_Testo_2_0mm", 2.0, False)
        cols = 2 
        rows = (len(exp_freqs) + cols - 1) // cols 
        row_step = (cy_horiz_report - tb_y) / (rows + 1)
        for i, freq in enumerate(exp_freqs):
            f_cx = x3 + (i % cols + 0.5) * ((x_split_report - x3) / cols)
            f_cy = cy_horiz_report - ((i // cols + 1) * row_step)
            create_centered_text(new_sheet, f_cx, f_cy, "f{} = {:.3f}".format(i+1, freq), tnt_freq)

        # ==========================================
        # --- UPPER LAYOUT POSITION ---
        # ==========================================
        available_H = H - tb_h - (margin * 2)

        w_model = tb_w * 0.46      
        w_right = tb_w * 0.22      
        w_mid = tb_w * 0.24        
        w_bottom_img = tb_w * 0.30 
        
        cx_left = x0 + (w_model / 2.0)
        cx_freq = x0 + (w_bottom_img / 2.0)
        cx_tab1_centro = x4 - (w_right / 2.0)
        cx_mid = x0 + (tb_w * 0.62)
        gap_immagini_basse = tb_w * 0.03
        cx_mac = cx_freq + (w_bottom_img / 2.0) + gap_immagini_basse + (w_bottom_img / 2.0)

        y_top_row = top_y + (available_H * 0.95) 
        y_bottom_row = top_y + (available_H * 0.08) 

        # 1. 3D Model and Particles
        place_image_with_border(new_sheet, image_model_path, cx_left, y_top_row, w_model, align="top")
        place_image_with_border(new_sheet, img_part, cx_mid, y_top_row, w_mid, align="top")

        # 2. Frequencies and MAC Matrix
        place_image_with_border(new_sheet, img_freq, cx_freq, y_bottom_row, w_bottom_img, align="bottom")
        place_image_with_border(new_sheet, img_mac, cx_mac, y_bottom_row, w_bottom_img, align="bottom")

        # 3. Cost graph
        cy_cost = top_y + (available_H * 0.54)
        place_image_with_border(new_sheet, img_cost, cx_mid, cy_cost, w_mid, align="center")

        # 4. TAB 1 - Calibrated Parameters 
        cy_tab1_start = y_top_row
        cw_calib = [w_right * 0.40, w_right * 0.22, w_right * 0.28] 
        calib_headers = ["Material", "Prop.", "Value"]
        title_tab1 = "=== CALIBRATED PARAMS ==="
        
        if calib_data:
            draw_dynamic_table(sheet=new_sheet, center_x=cx_tab1_centro, start_y=cy_tab1_start, 
                               title=title_tab1, headers=calib_headers, data_matrix=calib_data, 
                               col_widths=cw_calib, row_height=(available_H * 0.02), 
                               tnt_id=tnt_var, tnt_bold_id=tnt_header_var)

        # ==========================================
        # --- 5. TAB 2 (DYNAMIC OPTIMIZATION) ---
        # ==========================================
        
        h_mac = w_bottom_img * 0.75 
        try:
            if os.path.exists(img_mac):
                img_file = System.Drawing.Image.FromFile(img_mac)
                aspect = float(img_file.Height) / float(img_file.Width)
                img_file.Dispose()
                h_mac = w_bottom_img * aspect
        except: pass
        
        cy_immagini_inferiori = y_bottom_row + (h_mac / 2.0)
        row_h_tab2 = available_H * 0.02
        h_totale_tab2 = row_h_tab2 * (2.5 + len(results_data))
        cy_tab2_start = cy_immagini_inferiori + (h_totale_tab2 / 2.0)
        
        bordo_destro_mac = cx_mac + (w_bottom_img / 2.0)
        cx_tab2 = bordo_destro_mac + ((x4 - bordo_destro_mac) / 2.0)
        
        w_disponibile_tab2 = (x4 - bordo_destro_mac) * 0.85
        cw_results = [w_disponibile_tab2 / 6.0] * 6 
        
        results_headers = ["UNC[Hz]", "ERR[%]", "MAC_unc", "CAL[Hz]", "ERR[%]", "MAC_cal"]
        title_tab2 = "=== FREQUENCIES AND MAC COMPARISON ==="
        
        draw_dynamic_table(sheet=new_sheet, center_x=cx_tab2, start_y=cy_tab2_start, 
                           title=title_tab2, headers=results_headers, data_matrix=results_data, 
                           col_widths=cw_results, row_height=row_h_tab2, 
                           tnt_id=tnt_var, tnt_bold_id=tnt_header_var)

    t.Commit()

forms.alert("Report generated. Check in your sheet list.")