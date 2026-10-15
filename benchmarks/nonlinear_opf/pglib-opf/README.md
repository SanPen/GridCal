# Power Grid Lib - Optimal Power Flow

This benchmark library is curated and maintained by the [IEEE PES Task Force on Benchmarks for Validation of Emerging Power System Algorithms](https://power-grid-lib.github.io/) and is designed to evaluate a well established version of the the AC Optimal Power Flow problem.  This [introductory video](https://youtu.be/fC3hzddCJ2c) and [detailed report](https://arxiv.org/abs/1908.02788) present the motivations and goals of this benchmark library.  In particular, these cases are designed for benchmarking algorithms that solve the following Non-Convex Nonlinear Program,

&nbsp;
![The Mathematical Model of the Optimal Power Flow Problem](MODEL.png?raw=true "Optional Title")
&nbsp;

A detailed description of this mathematical model is available [here](https://arxiv.org/abs/1502.07847).  All of the cases files are curated in the [MATPOWER](https://matpower.org) data format.  Open-source reference implementations are available in [MATPOWER](https://matpower.org) and [PowerModels.jl](https://github.com/lanl-ansi/PowerModels.jl) and baseline results are reported in [BASELINE.md](BASELINE.md).

### Problem Variants

These cases may also be useful for benchmarking the following variants of the Optimal Power Flow problem,
* DC Optimal Power Flow
* AC Optimal Transmission Switching
* DC Optimal Transmission Switching

That said, these cases are curated with the AC Optimal Power Flow problem in mind.  Application to other domains and problem variants should be done with discretion.

## Case File Overview

A forthcoming technical report will detail the sources, motivations, and procedures for curating these case files.

In this repository the network data files are organized into the following three broad groups:

* /*.m - base case benchmarks as originally specified
* /api/*.m - heavily loaded test cases (i.e. binding thermal limit constraints)
* /sad/*.m - small phase angle difference cases (i.e. binding phase angle difference constraints)

## Contributions

All case files are provided under a [Creative Commons Attribution License](http://creativecommons.org/licenses/by/4.0/), which allows anyone to share or adapt these cases as long as they give appropriate credit to the orginal author, provide a link to the license, and indicate if changes were made.

Community-based recommendations and contributions are welcome and encouraged in all PGLib repositories. Please feel free to submit comments and questions in the [issue tracker](https://github.com/power-grid-lib/pglib-opf/issues).  Corrections and new network contributions are welcome via pull requests.  All data contributions are subject to a quality assurance review by the repository curator(s).

## Citation Guidelines

This repository is not static.  Consequently, it is critically important to indicate the version number when referencing this repository in scholarly work.

Users of this these cases are encouraged to cite the original source documents that are indicated in the file headers and the [achrive report](https://arxiv.org/abs/1908.02788).
