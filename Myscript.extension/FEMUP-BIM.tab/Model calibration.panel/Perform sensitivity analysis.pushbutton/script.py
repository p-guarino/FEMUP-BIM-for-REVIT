# -*- coding: utf-8 -*-
import clr
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

import System
from System.Windows.Forms import Application, Form, Label, TextBox, Button, ComboBox, ListBox, NumericUpDown, FolderBrowserDialog, OpenFileDialog, DialogResult, MessageBox, MessageBoxButtons, ProgressBar, Cursors, MethodInvoker
from System.Drawing import Point, Size, Font, FontStyle, Color
import os
import shutil
import subprocess
import threading
import re

TEMPLATE_NAME = "Launch_Sensitivity_Analysis.py"
RUN_NAME = "Launch_Sensitivity_Analysis_run.py"
MATERIALS_TXT = "materials sensitivity analysis.txt"
LOG_DIR_FILE = os.path.join(os.path.expanduser("~\\Documents"), "log_directory.txt")
EXP_FREQ_PATH_FILE = "experimental_frequency_path.txt"
EXP_MODES_PATH_FILE = "experimental_modeshape_path.txt"

# ======================================================================
# INP parsing
# ======================================================================
NAME_RE = re.compile(r'name\s*=\s*("[^"]*"|[^,\n\r]+)', re.IGNORECASE)

def _get_name(line):
    m = NAME_RE.search(line)
    if not m:
        return None
    return m.group(1).strip().strip('"\'')

def _first_float(line):
    tok = line.split(",")[0].strip()
    try:
        return float(tok)
    except ValueError:
        return None

def parse_inp(path):
    """Returns (parts, instances, materials).
    materials = list of dict {"name", "E", "Dens"} in the order found in the .inp"""
    parts = []; instances = []; materials = []; by_name = {}
    current = None      # current material block
    expect = None       # "E" or "Dens": next data line holds that value
    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("**"):
                continue
            if line[0] == "*":
                expect = None
                low = line.lower()
                if low.startswith("*material"):
                    name = _get_name(line)
                    if name is None:
                        current = None
                        continue
                    if name in by_name:
                        current = by_name[name]
                    else:
                        current = {"name": name, "E": None, "Dens": None}
                        by_name[name] = current
                        materials.append(current)
                elif low.startswith("*elastic"):
                    # only isotropic elasticity (default type) has a single E
                    if current is not None and ("type" not in low or "iso" in low):
                        expect = "E"
                elif low.startswith("*density"):
                    if current is not None:
                        expect = "Dens"
                elif low.startswith("*part"):
                    n = _get_name(line)
                    if n and n not in parts: parts.append(n)
                elif low.startswith("*instance"):
                    n = _get_name(line)
                    if n and n not in instances: instances.append(n)
                continue
            if expect is not None:
                v = _first_float(line)
                if v is not None and current[expect] is None:
                    current[expect] = v
                expect = None
    return parts, instances, materials

def _fmt_value(v):
    return repr(v) if v is not None else "n/a"

def write_materials_txt(folder, materials):
    path = os.path.join(folder, MATERIALS_TXT)
    with open(path, "w") as f:
        f.write("Material, E, Dens\n")
        for m in materials:
            f.write("{}, {}, {}\n".format(m["name"], _fmt_value(m["E"]), _fmt_value(m["Dens"])))
    return path

def build_entries(materials):
    """[(name, [(prop, value), ...]), ...] with only properties > 0"""
    entries = []
    for m in materials:
        props = [(p, m[p]) for p in ("E", "Dens") if m[p] is not None and m[p] > 0]
        if props:
            entries.append((m["name"], props))
    return entries

# ======================================================================
# _run file generation
# ======================================================================
KEY_RE = re.compile(r'^\s*["\']([^"\']+)["\']\s*:')
MAT_COMMENT_RE = re.compile(r'^\s*#\s*\(\s*\d+\s+materials', re.IGNORECASE)
DELTAX_RE = re.compile(r'(RunSensAna\s*\(\s*deltax\s*=\s*)[^)]*')

def _fmt_multiline(rows, indent):
    inner = indent + "    "
    out = ["["]
    for i, (txt, comment) in enumerate(rows):
        last = (i == len(rows) - 1)
        s = "\n" + inner + txt + ("" if last else ",")
        if comment:
            s += ("   " if last else "  ") + "# " + comment
        out.append(s)
    out.append("\n" + indent + "]")
    return "".join(out)

def build_run_lines(lines, entries, single, delta_pct):
    """Returns (new_lines, missing_keys)"""
    n_mat = len(entries)
    n_par = sum(len(p) for _, p in entries)

    multi = {
        "xo": [(", ".join(repr(v) for _, v in props), name) for name, props in entries],
        "Material": [(", ".join('"{}"'.format(name) for _ in props), None) for name, props in entries],
        "PROP": [(", ".join('"{}"'.format(p) for p, _ in props), None) for name, props in entries],
    }

    found = set()
    new_lines = []
    skip = False
    for line in lines:
        if skip:
            if "]" in line: skip = False
            continue

        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        m = KEY_RE.match(line)
        if m:
            key = m.group(1)
            opens_list = "[" in line and "]" not in line

            if key in multi:
                new_lines.append('{}"{}": {},\n'.format(indent, key, _fmt_multiline(multi[key], indent)))
                found.add(key)
                if opens_list: skip = True
                continue

            if key in single:
                new_lines.append('{}"{}": {},\n'.format(indent, key, single[key]))
                found.add(key)
                if opens_list: skip = True
                continue

            if key in ("xmin", "xmax"):
                found.add(key)
                if re.search(r'\]\s*\*\s*\d+', line):
                    # keep template bounds, update only the multiplier (and the comment)
                    line = re.sub(r'(\]\s*\*\s*)\d+', lambda mm: mm.group(1) + str(n_par), line, count=1)
                    line = re.sub(r'\d+(\s+parametri)', lambda mm: str(n_par) + mm.group(1), line)
                    new_lines.append(line)
                else:
                    default = "0.70" if key == "xmin" else "1.30"
                    new_lines.append('{}"{}": [{}] * {},\n'.format(indent, key, default, n_par))
                    if opens_list: skip = True
                continue

        if MAT_COMMENT_RE.match(line):
            new_lines.append("{}# ({} materials, {} parameters)\n".format(indent, n_mat, n_par))
            continue

        if "RunSensAna" in line and DELTAX_RE.search(line):
            line = DELTAX_RE.sub(lambda mm: mm.group(1) + "{}./100.".format(delta_pct), line)
            found.add("deltax")

        new_lines.append(line)

    expected = set(multi.keys()) | set(single.keys()) | set(["xmin", "xmax", "deltax"])
    missing = sorted(expected - found)
    return new_lines, missing

def _read_path_file(folder, name):
    p = os.path.join(folder, name)
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                v = f.read().strip()
            if v: return v
        except: pass
    return None

# ======================================================================
# UI
# ======================================================================
class SensitivityForm(Form):
    def __init__(self):
        self.Text = "Perform Sensitivity Analysis"
        self.Size = Size(900, 720)
        self.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
        self.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedSingle
        self.MaximizeBox = False

        self.base_font = Font("Segoe UI", 11)
        self.label_font = Font("Segoe UI", 11, FontStyle.Bold)

        x0 = 30; label_w = 280; box_w = 400; h = 30
        btn_w = 120; btn_h = 35; dy = 45
        x_box = x0 + label_w + 10
        x_btn = x0 + label_w + box_w + 20
        y = 30

        def label(text, y_):
            c = Label(Text=text, Location=Point(x0, y_), Size=Size(label_w, h))
            c.Font = self.label_font
            c.TextAlign = System.Drawing.ContentAlignment.MiddleRight
            self.Controls.Add(c); return c

        def button(text, x_, y_, handler):
            c = Button(Text=text, Location=Point(x_, y_), Size=Size(btn_w, btn_h))
            c.Font = self.base_font
            c.Click += handler
            self.Controls.Add(c); return c

        def textbox(y_, readonly=True):
            c = TextBox(Location=Point(x_box, y_), Size=Size(box_w, h))
            c.Font = self.base_font; c.ReadOnly = readonly
            self.Controls.Add(c); return c

        def combo(y_):
            c = ComboBox(Location=Point(x_box, y_), Size=Size(box_w, h))
            c.Font = self.base_font
            c.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList
            self.Controls.Add(c); return c

        # --- Folder / INP ---
        label("Working Folder", y)
        self.text_folder = textbox(y)
        self.btn_folder = button("Select", x_btn, y - (btn_h - h) // 2, self.select_folder)
        y += dy

        label("File .inp", y)
        self.text_inp = textbox(y)
        self.btn_inp = button("Select", x_btn, y - (btn_h - h) // 2, self.select_inp_file)
        y += dy

        label("Part", y);     self.combo_part = combo(y);     y += dy
        label("Assembly", y); self.combo_assembly = combo(y); y += dy

        # --- Materials found (read only) ---
        list_h = 220
        label("Materials Found", y)
        self.list_materials = ListBox(Location=Point(x_box, y), Size=Size(box_w + btn_w + 10, list_h))
        self.list_materials.Font = Font("Consolas", 10)
        # "None" is a Python keyword: getattr is required in IronPython
        self.list_materials.SelectionMode = getattr(System.Windows.Forms.SelectionMode, "None")
        self.Controls.Add(self.list_materials)
        y += list_h + 15

        # --- Variation % ---
        label("Parameter Variation (%)", y)
        self.num_delta = NumericUpDown(Location=Point(x_box, y), Size=Size(120, h))
        self.num_delta.Font = self.base_font
        self.num_delta.Minimum = System.Decimal(1)
        self.num_delta.Maximum = System.Decimal(50)
        self.num_delta.Value = System.Decimal(1)
        self.num_delta.DecimalPlaces = 0
        self.Controls.Add(self.num_delta)
        y += dy

        # --- Buttons / status ---
        button_y = self.ClientSize.Height - btn_h - 25
        bx = self.ClientSize.Width // 2 - (btn_w * 3 + 40) // 2
        self.btn_ok = button("OK", bx, button_y, self.ok_clicked)
        self.btn_cancel = button("Cancel", bx + btn_w + 20, button_y, self.cancel_clicked)
        self.btn_run = button("Run", bx + (btn_w + 20) * 2, button_y, self.run_clicked)

        self.progress_bar = ProgressBar(Location=Point(x0, button_y - 35), Size=Size(self.ClientSize.Width - x0 * 2, 20))
        self.progress_bar.Style = System.Windows.Forms.ProgressBarStyle.Marquee
        self.progress_bar.Visible = False
        self.Controls.Add(self.progress_bar)

        self.status_label = Label(Text="Ready", Location=Point(x0, button_y - 65), Size=Size(self.ClientSize.Width - x0 * 2, 25))
        self.status_label.Font = self.base_font
        self.status_label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter
        self.status_label.ForeColor = Color.DarkBlue
        self.Controls.Add(self.status_label)

        # --- State ---
        self.folder_path = None
        self.materials = []
        self.process = None
        self.cancel_requested = False
        self.FormClosing += self.on_form_closing

        self._load_default_folder()

    # ------------------------------------------------------------------
    def _set_status(self, text, color=None):
        self.status_label.ForeColor = color if color is not None else Color.DarkBlue
        self.status_label.Text = text

    def _load_default_folder(self):
        # Same working folder selected with "Select Folder" in the FEMU tool
        try:
            if os.path.exists(LOG_DIR_FILE):
                with open(LOG_DIR_FILE, "r") as f:
                    p = f.read().strip()
                if os.path.isdir(p):
                    self.folder_path = p
                    self.text_folder.Text = p
        except: pass

    def _populate_combobox(self, cb, items):
        cb.Items.Clear()
        for it in items: cb.Items.Add(it)
        if items: cb.SelectedIndex = 0

    # ------------------------------------------------------------------
    def select_folder(self, sender, event):
        dlg = FolderBrowserDialog()
        if self.folder_path: dlg.SelectedPath = self.folder_path
        if dlg.ShowDialog() == DialogResult.OK:
            self.folder_path = dlg.SelectedPath
            self.text_folder.Text = self.folder_path

    def select_inp_file(self, sender, event):
        dlg = OpenFileDialog(); dlg.Filter = "Input files (*.inp)|*.inp"
        if self.folder_path: dlg.InitialDirectory = self.folder_path
        if dlg.ShowDialog() != DialogResult.OK:
            return
        inp = dlg.FileName
        self.text_inp.Text = inp
        if not self.folder_path:
            self.folder_path = os.path.dirname(inp)
            self.text_folder.Text = self.folder_path

        self._set_status("Reading .inp file...")
        self.Cursor = Cursors.WaitCursor
        Application.DoEvents()
        try:
            parts, instances, materials = parse_inp(inp)
        except Exception as e:
            self.Cursor = Cursors.Default
            self._set_status("Error reading .inp", Color.DarkRed)
            MessageBox.Show(self, "Error reading .inp file:\n%s" % str(e), "Error")
            return
        self.Cursor = Cursors.Default

        self.materials = materials
        self._populate_combobox(self.combo_part, parts)
        self._populate_combobox(self.combo_assembly, instances)

        self.list_materials.Items.Clear()
        for m in materials:
            self.list_materials.Items.Add("{:<20} E = {:<14} Dens = {}".format(m["name"], _fmt_value(m["E"]), _fmt_value(m["Dens"])))

        if not materials:
            self._set_status("No materials found in the .inp file", Color.DarkRed)
            return
        try:
            txt = write_materials_txt(self.folder_path, materials)
            self._set_status("{} materials found - saved to '{}'".format(len(materials), os.path.basename(txt)), Color.DarkGreen)
        except Exception as e:
            self._set_status("Error writing materials file", Color.DarkRed)
            MessageBox.Show(self, "Error writing '%s':\n%s" % (MATERIALS_TXT, str(e)), "Error")

    # ------------------------------------------------------------------
    def ok_clicked(self, sender, event):
        if not self.folder_path or not self.text_inp.Text:
            MessageBox.Show(self, "Please select the working folder and the .inp file.", "Error"); return
        entries = build_entries(self.materials)
        if not entries:
            MessageBox.Show(self, "No materials with valid E / Density found.", "Error"); return
        if self.combo_part.SelectedItem is None or self.combo_assembly.SelectedItem is None:
            MessageBox.Show(self, "Part or Assembly not found in the .inp file.", "Error"); return
        self.generate_run_file(entries)

    def generate_run_file(self, entries):
        folder = self.folder_path
        orig = os.path.join(folder, TEMPLATE_NAME)
        runf = os.path.join(folder, RUN_NAME)
        if not os.path.exists(orig):
            MessageBox.Show(self, "Template %s missing in:\n%s" % (TEMPLATE_NAME, folder), "Error"); return

        inp = self.text_inp.Text
        name_fem = os.path.splitext(os.path.basename(inp))[0]
        delta_pct = System.Decimal.ToInt32(self.num_delta.Value)

        single = {
            "WD": 'r"{}"'.format(folder),
            "name_FEM": '"{}"'.format(name_fem),
            "name_PART": '"{}"'.format(self.combo_part.SelectedItem),
            "name_PART_ASSEM": '"{}"'.format(self.combo_assembly.SelectedItem),
            "jobname": '"{}"'.format(name_fem),
        }
        # Experimental files selected with the FEMU tool (if available)
        exp_freq = _read_path_file(folder, EXP_FREQ_PATH_FILE)
        exp_modes = _read_path_file(folder, EXP_MODES_PATH_FILE)
        if exp_freq:  single["Exp_Freq_file"] = 'r"{}"'.format(exp_freq)
        if exp_modes: single["Exp_Modes_file"] = 'r"{}"'.format(exp_modes)

        try:
            write_materials_txt(folder, self.materials)
            with open(orig, "r") as f:
                lines = f.readlines()
            new_lines, missing = build_run_lines(lines, entries, single, delta_pct)
            with open(runf, "w") as f:
                f.writelines(new_lines)
        except Exception as e:
            MessageBox.Show(self, "Error generating %s:\n%s" % (RUN_NAME, str(e)), "Error"); return

        n_par = sum(len(p) for _, p in entries)
        self._set_status("{} generated ({} materials, {} parameters, deltax = {}%)".format(RUN_NAME, len(entries), n_par, delta_pct), Color.DarkGreen)
        msg = "%s generated successfully." % RUN_NAME
        if missing:
            msg += "\n\nWarning - not found in the template:\n" + ", ".join(missing)
        MessageBox.Show(self, msg, "Done")

    # ------------------------------------------------------------------
    # Process execution / cancellation
    # ------------------------------------------------------------------
    def _is_running(self):
        return self.process is not None and self.process.poll() is None

    def _ui(self, func):
        if self.IsDisposed or not self.IsHandleCreated:
            return
        self.BeginInvoke(MethodInvoker(func))

    def _kill_process_tree(self):
        p = self.process
        if p is None or p.poll() is not None:
            return
        try:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(p.pid)])
        except Exception as e:
            MessageBox.Show("Unable to terminate the process: %s" % str(e), "Error")

    def cancel_clicked(self, sender, event):
        if self._is_running():
            res = MessageBox.Show(self, "The analysis is running. Do you want to stop it?", "Confirm", MessageBoxButtons.YesNo)
            if res == DialogResult.Yes:
                self.cancel_requested = True
                self._set_status("Stopping...", Color.DarkRed)
                self._kill_process_tree()
            return
        self.Close()

    def on_form_closing(self, sender, e):
        if self._is_running():
            res = MessageBox.Show(self, "The analysis is running. Closing will stop it. Continue?", "Confirm", MessageBoxButtons.YesNo)
            if res != DialogResult.Yes:
                e.Cancel = True
                return
            self.cancel_requested = True
            self._kill_process_tree()

    def run_clicked(self, sender, event):
        if not self.folder_path:
            MessageBox.Show(self, "Select a working folder first."); return
        if not os.path.exists(os.path.join(self.folder_path, RUN_NAME)):
            MessageBox.Show(self, "Generate the file first (OK)."); return
        if self._is_running():
            MessageBox.Show(self, "A process is already running."); return

        self.cancel_requested = False
        self.btn_run.Enabled = False
        self.btn_ok.Enabled = False
        self._set_status("Running...")
        self.progress_bar.Visible = True

        t = threading.Thread(target=self.run_process, args=(self.folder_path, "python " + RUN_NAME))
        t.daemon = True
        t.start()

    def run_process(self, directory, command):
        rc = None; err = None
        try:
            self.process = subprocess.Popen(command, shell=True, cwd=directory)
            rc = self.process.wait()
        except Exception as e:
            err = str(e)
        finally:
            self.process = None
        self._ui(lambda: self._on_process_finished(rc, err))

    def _on_process_finished(self, rc, err):
        self.progress_bar.Visible = False
        self.btn_run.Enabled = True
        self.btn_ok.Enabled = True
        if self.cancel_requested:
            self._set_status("Stopped by user", Color.DarkRed)
        elif err:
            self._set_status("Error", Color.DarkRed)
            MessageBox.Show(self, "Error: %s" % err, "Error")
        elif rc == 0:
            self._set_status("Completed", Color.DarkGreen)
            MessageBox.Show(self, "Sensitivity analysis completed.", "Done")
        else:
            self._set_status("Finished with exit code %s" % rc, Color.DarkRed)

if __name__ == "__main__":
    Application.EnableVisualStyles()
    Application.Run(SensitivityForm())