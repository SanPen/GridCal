function mpc_bb = mpc_nodal2bb(mpc_nodal_ORIGINAL)
%   MPC_NODAL2BB Transforms the Matpower case (mpc) file from NodeBreaker 
%       to BusBranch topology (based on the data from the original CIM files).
%
%       The NodeBreaker topology means that switches and breakers are 
%       represented as low-impedence branches. This model is used for 
%       optimization of switching actions (in the GARPUR project this is 
%       implemented in AMPL). However, sometimes the low-impedences might
%       cause the admittance matrix of the mpc to be ill conditioned and
%       thus the AC powerflow will not converge or will give wrong results.
%       In order to cope with this problem, this function can be used to
%       translate back the NodeBreaker to BusBranch model. 
%
%   INPUTS:
%       * mpc_nodal_ORIGINAL - mpc which is a NodeBreaker model. 
%
%   OUTPUTS:
%       * mpc_bb - mpc which is a BusBranch model. 
%
%   See also: MPC_BB2NODAL, CIM_READ
%
%   Author(s): Konstantin Gerasimov, kkgerasimov@gmail.com
%   Last revision: 2016.May.10
%   Copyright: This function is created for KU-Leuven as part of the GARPUR
%       project http://www.garpur-project.eu


%   LEGEND of abbreviations used in variable names:
%       bb = bus-branch
%       br = branch
%       col = column
%       num = number
%       orig = original, i.e. which comes as input to this function
%       sw = switch

%% Checks
mpc_bb = mpc_nodal_ORIGINAL; % it is here in the beginning in order to be returned if the input is already BusBranch model

if ~isfield(mpc_nodal_ORIGINAL,'NodeBreaker_topology')
    warning('The mpc does not have data about NodeBreaker topology. Most probably it is already BusBranch topology and thus the same mpc is returned!')
    return
end
if ~mpc_nodal_ORIGINAL.NodeBreaker_topology.is_mpc_NodeBreaker
    warning('The mpc is already BusBranch model and thus the same mpc is returned!');
    return
end

%% Initializations
define_constants;  % The Matpower constants

% check the consistency of the input model
assert(length(mpc_nodal_ORIGINAL.bus(:,BUS_I)) == length(mpc_nodal_ORIGINAL.NodeBreaker_topology.Nodes));

ORIGINAL_BusIDs = mpc_nodal_ORIGINAL.bus(:,BUS_I);
NEW_BusIDs = zeros(size(ORIGINAL_BusIDs));

num_switches = length(mpc_nodal_ORIGINAL.NodeBreaker_topology.Switches);
iBranches_toDELETE = zeros(size(mpc_nodal_ORIGINAL.branch,1),1);

%% Transform from BusBreaker to NodeBranch topology
for iSwitch = 1 : num_switches
    orig_NodeID_From = mpc_nodal_ORIGINAL.NodeBreaker_topology.Switches(iSwitch).node_from_id;
    orig_NodeID_To   = mpc_nodal_ORIGINAL.NodeBreaker_topology.Switches(iSwitch).node_to_id;
    orig_BusID_From  = mpc_nodal_ORIGINAL.NodeBreaker_topology.Nodes([mpc_nodal_ORIGINAL.NodeBreaker_topology.Nodes.id]==orig_NodeID_From).bus_id;
    orig_BusID_To    = mpc_nodal_ORIGINAL.NodeBreaker_topology.Nodes([mpc_nodal_ORIGINAL.NodeBreaker_topology.Nodes.id]==orig_NodeID_To).bus_id;
    
    iBranchSw = mpc_bb.NodeBreaker_topology.Switches(iSwitch).branch_id;
    mpc_bb.NodeBreaker_topology.Switches(iSwitch).branch_id = 0; % Delete the branch id for the switch, because the branch of the switch itself will be removed
    
    switch_Status = mpc_bb.branch(iBranchSw, BR_STATUS);
    mpc_bb.NodeBreaker_topology.Switches(iSwitch).status = switch_Status; % NB: This suggests that AMPL is going to account for switching actions by changing the branch status
    
    iBranches_toDELETE(iBranchSw) = 1; % mark the switch branch for deletion in the mpc_bb.branch
    
    if switch_Status
        % the switch is closed => merge its both nodes (previously separate buses) in one bus
        iBus_From = find(mpc_nodal_ORIGINAL.bus(:, BUS_I) == orig_BusID_From);
        iBus_To   = find(mpc_nodal_ORIGINAL.bus(:, BUS_I) == orig_BusID_To);
        
        if NEW_BusIDs(iBus_From)
            % the bus was previously renumbered
            new_BusID = NEW_BusIDs(iBus_From);
        else
            % the bus was not previously renumbered
            new_BusID = ORIGINAL_BusIDs(iBus_From);
        end
        if NEW_BusIDs(iBus_To)
            % the bus was previously renumbered
            old_BusID = NEW_BusIDs(iBus_To);
        else
            % the bus was not previously renumbered
            old_BusID = ORIGINAL_BusIDs(iBus_To);
        end
        % renumber Buses
        NEW_BusIDs(NEW_BusIDs == old_BusID) = new_BusID;
        NEW_BusIDs(ORIGINAL_BusIDs == old_BusID) = new_BusID;
        
    else
        % the switch is opened => Do nothing and leave its both nodes as separate buses
        fprintf('Switch(%d) is switched OFF. \n', iSwitch);
    end
end

% add the numbers also of the buses which should not be renumbered
NEW_BusIDs(NEW_BusIDs==0) = ORIGINAL_BusIDs(NEW_BusIDs==0);

% Create new, sequential (starting from 1) busIDs
list_unique_NEW_BusIDs = unique(NEW_BusIDs);
num_NEW_BusIDs = length(list_unique_NEW_BusIDs);
NEW_BusIDs_SEQUENTIAL = zeros(size(NEW_BusIDs));
for iBusNEW = 1:num_NEW_BusIDs
    NEW_BusIDs_SEQUENTIAL(NEW_BusIDs == list_unique_NEW_BusIDs(iBusNEW)) = iBusNEW;
end
% Save the new sequential numbering in order to be able to match back
% which nodes belong to which buses
for iNode = 1:length(mpc_bb.NodeBreaker_topology.Nodes)
    mpc_bb.NodeBreaker_topology.Nodes(iNode).bus_id = NEW_BusIDs_SEQUENTIAL(iNode);
end

%% Create the new Matpower bus matrix
num_BusCols = length(mpc_nodal_ORIGINAL.bus(1,:));
buses_NEW = zeros(num_NEW_BusIDs,num_BusCols);
for iBus = 1:num_NEW_BusIDs
    iBuses = find(NEW_BusIDs_SEQUENTIAL == iBus);
    % copy all columns of the first bus from the new bus group (all voltages, angles and so on are assumed to be the same)
    buses_NEW(iBus,:) = mpc_nodal_ORIGINAL.bus(iBuses(1),:);
    % fix the demand and shunts
    buses_NEW(iBus,PD) = sum(mpc_nodal_ORIGINAL.bus(iBuses,PD));
    buses_NEW(iBus,QD) = sum(mpc_nodal_ORIGINAL.bus(iBuses,QD));
    buses_NEW(iBus,GS) = sum(mpc_nodal_ORIGINAL.bus(iBuses,GS));
    buses_NEW(iBus,BS) = sum(mpc_nodal_ORIGINAL.bus(iBuses,BS));
    % fix the bus number
    buses_NEW(iBus,BUS_I) = iBus;
end
mpc_bb.bus = buses_NEW;

%% Adjust the numbering of branches and generators
mpc_bb.branch(logical(iBranches_toDELETE),:) = []; % remove the switch branches
for iBranch = 1:size(mpc_bb.branch,1)
    mpc_bb.branch(iBranch,F_BUS) = NEW_BusIDs_SEQUENTIAL( ORIGINAL_BusIDs == mpc_bb.branch(iBranch,F_BUS) );
    mpc_bb.branch(iBranch,T_BUS) = NEW_BusIDs_SEQUENTIAL( ORIGINAL_BusIDs == mpc_bb.branch(iBranch,T_BUS) );
end

for iGen = 1:size(mpc_bb.gen,1)
    mpc_bb.gen(iGen,GEN_BUS) = NEW_BusIDs_SEQUENTIAL( ORIGINAL_BusIDs == mpc_bb.gen(iGen,GEN_BUS) );
end

%% Cleanup
mpc_bb.NodeBreaker_topology.is_mpc_NodeBreaker = false; % raise flag that the topology is BusBranch
mpc_bb.NodeBreaker_topology.DEFAULT_SWITCH_IMPEDANCE = [];

end

%% END of file
