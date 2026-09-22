
# Code to launch the model upating from Python
import numpy as np
import subprocess
from FEMUP_tools import *
import matplotlib.pyplot as plt


FEMUP_options = {
    # Model options
    "nmodes": 18,
    "Tolnodes": 0.01,
    "n_numCpus": 15,

    # Optimization hyper-parameters
    # (12 materials * 2 properties)
    "xo": [
        7400000000, 1800,  # Arch1
        7400000000, 1800,  # Arch2
        7400000000, 1800,  # Arch3
        2700000000, 2200,  # Chapel
        400000000,  1800,  # Infill1
        400000000,  1800,  # Infill2
        400000000,  1800,  # Infill3
        7400000000, 2000,  # Pier1
        7400000000, 2000,  # Pier2
        2000000000, 2000,  # Road1
        2000000000, 2000,  # Road2
        2000000000, 2000   # Road3
    ],
    
    "xmin": [0.70] * 24,  # Lower bounds (moltiplicato per 24 parametri)
    "xmax": [1.30] * 24,  # Upper bounds (moltiplicato per 24 parametri)

    "Material": [
        "Arch1", "Arch1",
        "Arch2", "Arch2",
        "Arch3", "Arch3",
        "Chapel", "Chapel",
        "Infill1", "Infill1",
        "Infill2", "Infill2",
        "Infill3", "Infill3",
        "Pier1", "Pier1",
        "Pier2", "Pier2",
        "Road1", "Road1",
        "Road2", "Road2",
        "Road3", "Road3"
    ],

    "PROP": [
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens",
        "E", "Dens"
    ],

    "nparticles": 10, 
    "max_iter": 10,    
    "velocity_rate": 0.025,   
    "w": 0.9,   
    "c1": 2,    
    "c2": 2,    
    "FEMUP_method": "PSO",   

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
FEMUP_anal.RunSensAna(deltax = 1./100.)

FEMUP_anal.rel_err_MAC

FEMUP_anal.Plot_Sens_Results()


