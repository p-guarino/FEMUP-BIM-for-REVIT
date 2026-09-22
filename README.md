# FEMUP-BIM for Revit

Calibrating a finite element model against dynamic measurements usually happens far away
from the BIM model. Sensor coordinates are copied by hand into a script, the optimisation
runs in a terminal, and the results end up in a folder of plots that nobody opens twice.
The model of the building and the assessment of the building live in different worlds.

This extension puts that loop inside Revit. You import the mesh of your FE model as
parametric families, click the nodes where the accelerometers actually were, declare
which material properties are uncertain and how far they may move, and start the
calibration. A Particle Swarm Optimisation then drives Abaqus through as many frequency
extractions as it needs, pairing numerical and experimental modes by MAC and frequency
distance. When it finishes, the calibrated parameters, the MAC matrix, the convergence
history and a view of the model come back as a Revit drawing sheet — stored next to the
model they describe, in the file the rest of the project already uses.

It was built for heritage structures, where the material properties are genuinely
unknown and a calibrated model is the only honest basis for an assessment, but nothing
in it is specific to masonry.

**→ [Read the walkthrough](WALKTHROUGH.md)** for installation and a step-by-step guide.

---

## What it does

| Panel | Buttons | Purpose |
|---|---|---|
| **Import mesh** | Import OBJ mesh · Import external OBJ mesh | Place the FE mesh nodes and the reference axes in Revit as parametric families. |
| **Model definition** | FEMU · Assign Boundary Conditions | Read the Abaqus `.inp`, assign sensor channels and restraints by selecting nodes, declare the material properties to calibrate. |
| **Model calibration** | Perform sensitivity analysis · Perform modal updating · Show Results | Find which parameters drive the response, calibrate them with a PSO against the experimental modes, and report the outcome on a Revit sheet. |

The calibration itself runs outside Revit: the plug-in generates a Python driver script
and launches it, and that script drives Abaqus through as many frequency extractions as
the optimisation needs.

## Repository contents

```
Myscript.extension/      The pyRevit extension — copy this into %APPDATA%\pyRevit\
Arch_bridge_Femup_BIM/   Example 1 — masonry arch bridge
Pinos_Puente_FEMUP/      Example 2 — Pinos Puente bridge
WALKTHROUGH.md           Installation and usage guide
```

Both example folders are complete working folders: FE input deck, experimental
frequencies and mode shapes, Abaqus driver scripts and the Python launcher. They hold
the input files used for the models presented in the paper below, so they can be used to
reproduce the published results.

> **Unzip `Pinos_Puente_FEMUP/Job_pinos_puente_inp_file.zip` in place before using that
> example.** Its input deck is 47.6 MB and is stored compressed.

## Requirements

* Autodesk Revit 2020 or later
* [pyRevit](https://pyrevitlabs.io) 4.8 or later
* Abaqus/CAE, callable as `abaqus` from a command prompt
* Python 3.6 or later, callable as `python`, with:

```bash
pip install numpy scipy matplotlib plotly pymoo scikit-learn
```

The walkthrough covers the installation in detail, including the constraints on folder
names and the checks worth running before the first calibration.

## Citation

If you use this work, please cite:

> *FEMUP-BIM: A Closed-Loop Framework for Heritage Structures Integrating BIM with
> Structural Assessment through Automated Modal Identification and Finite Element Model
> Updating.*

## Author

Pasquale Guarino — [@p-guarino](https://github.com/p-guarino)
