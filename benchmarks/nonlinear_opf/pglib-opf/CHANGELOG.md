PGLib OPF Benchmarks Change Log
===============================

### v23.07
- Add 2 cases from the Synthetic Australian system project
- Add 5 cases from the EPIGRIDS project
- Revised API cases to have more realistic reactive power dispatch, see PowerModelsAnnex v0.9 
- Updated baseline results and case generation to PowerModels v0.19

### v21.07
- Add 60 bus Nordic system and 8387 bus pegase system

### v20.07
- Add 18 cases from ARPA-e's Grid Optimization Competition, Challenge 1 Final Event
- Update some case names from `_tamu` to `_activ` (#26)
- Updated baseline results and case generation to PowerModels v0.17
- Removed `pglib_opf_case30_fsr.m` due to marginal benchmarking value
- Removed 500, 2000 and 10000 bus `activ` cases in favor of similar grid optimization competition cases
- Removed 2316 bus `SDET` case in favor of similar grid optimization competition cases

### v19.05
- Minor fixes to generator bounds, #22, #29

### v19.01
- Fixed generator voltage setpoints, #5
- Made thermal limits monotonic, #15
- Updated Polish network source files to MATPOWER v7.0, #17
- Simplified generator data, #18
- Made minor corrections to the fuel cost model
- Updated baseline results and case generation to PowerModels v0.9

### v18.08
- Add TAMU cases, #7
- Add SDET cases, #11
- Add GOC cases

### v18.06
- Cleaned up transformer parameters, #4
- Added default base kv values, #6
- Updated baseline results and case generation to PowerModels v0.7

### v17.08
- Initial release, 108 cases

