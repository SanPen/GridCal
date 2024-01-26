
Theory
==========


General
------------

.. toctree::
    :maxdepth: 3

    theory/from_objects_to_matrices
    theory/branch_model
    theory/xfo_sc

Power Flow
------------------

The following subsections include theory about the power flow algorithms supported by
**GridCal**. For control modes (both :ref:`reactive power control<q_control>` and
:ref:`transformer OLTC control<taps_control>`), refer to the
:ref:`Power Flow Driver API Reference<pf_driver>`.

.. toctree::
    :maxdepth: 3

    theory/power_flow/newton_raphson
    theory/power_flow/levenberg_marquardt
    theory/power_flow/fast_decoupled
    theory/power_flow/dc_approximation
    theory/power_flow/linear_ac_power_flow
    theory/power_flow/holomorphic_embedding
    theory/power_flow/post_power_flow
    theory/power_flow/continuation_power_flow
    theory/power_flow/distributed_slack


Optimal power flow
------------------------------------

.. toctree::
    :maxdepth: 3

    theory/opf/opf
    theory/opf/opf_dc_ts
    theory/opf/opf_ac_ts
    theory/opf/hydro


Short Circuit
------------------

.. toctree::
    :maxdepth: 3

    theory/short_circuit/3_phase_sc


Linear factors
------------------------------------------------------------------------

.. toctree::
    :maxdepth: 3

    theory/ptdf


Investments Evaluation
------------------------------------

.. toctree::
    :maxdepth: 3

    theory/investments_evaluation