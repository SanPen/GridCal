# Power Grid Lib - Optimal Power Flow with HVDC Lines

This benchmark library is curated and maintained by the [IEEE PES Task Force on Benchmarks for Validation of Emerging Power System Algorithms](https://power-grid-lib.github.io/) and is designed to evaluate a variation of the Optimal Power Flow problem with HVDC lines.  Specifically, these cases are designed for benchmarking algorithms that solve the following the Non-Convex Nonlinear Program described in the formulation [PDF document](MODEL.pdf). An extensive description of the case data and optimization model is provided in the [transactions paper](https://ieeexplore.ieee.org/document/8636236).  

All of the cases files are curated in an extended version of the [MatACDC](https://www.esat.kuleuven.be/electa/teaching/matacdc/MatACDCManual) data format.  An open-source reference implementations are available in [PowerModelsACDC.jl](https://github.com/hakanergun/PowerModelsACDC.jl).

## Problem Overview

These cases are useful for benchmarking solution methods for a variant of the optimal power flow problem common in the academic literature. The features of this model are:
* Respresentation of the HVDC converter station including converter transformer, harmonic filter and quadratic losses
* Point to point and fully meshed HVDC configuations
* Optimization of the ac side active and reactive power set points and dc side active power set points for all converters
* Parametrized model to omit converter transformers or filters 


## Case File Overview

* CASE_5_3  Power flow data for modified 5 bus, 5 gen, 3 bus dc case based on PJM 5-bus system
* CASE_24_7 based on the IEEE reliability test system with HVDC grid connecting three zones
* CASE_39_10 Power flow data for 39 bus New England system with additional 10 converter stations and 12 dc branches
* CASE_3120_5 Power flow data for Polish system - summer 2008 morning peak, with 5 additional converter stations and 5 dc branches

## Example script to run test case
```
using PowerModelsACDC, PowerModels, Ipopt


ipopt = with_optimizer(Ipopt.Optimizer, tol=1e-6, print_level=0)
s = Dict("output" => Dict("branch_flows" => true), "conv_losses_mp" => true)

file5_3 = "case5_3_he.m"
data = PowerModels.parse_file(file5_3)
data["convdc"] = data["dcconv"]
data["busdc"] = data["dcbus"]
data["branchdc"] = data["dcbranch"]
PowerModelsACDC.process_additional_data!(data)
result5_3 = run_acdcopf(data, ACPPowerModel, ipopt; setting = s)
```
## Contributions

All case files are provided under a [Creative Commons Attribution License](http://creativecommons.org/licenses/by/4.0/), which allows anyone to share or adapt these cases as long as they give appropriate credit to the original author, provide a link to the license, and indicate if changes were made.

Community-based recommendations and contributions are welcome and encouraged in all PGLib repositories. Please feel free to submit comments and questions in the [issue tracker](https://github.com/power-grid-lib/pglib-uc/issues).  Corrections and new network contributions are welcome via pull requests.  All data contributions are subject to a quality assurance review by the repository curator(s).


## Citation Guidelines

This repository is not static.  Consequently, it is critically important to indicate the version number when referencing this repository in scholarly work.

Users of this these cases are encouraged to cite the original source documents mentioned in this overview document.



