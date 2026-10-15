% Build 18 authenticated Simulink models for the standard VeraGrid FMUs.

project = fileparts(mfilename('fullpath'));
catalog = fullfile(project, 'catalog');
model_dir = fullfile(project, 'models');
receipt_path = fullfile(project, 'model-build-receipt.json');
cells_path = fullfile(project, 'execution-cells.json');
assert(strcmp(version('-release'), '2025b'), 'MATLAB R2025b is required');
assert(license('test', 'MATLAB') && license('test', 'SIMULINK'), 'MATLAB and Simulink licenses are required');
assert(isfolder(catalog) && isfile(cells_path), 'Incomplete execution bundle');
assert(~isfolder(model_dir) && ~isfile(receipt_path), 'Refusing to overwrite build evidence');
cells = jsondecode(fileread(cells_path));
assert(numel(cells) == 18, 'Exactly 18 cells are required');
mkdir(model_dir);
load_system('simulink');
load_system('simulink_extras');
addpath(genpath(catalog));
model_receipts = cell(18, 1);

for cell_index = 1:18
    cell_data = cells(cell_index);
    fmu_path = fullfile(catalog, strrep(cell_data.fmu_path, '/', filesep));
    [~, fmu_stem, fmu_extension] = fileparts(fmu_path);
    fmu_name = [fmu_stem fmu_extension];
    assert(isfile(fmu_path), 'Missing FMU %s', fmu_path);
    fmu_stream = System.IO.File.OpenRead(fmu_path);
    fmu_hasher = System.Security.Cryptography.SHA256.Create();
    fmu_bytes = fmu_hasher.ComputeHash(fmu_stream);
    fmu_hash = lower(reshape(dec2hex(uint8(fmu_bytes), 2).', 1, []));
    fmu_hasher.Dispose();
    fmu_stream.Dispose();
    assert(strcmp(fmu_hash, cell_data.fmu_sha256), 'FMU hash mismatch');

    model_name = ['VGReplay_' cell_data.model_name];
    model_path = fullfile(model_dir, [model_name '.slx']);
    assert(~isfile(model_path), 'Refusing to overwrite %s', model_path);
    new_system(model_name);
    if strcmp(cell_data.interface, 'me')
        solver = 'ode4';
    else
        solver = 'FixedStepDiscrete';
    end
    set_param(model_name, 'StartTime', '0', 'StopTime', '2', ...
        'SolverType', 'Fixed-step', 'Solver', solver, 'FixedStep', '0.001', ...
        'ReturnWorkspaceOutputs', 'on', 'SaveTime', 'on', 'TimeSaveName', 'tout', ...
        'SaveOutput', 'off', 'SignalLogging', 'off');

    fmu_block = [model_name '/VeraGrid FMU'];
    if strcmp(cell_data.interface, 'cs')
        if strcmp(cell_data.fmi_version, '3.0')
            add_block('simulink_extras/FMU Import/FMU', fmu_block, ...
                'FMUName', fmu_name, 'FMUDebugLogging', 'off', ...
                'FMUSampleTime', '0.001', 'CSEventModeEnabled', 'on', ...
                'Position', [380 90 650 330]);
        else
            add_block('simulink_extras/FMU Import/FMU', fmu_block, ...
                'FMUName', fmu_name, 'FMUDebugLogging', 'off', ...
                'FMUSampleTime', '0.001', 'Position', [380 90 650 330]);
        end
    else
        add_block('simulink_extras/FMU Import/FMU', fmu_block, ...
            'FMUName', fmu_name, 'FMUDebugLogging', 'off', ...
            'Position', [380 90 650 330]);
    end
    set_param(fmu_block, 'FMUInputMapping', 'Flat');
    set_param(fmu_block, 'FMUOutputMapping', 'Flat');
    set_param(model_name, 'SimulationCommand', 'update');

    % Parse only the exact literal grammar emitted by the FMU Import block.
    mask_lines = splitlines(string(get_param(fmu_block, 'MaskDisplay')));
    fprintf('MASK_FIRST_LINE %s %s\n', cell_data.model_name, char(mask_lines(1)));
    if strcmp(cell_data.fmi_version, '3.0')
        identity_token = regexp(char(mask_lines(1)), '^disp\(''([A-Za-z_][A-Za-z0-9_]*) \[(Co-Simulation|Model Exchange), v3\.0\]''\);$', 'tokens', 'once');
        if strcmp(cell_data.interface, 'cs')
            expected_interface_label = 'Co-Simulation';
        else
            expected_interface_label = 'Model Exchange';
        end
        assert(~isempty(identity_token) && strcmp(identity_token{1}, cell_data.model_identifier) ...
            && strcmp(identity_token{2}, expected_interface_label), 'Mask identity mismatch');
    else
        identity_token = regexp(char(mask_lines(1)), '^disp\(''([A-Za-z_][A-Za-z0-9_]*)''\);$', 'tokens', 'once');
        assert(~isempty(identity_token) && strcmp(identity_token{1}, cell_data.model_identifier), 'Mask identity mismatch');
    end
    label_names = cell(numel(mask_lines) - 1, 1);
    label_directions = cell(numel(mask_lines) - 1, 1);
    label_numbers = zeros(numel(mask_lines) - 1, 1);
    for label_index = 2:numel(mask_lines)
        label_token = regexp(char(mask_lines(label_index)), ...
            '^port_label\(''(input|output)'',([1-9][0-9]*),''([A-Za-z_][A-Za-z0-9_]*)''\);$', 'tokens', 'once');
        assert(~isempty(label_token), 'Unexpected MaskDisplay statement');
        label_directions{label_index - 1} = label_token{1};
        label_numbers(label_index - 1) = str2double(label_token{2});
        label_names{label_index - 1} = label_token{3};
    end
    input_selector = strcmp(label_directions, 'input');
    output_selector = strcmp(label_directions, 'output');
    assert(isequal(sort(label_names(input_selector)), sort(cellstr(cell_data.input_names))), 'Input label set mismatch');
    assert(isequal(sort(label_names(output_selector)), sort(cellstr(cell_data.output_names))), 'Output label set mismatch');

    fmu_ports = get_param(fmu_block, 'PortHandles');
    input_port_text = get_param(fmu_ports.Inport, 'PortNumber');
    output_port_text = get_param(fmu_ports.Outport, 'PortNumber');
    if iscell(input_port_text)
        input_port_numbers = zeros(size(input_port_text));
        for port_index = 1:numel(input_port_text)
            if ischar(input_port_text{port_index}) || isstring(input_port_text{port_index})
                input_port_numbers(port_index) = str2double(input_port_text{port_index});
            else
                input_port_numbers(port_index) = double(input_port_text{port_index});
            end
        end
    else
        if ischar(input_port_text) || isstring(input_port_text)
            input_port_numbers = str2double(input_port_text);
        else
            input_port_numbers = double(input_port_text);
        end
    end
    if iscell(output_port_text)
        output_port_numbers = zeros(size(output_port_text));
        for port_index = 1:numel(output_port_text)
            if ischar(output_port_text{port_index}) || isstring(output_port_text{port_index})
                output_port_numbers(port_index) = str2double(output_port_text{port_index});
            else
                output_port_numbers(port_index) = double(output_port_text{port_index});
            end
        end
    else
        if ischar(output_port_text) || isstring(output_port_text)
            output_port_numbers = str2double(output_port_text);
        else
            output_port_numbers = double(output_port_text);
        end
    end
    assert(isequal(sort(input_port_numbers(:)).', 1:numel(cell_data.input_names)), 'Input PortNumber sequence mismatch');
    assert(isequal(sort(output_port_numbers(:)).', 1:numel(cell_data.output_names)), 'Output PortNumber sequence mismatch');

    input_mappings = cell(numel(cell_data.input_names), 1);
    for input_index = 1:numel(cell_data.input_names)
        input_name = char(cell_data.input_names(input_index));
        label_row = find(input_selector & strcmp(label_names, input_name));
        assert(numel(label_row) == 1, 'Ambiguous input label %s', input_name);
        port_number = label_numbers(label_row);
        handle_row = find(input_port_numbers == port_number);
        assert(numel(handle_row) == 1, 'Ambiguous input PortNumber');
        source_block = [model_name '/' input_name];
        add_block('simulink/Sources/In1', source_block, 'Port', num2str(input_index), ...
            'Position', [40 45 + 55 * input_index 120 65 + 55 * input_index]);
        source_ports = get_param(source_block, 'PortHandles');
        add_line(model_name, source_ports.Outport, fmu_ports.Inport(handle_row), 'autorouting', 'on');
        mapping = struct();
        mapping.name = input_name;
        mapping.mask_port_number = port_number;
        mapping.root_port_number = input_index;
        input_mappings{input_index} = mapping;
    end
    output_mappings = cell(numel(cell_data.output_names), 1);
    for output_index = 1:numel(cell_data.output_names)
        output_name = char(cell_data.output_names(output_index));
        label_row = find(output_selector & strcmp(label_names, output_name));
        assert(numel(label_row) == 1, 'Ambiguous output label %s', output_name);
        port_number = label_numbers(label_row);
        handle_row = find(output_port_numbers == port_number);
        assert(numel(handle_row) == 1, 'Ambiguous output PortNumber');
        sink_block = [model_name '/Log ' output_name];
        add_block('simulink/Sinks/To Workspace', sink_block, 'VariableName', output_name, ...
            'SaveFormat', 'Timeseries', 'MaxDataPoints', 'inf', ...
            'Position', [760 45 + 55 * output_index 920 75 + 55 * output_index]);
        sink_ports = get_param(sink_block, 'PortHandles');
        add_line(model_name, fmu_ports.Outport(handle_row), sink_ports.Inport, 'autorouting', 'on');
        mapping = struct();
        mapping.name = output_name;
        mapping.mask_port_number = port_number;
        mapping.workspace_variable = output_name;
        output_mappings{output_index} = mapping;
    end
    set_param(model_name, 'PreLoadFcn', '', 'PostLoadFcn', '', 'InitFcn', '', ...
        'StartFcn', '', 'StopFcn', '', 'CloseFcn', '');
    Simulink.BlockDiagram.arrangeSystem(model_name);
    save_system(model_name, model_path);
    model_stream = System.IO.File.OpenRead(model_path);
    model_hasher = System.Security.Cryptography.SHA256.Create();
    model_bytes = model_hasher.ComputeHash(model_stream);
    model_hash = lower(reshape(dec2hex(uint8(model_bytes), 2).', 1, []));
    model_hasher.Dispose();
    model_stream.Dispose();
    close_system(model_name, 0);
    model_receipt = struct();
    model_receipt.model_name = model_name;
    model_receipt.model_file = [model_name '.slx'];
    model_receipt.model_sha256 = model_hash;
    model_receipt.fmu_path = cell_data.fmu_path;
    model_receipt.fmu_sha256 = fmu_hash;
    model_receipt.input_mappings = vertcat(input_mappings{:});
    model_receipt.output_mappings = vertcat(output_mappings{:});
    model_receipt.solver = solver;
    model_receipts{cell_index} = model_receipt;
end

receipt = struct();
receipt.schema = 'veragrid.standard-simulink-model-build/1';
receipt.status = 'PASS_MODELS_BUILT_NOT_SIMULATED';
receipt.created_utc = char(datetime('now', 'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
receipt.host = char(java.net.InetAddress.getLocalHost.getHostName);
receipt.user = char(System.Security.Principal.WindowsIdentity.GetCurrent().Name);
receipt.matlab_release = version('-release');
receipt.matlab_version = version;
receipt.matlab_license = logical(license('test', 'MATLAB'));
receipt.simulink_license = logical(license('test', 'SIMULINK'));
receipt.model_count = 18;
receipt.models = vertcat(model_receipts{:});
receipt_handle = fopen(receipt_path, 'w', 'n', 'UTF-8');
assert(receipt_handle >= 0, 'Cannot create build receipt');
fwrite(receipt_handle, jsonencode(receipt, PrettyPrint=true), 'char');
fwrite(receipt_handle, newline, 'char');
fclose(receipt_handle);
rmpath(genpath(catalog));
fprintf('MODEL_BUILD_RECEIPT=%s\n', receipt_path);
