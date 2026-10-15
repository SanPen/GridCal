% Build six isolated Simulink models for the normalized first-order FMUs.

project = fileparts(mfilename('fullpath'));
fmu_dir = fullfile(project, 'fmus');
model_dir = fullfile(project, 'models');
receipt_path = fullfile(project, 'model-build-receipt.json');
manifest_path = fullfile(project, 'first-order-fmu-manifest.json');
assert(strcmp(version('-release'), '2025b'), 'This recipe requires MATLAB R2025b');
assert(license('test', 'MATLAB') && license('test', 'SIMULINK'), ...
    'Licensed MATLAB and Simulink are required');
assert(isfile(manifest_path), 'Missing current FMU manifest');
fmu_manifest = jsondecode(fileread(manifest_path));
assert(strcmp(fmu_manifest.status, 'PASS') && fmu_manifest.cell_count == 6 ...
    && fmu_manifest.pass_count == 6, 'Incomplete current FMU matrix');
assert(isfolder(fmu_dir), 'Missing FMU directory: %s', fmu_dir);
assert(~isfolder(model_dir), 'Refusing to overwrite model directory: %s', model_dir);
assert(~isfile(receipt_path), 'Refusing to overwrite receipt: %s', receipt_path);
mkdir(model_dir);

expected_cell_ids = {'fmi10_cs', 'fmi10_me', 'fmi20_cs', ...
    'fmi20_me', 'fmi30_cs', 'fmi30_me'};
fixtures = cell(6, 5);
assert(numel(fmu_manifest.cells) == 6, 'Expected exactly six manifest cells');
for manifest_index = 1:6
    manifest_cell = fmu_manifest.cells(manifest_index);
    assert(strcmp(manifest_cell.cell_id, expected_cell_ids{manifest_index}) ...
        && strcmp(manifest_cell.status, 'PASS'), 'Unexpected manifest cell');
    assert(strcmp(manifest_cell.fmu_name, ...
        [manifest_cell.model_name_requested '.fmu']), 'Unsafe FMU filename');
    assert(isempty(strfind(manifest_cell.fmu_name, '/')) ...
        && isempty(strfind(manifest_cell.fmu_name, '\')), 'Unsafe FMU path');
    fixtures{manifest_index, 1} = manifest_cell.fmi_version;
    fixtures{manifest_index, 2} = upper(manifest_cell.interface);
    fixtures{manifest_index, 3} = manifest_cell.fmu_name;
    fixtures{manifest_index, 4} = manifest_cell.fmu_sha256;
    fixtures{manifest_index, 5} = manifest_cell.fmu_size_bytes;
end

load_system('simulink');
load_system('simulink_extras');
addpath(fmu_dir);
model_receipts = cell(size(fixtures, 1), 1);

for index = 1:size(fixtures, 1)
    fmi_version = fixtures{index, 1};
    interface = fixtures{index, 2};
    fixture_name = fixtures{index, 3};
    expected_hash = fixtures{index, 4};
    fixture_path = fullfile(fmu_dir, fixture_name);
    assert(isfile(fixture_path), 'Missing fixture: %s', fixture_path);
    fixture_info = dir(fixture_path);
    assert(fixture_info.bytes == fixtures{index, 5}, 'Fixture size mismatch');

    fixture_stream = System.IO.File.OpenRead(fixture_path);
    fixture_hasher = System.Security.Cryptography.SHA256.Create();
    fixture_bytes = fixture_hasher.ComputeHash(fixture_stream);
    fixture_hash = lower(reshape(dec2hex(uint8(fixture_bytes), 2).', 1, []));
    fixture_hasher.Dispose();
    fixture_stream.Dispose();
    assert(strcmp(fixture_hash, expected_hash), 'Fixture hash mismatch: %s', fixture_name);

    version_token = strrep(fmi_version, '.', '');
    model_name = ['VGFirstOrderFMI' version_token interface];
    model_path = fullfile(model_dir, [model_name '.slx']);
    assert(~isfile(model_path), 'Refusing to overwrite model: %s', model_path);
    new_system(model_name);

    if strcmp(interface, 'ME')
        solver = 'ode4';
    else
        solver = 'FixedStepDiscrete';
    end
    set_param(model_name, ...
        'StartTime', '0', ...
        'StopTime', '1.2', ...
        'SolverType', 'Fixed-step', ...
        'Solver', solver, ...
        'FixedStep', '0.001', ...
        'ReturnWorkspaceOutputs', 'on', ...
        'SaveTime', 'on', ...
        'TimeSaveName', 'tout', ...
        'SaveOutput', 'off', ...
        'SignalLogging', 'off');

    % Construct u=0; +1 at 0.2 s; -1.5 at 0.5 s; +0.75 at 0.8 s.
    % The explicit 1 ms ZOH establishes u[n] over [t[n], t[n+1]).
    add_block('simulink/Sources/Constant', [model_name '/u base'], ...
        'Value', '0', 'Position', [35 45 85 75]);
    add_block('simulink/Sources/Step', [model_name '/u event 0p2'], ...
        'Time', '0.2', 'Before', '0', 'After', '1.0', ...
        'Position', [35 95 85 125]);
    add_block('simulink/Sources/Step', [model_name '/u event 0p5'], ...
        'Time', '0.5', 'Before', '0', 'After', '-1.5', ...
        'Position', [35 145 85 175]);
    add_block('simulink/Sources/Step', [model_name '/u event 0p8'], ...
        'Time', '0.8', 'Before', '0', 'After', '0.75', ...
        'Position', [35 195 85 225]);
    add_block('simulink/Math Operations/Sum', [model_name '/u schedule'], ...
        'Inputs', '++++', 'Position', [135 85 165 190]);
    add_line(model_name, 'u base/1', 'u schedule/1');
    add_line(model_name, 'u event 0p2/1', 'u schedule/2');
    add_line(model_name, 'u event 0p5/1', 'u schedule/3');
    add_line(model_name, 'u event 0p8/1', 'u schedule/4');
    add_block('simulink/Discrete/Zero-Order Hold', [model_name '/u ZOH 1ms'], ...
        'SampleTime', '0.001', 'Position', [205 115 270 155]);
    add_line(model_name, 'u schedule/1', 'u ZOH 1ms/1');

    fmu_block = [model_name '/VeraGrid first order FMU'];
    if strcmp(interface, 'CS')
        if strcmp(fmi_version, '3.0')
            add_block('simulink_extras/FMU Import/FMU', fmu_block, ...
                'FMUName', fixture_name, ...
                'FMUDebugLogging', 'off', ...
                'FMUSampleTime', '0.001', ...
                'CSEventModeEnabled', 'on', ...
                'Position', [345 90 560 190]);
        else
            add_block('simulink_extras/FMU Import/FMU', fmu_block, ...
                'FMUName', fixture_name, ...
                'FMUDebugLogging', 'off', ...
                'FMUSampleTime', '0.001', ...
                'Position', [345 90 560 190]);
        end
    else
        add_block('simulink_extras/FMU Import/FMU', fmu_block, ...
            'FMUName', fixture_name, ...
            'FMUDebugLogging', 'off', ...
            'Position', [345 90 560 190]);
    end

    set_param(model_name, 'SimulationCommand', 'update');
    fmu_ports = get_param(fmu_block, 'PortHandles');
    assert(numel(fmu_ports.Inport) == 1, 'Expected one input in %s', model_name);
    assert(numel(fmu_ports.Outport) == 1, 'Expected one output in %s', model_name);
    zoh_ports = get_param([model_name '/u ZOH 1ms'], 'PortHandles');
    add_line(model_name, zoh_ports.Outport, fmu_ports.Inport(1), 'autorouting', 'on');

    add_block('simulink/Sinks/To Workspace', [model_name '/Log u'], ...
        'VariableName', 'u_command', ...
        'SaveFormat', 'Timeseries', ...
        'MaxDataPoints', 'inf', ...
        'Position', [335 235 470 270]);
    u_log_ports = get_param([model_name '/Log u'], 'PortHandles');
    add_line(model_name, zoh_ports.Outport, u_log_ports.Inport, 'autorouting', 'on');

    add_block('simulink/Sinks/To Workspace', [model_name '/Log x'], ...
        'VariableName', 'x_state', ...
        'SaveFormat', 'Timeseries', ...
        'MaxDataPoints', 'inf', ...
        'Position', [640 120 775 155]);
    x_log_ports = get_param([model_name '/Log x'], 'PortHandles');
    add_line(model_name, fmu_ports.Outport(1), x_log_ports.Inport, 'autorouting', 'on');

    set_param(model_name, ...
        'PreLoadFcn', '', ...
        'PostLoadFcn', '', ...
        'InitFcn', '', ...
        'StartFcn', '', ...
        'StopFcn', '', ...
        'CloseFcn', '');
    annotation = Simulink.Annotation(model_name, sprintf( ...
        'Normalized first order: 0.1 dx/dt = u - x | FMI %s %s | h = 1 ms | source %s', ...
        fmi_version, interface, fmu_manifest.source_commit));
    annotation.Position = [35 10 805 35];
    Simulink.BlockDiagram.arrangeSystem(model_name);
    save_system(model_name, model_path);

    model_stream = System.IO.File.OpenRead(model_path);
    model_hasher = System.Security.Cryptography.SHA256.Create();
    model_bytes = model_hasher.ComputeHash(model_stream);
    model_hash = lower(reshape(dec2hex(uint8(model_bytes), 2).', 1, []));
    model_hasher.Dispose();
    model_stream.Dispose();
    callbacks = {'PreLoadFcn', 'PostLoadFcn', 'InitFcn', 'StartFcn', 'StopFcn', 'CloseFcn'};
    for callback_index = 1:numel(callbacks)
        assert(isempty(get_param(model_name, callbacks{callback_index})), ...
            'Unexpected callback %s in %s', callbacks{callback_index}, model_name);
    end
    close_system(model_name, 0);

    cell_receipt = struct();
    cell_receipt.model = [model_name '.slx'];
    cell_receipt.model_sha256 = model_hash;
    cell_receipt.fmi_version = fmi_version;
    cell_receipt.interface = interface;
    cell_receipt.fixture = fixture_name;
    cell_receipt.fixture_sha256 = fixture_hash;
    cell_receipt.input_ports = 1;
    cell_receipt.output_ports = 1;
    cell_receipt.input_variable = 'u';
    cell_receipt.output_variable = 'x';
    cell_receipt.solver = solver;
    cell_receipt.start_time = 0;
    cell_receipt.stop_time = 1.2;
    cell_receipt.fixed_step = 0.001;
    cell_receipt.expected_samples = 1201;
    cell_receipt.input_block = 'summed Step sources followed by Zero-Order Hold';
    cell_receipt.zoh_sample_time = 0.001;
    cell_receipt.input_schedule = [0.0 0.0; 0.2 1.0; 0.5 -0.5; 0.8 0.25];
    cell_receipt.boundary_convention = 'right-continuous u[n], held on [t[n],t[n+1])';
    model_receipts{index} = cell_receipt;
end

rmpath(fmu_dir);
builder_path = fullfile(project, 'build_first_order_matrix.m');
builder_stream = System.IO.File.OpenRead(builder_path);
builder_hasher = System.Security.Cryptography.SHA256.Create();
builder_bytes = builder_hasher.ComputeHash(builder_stream);
builder_hash = lower(reshape(dec2hex(uint8(builder_bytes), 2).', 1, []));
builder_hasher.Dispose();
builder_stream.Dispose();
assert(strcmp(builder_hash, fmu_manifest.recipe_assets.builder.sha256), ...
    'Builder identity differs from the current manifest');

receipt = struct();
receipt.schema = 'veragrid.first-order-simulink-model-build/1';
receipt.status = 'PASS_MODELS_BUILT_NOT_SIMULATED';
receipt.claim = 'normalized first-order verification fixture; not a device-specific physical model';
receipt.source_commit = fmu_manifest.source_commit;
receipt.git_tree_sha1 = fmu_manifest.git_tree_sha1;
receipt.source_provenance = fmu_manifest.source_provenance;
receipt.recipe_assets = fmu_manifest.recipe_assets;
receipt.created_utc = char(datetime('now', 'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
receipt.user = char(System.Security.Principal.WindowsIdentity.GetCurrent().Name);
receipt.matlab_release = version('-release');
receipt.matlab_version = version;
receipt.matlab_license = logical(license('test', 'MATLAB'));
receipt.simulink_license = logical(license('test', 'SIMULINK'));
receipt.builder_sha256 = builder_hash;
receipt.model_count = size(fixtures, 1);
receipt.models = vertcat(model_receipts{:});
receipt.executed_fmus = 0;

receipt_handle = fopen(receipt_path, 'w', 'n', 'UTF-8');
assert(receipt_handle >= 0, 'Could not create %s', receipt_path);
fwrite(receipt_handle, jsonencode(receipt, PrettyPrint=true), 'char');
fwrite(receipt_handle, newline, 'char');
fclose(receipt_handle);
fprintf('MODEL_BUILD_RECEIPT=%s\n', receipt_path);
