

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
jobname="Job_pinos_puente"
bc_file = ''

################################################################################
# PREPARE BASE INP
################################################################################

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

mdb.ModelFromInputFile(name=name_FEM,inputFileName=name_FEM+'.inp')
FEM_m = mdb.models[name_FEM]
FEM_m = FEM_m

FEMassembly = FEM_m.rootAssembly
print("Instance names in the model after uploading .inp file:")
for inst_name in FEMassembly.instances.keys():
       print(inst_name)

# GENERATE SETS WITH THE SENSORS
for i in np.arange(np.shape(Sensors)[0]):
    inst=instance_sensors[i]
    #Sel_node = FEMassembly.instances[inst].nodes.getByBoundingSphere((Sensors[i,0],Sensors[i,1],Sensors[i,2]),Tolnodes)
    Sel_node = FEMassembly.instances[inst].nodes.getClosest((Sensors[i,0],Sensors[i,1],Sensors[i,2]))
    node_el = FEMassembly.instances[inst].nodes.sequenceFromLabels([Sel_node.label])
    #FEMassembly.Set(nodes=Sel_node, name='SENSOR_POSITION'+str(i+1))
    FEMassembly.Set(nodes=node_el, name='SENSOR_POSITION'+str(i+1))

# SET BOUNDARY CONDITIONS
if len(bc_file)>1:
    cont = 0
    instance_bcs = []
    BCS = []
    with open(bc_file,'r') as file:
        for line in file:
            if cont>0:
                instance_bcs.append(line.strip().split(',')[-1][1:])
                BCS.append(line.strip().split(',')[0:-1])
            cont += 1
    BCS = np.array(BCS).astype(float)
    
    for i in np.arange(np.shape(BCS)[0]):
        bc = BCS[i,:]
        inst_bc = instance_bcs[i]
        n1 = FEMassembly.instances[inst_bc].nodes
        Sel_node = n1.getClosest((bc[0],bc[1],bc[2]))
        node_el = FEMassembly.instances[inst].nodes.sequenceFromLabels([Sel_node.label])
        region = FEMassembly.Set(nodes=node_el, name='BC_N-'+str(i))
        if bc[3] == 1 and bc[4] == 1 and bc[5] == 1:
            FEM_m.DisplacementBC(name='BC_N-'+str(i), createStepName='Initial', 
                region=region, u1=SET, u2=SET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET, 
                amplitude=UNSET, distributionType=UNIFORM, fieldName='', 
                localCsys=None)
        if bc[3] == 1 and bc[4] == 1 and bc[5] == 0:
            FEM_m.DisplacementBC(name='BC_N-'+str(i), createStepName='Initial', 
                region=region, u1=SET, u2=SET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET, 
                amplitude=UNSET, distributionType=UNIFORM, fieldName='', 
                localCsys=None)
        if bc[3] == 1 and bc[4] == 0 and bc[5] == 0:
            FEM_m.DisplacementBC(name='BC_N-'+str(i), createStepName='Initial', 
                region=region, u1=SET, u2=UNSET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET, 
                amplitude=UNSET, distributionType=UNIFORM, fieldName='', 
                localCsys=None)
        if bc[3] == 0 and bc[4] == 1 and bc[5] == 1:
            FEM_m.DisplacementBC(name='BC_N-'+str(i), createStepName='Initial', 
                region=region, u1=UNSET, u2=SET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET, 
                amplitude=UNSET, distributionType=UNIFORM, fieldName='', 
                localCsys=None)
        if bc[3] == 0 and bc[4] == 1 and bc[5] == 0:
            FEM_m.DisplacementBC(name='BC_N-'+str(i), createStepName='Initial', 
                region=region, u1=UNSET, u2=SET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET, 
                amplitude=UNSET, distributionType=UNIFORM, fieldName='', 
                localCsys=None)
        if bc[3] == 0 and bc[4] == 0 and bc[5] == 1:
            FEM_m.DisplacementBC(name='BC_N-'+str(i), createStepName='Initial', 
                region=region, u1=UNSET, u2=UNSET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET, 
                amplitude=UNSET, distributionType=UNIFORM, fieldName='', 
                localCsys=None)

# SET NUMBER OF MODES
for istep in FEM_m.steps.keys():
     if istep != 'Initial':
         del FEM_m.steps[istep]

FEM_m.FrequencyStep(name='Modal Step', previous='Initial',numEigen=nmodes)

# Create Load case
####################################################
if n_numCpus == 0:
   myJob1 = mdb.Job(name=jobname, model=name_FEM, description='', type=ANALYSIS, 
       atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90, 
       memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True, 
       explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF, 
       modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine='', 
       scratch='', resultsFormat=ODB)
else:
   myJob1 = mdb.Job(name=jobname, model=name_FEM, description='', type=ANALYSIS, 
       atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90, 
       memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True, 
       explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF, 
       modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine='', 
       scratch='', resultsFormat=ODB, multiprocessingMode=DEFAULT, numCpus=n_numCpus, 
       numDomains=n_numCpus, numGPUs=n_numGPUs)

myJob1 = myJob1
# Write the input file
myJob1.writeInput()

