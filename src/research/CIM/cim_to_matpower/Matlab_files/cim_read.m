function mpc_bb = cim_read( cim_files, boundary_profiles, log_filename )
%   CIM_READ Reads CIM (Common Information Model, IEC 61970) XML files
%       and creates a Matpower case (mpc) case file as BusBreaker model,
%       but also containing information about the NodeBreaker topology.
%
%       The import is implemented through the specially developed for the
%       GARPUR project Python package CIM2Matpower which utilizes the open
%       source PyCIM Python package for parsing CIM files.
%
%   IMPORTANT: Currently only CIMv14 is supported!
%
%   IMPORTANT: The CIM files and the boundary profiles must not contain
%       Unicode characters because then the PyCIM parser fails.
%
%   IMPORTANT: Despite what the Matlab documentation says, if you change 
%       the Python source code files, you must restart Matlab!
%
%   IMPORTANT: The created in the frames of the GARPUR project software
%       quantification platform prototype is tested with CIM data provided
%       by the French TSO RTE. Their files have some peculiarities which
%       differ from the CIMv14 standard. In order to cope with that, some 
%       changes are made directly to the original RTE CIM files by calling
%       explicitly the Python function "fix_RTE_cim_files", specially
%       developed for this purpose. However, if the "fix_RTE_cim_files"
%       function is called on regular CIMv14 files, it will not change them.
%       Irrelevant of whether changes are made or not to the original CIM
%       files, "fix_RTE_cim_files" always leaves XML comments at the end of
%       the file.
%
%   INPUTS:
%       * cim_files - cell array of stings with the filenames of the CIM
%           files to be imported (preferably with full path). Usually they 
%           come in three files: EQ, SV and TP.
%           If "cim_read" is called with no arguments or if "cim_files" is 
%           set to empty string, then a dialogue will open to select 
%           interactively the CIM files. If user hits Cancel, then "cim_read"
%           is terminated and an empty matrix is returned.
%       * boundary_profiles - cell array of stings with the filenames of 
%           the CIM boundary profiles (preferably with full path). Usually 
%           they come in two files: EQ and TP.
%           If "cim_read" is called with 1 or 0 arguments, a dialogue will 
%           open to select the CIM boundary profiles interactively.
%           If "boundary_profiles" is set to empty matrix [] or empty 
%           string '' or if user hits Cancel on the interactive file 
%           selection, then NO boundary profiles are parsed.
%       * log_filename - string with the file name (preferably with full 
%           path) of the log file, which will contain information from the 
%           Python code about the CIM import.
%           If "cim_read" is called with 2 or less arguments, a dialogue 
%           will open to select the log file name interactively.
%           If "log_filename" is set to empty matrix [] or empty string ''
%           or if user hits Cancel on the interactive file selection,
%           then NO log file will be saved.
%
%   OUTPUTS:
%       * mpc_bb - a Matpower case (mpc) which is a BusBreaker model, 
%           containing also a field NodeBreaker_topology which preserves
%           the information from the CIM that cannot be imported in the
%           standard mpc structure but is relevant for the creation of 
%           NodeBreaker model.
%
%   See also: MPC_NODAL2BB, MPC_BB2NODAL and the Python package CIM2Matpower
%
%   Author: Konstantin Gerasimov, kkgerasimov@gmail.com
%   Last revision: 2016.May.10
%   Copyright: This function is created for KU-Leuven as part of the GARPUR
%       project http://www.garpur-project.eu

%% Initialization
separatorLine_Length = 80;
separatorLine_Symbol = '=';
% Python_DIR_SYMBOL = '/';

fprintf(['\n' repmat(separatorLine_Symbol,1,separatorLine_Length) '\n']);

% cim files
if  ~exist('cim_files', 'var') || isempty(cim_files)
    FilterSpec = {'*.xml','CIM files'; ...
                  '*.*',  'All files'};
    DialogTitle = 'Select the _EQ, _TP and _SV CIM files';
    
    [FileName,PathName,~] = uigetfile(FilterSpec,DialogTitle,'MultiSelect', 'on');
    if isequal(FileName,0)
       warning('User canceled the import. NO CIM files are imported!')
       mpc_bb = [];
       fprintf(['\n' repmat(separatorLine_Symbol,1,separatorLine_Length) '\n']);
       return
    else
        for iFor = 1:length(FileName)
            cim_files{iFor} = fullfile(PathName, FileName{iFor});
        end
    end
end

num_cim_files = length(cim_files);
if num_cim_files ~= 3
    warning('CIM files usually come in three: _EQ, _TP and _SV. You have selected %d file(s)!', num_cim_files);
end
if num_cim_files == 3
    % NB: It is very important that the CIM files are read in the
    % following order: EQ, TP and then SV. Otherwise the PyCIM RDFXMLReader
    % fails.
    idx_EQ = find(cellfun(@(x) ~isempty(x),regexp(cim_files,'.*_EQ.xml')));
    idx_TP = find(cellfun(@(x) ~isempty(x),regexp(cim_files,'.*_TP.xml')));
    idx_SV = find(cellfun(@(x) ~isempty(x),regexp(cim_files,'.*_SV.xml')));
    if isempty(idx_EQ) || isempty(idx_TP) || isempty(idx_SV)
        % The names of the CIM files do NOT end with _EQ.xml, _TP.xml or 
        % _SV.xml, so we do NOTHING and suggest that the user has provided 
        % the files in the correct order.
    else
        cim_files = {cim_files{idx_EQ}, cim_files{idx_TP}, cim_files{idx_SV}};
    end
end

fprintf('\nSelected CIM files:\n')
py_cim_files = py.list();
for iFor = 1:num_cim_files
    fprintf('\t%s\n',cim_files{iFor});
    % NB: Python expects the directory to be '/' and NOT '\'! - actually it turns out it doesn't matter
    % py_cim_files.append(strrep(cim_files{iFor}, filesep, Python_DIR_SYMBOL));
    py_cim_files.append(cim_files{iFor});
end

% boundary profiles
if ~exist('boundary_profiles', 'var')
    FilterSpec = {'*.xml','CIM boundary profiles'; ...
                  '*.*',  'All files'};
    DialogTitle = 'Select the EQ and TP CIM boundary profiles';
    
    [FileName,PathName,~] = uigetfile(FilterSpec,DialogTitle,'MultiSelect', 'on');
    if isequal(FileName,0)
       warning('User canceled the import. NO CIM files are imported!');
       boundary_profiles = '';
    else
        for iFor = 1:length(FileName)
            boundary_profiles{iFor} = fullfile(PathName, FileName{iFor});
        end
    end
end

fprintf('\nSelected CIM boundary profiles:\n')
py_boundary_profiles = py.list();
if isempty(boundary_profiles)
    fprintf('\tNONE\n');
else
    num_boundary_profiles = length(boundary_profiles);
    if num_boundary_profiles ~= 2
        warning('CIM boundary profiles usually come in two: EQ and TP. You have selected %d file(s)!', num_boundary_profiles);
    end
    if num_boundary_profiles == 2
        % NB: It is very important not only that the boundary files are read
        % before the CIM files, but also the boundary files must be in the
        % following order: EQ and then TP. Otherwise the PyCIM RDFXMLReader
        % fails. If they are selected interactively by the user, and if thay
        % end with _TP.xml and _TP.xml respectively, then they will be loaded
        % in the correct order.
        idx_EQ = find(cellfun(@(x) ~isempty(x),regexp(boundary_profiles,'.*_EQ.xml')));
        idx_TP = find(cellfun(@(x) ~isempty(x),regexp(boundary_profiles,'.*_TP.xml')));
        if isempty(idx_EQ) || isempty(idx_TP)
            % The names of the CIM files do NOT end with _EQ.xml or _TP.xml, 
            % so we do NOTHING and suggest that the user has provided the 
            % files in the correct order.
        else
            boundary_profiles = {boundary_profiles{idx_EQ}, boundary_profiles{idx_TP}};
        end
    end
    for iFor = 1:num_boundary_profiles
        fprintf('\t%s\n',boundary_profiles{iFor});
        % NB: Python expects the directory to be '/' and NOT '\'! - actually it turns out it doesn't matter
        % py_boundary_profiles.append(strrep(boundary_profiles{iFor}, filesep, Python_DIR_SYMBOL));
        py_boundary_profiles.append(boundary_profiles{iFor});
    end
end

% log file
if ~exist('log_filename', 'var')
    FilterSpec = {'*.log','Log files'; ...
                  '*.txt','Text files'; ...
                  '*.*',  'All files'};
    DialogTitle = 'Save log from CIM import as...';
    
    [FileName,PathName,~] = uiputfile(FilterSpec,DialogTitle);
    if isequal(FileName,0)
       log_filename = '';
    else
       log_filename = fullfile(PathName, FileName);
    end
elseif isempty(log_filename)
    % fix in case an empty matrix [] is given
    log_filename = '';
end

fprintf('\nLog file:\n')
if isempty(log_filename)
    fprintf('\tNONE\n\n');
else
    fprintf('\t%s\n\n', log_filename);
    % NB: Python expects the directory to be '/' and NOT '\'! - actually it turns out it doesn't matter
    % log_filename = strrep(log_filename, filesep, Python_DIR_SYMBOL);
end


%% Run the Python code for importing CIM files
% pre-process CIM files - NB: it is explicitly called within the Python "cim_to_mpc" function
% py.CIM2Matpower.PreProcess_CIM_files.fix_RTE_cim_files(py_cim_files)

mpc_py = py.CIM2Matpower.CIM2Matpower.cim_to_mpc(py_cim_files, py_boundary_profiles, log_filename);

% imported_CIM = lib.py2mat(mpc_py);
% NB: if "lib.py2mat(mpc_py)" fails for some reason, the below three lines of code can be used
py.scipy.io.savemat('imported_CIM.mat', mpc_py);
imported_CIM = load('imported_CIM');
% delete('imported_CIM.mat');

%% Post-process the imported CIM data
% fix the mpc
mpc_bb.baseMVA = imported_CIM.baseMVA;
[~,order] = sort(imported_CIM.bus(:,1));
mpc_bb.bus = imported_CIM.bus(order,:);
mpc_bb.branch = imported_CIM.branch;
mpc_bb.gen = imported_CIM.gen;

% fix the NodeBreaker_topology structure
% NB: The fileds within the mpc_bb.NodeBreaker_topology struct are ordered in the order of
% creation, so in order to keep them alphabetically ordered, do not move
% around the lines below. However, it was chosen that the fields within
% the fields are reordered explicitly with the "orderfields" function.
mpc_bb.NodeBreaker_topology.CIM_filenames = imported_CIM.NodeBreaker_topology.CIM_filenames;

if iscell(imported_CIM.NodeBreaker_topology.areas)
    areas = cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.areas);
    [~,order] = sort([areas.id]);
    mpc_bb.NodeBreaker_topology.Areas = orderfields(areas(order),{'id', 'name', 'id_cim', 'pTolerance', 'netInterchange'});
    clear areas
else
    mpc_bb.NodeBreaker_topology.Areas = [];
end

% mpc_bb.NodeBreaker_topology.Branches are not sorted in order to correspond to the mpc_bb.branch
% (the problem is that unlike mpc.bus, mpc.branch do not have explicitly id)
mpc_bb.NodeBreaker_topology.Branches = orderfields(cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.branches),...
    {'id', 'node_from_id', 'node_to_id', 'name', 'id_cim', 'status_from', 'status_to'});

% mpc_bb.NodeBreaker_topology.Generators are not sorted in order to correspond to the mpc_bb.gen
% (the problem is that unlike mpc_bb.bus, mpc_bb.gen do not have explicitly id)
mpc_bb.NodeBreaker_topology.Generators = orderfields(cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.generators),...
    {'id', 'node_id', 'name', 'id_cim', 'mode', 'type', 'fuel_type'});

loads = cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.loads);
[~,order] = sort([loads.node_id]);
mpc_bb.NodeBreaker_topology.Loads = orderfields(loads(order),{'node_id', 'name', 'id_cim', 'status', 'p_mw', 'q_mvar'});
clear loads

nodes = cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.nodes);
[~,order] = sort([nodes.id]);
mpc_bb.NodeBreaker_topology.Nodes = orderfields(nodes(order),{'id', 'bus_id', 'desc', 'name', 'id_cim'});
clear nodes

if iscell(imported_CIM.NodeBreaker_topology.phasetapchangers)
    mpc_bb.NodeBreaker_topology.PhaseTapChangers = orderfields(cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.phasetapchangers),...
        {'branch_id', 'id_cim', 'step_num_list', 'angle_shift_deg_list', 'x_pu_list', 'continuous_position'});
else
    mpc_bb.NodeBreaker_topology.PhaseTapChangers = [];
end

if iscell(imported_CIM.NodeBreaker_topology.ratiotapchangers)
    mpc_bb.NodeBreaker_topology.RatioTapChangers = orderfields(cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.ratiotapchangers),...
        {'branch_id', 'id_cim', 'lowStep', 'highStep', 'neutralU_kV', 'stepVoltageIncrement_kV', 'continuousPosition'...
        'hasRegulatingControl', 'RC_discrete', 'RC_mode', 'RC_targetRange_kV', 'RC_targetValue_kV'});
else
    mpc_bb.NodeBreaker_topology.RatioTapChangers = [];
end

if iscell(imported_CIM.NodeBreaker_topology.shunts)
    shunts = cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.shunts);
    [~,order] = sort([shunts.node_id]);
    mpc_bb.NodeBreaker_topology.Shunts = orderfields(shunts(order),...
        {'node_id', 'name', 'id_cim', 'status', 'bPerSection_MVAr', 'gPerSection_MVAr', 'maximumSections', 'numActiveSections'});
    clear shunts
else
    mpc_bb.NodeBreaker_topology.Shunts = [];
end

if iscell(imported_CIM.NodeBreaker_topology.substations)
    substations = cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.substations);
    [~,order] = sort({substations.name});
    mpc_bb.NodeBreaker_topology.Substations = orderfields(substations(order),{'name', 'node_id_list', 'id_cim'});
    clear substations
else
    mpc_bb.NodeBreaker_topology.Substations = [];
end

if iscell(imported_CIM.NodeBreaker_topology.switches)
    mpc_bb.NodeBreaker_topology.Switches = orderfields(cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.switches),...
        {'node_from_id', 'node_to_id', 'name', 'id_cim', 'branch_id', 'status'});
else
    mpc_bb.NodeBreaker_topology.Switches = [];
end

if iscell(imported_CIM.NodeBreaker_topology.zones)
    zones = cellfun(@(elem) elem, imported_CIM.NodeBreaker_topology.zones);
    [~,order] = sort([zones.id]);
    mpc_bb.NodeBreaker_topology.Zones = orderfields(zones(order),{'id', 'name', 'id_cim'});
    clear zones
else
    mpc_bb.NodeBreaker_topology.Zones = [];
end

% raise flag that the topology is BusBranch
mpc_bb.NodeBreaker_topology.is_mpc_NodeBreaker = false;

%% Matpower function to display summary about the import mpc
fprintf('\nSummary of the created Matpower case:\n')
case_info(mpc_bb)

%% End cim_read()
fprintf(['\n' repmat(separatorLine_Symbol,1,separatorLine_Length) '\n']);
end

%% END of file
