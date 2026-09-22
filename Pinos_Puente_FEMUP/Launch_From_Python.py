# Code to launch the model upating from Python
import numpy as np
import subprocess
from FEMUP_tools import *
import matplotlib.pyplot as plt
from matplotlib import cm # Aggiunto per sicurezza per il grafico 3D

FEMUP_options = {
    # Model options
    "nmodes": 18,
    "Tolnodes": 0.01,
    "n_numCpus": 15,

    # Optimization hyper-parameters
    "xo": [
      7400000000, 2000,  # Pier1
      7400000000, 2000,  # Pier2
      2700000000, 2200   # Chapel
  ],
    "xmin": [0.70, 0.70, 0.70, 0.70, 0.70, 0.70],  # Lower bounds for scaling factors
    "xmax": [1.30, 1.30, 1.30, 1.30, 1.30, 1.30],  # Upper bounds for scaling factors
    "Material": ["Pier1","Pier1",
        "Pier2", "Pier2",
        "Chapel", "Chapel"
    ],
    "PROP": ["E","Dens",
             "E", "Dens",
             "E", "Dens"
  ],
    "nparticles": 30,  # Number of particles in PSO
    "max_iter": 30,    # Maximum number of iterations
    "velocity_rate": 0.025,    # Rate of change of velocity
    "w": 0.9,   # Inertia weight for PSO
    "c1": 2,    # Cognitive component for PSO
    "c2": 2,    # Social component for PSO
    "FEMUP_method": "PSO",   # Optimization method

    # Weighting factors
    "alpha": 1.0,
    "beta": 10.0,
    "eta": 0
}

Dirnames = {
    "WD": r"D:\Users\User\Desktop\Workfolder\Pinos_Puente_FEMUP",
    "name_FEM": "Job_pinos_puente",
    "name_PART": "Pinos_Puente",
    "name_PART_ASSEM": "Pinos_Puente-1",
    "jobname": "Job_pinos_puente",
    #"bc_file": "log_bc_1.txt",   # uncommented automatically by "Optimize / Update BCs"

    # Experimental data files
    "Exp_Freq_file": "Experimental_Frequencies.txt",
    "Exp_Modes_file": "Experimental_Mode_shapes.txt",
    "Sensors_file": "Sensors.txt",
    "Geometry_File": "Modal_Geometry.txt"
}


####################################################
# Create Object for model updating
FEMUP_anal = FEMUP(Dirnames,FEMUP_options)

# ----------------------------------
# Function to plot the geometry!
FEMUP_anal.Plot_Geometry()

####################################################
# Uncalibrated solutions
FEMUP_anal.RunFEM(list(np.ones(len(FEMUP_options["xo"]))))
FEMUP_anal.cost_fun_din()
FEMUP_anal.Uncalibrated_freqs = FEMUP_anal.numfreq[FEMUP_anal.pairs]
FEMUP_anal.Uncalibrated_Modes = FEMUP_anal.phi[:,FEMUP_anal.pairs]

# Function to plot the a mode shape
mf = 1E+3  # Magnification factor
mp = 3 # Mode to plot
FEMUP_anal.Plot_Geometry(MS = FEMUP_anal.Uncalibrated_Modes[:,mp-1]*mf)

####################################################
# Calibrate
FEMUP_anal.calibrate()

####################################################
# Outputs results   
####################################################

# Numerical results
# --------------------------------------------------------
MAC_matrix_unc = MAC(FEMUP_anal.Uncalibrated_Modes, FEMUP_anal.Exp_Modes)
MAC_matrix_cal = MAC(FEMUP_anal.Calibrated_Modes, FEMUP_anal.Exp_Modes)

Rel_err_freq_unc = []
for i in range(len(FEMUP_anal.Uncalibrated_freqs)):
    Rel_err_freq_unc.append(100.*(FEMUP_anal.Uncalibrated_freqs[i] - FEMUP_anal.Exp_Freq[i]) / FEMUP_anal.Exp_Freq[i]) 
Rel_err_freq = []
for i in range(len(FEMUP_anal.Calibrated_freqs)):
    Rel_err_freq.append(100.*(FEMUP_anal.Calibrated_freqs[i] - FEMUP_anal.Exp_Freq[i]) / FEMUP_anal.Exp_Freq[i])      
# Save results to txt file
out = np.column_stack((FEMUP_anal.Exp_Freq,FEMUP_anal.Uncalibrated_freqs, Rel_err_freq_unc, np.diag(MAC_matrix_unc), FEMUP_anal.Calibrated_freqs, np.array(Rel_err_freq),np.diag(MAC_matrix_cal)))
np.savetxt('Calibration_Results.txt', out, fmt='%.6f', header='Freq. Exp [Hz], Uncalibrated, Rel_Error [%], MAC vals, Calibrated, Rel_Error [%], MAC vals')  

# Fitted parameters
with open("Calibrated_Parameters.txt", "w") as file:
    for i_param in range(len(FEMUP_anal.xo)):
        if FEMUP_anal.FEMUP_options["PROP"][i_param] == 'E':
            txt = f"Parameter {i_param+1} - MATERIAL: {FEMUP_anal.FEMUP_options['Material'][i_param]}: E_nom = {FEMUP_anal.xo[i_param]:.6f}; E_calib = {FEMUP_anal.xo[i_param]*FEMUP_anal.theta[i_param]:.6f}\n"
        elif FEMUP_anal.FEMUP_options["PROP"][i_param] == 'Dens':
            txt = f"Parameter {i_param+1} - MATERIAL: {FEMUP_anal.FEMUP_options['Material'][i_param]}: Dens_nom = {FEMUP_anal.xo[i_param]:.6f}; Dens_calib = {FEMUP_anal.xo[i_param]*FEMUP_anal.theta[i_param]:.6f}\n"
        file.write(txt)

# ========================================================
# NUOVO: Salvataggio del valore finale della Cost Function
# ========================================================
# Recupera il miglior (minimo) valore della cost function all'ultima iterazione
final_cost_value = np.min(FEMUP_anal.cost_history[-1, :])
with open("Final_Cost_Function.txt", "w") as cost_file:
    cost_file.write(f"Valore finale della funzione di costo: {final_cost_value:.8e}\n")


# Graphical results
# --------------------------------------------------------

#%% CONVERGENCE OF THE SOLUTION
# Plot - Convergence - Cost Function vs iterations
plt.figure(figsize=(10, 6))
for i in range(FEMUP_anal.cost_history.shape[1]):
    plt.plot(FEMUP_anal.cost_history[:, i], label=f'Particle {i+1}', alpha=0.6)
plt.xlabel('Iteration')
plt.ylabel('Cost Function Value')
plt.title('Particle Cost Function Values over Iterations')
plt.grid(True)
plt.tight_layout()
plt.savefig('Convergence_Cost_History.png', dpi=300, bbox_inches='tight') # Salvataggio immagine
plt.show()

# Plot - Convergence - Particles' position vs iterations
plt.figure(figsize=(10, 6))
for i in range(FEMUP_anal.cost_history.shape[1]):
    plt.plot(FEMUP_anal.x_history[:, i], label=f'Particle {i+1}', marker='o', alpha=0.6)
plt.xlabel('Iteration')
plt.ylabel('Stiffness multipliers')
plt.title('Particle Positions over Iterations')
plt.grid(True)
plt.tight_layout()
plt.savefig('Convergence_Particle_History.png', dpi=300, bbox_inches='tight') # Salvataggio immagine
plt.show()


#%% Plot Mode shapes
FEMUP_anal.Plot_Geometry(MS = FEMUP_anal.Calibrated_Modes[:,mp-1]*mf)

#%% Plot MAC matrix
# Planar view
plt.figure(figsize=(10, 6)) 
plt.imshow(MAC_matrix_cal, cmap='viridis', aspect='auto')
for (i, j), val in np.ndenumerate(MAC_matrix_cal):
    if val > 0.2: plt.text(j, i, f"{val:.2f}", ha='center', va='center', color='white' if val < 0.5 else 'black')
plt.colorbar(label='MAC Value')
plt.title('MAC Matrix - Calibrated Modes')
plt.xlabel('Experimental Modes')
plt.ylabel('Calibrated Modes')
plt.xticks(ticks=np.arange(len(FEMUP_anal.Exp_Freq)), labels=np.arange(1, len(FEMUP_anal.Exp_Freq) + 1))
plt.yticks(ticks=np.arange(len(FEMUP_anal.Exp_Freq)),
              labels=np.arange(1, len(FEMUP_anal.Exp_Freq) + 1))
plt.tight_layout()
plt.savefig('MAC_Matrix_2D.png', dpi=300, bbox_inches='tight') # Salvataggio immagine
plt.show()

# 3D view
fig = plt.figure(figsize=(10, 6))
ax = fig.add_subplot(111, projection='3d')
_x = np.arange(1, len(FEMUP_anal.Exp_Freq) + 1)
_y = np.arange(1, len(FEMUP_anal.Exp_Freq) + 1)
_xx, _yy = np.meshgrid(_x, _y)
x, y = _xx.ravel(), _yy.ravel()
z = np.zeros_like(x)
dz = MAC_matrix_cal.ravel()
dx = dy = 0.8
norm = plt.Normalize(dz.min(), dz.max())
colors = cm.viridis(norm(dz))  # Colors scaled with MAC values
ax.bar3d(x, y, z, dx, dy, dz, color=colors, shade=True)
ax.set_xlabel('Experimental Modes')
ax.set_ylabel('Calibrated Modes')
ax.set_zlabel('MAC Value')
ax.set_xticks(_x + 0.4)
ax.set_yticks(_y + 0.4)
ax.set_xticklabels(np.arange(1, len(FEMUP_anal.Exp_Freq) + 1))
ax.set_yticklabels(np.arange(1, len(FEMUP_anal.Exp_Freq) + 1))
plt.savefig('MAC_Matrix_3D.png', dpi=300, bbox_inches='tight') # Salvataggio immagine
plt.show()

#%% Plot Unc/Calibrated Frequencies vs Experimental Frequencies
plt.figure(figsize=(10, 6))     
plt.plot(FEMUP_anal.Exp_Freq, FEMUP_anal.Uncalibrated_freqs, 's-', label='Uncalibrated', alpha=0.7)
plt.plot(FEMUP_anal.Exp_Freq, FEMUP_anal.Calibrated_freqs, 's-', label='Calibrated', alpha=0.7)
plt.plot(FEMUP_anal.Exp_Freq, FEMUP_anal.Exp_Freq, 'k--', label='Experimental', alpha=0.5)
plt.xlabel('Experimental Frequencies [Hz]') 
plt.ylabel('Frequencies [Hz]')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig('Frequencies_Comparison.png', dpi=300, bbox_inches='tight') # Salvataggio immagine
plt.show()