# IMPORT TOOLBOXES
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import os
import numpy as np

################################################################################
# PARAMETERS
# (Vengono sovrascritti automaticamente da FEMUP_tools.py)
################################################################################

nmodes = 20
Tolnodes = 0.3
n_numCpus = 0
# WD default sicuro per Linux (corrente)
WD = os.getcwd()
name_FEM = 'Job_pinos_puente'
name_PART = 'Pinos_Puente'
name_PART_ASSEM = 'Pinos_Puente-1'
Sensors_file = 'Sensors.txt'
jobname = 'Job_pinos_puente'
name_freq_file = "Num_Freq.csv"
name_MOD_file = "Num_Modes.csv"

################################################################################
# READ ODB (CLUSTER OPTIMIZED)
################################################################################

# Change Directory (Safe check)
if os.path.exists(WD):
    os.chdir(WD)

# Read Positions of sensors
cont = 0
instance_sensors = []
Sensors = []
if os.path.exists(Sensors_file):
    with open(Sensors_file,'r') as file:
        for line in file:
            if cont > 0 and len(line.strip()) > 0:
                parts = line.strip().split(',')
                if len(parts) > 1:
                    # parts: [X, Y, Z, dx, dy, dz, InstanceName]
                    instance_sensors.append(parts[-1][1:])
                    # Sensors matrix: [X, Y, Z, dx, dy, dz]
                    Sensors.append(parts[0:-1])
            cont += 1
    Sensors = np.array(Sensors).astype(float)
else:
    print("Warning: Sensors file not found")
    Sensors = np.array([])

#---------------------------------
# Clear Database
Mdb()

# Postprocessing
# -------------------------------
# Open odb file (Linux Safe Path Join)
nameodb = os.path.join(WD, jobname + ".odb")

if not os.path.exists(nameodb):
    raise Exception("ODB file not found at: " + nameodb)

myOdb = session.openOdb(name=nameodb)

# Check Step Existence
step_name = 'Modal Step'
if step_name not in myOdb.steps.keys():
    # Fallback: try to find the first Frequency step
    for key, val in myOdb.steps.items():
        if val.domain == FREQUENCY:
            step_name = key
            break

output_step = myOdb.steps[step_name]
num_frames = len(output_step.frames)
# Ensure we don't go out of bounds if Abaqus calculated fewer modes
nmodes_extracted = min(nmodes, num_frames - 1) 

# Initialize Arrays
numfreq = np.zeros((nmodes_extracted, 1))
phi = np.zeros((len(Sensors), nmodes_extracted))

# -------------------------------
# FAST EXTRACTION LOOP (Direct ODB Access)
# No Viewports needed - works perfectly on Headless Cluster
# -------------------------------

for m in range(nmodes_extracted):
    # Frame 0 is usually base state, Frame 1 is Mode 1
    frame = output_step.frames[m+1]
    
    # 1. Extract Frequency
    # Try getting it from frame attribute (safer)
    if hasattr(frame, 'frequency'):
        numfreq[m] = frame.frequency
    else:
        # Fallback to string parsing if attribute missing
        try:
            # description format: "Mode 1: Value = 123.45 Freq = 55.55 ..."
            desc = frame.description
            # Assuming 'Freq =' is followed by the value
            if 'Freq =' in desc:
                part = desc.split('Freq =')[1]
                numfreq[m] = float(part.split()[0])
            else:
                # Old fallback from your original code
                numfreq[m] = float(desc.split()[7])
        except:
            numfreq[m] = 0.0

    # 2. Extract Mode Shapes (Displacements)
    # Get the Displacement Field for the whole frame
    disp_field = frame.fieldOutputs['U']
    
    for s in range(len(Sensors)):
        # Reconstruct Set Name (Matches Prepare_inp_base.py)
        set_name = 'SENSOR_POSITION' + str(s+1)
        
        if set_name in myOdb.rootAssembly.nodeSets.keys():
            region = myOdb.rootAssembly.nodeSets[set_name]
            
            # Extract U vector at this specific node
            # getSubset is very fast
            subset = disp_field.getSubset(region=region)
            if len(subset.values) > 0:
                # Vector U = [Ux, Uy, Uz]
                u_vec = subset.values[0].data 
                
                # Sensor Direction = [dx, dy, dz]
                # Sensors array structure assumed: [X, Y, Z, dx, dy, dz]
                sens_dir = Sensors[s, 3:6]
                
                # Normalize direction just in case
                norm_dir = np.linalg.norm(sens_dir)
                if norm_dir > 0:
                    sens_dir = sens_dir / norm_dir
                
                # Project Displacement onto Sensor Direction (Dot Product)
                phi[s, m] = np.dot(u_vec, sens_dir)
        else:
            # Handle missing set case
            phi[s, m] = 0.0

# Close ODB to release file lock
myOdb.close()

# Save CSVs
np.savetxt(name_freq_file, numfreq, delimiter=",")
np.savetxt(name_MOD_file, phi, delimiter=",")