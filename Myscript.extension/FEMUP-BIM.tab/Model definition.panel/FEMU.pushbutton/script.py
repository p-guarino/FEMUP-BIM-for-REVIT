# -*- coding: utf-8 -*-
__title__ = "     FEMU     "
__doc__ = "Select materials and sensors from .inp file"
__author__ = "Pasquale Guarino"

from pyrevit import forms, script, revit
from Autodesk.Revit.DB import *
import os
import re
from System.Windows.Forms import Form, Button, Application, CheckBox, TextBox, Label, DialogResult, AnchorStyles, ComboBox
from System.Drawing import Point, Size, Font, FontStyle
import math

# === CONFIGURATION ===
family_name = "Point" 
sensor_labels = ["X", "Y", "Z"]

# === Paths ===
user_documents_folder = os.path.expanduser('~\\Documents')
log_file_name = "log_directory.txt"
log_file_path = os.path.join(user_documents_folder, log_file_name)
log_directory = None

# === Import INP file and save parts/materials/assemblies ===
def import_and_save_inp_parts():
    fp = forms.pick_file(title="Select .inp File", file_ext="inp")
    if not fp:
        forms.alert("No file selected.")
        return

    part_names = []
    material_names = []
    instance_names = []

    # Smart Regex: Searches for 'name=', captures everything until a comma or newline
    part_pattern = re.compile(r"\*Part\b.*?name\s*=\s*([^,\n\r]+)", re.IGNORECASE)
    material_pattern = re.compile(r"\*Material\b.*?name\s*=\s*([^,\n\r]+)", re.IGNORECASE)
    instance_pattern = re.compile(r"\*Instance\b.*?name\s*=\s*([^,\n\r]+)", re.IGNORECASE)

    try:
        with open(fp, 'r') as f:
            for line in f:
                line = line.strip()
                
                part_match = part_pattern.search(line)
                if part_match:
                    # .strip() removes whitespaces, .strip('\"\'') removes quotes
                    clean_name = part_match.group(1).strip().strip('\"\'')
                    part_names.append(clean_name)
                    
                material_match = material_pattern.search(line)
                if material_match:
                    clean_name = material_match.group(1).strip().strip('\"\'')
                    material_names.append(clean_name)
                    
                instance_match = instance_pattern.search(line)
                if instance_match:
                    clean_name = instance_match.group(1).strip().strip('\"\'')
                    instance_names.append(clean_name)

        out_dir = os.path.dirname(fp)
        out_file = os.path.join(out_dir, "inp_parts_materials.txt")

        with open(out_file, 'w') as f:
            f.write("Parts:\n")
            for name in part_names:
                f.write(name + "\n")
            f.write("\nMaterials:\n")
            for name in material_names:
                f.write(name + "\n")
            f.write("\nAssemblies:\n")
            for name in instance_names:
                f.write(name + "\n")

        forms.alert("INP file parsed successfully.\nData saved to:\n{}".format(out_file))

    except Exception as e:
        forms.alert("Error importing .inp file:\n{}".format(e))

# === Get unique selected points ===
def get_selected_points():
    selection = revit.get_selection()
    if not selection:
        forms.alert("Please select mesh nodes.")
        script.exit()
    seen = set()
    pts = []
    for el in selection:
        if isinstance(el, FamilyInstance) and el.Symbol.Family.Name == family_name:
            p = el.Location.Point
            key = (round(p.X,6), round(p.Y,6), round(p.Z,6))
            if key not in seen:
                seen.add(key)
                pts.append(p)
    if not pts:
        forms.alert("No valid points found in selection.")
        script.exit()
    return pts

# === Save/load directory ===
def save_directory_to_file(directory):
    try:
        if not os.path.isdir(user_documents_folder): os.makedirs(user_documents_folder)
        with open(log_file_path, 'w') as f: f.write(directory)
    except Exception as e:
        forms.alert("Error saving directory preference:\n{}".format(e))

def load_directory_from_file():
    global log_directory
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r') as f:
                path = f.read().strip()
            if os.path.isdir(path): log_directory = path
        except: pass

# === Ask for folder ===
def ask_directory():
    global log_directory
    d = forms.pick_folder(title="Select Folder to Save Files")
    if not d:
        forms.alert("No folder selected.")
        script.exit()
    log_directory = d
    save_directory_to_file(log_directory)
    forms.alert("Working directory set to:\n{}".format(log_directory))

# === Get next index ===
def get_next_index():
    existing=[]; p=re.compile(r"log_ch_(\d+)\.txt$")
    for fn in os.listdir(log_directory or '.'):
        m=p.match(fn)
        if m: existing.append(int(m.group(1)))
    return max(existing)+1 if existing else 1

# === Save log ===
def save_sensor_log(points, dirs, element_name="", direction_values=None):
    if not log_directory: forms.alert("No working directory selected."); script.exit()
    path = os.path.join(log_directory, "log_ch_{}.txt".format(get_next_index()))
    try:
        with open(path,'w') as f:
            for p in points:
                base="{0:.6f}, {1:.6f}, {2:.6f}".format(p.X,p.Y,p.Z)
                flags = []
                for d_label in sensor_labels:
                    if d_label in dirs:
                        val = direction_values.get(d_label, 1) if direction_values else 1
                        flags.append(val)
                    else:
                        flags.append(0)
                line = base + ", " + ", ".join(str(x) for x in flags)
                if element_name:
                    line += ", " + element_name
                f.write(line+"\n")
    except Exception as e:
        forms.alert("Error saving sensor log:\n{}".format(e)); script.exit()

# === Export ===
def export_sensor_positions():
    if not log_directory:
        forms.alert("No working directory selected.")
        script.exit()
    p = re.compile(r"log_ch_(\d+)\.txt$")
    items = []
    for fn in os.listdir(log_directory):
        m = p.match(fn)
        if m:
            items.append((int(m.group(1)), fn))
    if not items:
        forms.alert("No individual sensor logs found to export.")
        return
    items.sort(key=lambda x: x[0])
    out = os.path.join(log_directory, "Sensors.txt")
    try:
        with open(out, 'w') as outf:
            outf.write("Coord x, Coord y, Coord z, dir1, dir2, dir3, Instance Part\n")
            for _, fn in items:
                with open(os.path.join(log_directory, fn), 'r') as inf:
                    outf.write(inf.read())
        for _, fn in items:
            os.remove(os.path.join(log_directory, fn))
        forms.alert("Sensors exported successfully to:\n{}".format(out))
    except Exception as e:
        forms.alert("Error exporting sensor positions:\n{}".format(e))
        script.exit()

# === Save material properties ===
def save_material_properties(name, e_vals, rho_vals):
    if not log_directory:
        forms.alert("No working directory selected.")
        return

    file_name = "Materials_Properties.txt"
    path = os.path.join(log_directory, file_name)

    try:
        # Prepare the new data row
        line_data = [name] + e_vals + rho_vals
        new_line = ", ".join(str(v) for v in line_data) + "\n"
        header = "Material, E_min, E_nom, E_max, Dens_min, Dens_nom, Dens_max\n"

        existing_lines = []
        if os.path.exists(path):
            with open(path, 'r') as f:
                existing_lines = f.readlines()

        # Clean empty lines to avoid unwanted whitespace
        valid_lines = [line for line in existing_lines if line.strip()]

        # Always write the current header: it also upgrades a file left over from an
        # older version, which still carried the unused v_min / v_nom / v_max columns.
        final_lines = [header]

        # Append all previously saved material lines,
        # DISCARDING any old row of the material we are currently updating
        data_lines = valid_lines[1:] if valid_lines and valid_lines[0].startswith("Material") else valid_lines
        for line in data_lines:
            if line.strip().startswith(name + ","):
                continue
            # Keep only the 7 current columns: a row written by an older version
            # carries three extra Poisson values that are no longer used.
            fields = [f.strip() for f in line.strip().split(",")]
            final_lines.append(", ".join(fields[:7]) + "\n")

        # Append the new material at the end
        final_lines.append(new_line)

        # Write everything back to the file cleanly
        with open(path, 'w') as f:
            f.writelines(final_lines)

        forms.alert("Material properties assigned successfully.")
    except Exception as e:
        forms.alert("Error saving material properties:\n{}".format(e))

# === UI Forms ===
class ActionForm(Form):
    def __init__(self):
        self.Text = "Choose Action"
        self.Size = Size(400, 450)
        self.StartPosition = self.StartPosition.CenterScreen
        self.result = None

        actions = [
            ("Select Folder", "Select Folder"),
            ("Import INP File", "Import INP File"),
            ("Assign Sensor Positions", "Assign Sensor Positions"),
            ("Export Sensor Positions", "Export Sensor Positions"),
            ("Assign Material Properties", "Assign Material Properties")
        ]

        for i, (label, result_value) in enumerate(actions):
            btn = Button()
            btn.Text = label
            btn.Size = Size(300, 50)
            btn.Location = Point((self.ClientSize.Width - btn.Width) // 2, 30 + i * 65)
            btn.Anchor = btn.Anchor | AnchorStyles.Left | AnchorStyles.Right
            btn.Click += self._make_handler(result_value)
            self.Controls.Add(btn)

    def _make_handler(self, value):
        def handler(sender, args):
            self.result = value
            self.Close()
        return handler

class SensorForm(Form):
    def __init__(self):
        self.Text = "Sensor Configuration"
        self.Size = Size(500, 360)
        self.StartPosition = self.StartPosition.CenterScreen
        self.directions = []
        self.direction_values = {}  
        self.selected_part = None
        self.DialogResult = DialogResult.Cancel 

        y_positions = [30, 65, 100] 

        self.chk_x = CheckBox(Text="X", Location=Point(40, y_positions[0]), Size=Size(40, 30))
        self.chk_y = CheckBox(Text="Y", Location=Point(40, y_positions[1]), Size=Size(40, 30))
        self.chk_z = CheckBox(Text="Z", Location=Point(40, y_positions[2]), Size=Size(40, 30))

        self.chk_x_plus = CheckBox(Text="+", Location=Point(90, y_positions[0]), Size=Size(40, 30))
        self.chk_x_minus = CheckBox(Text="-", Location=Point(140, y_positions[0]), Size=Size(40, 30))

        self.chk_y_plus = CheckBox(Text="+", Location=Point(90, y_positions[1]), Size=Size(40, 30))
        self.chk_y_minus = CheckBox(Text="-", Location=Point(140, y_positions[1]), Size=Size(40, 30))

        self.chk_z_plus = CheckBox(Text="+", Location=Point(90, y_positions[2]), Size=Size(40, 30))
        self.chk_z_minus = CheckBox(Text="-", Location=Point(140, y_positions[2]), Size=Size(40, 30))

        for plus_chk in [self.chk_x_plus, self.chk_y_plus, self.chk_z_plus]:
            plus_chk.Checked = True

        self.chk_x_plus.CheckedChanged += lambda s,e: self._toggle_sign(self.chk_x_plus, self.chk_x_minus)
        self.chk_x_minus.CheckedChanged += lambda s,e: self._toggle_sign(self.chk_x_minus, self.chk_x_plus)

        self.chk_y_plus.CheckedChanged += lambda s,e: self._toggle_sign(self.chk_y_plus, self.chk_y_minus)
        self.chk_y_minus.CheckedChanged += lambda s,e: self._toggle_sign(self.chk_y_minus, self.chk_y_plus)

        self.chk_z_plus.CheckedChanged += lambda s,e: self._toggle_sign(self.chk_z_plus, self.chk_z_minus)
        self.chk_z_minus.CheckedChanged += lambda s,e: self._toggle_sign(self.chk_z_minus, self.chk_z_plus)

        self.lbl_part = Label(Text="Select Instance:", Location=Point(40, 145), Size=Size(300, 25))
        self.part_dropdown = ComboBox()
        self.part_dropdown.Location = Point(40, 175)
        self.part_dropdown.Size = Size(300, 30)
        self._load_instances()

        btn_ok = Button(Text="OK", Size=Size(100, 40))
        btn_ok.Location = Point((self.ClientSize.Width - btn_ok.Width) // 2, 230)
        btn_ok.Click += self._on_ok

        controls = [
            self.chk_x, self.chk_x_plus, self.chk_x_minus,
            self.chk_y, self.chk_y_plus, self.chk_y_minus,
            self.chk_z, self.chk_z_plus, self.chk_z_minus,
            self.lbl_part, self.part_dropdown, btn_ok
        ]
        for ctrl in controls:
            self.Controls.Add(ctrl)

    def _toggle_sign(self, sender, other):
        if sender.Checked:
            other.Checked = False
        elif not other.Checked: 
            sender.Checked = True

    def _load_instances(self):
        global log_directory 
        if not log_directory: return
        parts_file = os.path.join(log_directory, "inp_parts_materials.txt")
        self.part_dropdown.Items.Clear()
        if not os.path.exists(parts_file): return
        with open(parts_file, 'r') as f:
            lines = f.readlines()
        instance_section = False
        for line in lines:
            l = line.strip()
            if l.lower() == "assemblies:":
                instance_section = True
                continue
            if instance_section and l:
                self.part_dropdown.Items.Add(l)
        if self.part_dropdown.Items.Count > 0:
            self.part_dropdown.SelectedIndex = 0

    def _on_ok(self, sender, args):
        self.directions = []
        self.direction_values = {}

        for dir_name, chk, chk_plus, chk_minus in [
            ("X", self.chk_x, self.chk_x_plus, self.chk_x_minus),
            ("Y", self.chk_y, self.chk_y_plus, self.chk_y_minus),
            ("Z", self.chk_z, self.chk_z_plus, self.chk_z_minus)
        ]:
            if chk.Checked:
                self.directions.append(dir_name)
                self.direction_values[dir_name] = -1 if chk_minus.Checked else 1
            if chk.Checked and not chk_plus.Checked and not chk_minus.Checked:
                forms.alert("Please select '+' or '-' for the {} direction.".format(dir_name))
                return 

        if not self.directions:
            forms.alert("Select at least one direction.")
            return
        if self.part_dropdown.SelectedItem is None and self.part_dropdown.Items.Count > 0 :
            forms.alert("Please select an instance.")
            return
            
        self.selected_part = self.part_dropdown.SelectedItem if self.part_dropdown.Items.Count > 0 else "N/A" 
        self.DialogResult = DialogResult.OK 
        self.Close()

class MaterialForm(Form):
    def __init__(self):
        self.Text = "Assign Material Properties"
        self.Size = Size(550, 440)
        self.StartPosition = self.StartPosition.CenterScreen
        font = Font("Segoe UI", 9)

        self.lbl_name = Label(Text="Select Material:", Location=Point(30, 20), Size=Size(480, 25), Font=font)
        self.Controls.Add(self.lbl_name)

        self.material_dropdown = ComboBox(Location=Point(30, 50), Size=Size(480, 30), Font=font)
        self.Controls.Add(self.material_dropdown)
        self._load_materials()

        y_start = 100; y_gap = 80; box_width = 140; box_height = 28; label_width = 300

        self.chk_e = CheckBox(Text="Elastic Modulus E (MPa)", Location=Point(30, y_start), Size=Size(label_width, 25), Font=font)
        self.Controls.Add(self.chk_e)
        self.txt_e_min = TextBox(Location=Point(30, y_start + 30), Size=Size(box_width, box_height), Font=font) 
        self.txt_e_nom = TextBox(Location=Point(190, y_start + 30), Size=Size(box_width, box_height), Font=font) 
        self.txt_e_max = TextBox(Location=Point(350, y_start + 30), Size=Size(box_width, box_height), Font=font) 
        self.Controls.Add(self.txt_e_min); self.Controls.Add(self.txt_e_nom); self.Controls.Add(self.txt_e_max)

        y_start += y_gap
        self.chk_rho = CheckBox(Text="Mass Density (kg/m³)", Location=Point(30, y_start), Size=Size(label_width, 25), Font=font)
        self.Controls.Add(self.chk_rho)
        self.txt_rho_min = TextBox(Location=Point(30, y_start + 30), Size=Size(box_width, box_height), Font=font) 
        self.txt_rho_nom = TextBox(Location=Point(190, y_start + 30), Size=Size(box_width, box_height), Font=font) 
        self.txt_rho_max = TextBox(Location=Point(350, y_start + 30), Size=Size(box_width, box_height), Font=font) 
        self.Controls.Add(self.txt_rho_min); self.Controls.Add(self.txt_rho_nom); self.Controls.Add(self.txt_rho_max)

        # The Poisson ratio is not a calibration variable, so it is neither asked for here
        # nor written to Materials_Properties.txt. Set it directly in the .inp file.

        btn_ok = Button(Text="Save", Location=Point(190, y_start + 80), Size=Size(150, 40), Font=Font("Segoe UI", 10, FontStyle.Bold))
        btn_ok.Click += self._on_save
        self.Controls.Add(btn_ok)

    def _load_materials(self):
        global log_directory 
        if not log_directory: return
        materials_file = os.path.join(log_directory, "inp_parts_materials.txt")
        if not os.path.exists(materials_file): return
        with open(materials_file, 'r') as f: lines = f.readlines()
        material_section = False
        for line in lines:
            l = line.strip()
            if l.lower() == "materials:": material_section = True; continue
            if l.lower() == "assemblies:": break
            if material_section and l: self.material_dropdown.Items.Add(l)
        if self.material_dropdown.Items.Count > 0: self.material_dropdown.SelectedIndex = 0

    def _get_value(self, textbox):
        try: return float(textbox.Text.strip()) if textbox.Text.strip() else 0
        except: return 0

    def _on_save(self, sender, args):
        name = self.material_dropdown.SelectedItem
        if not name: forms.alert("Select a material."); return

        e_vals = [self._get_value(self.txt_e_min), self._get_value(self.txt_e_nom), self._get_value(self.txt_e_max)] if self.chk_e.Checked else [0,0,0]
        rho_vals = [self._get_value(self.txt_rho_min), self._get_value(self.txt_rho_nom), self._get_value(self.txt_rho_max)] if self.chk_rho.Checked else [0,0,0]
        save_material_properties(name, e_vals, rho_vals)
        self.Close()

def get_family_symbol_by_name(doc, family_name_str):
    collector = FilteredElementCollector(doc).OfClass(FamilySymbol)
    for s in collector:
        if s.Family.Name == family_name_str:
            if not s.IsActive:
                try:
                    s.Activate()
                    doc.Regenerate() 
                except Exception:
                    continue 
            return s 
    return None 

def load_family_if_missing(doc, fam_name):
    """Loads a family from the script directory if it isn't already in the document."""
    if not get_family_symbol_by_name(doc, fam_name):
        script_dir = os.path.dirname(__file__)
        file_name = fam_name + ".rfa"
        full_path = os.path.join(script_dir, file_name)
        if os.path.exists(full_path):
            try:
                doc.LoadFamily(full_path)
            except Exception as e:
                print("Could not load family {}: {}".format(fam_name, e))

def place_sensor_arrows_visualization(doc, points, directions_selected, direction_sign_values):
    # Dictionaries mapping axis and sign to specific family names
    arrow_family_names = {
        ("X", 1): "X axis",
        ("X", -1): "X axis",  # We rotate this one
        ("Y", 1): "Y axis",
        ("Y", -1): "Y axis",  # We rotate this one
        ("Z", 1): "Z axis",
        ("Z", -1): "Z axis_neg" # The dedicated pre-flipped family for negative Z
    }

    # Ensure all required families are loaded before starting
    required_families = set(arrow_family_names.values())
    
    t_load = Transaction(doc, "Load Sensor Families")
    t_load.Start()
    for fam_name in required_families:
        load_family_if_missing(doc, fam_name)
    t_load.Commit()

    family_symbols = {}
    missing_symbols = set()
    
    # Cache all symbols needed based on current selection
    for axis_key in directions_selected:
        sign = direction_sign_values.get(axis_key, 1)
        fam_name = arrow_family_names.get((axis_key, sign))
        
        symbol = get_family_symbol_by_name(doc, fam_name)
        if not symbol:
            missing_symbols.add(fam_name)
        else:
            family_symbols[(axis_key, sign)] = symbol

    if missing_symbols:
        forms.alert("Missing Family Symbols:\n{}\nPlease ensure these families exist in the script folder.".format(", ".join(missing_symbols)))
        return

    t = Transaction(doc, "Assign Sensors")
    try:
        t.Start()
        
        # Setup Red Color Override for Axes
        red_color = Color(255, 0, 0)
        red_override = OverrideGraphicSettings()
        red_override.SetProjectionLineColor(red_color)
        
        solid_fill_collector = FilteredElementCollector(doc).OfClass(FillPatternElement)
        solid_pattern_id = None
        for fp in solid_fill_collector:
            if fp.GetFillPattern().IsSolidFill:
                solid_pattern_id = fp.Id
                break
                
        if solid_pattern_id:
            try:
                red_override.SetSurfaceForegroundPatternId(solid_pattern_id)
                red_override.SetSurfaceForegroundPatternColor(red_color)
            except AttributeError:
                pass 

        for p_coord in points: 
            for axis_key in directions_selected: 
                sign = direction_sign_values.get(axis_key, 1) 
                
                # Get the appropriate symbol (standard or pre-flipped for Z)
                current_symbol = family_symbols.get((axis_key, sign))
                if not current_symbol: continue 

                arrow_instance = doc.Create.NewFamilyInstance(p_coord, current_symbol, Structure.StructuralType.NonStructural)
                doc.Regenerate() 

                if not arrow_instance: continue
                
                doc.ActiveView.SetElementOverrides(arrow_instance.Id, red_override)

                # Only attempt rotation for X and Y if sign is negative.
                # Z is handled by loading the pre-flipped 'Z axis_neg' family.
                if sign == -1 and axis_key in ["X", "Y"]:
                    rotation_axis_vector = XYZ.BasisZ
                    rotation_line = Line.CreateBound(p_coord, p_coord + rotation_axis_vector)
                    try:
                        ElementTransformUtils.RotateElement(doc, arrow_instance.Id, rotation_line, math.pi)
                    except Exception:
                        pass 

        t.Commit()
        forms.alert("Sensors assigned and configured successfully.")

    except Exception as e:
        if t.HasStarted() and t.GetStatus() == TransactionStatus.Started:
            t.RollBack()
        forms.alert("An error occurred during sensor assignment:\n{}".format(e))

def main():
    load_directory_from_file()

    form = ActionForm()
    Application.EnableVisualStyles() 
    Application.Run(form) 
    action = form.result

    if action == "Import INP File":
        import_and_save_inp_parts()
    elif action == "Select Folder":
        ask_directory()
    elif action == "Assign Sensor Positions":
        if not log_directory:
            forms.alert("Please Select Folder first.")
            return

        pts = get_selected_points() 
        
        sensor_form = SensorForm()
        sensor_form.ShowDialog()  

        if sensor_form.DialogResult == DialogResult.OK:
            save_sensor_log(pts, sensor_form.directions, sensor_form.selected_part, sensor_form.direction_values)
            place_sensor_arrows_visualization(revit.doc, pts, sensor_form.directions, sensor_form.direction_values)

    elif action == "Export Sensor Positions":
        export_sensor_positions()
    elif action == "Assign Material Properties":
        if not log_directory:
            forms.alert("Please Select Folder first.")
            return
        mf = MaterialForm()
        Application.Run(mf) 

if __name__ == "__main__":
    main()