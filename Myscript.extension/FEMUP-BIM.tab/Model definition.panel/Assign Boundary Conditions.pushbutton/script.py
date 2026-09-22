# -*- coding: utf-8 -*-
__title__ = "Assign Boundary\nConditions"
__doc__ = "Assign boundary conditions."
__author__ = "Pasquale Guarino"

from pyrevit import forms, script, revit
from Autodesk.Revit.DB import *
import os
import re
from System.Windows.Forms import Form, Button, Application, CheckBox, TextBox, Label, SaveFileDialog, DialogResult, AnchorStyles, ComboBox, ComboBoxStyle
from System.Drawing import Point, Size

# === CONFIGURATION ===
family_name = "Point"
labels = ["X", "Y", "Z", "URX", "URY", "URZ"]

# === Paths ===
user_documents_folder = os.path.expanduser('~\\Documents')
log_file_name = "log_directory.txt"
log_file_path = os.path.join(user_documents_folder, log_file_name)
log_directory = None

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
        forms.alert("No valid points found.")
        script.exit()
    return pts

def save_directory_to_file(directory):
    try:
        if not os.path.isdir(user_documents_folder): os.makedirs(user_documents_folder)
        with open(log_file_path, 'w') as f: f.write(directory)
    except Exception as e:
        forms.alert("Error saving directory:\n{}".format(e))

def load_directory_from_file():
    global log_directory
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r') as f:
                path = f.read().strip()
                if os.path.isdir(path): log_directory = path
        except: pass

def get_next_index():
    existing=[]; p=re.compile(r"log_bc_(\d+)\.txt$")
    for fn in os.listdir(log_directory or '.'):
        m=p.match(fn)
        if m: existing.append(int(m.group(1)))
    return max(existing)+1 if existing else 1

def save_bc_log(points, dirs, element_name=""):
    if not log_directory:
        forms.alert("No directory selected.")
        script.exit()
    dlg = SaveFileDialog()
    dlg.InitialDirectory = log_directory
    dlg.Filter = "Text files (*.txt)|*.txt"
    dlg.Title = "Save BC Log As"
    dlg.FileName = "log_bc_{}.txt".format(get_next_index())
    if dlg.ShowDialog() != DialogResult.OK:
        return
    path = dlg.FileName
    try:
        with open(path,'w') as f:
            # --- AGGIUNTA DELLA RIGA DI INTESTAZIONE ---
            header_line = "Coord x, Coord y, Coord z, U1, U2, U3, UR1, UR2, UR3, Instance Part\n"
            f.write(header_line)
            # --- FINE AGGIUNTA ---

            for p in points:
                base="{0:.6f}, {1:.6f}, {2:.6f}".format(p.X,p.Y,p.Z)
                flags=[1 if d in dirs else 0 for d in labels]
                
                line = base + ", " + ", ".join(str(x) for x in flags)
                if element_name:
                    line += ", " + element_name
                f.write(line+"\n")
        forms.alert("Boundary conditions saved to:\n{}".format(path))
    except Exception as e:
        forms.alert("Error saving BC log:\n{}".format(e))
        script.exit()

# --- Funzione per caricare le istanze ---
def _load_instances(part_dropdown_control, directory):
    parts_file = os.path.join(directory, "inp_parts_materials.txt")
    part_dropdown_control.Items.Clear()
    if not os.path.exists(parts_file):
        forms.alert("File inp_parts_materials.txt not found in directory: {}".format(directory))
        return
    with open(parts_file, 'r') as f:
        lines = f.readlines()
    instance_section = False
    for line in lines:
        l = line.strip()
        if l.lower() == "assemblies:":
            instance_section = True
            continue
        if instance_section and l:
            part_dropdown_control.Items.Add(l)
    if part_dropdown_control.Items.Count > 0:
        part_dropdown_control.SelectedIndex = 0

class BCForm(Form):
    def __init__(self):
        self.Text = "Assign Boundary Conditions"
        self.Size = Size(420, 380)
        self.StartPosition = self.StartPosition.CenterScreen
        self.directions = []
        self.element_name = None

        self.checkboxes = []
        positions = [(40, 30), (140, 30), (240, 30), (40, 80), (140, 80), (240, 80)]
        for i, label in enumerate(labels):
            cb = CheckBox(Text=label, Location=Point(*positions[i]), Size=Size(80, 30))
            self.Controls.Add(cb)
            self.checkboxes.append(cb)

        self.lbl_part = Label(Text="Select Part/Assembly:", Location=Point(40, 140), Size=Size(300, 25))
        self.part_dropdown = ComboBox(Location=Point(40, 170), Size=Size(300, 30))
        self.part_dropdown.DropDownStyle = ComboBoxStyle.DropDownList
        self.Controls.Add(self.lbl_part)
        self.Controls.Add(self.part_dropdown)

        btn_ok = Button(Text="OK", Size=Size(100, 40))
        btn_ok.Location = Point((self.ClientSize.Width - btn_ok.Width) // 2, 240)
        btn_ok.Click += self._on_ok

        self.Controls.Add(btn_ok)

        global log_directory
        if log_directory:
            _load_instances(self.part_dropdown, log_directory)
        else:
            forms.alert("Log directory not set. Cannot load parts from file.")

    def _on_ok(self, sender, args):
        self.directions = []
        for i, cb in enumerate(self.checkboxes):
            if cb.Checked:
                self.directions.append(labels[i])

        if self.part_dropdown.SelectedItem:
            self.element_name = self.part_dropdown.SelectedItem.ToString()
        else:
            forms.alert("Please select a part from the dropdown.")
            return

        if not self.directions:
            forms.alert("Select at least one direction.")
            return
            
        self.Close()

# === MAIN ===
load_directory_from_file()
points = get_selected_points()
form = BCForm()
Application.Run(form)

if form.directions and form.element_name:
    save_bc_log(points, form.directions, form.element_name)