# FEMUP-BIM — Walkthrough

A step-by-step guide to installing and using the **FEMUP-BIM** pyRevit extension: a
closed-loop workflow that takes a Revit/BIM model of a heritage structure, assigns
sensor channels and boundary conditions on its nodes, runs a Finite Element Model
Updating (FEMU) against experimental modal data in Abaqus, and returns the calibrated
results as a Revit drawing sheet.

The two example folders in this repository contain the exact input files used for the
models presented in:

> *FEMUP-BIM: A Closed-Loop Framework for Heritage Structures Integrating BIM with
> Structural Assessment through Automated Modal Identification and Finite Element
> Model Updating.*

You can use them to reproduce the results reported in the paper.

---

## Table of contents

1. [Repository contents](#1-repository-contents)
2. [Requirements](#2-requirements)
3. [Installing pyRevit and the extension](#3-installing-pyrevit-and-the-extension)
4. [Preparing the working folder](#4-preparing-the-working-folder)
5. [Step 1 — Import the mesh](#5-step-1--import-the-mesh)
6. [Step 2 — Model definition (FEMU)](#6-step-2--model-definition-femu)
7. [Step 3 — Perform modal updating](#7-step-3--perform-modal-updating)
8. [Step 4 — Show Results](#8-step-4--show-results)
9. [Step 5 — Perform sensitivity analysis](#9-step-5--perform-sensitivity-analysis)
10. [File reference](#10-file-reference)

---

## 1. Repository contents

```
Myscript.extension/          The pyRevit extension (the plug-in itself)
  FEMUP-BIM.tab/
    Import mesh.panel/           Import OBJ mesh | Import external OBJ mesh
    Model definition.panel/      FEMU | Assign Boundary Conditions
    Model calibration.panel/     Perform sensitivity analysis | Perform modal updating | Show Results

Arch_bridge_Femup_BIM/       Example 1 — masonry arch bridge (working folder)
Pinos_Puente_FEMUP/          Example 2 — Pinos Puente bridge (working folder)
```

Each example folder is a complete **working folder**: it is the template you should
copy when you set up your own model. Everything the calibration needs — FE input deck,
experimental data, Abaqus driver scripts and the Python launcher — lives in one flat
folder, because all the scripts are executed with that folder as the current directory.

The `.pushbutton` folders of the two import buttons also carry the Revit families used
by the plug-in (`Point.rfa`, `X axis.rfa`, `Y axis.rfa`, `Z axis.rfa`,
`Z axis_neg.rfa`, `Femup_sheet.rfa`). They are loaded into the project automatically,
so you never need to load them by hand.

---

## 2. Requirements

### On the Revit machine

| Software | Version | Notes |
|---|---|---|
| Autodesk Revit | 2020 or later | The *Show Results* button uses the `ImageInstance` API introduced in Revit 2020. |
| pyRevit | 4.8 or later | Provides the IronPython runtime and the ribbon loader. |
| Abaqus/CAE | any version with a working `abaqus` command | Must be callable as `abaqus` from a normal command prompt. |
| CPython | 3.6 or later | Must be callable as `python` from a normal command prompt (the plug-in launches `python Launch_From_Python_run.py`). This is **not** the IronPython inside Revit. |

The Revit-side scripts only use pyRevit, the Revit API and .NET WinForms — nothing to
install beyond pyRevit itself.

### Python packages (CPython, not Revit)

The calibration engine `FEMUP_tools.py` imports:

```bash
pip install numpy scipy matplotlib plotly pymoo scikit-learn
```

| Package | Used for |
|---|---|
| `numpy` | all numerical work; also imported by the Abaqus scripts |
| `pymoo` (>= 0.6) | the PSO optimiser (`pymoo.algorithms.soo.nonconvex.pso`) |
| `scikit-learn` | `mean_squared_error` |
| `matplotlib` | convergence, MAC and frequency plots |
| `plotly` | interactive 3-D geometry / mode-shape viewer (`Geometry_Model.html`) |
| `scipy` | pulled in as a `pymoo` / `scikit-learn` dependency |

Check the install from a command prompt:

```bash
python -c "import numpy, pymoo, sklearn, matplotlib, plotly; print('ok')"
```

And check that Abaqus is on the PATH:

```bash
abaqus information=release
```

If either command fails, the *Run* button will start a process that dies immediately.

---

## 3. Installing pyRevit and the extension

### 3.1 Get pyRevit

* Official site: <https://pyrevitlabs.io>
* Releases / installer: <https://github.com/pyrevitlabs/pyRevit/releases>

Download the latest `pyRevit_<version>_signed.exe` installer and run it with Revit
closed. The installer registers the pyRevit add-in for every Revit version it finds on
the machine.

### 3.2 Install the extension

Copy the whole `Myscript.extension` folder (keep the name and the `.extension` suffix)
into:

```
C:\Users\<your-username>\AppData\Roaming\pyRevit\
```

so that you end up with:

```
C:\Users\<your-username>\AppData\Roaming\pyRevit\Myscript.extension\FEMUP-BIM.tab\...
```

You can paste `%APPDATA%\pyRevit` into the Explorer address bar to get there directly.
Create the `pyRevit` folder if it does not exist.

Start Revit. A new **FEMUP-BIM** tab appears with three panels:

```
Import mesh          Model definition              Model calibration
├ Import OBJ mesh    ├ FEMU                        ├ Perform sensitivity analysis
└ Import external    └ Assign Boundary Conditions  ├ Perform modal updating
  OBJ mesh                                         └ Show Results
```

If the tab does not show up, open **pyRevit → Settings → Custom Extension Directories**,
add `C:\Users\<your-username>\AppData\Roaming\pyRevit`, save, then **pyRevit → Reload**.

---

## 4. Preparing the working folder

Copy one of the example folders and replace its contents with your own model. The
working folder must contain:

**You provide**

| File | What it is |
|---|---|
| `<job>.inp` | The Abaqus input deck of the model (parts, materials, assembly, mesh). |
| `<model>.obj` | The geometry exported from Abaqus, used for the Revit representation. |
| `Experimental_Frequencies.txt` | One experimental natural frequency per line, in Hz. |
| `Experimental_Mode_shapes.txt` | The experimental mode-shape matrix. |
| `Modal_Geometry.txt` | Optional wireframe used by the plotly viewer (see §4.4). |

**Shipped with the examples — copy them across unchanged**

| File | Role |
|---|---|
| `FEMUP_tools.py` | The FEMU engine: builds the model, drives Abaqus, runs the PSO, computes MAC. |
| `Prepare_inp_base.py` | Abaqus/CAE script: creates the sensor node sets, the boundary conditions and the frequency step, then writes the base `.inp`. |
| `Post_process_inp_base.py` | Abaqus/CAE script: reads the `.odb`, extracts frequencies and projects the modal displacements onto the sensor directions. |
| `Launch_From_Python.py` | Template driver for the model updating. |
| `Launch_Sensitivity_Analysis.py` | Template driver for the sensitivity analysis. |

**Generated for you** — by the plug-in or by the run: `<objname>_outer_points.txt`,
`inp_parts_materials.txt`, `Materials_Properties.txt`, `Sensors.txt`, `log_ch_*.txt`,
`log_bc_*.txt`, `Prepare_inp.py`, `Post_process_inp_iter.py`,
`Launch_From_Python_run.py`, `Launch_Sensitivity_Analysis_run.py`, and all the result
files. None of these has to be present when you start.

### 4.1 Exporting the OBJ from Abaqus

In Abaqus/CAE, switch to the **Assembly** module and use
**File → Export → OBJ…** on the current viewport.

**Before exporting, add three axis markers.** The importer takes the **last three
vertices of the OBJ file** as the positions of the X, Y and Z axis symbols placed in
Revit. In both examples these are three single-point parts instanced last in the
assembly, on the positive axes at a distance of roughly one tenth of the model length:

```
# Pinos Puente — last three vertices of pinos_puente.obj
v 3.9439      -0.00030657   -0.00016184     -> X axis marker
v 0.000178565  3.9432        5.21717e-05    -> Y axis marker
v 0.000298729 -0.00030657    3.94344        -> Z axis marker
```

Create one tiny part per axis, instance the three of them **after** the structure, and
export. Without them the importer will consume three real mesh vertices for the axes.

**Units.** Export the OBJ in the same units as the `.inp` — metres in both examples.
Neither import button applies any unit conversion: the OBJ coordinates are placed in
Revit exactly as they are, and they are read straight back out into `Sensors.txt` and
matched against the Abaqus node coordinates. The numbers must be identical, so do not
rescale the OBJ on export.

### 4.2 `Experimental_Frequencies.txt`

One frequency per line, in Hz, in ascending order, no header:

```
6.03992364205733
10.8862282030959
13.0093860612473
22.7260205812234
```

### 4.3 `Experimental_Mode_shapes.txt`

A plain matrix, **one row per measured channel, one column per mode**, whitespace or
tab separated, no header. The number of columns must equal the number of lines in
`Experimental_Frequencies.txt`.

```
0.128301728197345    0.203888456916785   -0.114435644713517    1
-0.594357241782568  -0.997113958416372    0.171652296302687    0
-0.186745329771914  -1                   -1                    0
...
```

> **The row order is the contract of the whole workflow.** Row *i* of
> `Experimental_Mode_shapes.txt` must correspond to data row *i* of `Sensors.txt`.
> The post-processor extracts the numerical displacement at sensor *i* and projects it
> onto the direction stored in row *i* of `Sensors.txt`. If the two orders disagree,
> the calibration runs to completion and returns meaningless MAC values.
>
> In the Pinos Puente example both files have exactly **18** rows: 18 channels, 4 modes.
> Use `0` for a channel that was not measured in a given mode — zero entries are
> excluded from the MAC computation.

### 4.4 `Modal_Geometry.txt`

An optional wireframe used only by `FEMUP_anal.Plot_Geometry()` to draw the interactive
plotly view (`Geometry_Model.html`). It is a text file with labelled blocks:

```
GEOMETRY DEFINITION

*NODES ID, X, Y, X
1,0.,-1.5,0.
...
*END
*LINES NODE 1 - NODE 2
...
*END
*SENSORS [ID,DIR (1-x, 2-y, 3-z),NAME]
...
*END
*COLOR PLANE
...
*END
*KINETIC EQUATIONS
...
*END
```

`Arch_bridge_Femup_BIM/Modal_Geometry.txt` is a complete working example.
If you do not want this plot, remove the `"Geometry_File"` entry from `Dirnames` and
comment out the `Plot_Geometry()` calls in the launcher — otherwise the run stops when
the file is missing.

### 4.5 Keep accented characters out of paths and names

**Use plain ASCII for the working folder, for the file names inside it, and for the
part, instance and material names in the `.inp`.** Accented letters — `à è é ì ò ù`, and
non-ASCII characters in general — can break the run at a point far away from where you
typed them, with an error message that does not mention the path at all.

The reason is the number of hand-offs the working folder path goes through:

```
Revit / pyRevit (IronPython 2.7)
  -> %USERPROFILE%\Documents\log_directory.txt      plain text
  -> Launch_From_Python_run.py                      WD = r"..."
  -> Prepare_inp.py / Post_process_inp_iter.py      WD = r"..."
  -> Abaqus/CAE (Python 2.7)
  -> the `abaqus` command line
```

Both IronPython inside Revit and the Python interpreter inside Abaqus are Python 2, and
none of these files is written with an explicit encoding, so a non-ASCII character is
stored using whatever default codec is active. Depending on the Windows code page it
either raises a `UnicodeEncodeError` or is silently written as a different character,
and the Abaqus script then fails to find a folder that looks perfectly correct on screen.

Names travel the same way: the part, instance and material names read from the `.inp`
are written into `inp_parts_materials.txt`, shown in the drop-downs, and written back
into the generated launcher as `"Material": ["..."]` — a Python source file that Abaqus
has to import.

Spaces are fine — the examples use them (`arch mesh.obj`, `materials sensitivity
analysis.txt`) and the scripts always run with the working folder as the current
directory, so file names are never passed as bare command-line arguments.

> The scripts in this repository already carry a trace of this: `Prepare_inp_base.py`
> has the comment `# Parallel mode (Removed special char 'à')` on a line where an
> accented character had to be taken out to make the file work.

If your Windows user name contains an accent, the safest move is to put the working
folder somewhere else entirely — `C:\FEMUP\<model>` rather than anywhere under
`C:\Users\<name>\`.

---

## 5. Step 1 — Import the mesh

Open (or create) the Revit project that will host the model, then use the
**Import mesh** panel. Both buttons first load the required families into the project —
the node family, the three axis symbols and the FEMUP title block — and then read the
OBJ you select and place the elements.

### 5.1 `Import OBJ mesh`

Places a `Point` family instance at **every** vertex of the mesh and draws a blue model
line for **every** edge of every face. You see the full geometry, edges included, so it
is the better choice when you want a readable picture of the model — but it is slow and
heavy. For reference, `arch mesh.obj` has 27,363 vertices and 30,278 faces, which means
about 27k family instances plus tens of thousands of model lines in a single
transaction. Use it on small meshes, and expect several minutes on a large one. A
progress bar with a *Cancel* button is shown during the placement.

### 5.2 `Import external OBJ mesh`

Places a `Point` only on the **boundary (surface) nodes** — the vertices belonging to
an edge that is used by a single face — and does not draw any line. Much faster, and
enough for picking sensor positions, which is what you normally do on the outer surface
anyway.

In both cases the three axis symbols are placed at the last three OBJ vertices and
overridden in red.

**The `_outer_points.txt` file.** On top of placing the families, this button writes a
text file listing the boundary vertices it kept. It is named after the OBJ, with
`_outer_points` appended, and it is saved **next to the OBJ file** — not in the working
folder, unless the two happen to be the same place:

```
pinos_puente.obj   ->   pinos_puente_outer_points.txt
```

One line per point, `x, y, z` with six decimals, comma separated, no header, in the same
coordinates as the OBJ:

```
40.051700, -2.848910, 0.133516
40.080900, -2.848290, 0.133947
40.046200, -2.848480, 0.159408
```

Nothing in the workflow reads it back — it is a by-product, useful to check how much of
the mesh was kept or to reuse the surface nodes elsewhere. For `pinos_puente.obj` it
comes out at 70,499 points from 83,786 vertices, about 2 MB, which is why it is not
shipped in this repository: the file is rewritten from scratch, overwriting any previous
version, every time you press the button.

### 5.3 Units

Both buttons apply **no unit conversion**: the OBJ numbers are written into Revit as they
are. That is why the coordinates in `Pinos_Puente_FEMUP/Sensors.txt`
(e.g. `34.790400, -1.800720, 0.400444`) are numerically the same as the Abaqus ones —
which is exactly what `Prepare_inp_base.py` needs when it calls `nodes.getClosest()` to
match each sensor to the nearest mesh node.

The practical consequence is that the model is not placed at its real-world size in
Revit: a bridge modelled in metres in Abaqus is drawn as if those numbers were feet, so
it appears about 3.28 times smaller. That is intentional and harmless — the geometry is
used for picking nodes, not for measuring — and it is what keeps the sensor coordinates
consistent with the FE model.

### 5.4 Working with the placed elements

The nodes and the axes are ordinary Revit family instances, so they behave like any
other family:

* **Pin** them (`Modify → Pin`) so you cannot drag them by accident. This is worth doing
  right after the import — a node moved by mistake changes the coordinate written to
  `Sensors.txt`.
* **Delete** them like any element, and re-run the import to start over.
* **Resize** them: they are parametric. The `Point` family is currently **50 mm**, which
  reads well at the scale of the examples in this repository. Select one node →
  **Edit Type** → change the size → *OK* updates every instance of that type. The same
  applies to the axis families.

---

## 6. Step 2 — Model definition (FEMU)

Click **FEMU**. A small dialog offers five actions, to be used roughly in this order.

### 6.1 Select Folder

Pick the working folder. Everything the plug-in writes goes there. The choice is
remembered in `%USERPROFILE%\Documents\log_directory.txt` and reused as the default by
the other buttons, so you only need to set it once per session.

### 6.2 Import INP File

Pick the `.inp`. The script scans it for `*Part`, `*Material` and `*Instance` entries
and writes a summary next to the `.inp`:

```
inp_parts_materials.txt

Parts:
Pinos_Puente

Materials:
Sandstone

Assemblies:
PINOS_PUENTE-1
```

This file is what fills the *Instance*, *Part*, *Assembly* and *Material* drop-downs in
every later dialog, so run this **before** assigning sensors, boundary conditions or
material properties. Note that it is written **beside the `.inp`** — if the `.inp` lives
somewhere else, copy `inp_parts_materials.txt` into the working folder.

### 6.3 Assign Sensor Positions

1. In the Revit view, **select the node(s)** where the sensor sits (the `Point` family
   instances). You can select several at once if the same channel definition applies to
   all of them.
2. Click **FEMU → Assign Sensor Positions**.
3. In the *Sensor Configuration* window, tick the **direction** box (`X`, `Y` or `Z`) and
   then the **sign** (`+` or `-`) on that row. For a sensor measuring along positive X,
   tick `X` and leave `+` selected.

   > The `+` boxes are pre-ticked on all three rows. That is only the default sign —
   > **a direction is written out only if its own `X` / `Y` / `Z` box is ticked.**
4. Choose the **Instance** the node belongs to, from the drop-down fed by
   `inp_parts_materials.txt`.
5. *OK*. The plug-in writes one line to a numbered log file `log_ch_<n>.txt` in the
   working folder and draws a red arrow family at the node so you can see what you have
   assigned.

**Direction conventions.** One assignment produces **one line**, i.e. **one measurement
channel**, whose direction is the vector formed by the boxes you ticked:

* `X` + `-` → `-1, 0, 0` — a channel along negative X.
* `X` + `-` **and** `Z` + `+` in the same dialog → `-1, 0, 1` — a **single** channel
  measuring along the diagonal between −X and +Z. The post-processor normalises this
  vector and projects the nodal displacement onto it. Use this for an inclined sensor.
* For a **bi-axial** sensor — two independent channels at the same node — assign the
  node **twice**, once per direction, so it produces two lines. This is what the
  provided `Sensors.txt` does:

  ```
  34.790400, -1.800720, 0.400444, 0,  0, 1, PINOS_PUENTE-1
  34.790400, -1.800720, 0.400444, 0, -1, 0, PINOS_PUENTE-1
  ```

  Those are rows 1 and 2, matching rows 1 and 2 of `Experimental_Mode_shapes.txt`.

**Made a mistake?** The `log_ch_*.txt` files are ordinary text files in the working
folder. If you picked the wrong node or the wrong direction, just delete the offending
`log_ch_<n>.txt` (and the red arrow in Revit) and assign it again. Nothing is final
until the next step.

### 6.4 Export Sensor Positions

Merges every `log_ch_*.txt` in numeric order into a single `Sensors.txt`, adds the
header line, and **deletes the individual logs**:

```
Coord x, Coord y, Coord z, dir1, dir2, dir3, Instance Part
34.790400, -1.800720, 0.400444, 0, 0, 1, PINOS_PUENTE-1
...
```

The order of the rows is the order in which you assigned the channels. Check it against
`Experimental_Mode_shapes.txt` now — this is the last easy moment to fix it.

### 6.5 Assign Material Properties

Defines which material properties are candidates for calibration and the interval they
may vary within.

1. Select the material from the drop-down (populated from `inp_parts_materials.txt`).
2. Tick **Elastic Modulus E (MPa)**, **Mass Density (kg/m³)**, or both, depending on
   what you want to calibrate.
3. For each ticked property fill the three boxes, left to right:
   **minimum — nominal — maximum**. The nominal value is the starting point; the
   optimiser searches between minimum and maximum.
4. **Save**.

This appends a row to `Materials_Properties.txt` in the working folder, creating it the
first time and replacing the row if you save the same material again:

```
Material, E_min, E_nom, E_max, Dens_min, Dens_nom, Dens_max
Sandstone, 8908000000.0, 10480000000.0, 12052000000.0, 1776.5, 2090, 2403.5
```

Repeat for every material you want to calibrate. A property left unticked is stored as
`0, 0, 0` and is simply ignored later — only properties with a **nominal value greater
than zero** become optimisation variables.

The Poisson ratio is **not** a calibration variable: it is not asked for in the dialog
and not written to the file. Set it directly in the `.inp`.

> If you have a `Materials_Properties.txt` written by an earlier version, with the three
> extra `v_min, v_nom, v_max` columns, you do not have to touch it: it is still read
> correctly, and the extra columns are dropped the next time you save a material from
> the dialog.

> Units: the values are written verbatim into the Abaqus model, so use the units of your
> `.inp`. In the examples E is given in Pa (`1.048e10`) despite the dialog label saying
> MPa — follow your `.inp`, not the label.

### 6.6 Assign Boundary Conditions

Same idea as the sensors, on its own ribbon button.

1. Select the node(s) in Revit.
2. Click **Assign Boundary Conditions**.
3. Tick the degrees of freedom to restrain — `X`, `Y`, `Z`, `URX`, `URY`, `URZ` — and
   pick the Part/Assembly instance.
4. *OK*, then confirm the file name in the *Save BC Log As* dialog. The default is
   `log_bc_<n>.txt` in the working folder; keep it there.

The file is written with a header and one line per node:

```
Coord x, Coord y, Coord z, U1, U2, U3, UR1, UR2, UR3, Instance Part
12.100200, -1.800770, 0.117642, 1, 1, 1, 0, 0, 0, PINOS_PUENTE-1
```

There is **no** "export boundary conditions" step: each `log_bc_<n>.txt` stays a
separate file, and the launcher points at one of them by name. Group all the nodes that
share the same restraint into a single assignment so you end up with few files.

> `Prepare_inp_base.py` applies the translational restraints `U1`, `U2`, `U3` only; the
> three rotational flags are written to the file but not used, which is the normal case
> for solid meshes.

### 6.7 Making the boundary conditions reach Abaqus

Creating the `log_bc_<n>.txt` file is not enough on its own: the launcher has to be told
which BC file to use, otherwise the model is solved free-free and the calibration
silently ignores your restraints. Three things must line up.

**1. The `"bc_file"` entry in the launcher.** `Launch_From_Python.py` carries it
commented out, inside `Dirnames`:

```python
Dirnames = {
    "WD": r"...",
    "name_FEM": "Job_pinos_puente",
    ...
    #"bc_file": "log_bc_1.txt",   # uncommented automatically by "Optimize / Update BCs"
```

**Edit the file name so that it matches the BC file you actually created.** If you saved
your restraints as `log_bc_3.txt`, the line must read `#"bc_file": "log_bc_3.txt",` —
leave it commented, the plug-in takes care of that. The path is relative to the working
folder, so the plain file name is what you want.

**2. The tick box.** In *Perform modal updating*, tick **Optimize / Update BCs** before
pressing *OK*. That is what removes the `#` when `Launch_From_Python_run.py` is
generated. Leave it unticked and the entry stays commented, which is the free-free case.

**3. The name must be `bc_file`, not anything else.** The key in `Dirnames` is copied
into the Abaqus script `Prepare_inp_base.py`, which declares:

```python
bc_file = ''
...
if len(bc_file) > 1 and os.path.exists(bc_file):
```

The substitution only fires on a line that starts with the key name, so the entry in the
launcher and the variable in the Abaqus script have to be spelled identically. If you
rename one, rename the other.

**Checking it worked.** After pressing *OK*, open `Launch_From_Python_run.py` and confirm
the line is now active:

```python
"bc_file": "log_bc_1.txt",
```

Then, once the run has started, open the generated `Prepare_inp.py` in the working folder
and confirm it contains `bc_file="log_bc_1.txt"` instead of `bc_file = ''`. If it does,
the restrained node sets `BC_N-0`, `BC_N-1`, … are being created in the Abaqus model.

> Only the nodes listed in that one file are restrained. If your restraints came out of
> several separate assignments, merge the `log_bc_*.txt` files by hand into a single file
> (one header line, then all the node rows) and point `"bc_file"` at it.

---

## 7. Step 3 — Perform modal updating

This button collects everything above into a runnable driver script and launches it.

### 7.1 Fill in the form

| Field | What to put |
|---|---|
| **Select Folder** | The working folder. Selecting it loads the materials and the parts/assemblies lists. |
| **File .inp** | The Abaqus input deck. Selecting it also sets *Job Name*. |
| **Experimental Frequencies** | `Experimental_Frequencies.txt`. |
| **Experimental Mode Shapes** | `Experimental_Mode_shapes.txt`. |
| **Part** | The part name, from `inp_parts_materials.txt`. |
| **Materials to Optimize** | Tick the materials to calibrate. Only those with a non-zero nominal value in `Materials_Properties.txt` contribute variables. |
| **Assembly** | The assembly instance name. |
| **Number of Modes** | Number of eigenvalues Abaqus extracts. Keep it comfortably above the number of experimental modes so every experimental mode finds a numerical partner. |
| **Nodes Tolerance** | Tolerance passed to the Abaqus scripts when matching sensor coordinates to mesh nodes. `0.01` in both examples. |
| **Num of Particles** | PSO swarm size. `30` in the arch-bridge example. |
| **Maximum Iterations** | PSO generations. `30` in the arch-bridge example. |
| **Alpha Parameter** | Weight on the mode-shape term of the cost function, `alpha * sum(1 - MAC_i)`. |
| **Beta Parameter** | Weight on the frequency term, `beta * sum(abs(f_num,i - f_exp,i) / f_exp,i)`. `1.0` / `10.0` in the examples: frequencies are the dominant target, mode shapes the tie-breaker. |
| **Eta Parameter** | Weight on the third (reserved) term; `0`. |
| **Boundary Conditions** | Tick **Optimize / Update BCs** to have the boundary-condition file applied — see [§6.7](#67-making-the-boundary-conditions-reach-abaqus). |
| **Job Name** | Abaqus job name, defaults to the `.inp` base name. |

**Cost of a run.** Each particle, at each iteration, is a full Abaqus frequency
extraction. `30 x 30 = 900` solver runs is normal for these models, which is hours to
days depending on the mesh and the machine. Start with a small swarm and few iterations
to check the plumbing end to end, then scale up.

### 7.2 OK — generate the driver

**OK** copies `Launch_From_Python.py` to **`Launch_From_Python_run.py`** in the working
folder and substitutes the values you entered. `Launch_From_Python.py` itself is never
modified, so it stays usable as a template.

The material intervals are converted to the **multiplier** form the optimiser works
with: `xo` receives the nominal values, and `xmin` / `xmax` receive `min/nominal` and
`max/nominal`. A material with `8.908e9 – 1.048e10 – 1.2052e10` becomes
`xo = 1.048e10`, `xmin = 0.85`, `xmax = 1.15`.

Open `Launch_From_Python_run.py` and read it once before running. It is a normal Python
script and everything the calibration will do is visible in it.

### 7.3 Run

**Run** executes `python Launch_From_Python_run.py` with the working folder as the
current directory, in a background thread. The status label shows *Running…* and a
marquee progress bar, while the console output goes to the process itself.

* **Cancel** during a run asks for confirmation and then kills the whole process tree —
  Python, Abaqus and the solver — with `taskkill /F /T`.
* Closing the window while a run is active asks the same question.
* When the process ends you get *Completed* (exit code 0) or the exit code.

What happens inside: `FEMUP_tools.py` writes `Prepare_inp.py` from
`Prepare_inp_base.py`, runs it through `abaqus cae noGUI=` to build the base model with
the sensor node sets, the boundary conditions and the frequency step; then, for every
candidate parameter set, it rewrites the material cards, runs `abaqus job=… interactive`,
post-processes the `.odb` to get frequencies and sensor-projected mode shapes, pairs
numerical and experimental modes by MAC and frequency distance, and evaluates the cost
function. Intermediate Abaqus files (`*.odb`, `*.msg`, `*.sta`, `*.lck`, …) are cleaned
up between iterations.

### 7.4 What you get

In the working folder:

| File | Content |
|---|---|
| `Calibration_Results.txt` | Per mode: experimental frequency, uncalibrated frequency, relative error, MAC; then the same three columns for the calibrated model. |
| `Calibrated_Parameters.txt` | One line per variable: nominal value and calibrated value. |
| `Final_Cost_Function.txt` | The best cost-function value at the last iteration. |
| `Convergence_Cost_History.png` | Cost function of every particle against iteration. |
| `Convergence_Particle_History.png` | Particle positions (the multipliers) against iteration. |
| `MAC_Matrix_2D.png` | MAC matrix of the calibrated model, 2-D. |
| `MAC_Matrix_3D.png` | The same MAC matrix as a 3-D bar plot. |
| `Frequencies_Comparison.png` | Uncalibrated and calibrated frequencies against the experimental ones. |

The first, second, third and fifth of these are the four charts *Show Results* places on
the sheet, so keep their names as they are if you edit the launcher.
| `Geometry_Model.html` | Interactive plotly view of the geometry / mode shapes. |

---

## 8. Step 4 — Show Results

Builds a Revit drawing sheet with the whole calibration report on it.

> **Set up the 3-D view first.** The image on the left of the sheet is produced with
> Revit's own `ExportImage`, which captures **the visible region of the current view**.
> Whatever is on screen is what ends up on the sheet. Open the 3-D view, orient and zoom
> the model the way you want it to appear, hide anything you do not want in the picture,
> and only then press the button.

1. Click **Show Results**.
2. Pick the folder with the FEMUP results (the working folder).

The script captures the current view to `Reference_sheet.png`, creates a new sheet
numbered `FEMUP-01` (then `FEMUP-02`, `FEMUP-03`, … on later runs) named
*Report Calibrazione*, and lays out:

* the captured 3-D model view, top left;
* the convergence plots of the particles and of the cost function, centre;
* the frequency-comparison and MAC-matrix plots, bottom;
* a **Calibrated Params** table, from `Calibrated_Parameters.txt`;
* a **Frequencies and MAC comparison** table, from `Calibration_Results.txt`;
* a FEMUP title block listing the PSO settings (modes, tolerance, particles,
  iterations, alpha, beta), the calibration variables with their ±% bounds and nominal
  values, and the experimental frequencies — all read back from
  `Launch_From_Python_run.py`.

The title block is taken from the family whose type name contains `Cartiglio` — provided
by `Femup_sheet.rfa`, which the import buttons load into the project. If it is not there,
the first title block found in the project is used instead.

A chart that is not found in the folder is skipped without warning, so if part of the
sheet comes out empty, check that the calibration actually finished and wrote the four
PNG files listed in [§7.4](#74-what-you-get).

---

## 9. Step 5 — Perform sensitivity analysis

Answers the question *which parameters actually matter?* before you spend hours on a
calibration. It perturbs each model parameter by a fixed percentage, one at a time, and
measures how much the modal frequencies and the mode shapes move.

It works exactly like *Perform modal updating*, on the other template: it copies
`Launch_Sensitivity_Analysis.py` to **`Launch_Sensitivity_Analysis_run.py`** and fills it
in.

1. **Working Folder** — defaults to the folder already chosen in *FEMU*.
2. **File .inp** — selecting it parses the deck and lists, read-only, every material it
   found with its `*Elastic` modulus and `*Density`, and fills the *Part* and *Assembly*
   drop-downs. It also writes `materials sensitivity analysis.txt` with that summary.
3. **Part** / **Assembly**.
4. **Parameter Variation (%)** — between **1** and **50**, default 1. This becomes
   `RunSensAna(deltax = <n>./100.)` in the generated script.
5. **OK** to generate, **Run** to execute. *Cancel* stops a running analysis the same way
   as in the updating dialog.

Unlike the updating dialog, this one does not ask you to choose the materials: **every**
material with a positive E or density found in the `.inp` becomes a parameter, so the
analysis covers the whole model. `Arch_bridge_Femup_BIM/Launch_Sensitivity_Analysis.py`
shows the resulting shape — 12 materials x 2 properties = 24 parameters.

Outputs, in the working folder:

| File | Content |
|---|---|
| `Sensitivity_Report_Freq.txt` | Relative frequency variation per unit parameter variation, per mode and per parameter. |
| `Sensitivity_Plot_Freq.png` | The same as a chart. |
| `Sensitivity_Report_MAC.txt` | Relative MAC variation per parameter. |
| `Sensitivity_Plot_MAC.png` | The same as a chart. |

Parameters that barely move the response are good candidates to be fixed at their
nominal value, which shrinks the search space of the calibration considerably.

---

## 10. File reference

### Written by the plug-in

| File | Written by | Purpose |
|---|---|---|
| `<objname>_outer_points.txt` | Import external OBJ mesh | The boundary vertices placed in Revit; written next to the OBJ, not in the working folder. |
| `inp_parts_materials.txt` | FEMU → Import INP File | Parts / materials / assemblies read from the `.inp`; feeds every drop-down. |
| `log_ch_<n>.txt` | FEMU → Assign Sensor Positions | One channel each, temporary. |
| `Sensors.txt` | FEMU → Export Sensor Positions | The channel list: coordinates, direction vector, instance. |
| `log_bc_<n>.txt` | Assign Boundary Conditions | Restrained nodes and DOFs. |
| `Materials_Properties.txt` | FEMU → Assign Material Properties | Calibration variables: min / nominal / max for E and rho. |
| `materials sensitivity analysis.txt` | Perform sensitivity analysis | E and rho of every material found in the `.inp`. |
| `Launch_From_Python_run.py` | Perform modal updating → OK | The generated driver. |
| `Launch_Sensitivity_Analysis_run.py` | Perform sensitivity analysis → OK | The generated driver. |
| `Reference_sheet.png` | Show Results | Screen capture of the current Revit view. |
| `%USERPROFILE%\Documents\log_directory.txt` | FEMU → Select Folder | Remembers the working folder across buttons and sessions. |

### Written by the calibration run

`Prepare_inp.py`, `Post_process_inp_iter.py`, `<job>_iter.inp`, `Calibration_Results.txt`,
`Calibrated_Parameters.txt`, `Final_Cost_Function.txt`, `Convergence_Cost_History.png`,
`Convergence_Particle_History.png`, `MAC_Matrix_2D.png`, `MAC_Matrix_3D.png`,
`Frequencies_Comparison.png`, `Geometry_Model.html`, `Sensitivity_Report_*.txt`,
`Sensitivity_Plot_*.png`.
