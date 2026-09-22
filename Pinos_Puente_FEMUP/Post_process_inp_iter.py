

# IMPORT TOOLBOXES
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import os
import numpy as np


################################################################################
# PARAMETERS
################################################################################

nmodes=18
Tolnodes=0.01
n_numCpus=15
WD=r"D:\Users\User\Desktop\Workfolder\Pinos_Puente_FEMUP"
name_FEM="Job_pinos_puente"
name_PART="Pinos_Puente"
name_PART_ASSEM="Pinos_Puente-1"
Sensors_file="Sensors.txt"
jobname="Job_pinos_puente_iter"


################################################################################
# READ ODB
################################################################################
name_freq_file = "Num_Freq_34294.csv"
name_MOD_file = "Num_Modes_34294.csv"

# Create Object for model updating
os.chdir(WD)  # Change Directory
 
# Read Positions of sensors
cont = 0
instance_sensors = []
Sensors = []
with open(Sensors_file,'r') as file:
    for line in file:
        if cont>0:
            instance_sensors.append(line.strip().split(',')[-1][1:])
            Sensors.append(line.strip().split(',')[0:-1])
        cont += 1

Sensors = np.array(Sensors).astype(float)

#---------------------------------
Mdb()


# Postprocessing
# -------------------------------
# -------------------------------
# Open odb file
nameodb = WD+"\\"+jobname+".odb"
myOdb = session.openOdb(name=nameodb)

# Resonant Frequencies
# -------------------------------
numfreq = np.zeros((nmodes,1))
for count in range(1,nmodes+1):
     frame = myOdb.steps['Modal Step'].frames[count]
     numfreq[count-1] = float(frame.description.split()[7])

# MODE SHAPES 
# -------------------------------
phi = np.zeros((np.shape(Sensors)[0],nmodes))

session.viewports['Viewport: 1'].setValues(displayedObject=myOdb)
for ij in np.arange(np.shape(Sensors)[0]):
    a = session.xyDataListFromField(odb=myOdb, outputPosition=NODAL, variable=(('U',NODAL), ), nodeSets=('SENSOR_POSITION'+str(ij+1), ))
    vec = Sensors[ij,3:]  # Dir vector of the sensor
    dispnode = np.zeros((nmodes,3))
    for ijij in np.arange(3):
     cont = 0  
     for values in a[ijij+1].data:
         if cont>= nmodes:
             break
         dispnode[cont,ijij] = values[1] 
         cont += 1
    for ijij in np.arange(nmodes):
        phi[ij,ijij] = np.dot(dispnode[ijij,:],vec) # Dot product

np.savetxt(name_freq_file, numfreq, delimiter=",")
np.savetxt(name_MOD_file, phi, delimiter=",")