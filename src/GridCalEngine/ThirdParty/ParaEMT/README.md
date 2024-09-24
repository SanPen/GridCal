<h1> ParaEMT </h1>
<h2> NREL's EMT simulator: An Open Source, Parallelizable, and HPC-Compatible Large-Scale Power System Electro-Magnetic Transient (EMT) Simulator </h2>

Welcome to the ParaEMT simulation package! This open-source tool aims to provide a powerful and flexible platform for simulating electromagnetic transients (EMT) of large-scale inverter-based resource (IBR)-dominated power systems. The purpose of making it open source is to foster a community of EMT simulation and assist in exploring new EMT algorithms and applying advanced computational techniques to EMT simulation.

<h1> Feature </h1>

* EMT modeling 
* EMT Network equation: nodal formulation based on Trapezoidal-rule method
* EMT network parallel solver: BBD
* Parallel computation of updating device states and network historical current
* Compatible with HPC
* Compatible with dynamic-link library (DLL) supported dynamic models
* Compiled with the just-in-time (JIT) compiler, Numba, in Python
* Results down-sampling
* Save simulation progress as a snapshot file, and resume the simulation from a saved snapshot
* Test systems library: the Kundur two-area system, IEEE 9-bus system, IEEE 39-bus system, Western Electricity Coordinating Council (WECC) 179-bus system, and WECC 240-bus system
* Fully open source and transparent: Allows unrestricted access to the underlying source code and encourages active engagement and contributions from the community

<h1> Note </h1>

* Because the Python package nxmetis is now an unmaintained extension, we have disabled the parallel simulation code related to the BBD technique, and the parallel version will be updated once it is ready.
* Solved power flow JSON files of all test systems have been added, and users can skip step0 for test systems.
* For conducting simulations on large systems, we recommend using the snapshot functionality to save a stable steady state (e.g., sim_snp_S5_50u_1pt.pkl for the 240-bus WECC system), and then 
conduct different contingency simulations from the snapshot.
* To reduce the required computer memory for storing simulation results on large systems, we recommend using a larger down-smapling rate, e.g., DSrate=50.
* Currently, we have built a lot of new functions, including **Python code for results plotting, bus/line fault simulation, distributed tramsmission line model, forced oscillation simulation, a license-free power flow solver using Python package ANDES, interface with DLL models, and son on. A new version that contains more functions will be released in the near future**.
* **A user manual webpage of ParaEMT, that includes guidance on installation, configuration, and so on, is under development and will be released in the near future**.


<h1> System component library </h1>

* ParaEMT is under continuous development, and currently supports the following models:

<img src="https://github.com/NREL/ParaEMT_public/assets/102193041/41ff1810-f951-4a28-9a48-3cfb455a627b" width="470">

<h1> Version Advisory </h1>

* Work with Python v3.7+.

<h1> Citing </h1>

* If you use ParaEMT for research or consulting, please cite the following papers ([paper 1](https://ieeexplore.ieee.org/document/10356767) and [paper 2](https://www.sciencedirect.com/science/article/pii/S0378779624006205)) in your publication that uses ParaEMT:
*
```
M. Xiong, B. Wang, D. Vaidhynathan, J. Maack, M. Reynolds, A. Hoke, K. Sun, J. Tan, “ParaEMT: an open source, parallelizable, and HPC-compatible EMT simulator for large-scale IBR-rich power grids,” IEEE Trans. Power Del., vol. 39, no. 2, pp. 911-921, Apr. 2024.
```
```
M. Xiong, B. Wang, D. Vaidhynathan, J. Maack, M. Reynolds, A. Hoke, K. Sun, D. Ramasubramanian, V. Verma, J. Tan, “An open-source parallel EMT simulation framework,” Electric Power Syst. Res., vol. 235, 2024, Art. no. 110734.
```

<h1> Getting Started with ParaEMT </h1>

* To conduct EMT simulations using ParaEMT, follow these steps:

<img src="https://github.com/NREL/ParaEMT_public/assets/102193041/72beb4a9-4aac-475b-a0ab-980435a339b0" width="800">

<h1> Structure of ParaEMT </h1>

* Main Functions and Subfunction Libraries 

  The first function, main_step0_CreateLargeCases, serves the dual purpose of executing and storing the power flow solution and, optionally, generating synthetic large-scale systems. The second function, main_step1_sim, is responsible for initializing and simulating the system dynamics. The third function, main_step2_save, saves the simulation results.

* Simulation Initialization
<img src="https://github.com/NREL/ParaEMT_public/assets/102193041/a27215f5-9778-4ef9-b603-735a245e16ee" width="350">

* Time Domain Simulation 
<img src="https://github.com/NREL/ParaEMT_public/assets/102193041/b8094dd4-7015-4060-a999-521adb4bafc6" width="350">

<h1> Developer </h1>

* ParaEMT has been developed under a Laboratory Directed Research and Development (LDRD) project titled “Large-Scale Electro-magnetic Transient (EMT) Capability for Evaluating 100% Inverter-Based Systems” at the U.S. Department of Energy's National Renewable Energy Laboratory.
* ParaEMT has also been developed under the NREL project titled "Intelligent Phasor-EMT Partitioning (I-PEP) for Accelerated Large-scale IBR Integration Studies (Award # DE-EE00038457)".
* NREL Software Record of Invention :  “Parallelizable Large-Scale Power System Electro-Magnetic Transient (EMT) Simulator”. Authors: Bin Wang, Jonathan Maack, Deepthi Vaidhynathan, Jin Tan, Matthew Reynolds.
https://doelps.org/arntrn

<h1> License </h1>

* ParaEMT is released under a BSD.  
* NREL Software Record of Invention:  Bin Wang, Jonathan Maack, Deepthi Vaidhynathan, Jin Tan, Matthew Reynolds “Parallelizable Large-Scale Power System Electro-Magnetic Transient (EMT) Simulator”.

<h1> Contact </h1>

* For any questions, feedback, or inquiries, please contact our team at ParaEMT@nrel.gov.
* Report bugs or issues by submitting a [GitHub issue](https://github.com/NREL/ParaEMT_public/issues)

<h1> Contribution </h1>
If you're passionate about improving ParaEMT, consider contributing to the future development of ParaEMT, you are also welcome to contact us or send a pull request.


