function mpc_nodal = mpc_bb2nodal(mpc_bb)
%   MPC_BB2NODAL Transforms the Matpower case (mpc) file from BusBreaker 
%       to NodeBranch topology (based on the data from the original CIM files).
%
%       The NodeBreaker topology means that switches and breakers are 
%       represented as low-impedence branches. This model is used for 
%       optimization of switching actions (in the GARPUR project this is 
%       implemented in AMPL). However, sometimes the low-impedences might
%       cause the admittance matrix of the mpc to be ill conditioned and
%       thus the AC powerflow will not converge or will give wrong results.
%       In order to cope with this problem, MPC_NODAL2BB function can be 
%       used to translate back the NodeBreaker to BusBranch model. 
%
%   INPUTS:
%       * mpc_bb - mpc which is a BusBranch model. 
%
%   OUTPUTS:
%       * mpc_nodal - mpc which is a NodeBranch model. 
%
%   See also: MPC_NODAL2BB, CIM_READ
%
%   Author(s): Konstantin Gerasimov, kkgerasimov@gmail.com
%   Last revision: 2016.May.10
%   Copyright: This function is created for KU-Leuven as part of the GARPUR
%       project http://www.garpur-project.eu

%% Checks
if ~isfield(mpc_bb,'NodeBreaker_topology')
    error('The mpc does not have data about NodeBreaker topology!')
end

mpc_nodal = mpc_bb; % this is in order to preserve all other data added to the mpc

if mpc_bb.NodeBreaker_topology.is_mpc_NodeBreaker
    warning('The mpc is already NodeBreaker model and thus the same mpc is returned!');
    return
end

%% Initialization
DEFAULT_SWITCH_IMPEDANCE = 1e-6;

define_constants;  % The Matpower constants

%% Create new buses, one for each node
num_bus_cols = size(mpc_bb.bus,2);
num_nodes = length(mpc_bb.NodeBreaker_topology.Nodes);
mpc_nodal.bus = zeros(num_nodes, num_bus_cols);
for iNode = 1 : num_nodes
    mpc_nodal.bus(iNode, BUS_I) = mpc_bb.NodeBreaker_topology.Nodes(iNode).id;
    iBusBB = find(mpc_bb.bus(:, BUS_I) == mpc_bb.NodeBreaker_topology.Nodes(iNode).bus_id);
    mpc_nodal.NodeBreaker_topology.Nodes(iNode).bus_id = iNode;
    mpc_nodal.bus(iNode, BUS_TYPE) = mpc_bb.bus(iBusBB, BUS_TYPE); % NB: This may hypotetically result in multiple REF buses... but then again it might not be a problem at all because they would be connected through low impedance switches.
    iLoads = find(and([mpc_bb.NodeBreaker_topology.Loads.node_id] == iNode, [mpc_bb.NodeBreaker_topology.Loads.status] == true));
    if iLoads
        mpc_nodal.bus(iNode, PD) = sum([mpc_bb.NodeBreaker_topology.Loads(iLoads).p_mw]);
        mpc_nodal.bus(iNode, QD) = sum([mpc_bb.NodeBreaker_topology.Loads(iLoads).q_mvar]);
    end
    iShunts = find(and([mpc_bb.NodeBreaker_topology.Shunts.node_id] == iNode, [mpc_bb.NodeBreaker_topology.Shunts.status] == true));
    if iShunts
        mpc_nodal.bus(iNode, GS) = sum([mpc_bb.NodeBreaker_topology.Shunts(iShunts).gPerSection_MVAr].*[mpc_bb.NodeBreaker_topology.Shunts(iShunts).numActiveSections]);
        mpc_nodal.bus(iNode, BS) = sum([mpc_bb.NodeBreaker_topology.Shunts(iShunts).bPerSection_MVAr].*[mpc_bb.NodeBreaker_topology.Shunts(iShunts).numActiveSections]);
    end
    mpc_nodal.bus(iNode, BUS_AREA:end) = mpc_bb.bus(iBusBB, BUS_AREA:end);
end

%% Renumber the branches' TO and FROM buses and add the switches as branches
num_branch_cols = size(mpc_bb.branch,2);
num_branches_wo_switches = size(mpc_bb.branch,1); % number of branches (without the switches)
num_switches = length(mpc_bb.NodeBreaker_topology.Switches);
mpc_nodal.branch = [mpc_bb.branch; zeros(num_switches, num_branch_cols)];
for iBranch = 1 : num_branches_wo_switches
    mpc_nodal.branch(iBranch, F_BUS) = mpc_bb.NodeBreaker_topology.Branches(iBranch).node_from_id;
    mpc_nodal.branch(iBranch, T_BUS) = mpc_bb.NodeBreaker_topology.Branches(iBranch).node_to_id;
end

iSwitch = 1;
for iBranch = num_branches_wo_switches+1 : num_branches_wo_switches+num_switches
    mpc_nodal.branch(iBranch, F_BUS) = mpc_bb.NodeBreaker_topology.Switches(iSwitch).node_from_id;
    mpc_nodal.branch(iBranch, T_BUS) = mpc_bb.NodeBreaker_topology.Switches(iSwitch).node_to_id;
    mpc_nodal.branch(iBranch, BR_X) = DEFAULT_SWITCH_IMPEDANCE;
    mpc_nodal.branch(iBranch, BR_STATUS) = mpc_bb.NodeBreaker_topology.Switches(iSwitch).status;
    mpc_nodal.NodeBreaker_topology.Switches(iSwitch).branch_id = iBranch;
    iSwitch = iSwitch + 1;
end

%% Renumber generators buses
num_gens = size(mpc_nodal.gen,1);
for iGen = 1 : num_gens
    mpc_nodal.gen(iGen, GEN_BUS) = mpc_bb.NodeBreaker_topology.Generators(iGen).node_id;
end

%% Raise flag that the topology is NodeBreaker
mpc_nodal.NodeBreaker_topology.is_mpc_NodeBreaker = true;
mpc_nodal.NodeBreaker_topology.DEFAULT_SWITCH_IMPEDANCE = DEFAULT_SWITCH_IMPEDANCE;

end

%% END of file
