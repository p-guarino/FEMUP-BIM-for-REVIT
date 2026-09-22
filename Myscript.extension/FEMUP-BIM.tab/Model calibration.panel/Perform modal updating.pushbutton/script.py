# -*- coding: utf-8 -*-
import clr
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

import System
from System.Windows.Forms import Application, Form, Label, TextBox, Button, ComboBox, CheckedListBox, CheckBox, FolderBrowserDialog, OpenFileDialog, DialogResult, MessageBox, ProgressBar
from System.Drawing import Point, Size, Font, FontStyle
import os
import shutil
import subprocess
import threading
import re 

class ParamFormMulti(Form):
    def __init__(self):
        self.Text = "Perform Modal Updating (Multi-Material)"
        self.Size = Size(900, 1000)
        self.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
        self.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedSingle
        self.MaximizeBox = False

        self.base_font = Font("Segoe UI", 11)
        self.label_font = Font("Segoe UI", 11, FontStyle.Bold)

        panel_x_offset = 30
        label_width = 280
        textbox_width = 400
        control_height = 30
        button_width = 120
        button_height = 35
        vertical_spacing = 45

        current_y = 30

        def add_control(parent, ctrl_type, text, x, y, width, height, is_label=False, is_button=False, is_readonly=False, handler=None, dropdown_style=None):
            if is_label:
                ctrl = Label(Text=text, Location=Point(x, y), Size=Size(width, height))
                ctrl.Font = self.label_font
                ctrl.TextAlign = System.Drawing.ContentAlignment.MiddleRight
            elif is_button:
                ctrl = Button(Text=text, Location=Point(x, y), Size=Size(width, height))
                ctrl.Font = self.base_font
                if handler: ctrl.Click += handler
            elif ctrl_type == TextBox:
                ctrl = TextBox(Text=text, Location=Point(x, y), Size=Size(width, height))
                ctrl.Font = self.base_font
                ctrl.ReadOnly = is_readonly
            elif ctrl_type == ComboBox:
                ctrl = ComboBox(Text=text, Location=Point(x, y), Size=Size(width, height))
                ctrl.Font = self.base_font
                if dropdown_style: ctrl.DropDownStyle = dropdown_style
                if handler: ctrl.SelectedIndexChanged += handler
            elif ctrl_type == CheckedListBox:
                ctrl = CheckedListBox(Location=Point(x, y), Size=Size(width, height))
                ctrl.Font = self.base_font
                ctrl.CheckOnClick = True
            elif ctrl_type == CheckBox:
                ctrl = CheckBox(Text=text, Location=Point(x, y), Size=Size(width, height))
                ctrl.Font = self.base_font
            parent.Controls.Add(ctrl)
            return ctrl

        # --- Folder and File Selection ---
        self.label_folder = add_control(self, Label, "Select Folder", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_folder = add_control(self, TextBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, control_height, is_readonly=True)
        self.btn_folder = add_control(self, Button, "Select", panel_x_offset + label_width + textbox_width + 20, current_y - (button_height - control_height) // 2, button_width, button_height, is_button=True, handler=self.select_folder)
        current_y += vertical_spacing

        self.label_inp = add_control(self, Label, "File .inp", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_inp = add_control(self, TextBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, control_height, is_readonly=True)
        self.btn_inp = add_control(self, Button, "Select", panel_x_offset + label_width + textbox_width + 20, current_y - (button_height - control_height) // 2, button_width, button_height, is_button=True, handler=self.select_inp_file)
        current_y += vertical_spacing

        self.label_exp_freq = add_control(self, Label, "Experimental Frequencies", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_exp_freq = add_control(self, TextBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, control_height, is_readonly=True)
        self.btn_exp_freq = add_control(self, Button, "Select", panel_x_offset + label_width + textbox_width + 20, current_y - (button_height - control_height) // 2, button_width, button_height, is_button=True, handler=self.select_exp_freq_file)
        current_y += vertical_spacing

        self.label_exp_modes = add_control(self, Label, "Experimental Mode Shapes", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_exp_modes = add_control(self, TextBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, control_height, is_readonly=True)
        self.btn_exp_modes = add_control(self, Button, "Select", panel_x_offset + label_width + textbox_width + 20, current_y - (button_height - control_height) // 2, button_width, button_height, is_button=True, handler=self.select_exp_modes_file)
        current_y += vertical_spacing

        # --- Dropdowns & Lists ---
        self.label_part = add_control(self, Label, "Part", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.combo_part = add_control(self, ComboBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, control_height, dropdown_style=System.Windows.Forms.ComboBoxStyle.DropDownList)
        current_y += vertical_spacing

        materials_list_height = 80 
        self.label_material = add_control(self, Label, "Materials to Optimize", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.checklist_materials = add_control(self, CheckedListBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, materials_list_height)
        current_y += (materials_list_height + 15) 

        self.label_assembly = add_control(self, Label, "Assembly", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.combo_assembly = add_control(self, ComboBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, control_height, dropdown_style=System.Windows.Forms.ComboBoxStyle.DropDownList)
        current_y += vertical_spacing

        # --- Parameters ---
        self.label_nmodes = add_control(self, Label, "Number of Modes", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_nmodes = add_control(self, TextBox, "", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_tolnodes = add_control(self, Label, "Nodes Tolerance", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_tolnodes = add_control(self, TextBox, "0.01", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_nparticles = add_control(self, Label, "Num of Particles", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_nparticles = add_control(self, TextBox, "20", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_max_iter = add_control(self, Label, "Maximum Iterations", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_max_iter = add_control(self, TextBox, "30", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_alpha = add_control(self, Label, "Alpha Parameter", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_alpha = add_control(self, TextBox, "1.0", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_beta = add_control(self, Label, "Beta Parameter", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_beta = add_control(self, TextBox, "10.0", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_eta = add_control(self, Label, "Eta Parameter", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_eta = add_control(self, TextBox, "0", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_bc = add_control(self, Label, "Boundary Conditions", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.chk_update_bc = add_control(self, CheckBox, "Optimize / Update BCs", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        self.label_jobname = add_control(self, Label, "Job Name", panel_x_offset, current_y, label_width, control_height, is_label=True)
        self.text_jobname = add_control(self, TextBox, "Arch_Bridge", panel_x_offset + label_width + 10, current_y, textbox_width, control_height)
        current_y += vertical_spacing

        # --- Buttons ---
        button_y = self.Size.Height - button_height - 60
        button_x_start = self.Size.Width // 2 - (button_width * 1.5 + 20)
        self.btn_ok = add_control(self, Button, "OK", button_x_start, button_y, button_width, button_height, is_button=True, handler=self.ok_clicked)
        self.btn_cancel = add_control(self, Button, "Cancel", button_x_start + button_width + 20, button_y, button_width, button_height, is_button=True, handler=self.cancel_clicked)
        self.btn_run = add_control(self, Button, "Run", button_x_start + (button_width * 2) + 40, button_y, button_width, button_height, is_button=True, handler=self.run_clicked)

        self.folder_path = None
        self.material_data = {}
        self.parts_list = []
        self.materials_list = []
        self.assemblies_list = []
        
        self.load_parts_materials() 
        self._populate_combobox(self.combo_part, self.parts_list)
        self._populate_checklist(self.checklist_materials, self.materials_list)
        self._populate_combobox(self.combo_assembly, self.assemblies_list)

        self.progress_bar = ProgressBar(Location=Point(panel_x_offset, button_y - 40), Size=Size(self.Size.Width - panel_x_offset * 2, 20))
        self.progress_bar.Style = System.Windows.Forms.ProgressBarStyle.Marquee
        self.progress_bar.Visible = False
        self.Controls.Add(self.progress_bar)

        self.status_label = Label(Text="Ready", Location=Point(panel_x_offset, button_y - 70), Size=Size(self.Size.Width - panel_x_offset * 2, 20))
        self.status_label.Font = self.base_font
        self.status_label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter
        self.status_label.ForeColor = System.Drawing.Color.DarkBlue
        self.Controls.Add(self.status_label)

        # --- Gestione processo ---
        self.process = None
        self.cancel_requested = False
        self.FormClosing += self.on_form_closing

    def _populate_combobox(self, combobox_control, items_list):
        combobox_control.Items.Clear()
        for item in items_list:
            combobox_control.Items.Add(item)
        if items_list:
            combobox_control.SelectedIndex = 0

    def _populate_checklist(self, checklist_control, items_list):
        checklist_control.Items.Clear()
        for item in items_list:
            checklist_control.Items.Add(item)

    def load_parts_materials(self):
        search_paths = []
        if self.folder_path and os.path.isdir(self.folder_path): search_paths.append(self.folder_path)
        current_dir = os.getcwd(); home_dir = os.path.expanduser("~")
        if current_dir not in search_paths: search_paths.append(current_dir)
        if home_dir not in search_paths: search_paths.append(home_dir)

        materials_file_found = None
        for path in search_paths:
            candidate = os.path.join(path, "Materials_Properties.txt")
            if os.path.exists(candidate):
                materials_file_found = candidate
                break

        self.material_data = {}
        if materials_file_found:
            try:
                with open(materials_file_found, "r") as f:
                    lines = f.readlines()
                if lines and "Material," in lines[0]: lines = lines[1:]
                for line in lines:
                    line = line.strip()
                    if line:
                        parts = line.split(",")
                        # 7 columns: Material, E_min, E_nom, E_max, Dens_min, Dens_nom, Dens_max.
                        # Files written by an older version carry three extra Poisson
                        # columns, which are read and ignored.
                        if len(parts) >= 7:
                            mat_name = parts[0].strip()
                            try:
                                self.material_data[mat_name] = [float(v.strip()) for v in parts[1:7]]
                            except ValueError: continue
            except Exception as e: MessageBox.Show("Error reading Materials_Properties.txt: %s" % str(e)) 
        
        self.materials_list = list(self.material_data.keys()) 

        inp_data_file_found = None
        for path in search_paths:
            candidate = os.path.join(path, "inp_parts_materials.txt")
            if os.path.exists(candidate):
                inp_data_file_found = candidate
                break

        if inp_data_file_found:
            parts = []; assemblies = []
            try:
                with open(inp_data_file_found, "r") as f:
                    lines = f.read().splitlines()
                in_parts = False; in_assemblies = False
                for line in lines:
                    line = line.strip()
                    if line.lower() == "parts:": in_parts = True; in_assemblies = False; continue
                    elif line.lower() == "materials:": in_parts = False; in_assemblies = False; continue
                    elif line.lower() == "assemblies:": in_parts = False; in_assemblies = True; continue
                    elif line == "": continue
                    if in_parts: parts.append(line)
                    elif in_assemblies: assemblies.append(line)
                self.parts_list = parts; self.assemblies_list = assemblies
            except: pass

    def select_folder(self, sender, event):
        dlg = FolderBrowserDialog()
        if dlg.ShowDialog() == DialogResult.OK:
            self.folder_path = dlg.SelectedPath
            self.text_folder.Text = self.folder_path
            self.load_parts_materials()
            self._populate_combobox(self.combo_part, self.parts_list)
            self._populate_checklist(self.checklist_materials, self.materials_list)
            self._populate_combobox(self.combo_assembly, self.assemblies_list)

    def select_inp_file(self, sender, event):
        dlg = OpenFileDialog(); dlg.Filter = "Input files (*.inp)|*.inp"
        if dlg.ShowDialog() == DialogResult.OK:
            self.text_inp.Text = dlg.FileName
            self.text_jobname.Text = os.path.splitext(os.path.basename(dlg.FileName))[0]

    def select_exp_freq_file(self, sender, event):
        dlg = OpenFileDialog(); dlg.Filter = "Text files (*.txt)|*.txt"
        if dlg.ShowDialog() == DialogResult.OK: self.text_exp_freq.Text = dlg.FileName

    def select_exp_modes_file(self, sender, event):
        dlg = OpenFileDialog(); dlg.Filter = "Text files (*.txt)|*.txt"
        if dlg.ShowDialog() == DialogResult.OK: self.text_exp_modes.Text = dlg.FileName

    def ok_clicked(self, sender, event):
        if not self.folder_path or not self.text_inp.Text or not self.text_exp_freq.Text or not self.text_exp_modes.Text:
            MessageBox.Show("Please complete all file selections.", "Error"); return

        checked_materials = [self.checklist_materials.Items[i] for i in range(self.checklist_materials.Items.Count) if self.checklist_materials.GetItemChecked(i)]
        if not checked_materials: MessageBox.Show("Please select at least one material.", "Error"); return

        m_props = []; m_nominal = []; m_xmin = []; m_xmax = []; m_names = []
        for mat in checked_materials:
            v = self.material_data.get(mat)
            if v[1] > 0: # E
                m_props.append("E"); m_nominal.append(v[1]); m_xmin.append(v[0]/v[1]); m_xmax.append(v[2]/v[1]); m_names.append(mat)
            if v[4] > 0: # Dens
                m_props.append("Dens"); m_nominal.append(v[4]); m_xmin.append(v[3]/v[4]); m_xmax.append(v[5]/v[4]); m_names.append(mat)

        data = {
            "folder_path": self.folder_path,
            "inp_file": self.text_inp.Text,
            "exp_freq_path": self.text_exp_freq.Text,
            "exp_modes_path": self.text_exp_modes.Text,
            "part": self.combo_part.SelectedItem,
            "assembly": self.combo_assembly.SelectedItem,
            "mat_names": m_names, "props": m_props, "nominal": m_nominal, "xmin": m_xmin, "xmax": m_xmax,
            "nmodes": self.text_nmodes.Text, "tolnodes": self.text_tolnodes.Text,
            "nparticles": self.text_nparticles.Text, "max_iter": self.text_max_iter.Text,
            "alpha": self.text_alpha.Text, "beta": self.text_beta.Text, "eta": self.text_eta.Text,
            "jobname": self.text_jobname.Text, "update_bc": self.chk_update_bc.Checked
        }
        self.generate_run_file(data)

    # ------------------------------------------------------------------
    # Gestione esecuzione / interruzione processo
    # ------------------------------------------------------------------
    def _is_running(self):
        return self.process is not None and self.process.poll() is None

    def _ui(self, func):
        # Esegue func sul thread della UI (non bloccante)
        if self.IsDisposed or not self.IsHandleCreated:
            return
        self.BeginInvoke(System.Windows.Forms.MethodInvoker(func))

    def _kill_process_tree(self):
        p = self.process
        if p is None or p.poll() is not None:
            return
        try:
            # /T = termina anche i processi figli (python -> abaqus -> solver), /F = forzato
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(p.pid)])
        except Exception as e:
            MessageBox.Show("Impossibile terminare il processo: %s" % str(e), "Errore")

    def cancel_clicked(self, sender, event):
        if self._is_running():
            res = MessageBox.Show(self, "Il processo è in esecuzione. Vuoi interromperlo?",
                                  "Conferma", System.Windows.Forms.MessageBoxButtons.YesNo)
            if res == DialogResult.Yes:
                self.cancel_requested = True
                self.status_label.ForeColor = System.Drawing.Color.DarkRed
                self.status_label.Text = "Interruzione in corso..."
                self._kill_process_tree()
            return  # la finestra resta aperta per mostrare lo stato
        self.Close()

    def on_form_closing(self, sender, e):
        if self._is_running():
            res = MessageBox.Show(self, "Il processo è in esecuzione. Chiudendo verrà interrotto. Continuare?",
                                  "Conferma", System.Windows.Forms.MessageBoxButtons.YesNo)
            if res != DialogResult.Yes:
                e.Cancel = True
                return
            self.cancel_requested = True
            self._kill_process_tree()

    def run_clicked(self, sender, event):
        if not self.folder_path:
            MessageBox.Show("Select a folder first."); return
        path = os.path.join(self.folder_path, "Launch_From_Python_run.py")
        if not os.path.exists(path):
            MessageBox.Show("Generate the file first."); return
        if self._is_running():
            MessageBox.Show("A process is already running."); return

        self.cancel_requested = False
        self.btn_run.Enabled = False
        self.btn_ok.Enabled = False
        self.status_label.ForeColor = System.Drawing.Color.DarkBlue
        self.status_label.Text = "Running..."
        self.progress_bar.Visible = True

        t = threading.Thread(target=self.run_abaqus_process,
                             args=(self.folder_path, "python Launch_From_Python_run.py"))
        t.daemon = True
        t.start()

    def run_abaqus_process(self, directory, command):
        rc = None; err = None
        try:
            self.process = subprocess.Popen(command, shell=True, cwd=directory)
            rc = self.process.wait()
        except Exception as e:
            err = str(e)
        finally:
            self.process = None
        # Prima si aggiorna la UI, poi (sul thread UI) si mostra l'eventuale alert
        self._ui(lambda: self._on_process_finished(rc, err))

    def _on_process_finished(self, rc, err):
        self.progress_bar.Visible = False
        self.btn_run.Enabled = True
        self.btn_ok.Enabled = True

        if self.cancel_requested:
            self.status_label.ForeColor = System.Drawing.Color.DarkRed
            self.status_label.Text = "Interrotto dall'utente"
        elif err:
            self.status_label.ForeColor = System.Drawing.Color.DarkRed
            self.status_label.Text = "Errore"
            MessageBox.Show(self, "Error: %s" % err, "Errore")
        elif rc == 0:
            self.status_label.ForeColor = System.Drawing.Color.DarkGreen
            self.status_label.Text = "Completato"
            MessageBox.Show(self, "Process Completed.", "Fatto")
        else:
            self.status_label.ForeColor = System.Drawing.Color.DarkRed
            self.status_label.Text = "Terminato con codice %s" % rc

    # ------------------------------------------------------------------

    def generate_run_file(self, data):
        orig = os.path.join(data["folder_path"], "Launch_From_Python.py")
        runf = os.path.join(data["folder_path"], "Launch_From_Python_run.py")
        if not os.path.exists(orig): MessageBox.Show("Template Launch_From_Python.py missing."); return
        shutil.copyfile(orig, runf)

        with open(runf, "r") as f: lines = f.readlines()

        # REPLACEMENTS USING DOUBLE QUOTES AS REQUESTED
        replacements = {
            "nmodes": data["nmodes"], "Tolnodes": data["tolnodes"], "nparticles": data["nparticles"],
            "max_iter": data["max_iter"], "alpha": data["alpha"], "beta": data["beta"], "eta": data["eta"],
            "xo": "[" + ", ".join(map(str, data["nominal"])) + "]",
            "xmin": "[" + ", ".join(["%.6f" % x for x in data["xmin"]]) + "]",
            "xmax": "[" + ", ".join(["%.6f" % x for x in data["xmax"]]) + "]",
            "Material": "[" + ", ".join(['"{}"'.format(m) for m in data["mat_names"]]) + "]",
            "PROP": "[" + ", ".join(['"{}"'.format(p) for p in data["props"]]) + "]",
            "WD": 'r"{}"'.format(data["folder_path"]),
            "name_FEM": '"{}"'.format(os.path.splitext(os.path.basename(data["inp_file"]))[0]),
            "name_PART": '"{}"'.format(data["part"]),
            "name_PART_ASSEM": '"{}"'.format(data["assembly"]),
            "Exp_Freq_file": 'r"{}"'.format(data["exp_freq_path"]), # Full absolute path
            "Exp_Modes_file": 'r"{}"'.format(data["exp_modes_path"]), # Full absolute path
            "jobname": '"{}"'.format(data["jobname"])
        }

        new_lines = []; skip = False
        for line in lines:
            if skip:
                if "]" in line: skip = False
                continue
            updated = False
            if data["update_bc"] and "bc_file" in line:
                if line.lstrip().startswith("#"): line = line.replace("#", "", 1)
            for k, v in replacements.items():
                if re.match(r'^\s*[\"\']' + re.escape(k) + r'[\"\']\s*:', line):
                    indent = line[:len(line)-len(line.lstrip())]
                    new_lines.append('{}"{}": {},\n'.format(indent, k, v))
                    updated = True
                    if "[" in line and "]" not in line: skip = True
                    break
            if not updated: new_lines.append(line)

        with open(runf, "w") as f: f.writelines(new_lines)
        MessageBox.Show("Launch_From_Python_run.py generated successfully.")

if __name__ == "__main__":
    Application.EnableVisualStyles()
    Application.Run(ParamFormMulti())