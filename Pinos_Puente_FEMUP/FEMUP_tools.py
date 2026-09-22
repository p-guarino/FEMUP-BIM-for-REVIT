
import re
import numpy as np
import os
import glob
import shutil
import subprocess
import random
from pymoo.algorithms.soo.nonconvex.pso import PSO
from pymoo.optimize import minimize
from pymoo.problems.functional import FunctionalProblem
from pymoo.constraints.as_penalty import ConstraintsAsPenalty
from pymoo.visualization.scatter import Scatter
from pymoo.problems import get_problem
from sklearn.metrics import mean_squared_error
from matplotlib import cm

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # Enables 3D plotting
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import plotly.graph_objects as go
import plotly.io as pio
pio.renderers.default = 'browser'  # opens in your default browser


# Callback to record data in PSO optimization
class MyCallback:
    def __init__(self):
        self.f_history  = []
        self.x_history = []  # X positions

    def __call__(self, algorithm):
        # Store cost values and positions of all particles
        self.f_history.append(algorithm.pop.get("F").copy())
        self.x_history.append(algorithm.pop.get("X").copy())

# Class for FEMUP (Finite Element Model Updating)
class FEMUP:
  def __init__(self,Dirnames,FEMUP_options,graph_style=None,verbose=1):
    if "nmodes" not in FEMUP_options:
        FEMUP_options['nmodes'] = 12
    if "Tolnodes" not in FEMUP_options:
        FEMUP_options['Tolnodes'] = 1
    if "n_numGPUs" not in FEMUP_options:
        FEMUP_options['n_numGPUs'] = 0
    if "match_mac" not in FEMUP_options:
        FEMUP_options['match_mac'] = 1.0
    if "match_freq" not in FEMUP_options:
        FEMUP_options['match_freq'] = 0.1
    if "Geometry_File" not in Dirnames:
        Dirnames['Geometry_File'] = ''

    if graph_style is None:
        graph_style = {
                'color_nodes': 'blue',
                'size_nodes': 5,
                'color_line': 'blue',
                'width_line': 4,
                'color_sensor': 'red',
                'length_sensor': 2,
                'width_sensor': 0.1,
                'colormap': 'Viridis',
                'opacitycolormap': 0.9
        }
        self.verbose = verbose
        self.graph_style = graph_style

    self.Dirnames = Dirnames
    self.FEMUP_options = FEMUP_options
    WD = Dirnames['WD']
    name_FEM = Dirnames['name_FEM']
    name_PART = Dirnames['name_PART']
    name_PART_ASSEM = Dirnames['name_PART_ASSEM']
    self.Sensors_file = Dirnames['Sensors_file']
    self.WD = WD
    self.name_FEM = name_FEM
    self.name_PART =  name_PART
    self.name_PART_ASSEM = name_PART_ASSEM
    self.Exp_Freq_file = Dirnames['Exp_Freq_file']
    self.Exp_Modes_file = Dirnames['Exp_Modes_file']
    self.Material = FEMUP_options['Material']
    self.PROP = FEMUP_options['PROP']
    self.alpha = FEMUP_options['alpha']
    self.beta = FEMUP_options['beta']
    self.eta = FEMUP_options['eta']
    self.nmodes = FEMUP_options['nmodes']
    self.Tolnodes = FEMUP_options['Tolnodes']
    self.n_numCpus = FEMUP_options['n_numCpus']
    self.n_numGPUs = FEMUP_options['n_numGPUs']
    self.match_mac = FEMUP_options['match_mac']
    self.match_freq = FEMUP_options['match_freq']
    self.verbose = verbose
    self.xo = FEMUP_options['xo']
    self.xmin = FEMUP_options['xmin']
    self.xmax = FEMUP_options['xmax']

    # Get existing files
    self.files_o = [f for f in os.listdir(WD) if os.path.isfile(os.path.join(WD, f))]

    # Read Modal Geometry   
    if len(Dirnames['Geometry_File']) > 0:
        self.Nodes, self.Lines, self.Sensors, self.Colorplane, self.SN, self.KC = read_geometry_file(Dirnames['Geometry_File'])
    else:
        # Default geometry file
        self.Nodes = np.array([])
        self.Lines = np.array([])
        self.Sensors = np.array([])
        self.Colorplane = np.array([])
        self.SN = np.array([])

    # Read experimental data
    self.Exp_Freq = np.loadtxt(self.Exp_Freq_file)
    self.Exp_Modes = np.loadtxt(self.Exp_Modes_file)
    self.instance = self.Sensors_file
    if verbose == 1:
        print ('Exp. Freq:', self.Exp_Freq)
        print ('Exp_Modes:')
        print (self.Exp_Modes)
    
    # Modify work files
    file_path = 'Prepare_inp_base.py'
    with open(file_path, 'r') as file:
        lines = file.readlines()
    file_path_out = 'Prepare_inp.py'
    with open(file_path_out, 'w') as file:
        for line in lines:
            stripped = line.strip()
            modified = False
            for key, new_line in FEMUP_options.items():
                if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                    file.write(key +'=' + str(new_line) + '\n')
                    modified = True
                    break
            for key, new_line in Dirnames.items():
                if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                    if key == "WD":
                       file.write(key +'=r"' + new_line + '"\n')
                    else:
                       file.write(key +'="' + new_line + '"\n')
                    modified = True
                    break
            if not modified:
                file.write(line)
    # Preprocess to generate the main .inp
    subprocess.run("abaqus cae noGUI="+file_path_out, shell=True)

  # Run FEM ------------------------------------------------------------------------
  def RunFEM(self,x=[],rand_name=0):
    # Copy inp
    input_path = self.Dirnames["jobname"] + '.inp'
    if rand_name == 0:
        output_path = self.Dirnames["jobname"] + '_iter.inp'
    else:
        n = random.randint(1, 99999)
        output_path = self.Dirnames["jobname"] + '_'+str(n)+'.inp'
    shutil.copyfile(input_path, output_path)
    # Copy Postprocessing file
    input_path_pp = 'Post_process_inp_base.py'
    if rand_name == 0:
        output_path_pp = 'Post_process_inp_iter.py'
    else:    
        output_path_pp = 'Post_process_inp_'+str(n)+'.py'
    shutil.copyfile(input_path_pp, output_path_pp)

    n = random.randint(1, 99999)
    name_freq_file = "Num_Freq_"+str(n)+".csv"
    name_MOD_file = "Num_Modes_"+str(n)+".csv"

    # Modify FEM if needed .............................................
    if len(x)>0:
        self.Modify_FEM(x)
    # Launch the model .................................................
    subprocess.run("abaqus job="+os.path.splitext(output_path)[0]+" input="+output_path+" interactive", shell=True,
                   input="y\n", text=True, stdout=subprocess.DEVNULL)

    # Postprocess .........................................................
    # Modify work files
    with open(input_path_pp, 'r') as file:
        lines = file.readlines()
    with open(output_path_pp, 'w') as file:
        for line in lines:
            stripped = line.strip()
            modified = False
            for key, new_line in self.FEMUP_options.items():
                if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                    file.write(key +'=' + str(new_line) + '\n')
                    modified = True
                    break
            for key, new_line in self.Dirnames.items():
                if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                    if key == "WD":
                       file.write(key +'=r"' + new_line + '"\n')
                    elif key == "jobname":
                       file.write(key +'="' + os.path.splitext(output_path)[0] + '"\n')
                    else:
                       file.write(key +'="' + new_line + '"\n')
                    modified = True
                    break
            if stripped.startswith(f"name_freq_file ="):
                file.write('name_freq_file = "' + name_freq_file + '"\n')
                modified = True
            if stripped.startswith(f"name_MOD_file ="):
                file.write('name_MOD_file = "' + name_MOD_file + '"\n')
                modified = True
            if not modified:
                file.write(line)
    # Run the postprocessing
    cont_cond = 0
    while cont_cond == 0:
        try:
            subprocess.run("abaqus cae noGUI="+output_path_pp, shell=True,
                        input="y\n",
                        text=True,
                        stdout=subprocess.DEVNULL)

            self.numfreq = np.loadtxt(name_freq_file, delimiter=",", skiprows=0)
            self.phi = np.loadtxt(name_MOD_file, delimiter=",", skiprows=0)
            cont_cond = 1
        except:
            print("Error in postprocessing, retrying...")
            subprocess.run("abaqus job="+os.path.splitext(output_path)[0]+" input="+output_path+" interactive", shell=True,
                   input="y\n", text=True, stdout=subprocess.DEVNULL)
            # Wait a bit before retrying
            import time
            time.sleep(5)

    # Delete temporary files
    #os.remove(name_freq_file)
    #os.remove(name_MOD_file)
    #os.remove(output_path_pp)
    #os.remove(os.path.splitext(output_path)[0]+'.odb')
    #os.remove(output_path)
    #return self

  # Run Sensitiviy Analysis ------------------------------------------------------------------------
  def RunSensAna(self,deltax=5./100.,rand_name=0):
    rel_err_freq = np.zeros((len(self.Material),self.nmodes))
    rel_err_MAC = np.zeros((len(self.Material),self.nmodes))
    for cont in np.arange(len(self.Material)+1):  
        x = list(np.ones(len(self.Material)))
        if cont > 0:
           x[cont-1] = x[cont-1]+deltax
        # Copy inp
        input_path = self.Dirnames["jobname"] + '.inp'
        if rand_name == 0:
            output_path = self.Dirnames["jobname"] + '_iter.inp'
        else:
            n = random.randint(1, 99999)
            output_path = self.Dirnames["jobname"] + '_'+str(n)+'.inp'
        shutil.copyfile(input_path, output_path)
        # Copy Postprocessing file
        input_path_pp = 'Post_process_inp_base.py'
        if rand_name == 0:
            output_path_pp = 'Post_process_inp_iter.py'
        else:    
            output_path_pp = 'Post_process_inp_'+str(n)+'.py'
        shutil.copyfile(input_path_pp, output_path_pp)
    
        n = random.randint(1, 99999)
        name_freq_file = "Num_Freq_"+str(n)+".csv"
        name_MOD_file = "Num_Modes_"+str(n)+".csv"
    
        # Modify FEM if needed .............................................
        if len(x)>0:
            self.Modify_FEM(x)
        # Launch the model .................................................
        subprocess.run("abaqus job="+os.path.splitext(output_path)[0]+" input="+output_path+" interactive", shell=True,
                       input="y\n", text=True, stdout=subprocess.DEVNULL)
    
        # Postprocess .........................................................
        # Modify work files
        with open(input_path_pp, 'r') as file:
            lines = file.readlines()
        with open(output_path_pp, 'w') as file:
            for line in lines:
                stripped = line.strip()
                modified = False
                for key, new_line in self.FEMUP_options.items():
                    if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                        file.write(key +'=' + str(new_line) + '\n')
                        modified = True
                        break
                for key, new_line in self.Dirnames.items():
                    if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                        if key == "WD":
                           file.write(key +'=r"' + new_line + '"\n')
                        elif key == "jobname":
                           file.write(key +'="' + os.path.splitext(output_path)[0] + '"\n')
                        else:
                           file.write(key +'="' + new_line + '"\n')
                        modified = True
                        break
                if stripped.startswith(f"name_freq_file ="):
                    file.write('name_freq_file = "' + name_freq_file + '"\n')
                    modified = True
                if stripped.startswith(f"name_MOD_file ="):
                    file.write('name_MOD_file = "' + name_MOD_file + '"\n')
                    modified = True
                if not modified:
                    file.write(line)
        # Run the postprocessing
        cont_cond = 0
        while cont_cond == 0:
            try:
                subprocess.run("abaqus cae noGUI="+output_path_pp, shell=True,
                            input="y\n",
                            text=True,
                            stdout=subprocess.DEVNULL)
    
                self.numfreq = np.loadtxt(name_freq_file, delimiter=",", skiprows=0)
                self.phi = np.loadtxt(name_MOD_file, delimiter=",", skiprows=0)
                cont_cond = 1
            except:
                print("Error in postprocessing, retrying...")
                subprocess.run("abaqus job="+os.path.splitext(output_path)[0]+" input="+output_path+" interactive", shell=True,
                       input="y\n", text=True, stdout=subprocess.DEVNULL)
                # Wait a bit before retrying
                import time
                time.sleep(5)
        if cont == 0:
            ref_freq = self.numfreq
            ref_modes = self.phi
        else:
            rel_err_freq[cont-1,:] = (self.numfreq-ref_freq)/deltax
            MACc = MAC(self.phi,ref_modes)
            rel_err_MAC[cont-1,:] = np.diag(MACc)
        # Delete temporary files
        os.remove(name_freq_file)
        os.remove(name_MOD_file)
        #os.remove(output_path_pp)
        #os.remove(os.path.splitext(output_path)[0]+'.odb')
        #os.remove(output_path)
        #return self
    self.rel_err_MAC = rel_err_MAC
    self.rel_err_freq = rel_err_freq

  def Plot_Sens_Results(self):
    import os  # Required for file paths

    # ---- Common Data Preparation
    # Create labels like "Material-Property" (e.g., "Concrete-E")
    param_labels = [f"{m}-{p}" for m, p in zip(self.FEMUP_options["Material"],
                                                 self.FEMUP_options["PROP"])]
    
    # -------------------------------------------------------------------------
    # PART 1: FREQUENCIES
    # -------------------------------------------------------------------------
    data = self.rel_err_freq
    rows, cols = data.shape
    xtick_labels = [f"Mode {i+1}" for i in range(cols)]

    # 1.A: Save TEXT FILE (Frequency Table)
    file_txt_freq = os.path.join(self.WD, "Sensitivity_Report_Freq.txt")
    with open(file_txt_freq, "w") as f:
        f.write("FREQUENCY SENSITIVITY REPORT\n")
        f.write("Values: Relative freq variation / Parameter variation\n")
        f.write("="*100 + "\n")
        
        # Header
        header = f"{'PARAMETER':<25} | " + "".join([f"{label:>10} " for label in xtick_labels]) + f"| {'MEAN':>10}\n"
        f.write(header)
        f.write("-" * len(header) + "\n")

        # Data Rows
        mean_params = np.mean(np.abs(data), axis=1) # Calculate mean per row
        for i in range(rows):
            row_str = f"{param_labels[i]:<25} | "
            for j in range(cols):
                row_str += f"{data[i, j]:10.5f} "
            row_str += f"| {mean_params[i]:10.5f}\n"
            f.write(row_str)
    
    print(f"Text file saved: {file_txt_freq}")

    # 1.B: Generate Frequency Plots
    x, y = np.meshgrid(np.arange(cols), np.arange(rows))
    x = x.ravel()
    y = y.ravel()
    z = np.zeros_like(x)
    dx = dy = 0.5 * np.ones_like(z)
    dz = data.ravel()
    
    norm3d = plt.Normalize(dz.min(), dz.max())
    colors3d = cm.viridis(norm3d(dz))
    
    # Sorting for bar chart
    sorted_index = np.argsort(mean_params)
    sorted_means = mean_params[sorted_index]
    norm1d = plt.Normalize(sorted_means.min(), sorted_means.max())
    colors1d = cm.viridis(norm1d(sorted_means))
    sorted_labels = [param_labels[i] for i in sorted_index]
    
    fig = plt.figure(figsize=(14, 6))
    
    # 3D Plot
    ax3d = fig.add_subplot(1, 2, 1, projection='3d')
    ax3d.bar3d(x, y, z, dx, dy, dz, color=colors3d)
    ax3d.set_xticks(np.arange(cols))
    ax3d.set_xticklabels(xtick_labels, rotation=45, ha="right", fontsize=8)
    ax3d.set_yticks(range(len(param_labels)))
    ax3d.set_yticklabels(param_labels, fontsize=8)
    ax3d.set_zlabel("Sensitivity value")
    ax3d.set_title("Frequency Sensitivity")
    
    # Bar Chart
    ax1d = fig.add_subplot(1, 2, 2)
    ax1d.bar(np.arange(len(sorted_means)), sorted_means, color=colors1d)
    ax1d.set_xlabel("Parameter")
    ax1d.set_ylabel("Mean sensitivity")
    ax1d.set_xticks(np.arange(len(sorted_means)))
    ax1d.set_xticklabels(sorted_labels, rotation=45, ha="right")
    ax1d.set_title("Parameter Influence Ranking (Freq)")
    
    fig.tight_layout()
    
    # Save PNG
    file_png_freq = os.path.join(self.WD, "Sensitivity_Plot_Freq.png")
    plt.savefig(file_png_freq, dpi=300) 
    print(f"Image saved: {file_png_freq}")
    
    plt.show() # Note: show() must be AFTER savefig()
    
    
    # -------------------------------------------------------------------------
    # PART 2: MODE SHAPES (MAC)
    # -------------------------------------------------------------------------
    # Use 1-MAC as variation metric
    data = 1 - self.rel_err_MAC
    
    # 2.A: Save TEXT FILE (MAC Table)
    file_txt_mac = os.path.join(self.WD, "Sensitivity_Report_MAC.txt")
    with open(file_txt_mac, "w") as f:
        f.write("MAC SENSITIVITY REPORT (Metric: 1 - MAC)\n")
        f.write("High values indicate significant mode shape distortion.\n")
        f.write("="*100 + "\n")
        
        # Header
        header = f"{'PARAMETER':<25} | " + "".join([f"{label:>10} " for label in xtick_labels]) + f"| {'MEAN':>10}\n"
        f.write(header)
        f.write("-" * len(header) + "\n")

        # Rows
        mean_params = np.mean(np.abs(data), axis=1)
        for i in range(rows):
            row_str = f"{param_labels[i]:<25} | "
            for j in range(cols):
                row_str += f"{data[i, j]:10.5f} "
            row_str += f"| {mean_params[i]:10.5f}\n"
            f.write(row_str)
            
    print(f"Text file saved: {file_txt_mac}")

    # 2.B: Generate MAC Plots
    dz = data.ravel()
    norm3d = plt.Normalize(dz.min(), dz.max())
    colors3d = cm.viridis(norm3d(dz))
    
    sorted_index = np.argsort(mean_params)
    sorted_means = mean_params[sorted_index]
    norm1d = plt.Normalize(sorted_means.min(), sorted_means.max())
    colors1d = cm.viridis(norm1d(sorted_means))
    sorted_labels = [param_labels[i] for i in sorted_index]
    
    fig = plt.figure(figsize=(14, 6))
    
    # 3D Plot
    ax3d = fig.add_subplot(1, 2, 1, projection='3d')
    ax3d.bar3d(x, y, z, dx, dy, dz, color=colors3d)
    ax3d.set_xticks(np.arange(cols))
    ax3d.set_xticklabels(xtick_labels, rotation=45, ha="right", fontsize=8)
    ax3d.set_yticks(range(len(param_labels)))
    ax3d.set_yticklabels(param_labels, fontsize=8)
    ax3d.set_zlabel("1-MAC")
    ax3d.set_title("Mode Shape Sensitivity (1-MAC)")
    
    # Bar Chart
    ax1d = fig.add_subplot(1, 2, 2)
    ax1d.bar(np.arange(len(sorted_means)), sorted_means, color=colors1d)
    ax1d.set_xlabel("Parameter")
    ax1d.set_ylabel("Mean 1-MAC")
    ax1d.set_xticks(np.arange(len(sorted_means)))
    ax1d.set_xticklabels(sorted_labels, rotation=45, ha="right")
    ax1d.set_title("Parameter Influence Ranking (MAC)")
    
    fig.tight_layout()
    
    # Save PNG
    file_png_mac = os.path.join(self.WD, "Sensitivity_Plot_MAC.png")
    plt.savefig(file_png_mac, dpi=300)
    print(f"Image saved: {file_png_mac}")
    
    plt.show()


  # Modify FEM ------------------------------------------------------------------------------
  def Modify_FEM(self,x):

    # Modify the .inp file
    inp_file = self.Dirnames["jobname"] + '_iter.inp'

    for i_param in range(len(x)):
        with open(inp_file, "r") as f:
            lines = f.readlines()

        el_mod = 0
        dens_mod = 0
        if self.FEMUP_options["PROP"][i_param] == 'E':
           el_mod = 1
           new_E = self.xo[i_param]*x[i_param]
        elif self.FEMUP_options["PROP"][i_param] == 'Dens':
           dens_mod = 1
           new_D = self.xo[i_param]*x[i_param]

        modified_lines = []
        i = 0
        no_assigned = 0
        while i < len(lines):
            line = lines[i]
            material_name = self.FEMUP_options["Material"][i_param]
            material_name_cap = material_name.upper()
            conmat_1 = '*MATERIAL, NAME="'+material_name+'"' in line
            conmat_2 = '*MATERIAL, NAME="'+material_name_cap+'"' in line
            conmat_3 = '*Material, NAME="'+material_name+'"' in line
            conmat_4 = '*Material, NAME="'+material_name_cap+'"' in line
            conmat_5 = '*MATERIAL, name="'+material_name+'"' in line
            conmat_6 = '*MATERIAL, name="'+material_name_cap+'"' in line
            conmat_7 = '*Material, name="'+material_name+'"' in line
            conmat_8 = '*Material, name="'+material_name_cap+'"' in line
            conmat_9 = '*MATERIAL, NAME='+material_name+'' in line
            conmat_10 = '*MATERIAL, NAME='+material_name_cap+'' in line
            conmat_11 = '*Material, NAME='+material_name+'' in line
            conmat_12 = '*Material, NAME='+material_name_cap+'' in line
            conmat_13 = '*MATERIAL, name='+material_name+'"' in line
            conmat_14 = '*MATERIAL, name='+material_name_cap+'' in line
            conmat_15 = '*Material, name='+material_name+'"' in line
            conmat_16 = '*Material, name='+material_name_cap+'' in line
            #print( '*Material, name="'+material_name+'"')
            cond_found = conmat_1 or conmat_2 or conmat_3 or conmat_4 or conmat_5 or conmat_6 or conmat_7 or conmat_8 
            cond_foundb = conmat_9 or conmat_10 or conmat_11 or conmat_12 or conmat_13 or conmat_14 or conmat_15 or conmat_16 
            if cond_found or cond_foundb:
                no_assigned = 1
                modified_lines.append(line)
                i += 1
                if el_mod == 1:
                    # Look for *ELASTIC
                    while i < len(lines) and "*ELASTIC" not in lines[i].upper():
                        modified_lines.append(lines[i])
                        i += 1
                        cond = "*ELASTIC" not in lines[i] or "*Elastic" not in lines[i]
                    if i <= len(lines) and "*ELASTIC" in lines[i].upper():
                        modified_lines.append(lines[i])  # *ELASTIC line
                        i += 1
                        # Replace the elastic constants line
                        if i < len(lines):
                            parts = lines[i].split(",")
                            E = float(parts[0].strip())
                            nu = float(parts[1].strip())
                            modified_lines.append(f"{new_E}, {nu}\n")
                            i += 1
                    continue  # skip to next line
                elif dens_mod == 1:
                    # Look for *Density
                    while i < len(lines) and "*DENSITY" not in lines[i].upper():
                        modified_lines.append(lines[i])
                        i += 1
                    if i < len(lines) and "*DENSITY" in lines[i].upper():
                        modified_lines.append(lines[i])  # *Density line
                        i += 1
                        # Replace the elastic constants line
                        if i < len(lines):
                            parts = lines[i].split(",")
                            Dens = float(parts[0].strip())
                            modified_lines.append(f"{new_D},\n")
                            i += 1
                    continue  # skip to next line
            elif line == lines[-1] and no_assigned==0:
                raise Exception('Material <<'+material_name+'>> not found! Please revise the setting')
            modified_lines.append(line)
            i += 1

        with open(inp_file, "w") as f:
            f.writelines(modified_lines)
    return self

  # Cost function
  def cost_fun_din(self):
    # Match Numerical-Experimental modes
    # MAC - Num. vs Exp
    MACc = MAC(self.Exp_Modes,self.phi)
    #print('MACc')
    #print(MACc)
    pairs = [];
    for i_mode in range(len(self.Exp_Freq)):
        metric = self.match_mac*(1.-MACc[i_mode,:])+self.match_freq*np.abs(self.numfreq.T-self.Exp_Freq[i_mode])/self.Exp_Freq[i_mode]      
        ind_max = metric.argmin()
        pairs.append(ind_max)
    print('Pairs:',pairs)
    self.pairs = pairs
    self.Num_Freq = self.numfreq[self.pairs].T    
    self.Num_Modes = self.phi[:,self.pairs]
    # Compute errors
    if self.verbose == 1:
        print('Num. Freq:',self.Exp_Freq,'Num. Freq:',self.Num_Freq)
    J1 = float(0)
    J2 = float(0)
    J3 = float(0)
    MAC_v = []
    for i_mode in range(len(self.Exp_Freq)):
        MAC_iter = MAC(self.Exp_Modes[:,i_mode],self.Num_Modes[:,i_mode])
        print(MAC_iter)
        J1 = J1+self.alpha*(1.-MAC_iter)
        J2 = J2+self.beta*np.abs(self.Num_Freq[i_mode]-self.Exp_Freq[i_mode])/self.Exp_Freq[i_mode]
        J3 = J3+self.eta*0
        MAC_v.append(MAC_iter)
    self.J1 = J1
    self.J2 = J2
    self.J3 = J3
    self.MAC_v = MAC_v
    self.costfun = J1+J2+J3
    if self.verbose == 1:
        print('J1',J1,'J2',J2,'J3',J3)
        print('MAC vals:',self.MAC_v)
    return self

  def cost_fun_param(self,x):  # Evaluation + cost_function
    self.RunFEM(x)
    self.cost_fun_din()
    return self.costfun

  def calibrate(self):

    if self.FEMUP_options["FEMUP_method"] == "PSO":
        if "velocity_rate" not in self.FEMUP_options:
            self.FEMUP_options['velocity_rate'] = 0.025
        if "w" not in self.FEMUP_options:
            self.FEMUP_options['w'] = 0.9
        if "c1" not in self.FEMUP_options:
            self.FEMUP_options['c1'] = 2.0
        if "c2" not in self.FEMUP_options:
            self.FEMUP_options['c2'] = 2.0

        nvar = len(self.FEMUP_options["xo"])
        self.FEMUP_options["nvar"] = nvar
        problem = FunctionalProblem(nvar,   #Variables
                                self.cost_fun_param,  #Cost function
                                xl=self.FEMUP_options["xmin"],
                                xu=self.FEMUP_options["xmax"]
                                #constr_ieq=constr_ieq,
                                )
        callback = MyCallback()
        algorithm = PSO(pop_size=self.FEMUP_options["nparticles"],max_velocity_rate=self.FEMUP_options["velocity_rate"],
                        w=self.FEMUP_options["w"], c1=self.FEMUP_options["c1"], c2=self.FEMUP_options["c2"])
        res = minimize(problem,
                algorithm,
                termination=('n_gen', self.FEMUP_options["max_iter"]),
                seed=None,
                save_history=True,
                verbose = self.verbose,
                callback=callback)
        opt = res.opt[0]
        X, F, CV = opt.get("X", "__F__", "__CV__")

        print("Best solution found: \nX = %s\nF = %s\nCV = %s\n" % (X, F, CV))
        self.theta = X 
        self.cost_history = np.array(callback.f_history)  # shape: (n_gen, n_particles)
        self.x_history = np.array(callback.x_history)  # (n_gen, n_particles, n_var)

        n_evals = np.array([e.evaluator.n_eval for e in res.history])
        opt = np.array([e.opt[0].F for e in res.history])

        self.n_evals = n_evals
        self.opt = opt
        self.resOSP = res

    self.RunFEM(self.theta)
    self.cost_fun_din()

    self.Calibrated_freqs = self.numfreq[self.pairs]
    self.Calibrated_Modes = self.phi[:,self.pairs]
    return self

    # Plot Geometry ------------------------------------------------------------------------------------------------------------
  def Plot_Geometry(self, MS=None):
        if MS is None:
            MS = np.ones((np.shape(self.Sensors)[0],1))*0  # Mode shape
        plot_geom(np.copy(self.Nodes),self.Lines,self.Sensors,self.Colorplane,self.KC,self.SN,MS,self.graph_style)




#%% DYNAMIC MONITORING

def plotly_volumetric_arrow(
    start, end,
    shaft_radius=0.4,
    head_length_ratio=0.3,
    head_radius_ratio=4.0,
    resolution=16,
    color='orange'
):
    """
    Create a volumetric 3D arrow (cylinder + cone) between two 3D points using Plotly Mesh3d.
    
    Parameters:
    - start: (3,) array-like, arrow tail
    - end: (3,) array-like, arrow head
    - shaft_radius: radius of the arrow shaft (cylinder)
    - head_length_ratio: length of the cone as a fraction of total arrow length
    - head_radius_ratio: cone radius relative to shaft radius
    - resolution: number of segments for circular cross-sections
    - color: color name or RGB value
    """
    start = np.array(start)
    end = np.array(end)
    vec = end - start
    L = np.linalg.norm(vec)
    if L == 0:
        return []

    # Normalize vector
    vec_unit = vec / L

    # Shaft and head geometry
    L_head = L * head_length_ratio
    L_shaft = L - L_head
    shaft_end = start + vec_unit * L_shaft
    head_tip = end

    # Build local coordinate system
    def orthogonal_vector(v):
        if abs(v[0]) < abs(v[1]):
            if abs(v[0]) < abs(v[2]):
                other = np.array([1, 0, 0])
            else:
                other = np.array([0, 0, 1])
        else:
            if abs(v[1]) < abs(v[2]):
                other = np.array([0, 1, 0])
            else:
                other = np.array([0, 0, 1])
        return np.cross(v, other)

    ortho1 = orthogonal_vector(vec_unit)
    ortho1 /= np.linalg.norm(ortho1)
    ortho2 = np.cross(vec_unit, ortho1)

    # Circle in XY plane
    theta = np.linspace(0, 2 * np.pi, resolution)
    circle = np.cos(theta)[..., None] * ortho1 + np.sin(theta)[..., None] * ortho2

    # === Shaft (cylinder) ===
    shaft_top = shaft_end
    shaft_base = start
    shaft_pts1 = shaft_base + shaft_radius * circle
    shaft_pts2 = shaft_top + shaft_radius * circle

    shaft_vertices = np.vstack([shaft_pts1, shaft_pts2])
    shaft_faces = []
    for i in range(resolution):
        a, b = i, (i + 1) % resolution
        shaft_faces.append([a, b, b + resolution])
        shaft_faces.append([a, b + resolution, a + resolution])

    # === Head (cone) ===
    cone_base = shaft_top
    cone_tip = head_tip
    cone_radius = shaft_radius * head_radius_ratio
    cone_base_pts = cone_base + cone_radius * circle

    offset = shaft_vertices.shape[0]
    cone_vertices = np.vstack([cone_base_pts, [cone_tip]])
    cone_faces = []
    for i in range(resolution):
        a, b = i, (i + 1) % resolution
        cone_faces.append([offset + a, offset + b, offset + resolution])  # tip is last vertex

    # Combine
    all_vertices = np.vstack([shaft_vertices, cone_vertices])
    all_faces = np.array(shaft_faces + cone_faces)

    x, y, z = all_vertices[:, 0], all_vertices[:, 1], all_vertices[:, 2]
    i, j, k = all_faces[:, 0], all_faces[:, 1], all_faces[:, 2]

    mesh = go.Mesh3d(
        x=x, y=y, z=z,
        i=i, j=j, k=k,
        color=color,
        opacity=1.0,
        flatshading=True,
        lighting=dict(ambient=0.4, diffuse=0.8),
        hoverinfo='skip',
        name='Arrow'
    )

    return mesh



def plot_geom(Nodes,Lines,Sensors,Colorplane,KC = [],SensorName=[],ModeShape=[],graph_style=None):

    # Graphical Options
    if graph_style is None:
        graph_style = {
            'color_nodes': 'blue',
            'size_nodes': 5,
            'color_line': 'blue',
            'width_line': 4,
            'color_sensor': 'red',
            'length_sensor': 2,
            'width_sensor': 0.1,
            'colormap': 'Viridis',
            'opacitycolormap': 0.8
        }
    color_nodes = graph_style['color_nodes']
    size_nodes = graph_style['size_nodes']
    color_line = graph_style['color_line']
    width_line = graph_style['width_line']
    color_sensor = graph_style['color_sensor']
    length_sensor = graph_style['length_sensor']
    width_sensor = graph_style['width_sensor']
    colormap = graph_style['colormap']
    opacitycolormap = graph_style['opacitycolormap']

    if len(ModeShape.shape) == 1:
       ModeShape = ModeShape[:, np.newaxis]

    # Deform structure
    Nodes_o = Nodes.copy()
    if len(ModeShape)  > 0:
       for i in range(np.shape(Sensors)[0]):
           node_s = np.where(Sensors[i,0]==Nodes[:,0])[0][0]
           dir = Sensors[i,1:4]
           if len(dir) == 1:
              if dir == 1:
                  dir = np.array([1,0,0])
              elif dir == 2:
                  dir = np.array([0,1,0])
              elif dir == 3:
                  dir = np.array([0,0,1])
           dir = dir/np.linalg.norm(dir)   
           Nodes[node_s,1:] = Nodes[node_s,1:] + ModeShape[i,:]*dir

    # Deformations
    U = Nodes-Nodes_o
    Def = np.sum(U.T**2,axis=0)**0.5    


    # KINETIC EQUATIONS
    if len(KC) > 0:
       for eq in KC:
           brackets = re.findall(r'\[(.*?)\]', eq)
           if any(',' in b for b in brackets):  # If a specific direction is defined
                return [eq]
           else:                                # If a complete node is defined
                modified_eq = []
                for i in range(1, 4):
                    modified = re.sub(r'\[(\d+)\]', rf'[\1,{i}]', eq)
                    modified_eq.append(modified)
           for eeqq in modified_eq:   # Execute kinetic equation after kinetic equation
            pattern = r'\[(\d+),\d+\]'
            matches = re.findall(pattern, eeqq)
            label_list = Nodes[:,0] 
            def replacer(match):
                    label = int(match.group(1))
                    level = match.group(2)
                    try:
                        index = np.where(label_list == label)[0][0]
                    except IndexError:
                        raise ValueError(f"Label {label} not found in Nodes[:,0]")
                    return f'[{index},{level}]'
                
            # Pattern to find [label,level]
            pattern = r'\[(\d+),(\d+)\]'
            new_eq = re.sub(pattern, replacer, eeqq)
            exec(new_eq)
            U = Nodes-Nodes_o   # Update the displacement vector
            Def = np.sum(U.T**2,axis=0)**0.5 # Update deformations

    # Plot Nodes
    scatter_nodes = go.Scatter3d(
        x=Nodes[:, 1],
        y=Nodes[:, 2],
        z=Nodes[:, 3],
        mode='markers',
        marker=dict(size=size_nodes, color=color_nodes),
        text=[f"Node {int(n)}" for n in Nodes[:, 0]],
        hovertemplate="%{text}<br>(%{x}, %{y}, %{z})",
        name="Nodes"  # name of the whole trace for legend
    )

    # Plot lines
    line_traces = []
    for i in range(np.shape(Lines)[0]):
        node_a = np.where(Lines[i,0]==Nodes[:,0])[0][0]
        node_b = np.where(Lines[i,1]==Nodes[:,0])[0][0]
        x = [Nodes[node_a, 1], Nodes[node_b, 1], None]
        y = [Nodes[node_a, 2], Nodes[node_b, 2], None]
        z = [Nodes[node_a, 3], Nodes[node_b, 3], None]
        line_trace = go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode='lines',
            line=dict(color=color_line, width=width_line),
            hoverinfo='skip',
            showlegend=False
        )
        line_traces.append(line_trace)

    # Plot sensors
    if np.all(U == 0):
        arrow_sens = []
        label_sens = []
        for i in range(np.shape(Sensors)[0]):
            node_s = np.where(Sensors[i,0]==Nodes[:,0])[0][0]
            A = Nodes[node_s,1:]
            dir = Sensors[i,1:4]
            if len(dir) == 1:
                if dir == 1:
                    dir = np.array([1,0,0])
                elif dir == 2:
                    dir = np.array([0,1,0])
                elif dir == 3:
                    dir = np.array([0,0,1])
            dir = dir/np.linalg.norm(dir)   
            B = Nodes[node_s,1:4] + dir*length_sensor
            arrow_sens.append(plotly_volumetric_arrow(A, B,shaft_radius=width_sensor, color=color_sensor))
            label_sens.append(go.Scatter3d(
                x=[B[0]],
                y=[B[1]],
                z=[B[2]],
                mode='markers',
                marker=dict(size=1, color='skyblue'),
                text=SensorName[i],  # Custom hover text
                hoverinfo='text'  # Only show the text
            ))
    else:
        opacitycolormap = None

    # Plot color planes
    CPtraces = []
    for i in range(np.shape(Colorplane)[0]):
        xp = []
        yp = []
        zp = []
        colors = []
        for j in range(len(Colorplane[i,:])):
            nodes_id = np.where(Colorplane[i,j]==Nodes[:,0])[0][0]
            xp.append(Nodes[nodes_id,1])
            yp.append(Nodes[nodes_id,2])
            zp.append(Nodes[nodes_id,3])
            if np.max(np.abs(Def)) != 0:
               colors.append(Def[nodes_id])
        mesh = go.Mesh3d(
            x = xp,
            y = yp,
            z = zp,
            i = [0],
            j = [1],
            k = [2],
            cmin = np.min(np.abs(Def)),
            cmax = np.max(np.abs(Def)),
            intensity=colors,
            colorscale=colormap,
            showscale=False,
            opacity=opacitycolormap,
            hoverinfo='skip'
        )
        CPtraces.append(mesh)

    layout = go.Layout(
    scene=dict(
        xaxis=dict(backgroundcolor='black', color='white', gridcolor='gray'),
        yaxis=dict(backgroundcolor='black', color='white', gridcolor='gray'),
        zaxis=dict(backgroundcolor='black', color='white', gridcolor='gray'),
        aspectmode='data',
        camera=dict(eye=dict(x=1.25, y=1.25, z=1.25))
    ),
    paper_bgcolor='black',
    plot_bgcolor='black',
    showlegend=False
    )
    # plt.show()
    if np.all(U == 0):
        fig = go.Figure(data=[scatter_nodes] + CPtraces + line_traces + arrow_sens + label_sens, layout=layout)
    else:
        fig = go.Figure(data=[scatter_nodes] + CPtraces + line_traces, layout=layout)
    fig.show()


def read_geometry_file(Geometry_File):
    # Read Geometry File
    with open(Geometry_File, 'r', encoding='utf-8') as file:
        text = file.read()

    # Find positions of the labels
    index_nodes = text.find("NODES ID")+1
    index_lines = text.find("LINES")
    index_sensors = text.find("SENSORS")
    index_CP = text.find("COLOR PLANE")
    index_KE = text.find("*KINETIC EQUATIONS")
    id_end = text.find("*END")
    index_end = []
    while id_end != -1:
        index_end.append(id_end)
        id_end = text.find("*END", id_end + 1)

    end_id = next((x for x in index_end if x > index_nodes), None)
    Nodes = np.array([line.split(sep=',') for line in text[index_nodes:end_id+1].splitlines()[1:-1]], dtype=float)
    end_id = next((x for x in index_end if x > index_lines), None)
    Lines = np.array([line.split(sep=',') for line in text[index_lines:end_id+1].splitlines()[1:-1]], dtype=float)
    end_id = next((x for x in index_end if x > index_sensors), None)
    Sensors_comp = [line.split(sep=',') for line in text[index_sensors:end_id+1].splitlines()[1:-1]]
    Sensors = np.array([sublist[:4] for sublist in Sensors_comp], dtype=float)
    SN = [sublist[-1] for sublist in Sensors_comp]

    end_id = next((x for x in index_end if x > index_CP), None)
    Colorplane = np.array([line.split(sep=',') for line in text[index_CP:end_id+1].splitlines()[1:-1]], dtype=float)

    end_id = next((x for x in index_end if x > index_KE), None)
    KC = text[index_KE+1:end_id].splitlines()[1:-1]

    return Nodes, Lines, Sensors, Colorplane, SN, KC

# MAC function
def MAC(phi_X, phi_A):
    """Modal Assurance Criterion (MAC) function."""
    #print('Phi X:')
    #print(phi_X)
    #print('Phi_A:')
    #print(phi_A)
    
    # Ensure phi_X and phi_A are 2D arrays
    if phi_X.ndim == 1:
        phi_X = phi_X[:, np.newaxis]  # Convert to 2D if it's 1D
    
    if phi_A.ndim == 1:
        phi_A = phi_A[:, np.newaxis]  # Convert to 2D if it's 1D
    
    # Check if phi_X and phi_A have the same number of rows (sensor locations)
    if phi_X.shape[0] != phi_A.shape[0]:
        raise Exception('Mode shapes must have the same first dimension (phi_X: {}, phi_A: {})'.format(phi_X.shape[0], phi_A.shape[0]))
    
    # Debugging: Print the shape of phi_X and phi_A
    #print('phi_X shape: {}, phi_A shape: {}'.format(phi_X.shape, phi_A.shape))
    
    # Calculate the MAC matrix step by step to avoid syntax issues
    phi_X_conj = np.conj(phi_X.T)  # Conjugate transpose of phi_X
    MAC_matrix = np.abs(np.dot(phi_X_conj, phi_A)) ** 2  # Dot product
    
    # Avoiding the complex conjugate and matrix multiplication issue
    for i in range(phi_X.shape[1]):
        for j in range(phi_A.shape[1]):
            idxA = np.where((phi_X[:, i] != 0) & (phi_A[:, j] != 0))[0]
            # Break down the operations
            conj_phi_X_i = np.conj(phi_X[idxA, i])
            conj_phi_A_j = np.conj(phi_A[idxA, j])
            phi_X_i_dot = np.real(np.dot(conj_phi_X_i, phi_X[idxA, i]))
            phi_A_j_dot = np.real(np.dot(conj_phi_A_j, phi_A[idxA, j]))
            
            denominator = phi_X_i_dot * phi_A_j_dot
            if denominator == 0:
                raise ValueError('Denominator in MAC calculation is zero.')
            
            MAC_matrix[i, j] = MAC_matrix[i, j] / denominator
    
    if MAC_matrix.shape == (1, 1):
        MAC_matrix = MAC_matrix[0, 0]  # If the MAC result is a single value, return it as a scalar
    
    #print('MAC Matrix:')
    #print(MAC_matrix)
    return MAC_matrix
