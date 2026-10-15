% Execute six Simulink first-order FMU models and retain exact raw traces.

project = fileparts(mfilename('fullpath'));
fmu_dir = fullfile(project, 'fmus');
model_dir = fullfile(project, 'models');
trace_dir = fullfile(project, 'traces');
receipt_path = fullfile(project, 'simulink-six-cell-receipt.json');
manifest_path = fullfile(project, 'first-order-fmu-manifest.json');
build_receipt_path = fullfile(project, 'model-build-receipt.json');
assert(strcmp(version('-release'), '2025b'), 'This recipe requires MATLAB R2025b');
assert(license('test', 'MATLAB') && license('test', 'SIMULINK'), ...
    'Licensed MATLAB and Simulink are required');
fmu_manifest = jsondecode(fileread(manifest_path));
build_receipt = jsondecode(fileread(build_receipt_path));
assert(strcmp(fmu_manifest.status, 'PASS') && numel(fmu_manifest.cells) == 6, ...
    'Incomplete current FMU manifest');
assert(build_receipt.model_count == 6 && numel(build_receipt.models) == 6, ...
    'Incomplete authenticated model build');
assert(strcmp(build_receipt.source_commit, fmu_manifest.source_commit) ...
    && strcmp(build_receipt.builder_sha256, fmu_manifest.recipe_assets.builder.sha256), ...
    'Build provenance differs from the current manifest');
assert(isfolder(model_dir), 'Missing model directory: %s', model_dir);
assert(isfolder(fmu_dir), 'Missing FMU directory: %s', fmu_dir);
assert(~isfolder(trace_dir), 'Refusing to overwrite trace directory: %s', trace_dir);
assert(~isfile(receipt_path), 'Refusing to overwrite receipt: %s', receipt_path);
mkdir(trace_dir);
addpath(fmu_dir);

cells = {
    '1.0', 'CS', 'VGFirstOrderFMI10CS';
    '1.0', 'ME', 'VGFirstOrderFMI10ME';
    '2.0', 'CS', 'VGFirstOrderFMI20CS';
    '2.0', 'ME', 'VGFirstOrderFMI20ME';
    '3.0', 'CS', 'VGFirstOrderFMI30CS';
    '3.0', 'ME', 'VGFirstOrderFMI30ME';
};

target_time = (0:0.001:1.2).';
cell_receipts = cell(size(cells, 1), 1);
pass_count = 0;
initial_runner_path = fullfile(project, 'run_first_order_matrix.m');
initial_runner_stream = System.IO.File.OpenRead(initial_runner_path);
initial_runner_hasher = System.Security.Cryptography.SHA256.Create();
initial_runner_bytes = initial_runner_hasher.ComputeHash(initial_runner_stream);
initial_runner_hash = lower(reshape(dec2hex(uint8(initial_runner_bytes), 2).', 1, []));
initial_runner_hasher.Dispose();
initial_runner_stream.Dispose();
assert(strcmp(initial_runner_hash, fmu_manifest.recipe_assets.runner.sha256), ...
    'Runner identity differs from the current manifest');

for index = 1:size(cells, 1)
    fmi_version = cells{index, 1};
    interface = cells{index, 2};
    model_name = cells{index, 3};
    model_path = fullfile(model_dir, [model_name '.slx']);
    assert(isfile(model_path), 'Missing model: %s', model_path);
    expected_model = build_receipt.models(index);
    manifest_cell = fmu_manifest.cells(index);
    expected_cell_id = ['fmi' strrep(fmi_version, '.', '') '_' lower(interface)];
    assert(strcmp(expected_model.model, [model_name '.slx']) ...
        && strcmp(manifest_cell.cell_id, expected_cell_id), 'Cell binding mismatch');
    authenticated_model_stream = System.IO.File.OpenRead(model_path);
    authenticated_model_hasher = System.Security.Cryptography.SHA256.Create();
    authenticated_model_bytes = authenticated_model_hasher.ComputeHash(authenticated_model_stream);
    authenticated_model_hash = lower(reshape(dec2hex(uint8(authenticated_model_bytes), 2).', 1, []));
    authenticated_model_hasher.Dispose();
    authenticated_model_stream.Dispose();
    assert(strcmp(authenticated_model_hash, expected_model.model_sha256), ...
        'Model identity mismatch before simulation');
    fixture_path = fullfile(fmu_dir, manifest_cell.fmu_name);
    fixture_info = dir(fixture_path);
    assert(numel(fixture_info) == 1 && fixture_info.bytes == manifest_cell.fmu_size_bytes, ...
        'FMU size mismatch before simulation');
    authenticated_fmu_stream = System.IO.File.OpenRead(fixture_path);
    authenticated_fmu_hasher = System.Security.Cryptography.SHA256.Create();
    authenticated_fmu_bytes = authenticated_fmu_hasher.ComputeHash(authenticated_fmu_stream);
    authenticated_fmu_hash = lower(reshape(dec2hex(uint8(authenticated_fmu_bytes), 2).', 1, []));
    authenticated_fmu_hasher.Dispose();
    authenticated_fmu_stream.Dispose();
    assert(strcmp(authenticated_fmu_hash, manifest_cell.fmu_sha256), ...
        'FMU identity mismatch before simulation');
    load_system(model_path);

    simulation_output = sim(model_name, 'ReturnWorkspaceOutputs', 'on');
    u_series = simulation_output.get('u_command');
    x_series = simulation_output.get('x_state');
    assert(isa(u_series, 'timeseries'), 'u_command is not a timeseries in %s', model_name);
    assert(isa(x_series, 'timeseries'), 'x_state is not a timeseries in %s', model_name);

    u_time = double(u_series.Time(:));
    u_values = double(squeeze(u_series.Data));
    u_values = u_values(:);
    x_time = double(x_series.Time(:));
    x_values = double(squeeze(x_series.Data));
    x_values = x_values(:);
    assert(numel(u_time) == 1201, 'Expected 1201 u samples in %s, got %d', model_name, numel(u_time));
    assert(numel(x_time) == 1201, 'Expected 1201 x samples in %s, got %d', model_name, numel(x_time));
    max_u_time_error = max(abs(u_time - target_time));
    max_x_time_error = max(abs(x_time - target_time));
    assert(max_u_time_error <= 5e-13, 'u time grid mismatch in %s', model_name);
    assert(max_x_time_error <= 5e-13, 'x time grid mismatch in %s', model_name);
    assert(all(isfinite(u_values)), 'Non-finite u in %s', model_name);
    assert(all(isfinite(x_values)), 'Non-finite x in %s', model_name);

    % Verify the exact old/new/new samples around every right-continuous event.
    assert(abs(u_values(200) - 0.0) <= 1e-15, 'u(0.199) mismatch in %s', model_name);
    assert(abs(u_values(201) - 1.0) <= 1e-15, 'u(0.200) mismatch in %s', model_name);
    assert(abs(u_values(202) - 1.0) <= 1e-15, 'u(0.201) mismatch in %s', model_name);
    assert(abs(u_values(500) - 1.0) <= 1e-15, 'u(0.499) mismatch in %s', model_name);
    assert(abs(u_values(501) + 0.5) <= 1e-15, 'u(0.500) mismatch in %s', model_name);
    assert(abs(u_values(502) + 0.5) <= 1e-15, 'u(0.501) mismatch in %s', model_name);
    assert(abs(u_values(800) + 0.5) <= 1e-15, 'u(0.799) mismatch in %s', model_name);
    assert(abs(u_values(801) - 0.25) <= 1e-15, 'u(0.800) mismatch in %s', model_name);
    assert(abs(u_values(802) - 0.25) <= 1e-15, 'u(0.801) mismatch in %s', model_name);

    cell_id = ['fmi' strrep(fmi_version, '.', '') '_' lower(interface)];
    trace_path = fullfile(trace_dir, [cell_id '.csv']);
    assert(~isfile(trace_path), 'Refusing to overwrite trace: %s', trace_path);
    trace_handle = fopen(trace_path, 'w', 'n', 'UTF-8');
    assert(trace_handle >= 0, 'Could not create trace: %s', trace_path);
    fprintf(trace_handle, 'time,u,x\n');
    for sample_index = 1:1201
        fprintf(trace_handle, '%.17g,%.17g,%.17g\n', ...
            target_time(sample_index), u_values(sample_index), x_values(sample_index));
    end
    fclose(trace_handle);

    trace_stream = System.IO.File.OpenRead(trace_path);
    trace_hasher = System.Security.Cryptography.SHA256.Create();
    trace_bytes = trace_hasher.ComputeHash(trace_stream);
    trace_hash = lower(reshape(dec2hex(uint8(trace_bytes), 2).', 1, []));
    trace_hasher.Dispose();
    trace_stream.Dispose();
    model_stream = System.IO.File.OpenRead(model_path);
    model_hasher = System.Security.Cryptography.SHA256.Create();
    model_bytes = model_hasher.ComputeHash(model_stream);
    model_hash = lower(reshape(dec2hex(uint8(model_bytes), 2).', 1, []));
    model_hasher.Dispose();
    model_stream.Dispose();
    assert(strcmp(model_hash, expected_model.model_sha256), ...
        'Model identity changed during simulation');

    cell_receipt = struct();
    cell_receipt.cell_id = cell_id;
    cell_receipt.fmi_version = fmi_version;
    cell_receipt.interface = interface;
    cell_receipt.model = [model_name '.slx'];
    cell_receipt.model_sha256 = model_hash;
    cell_receipt.fmu = manifest_cell.fmu_name;
    cell_receipt.fmu_sha256 = authenticated_fmu_hash;
    cell_receipt.trace = [cell_id '.csv'];
    cell_receipt.trace_sha256 = trace_hash;
    cell_receipt.sample_count = 1201;
    cell_receipt.max_abs_u_time_error = max_u_time_error;
    cell_receipt.max_abs_x_time_error = max_x_time_error;
    cell_receipt.event_samples = [u_values(200:202); u_values(500:502); u_values(800:802)];
    cell_receipt.finite = true;
    cell_receipt.status = 'PASS';
    cell_receipts{index} = cell_receipt;
    pass_count = pass_count + 1;
    close_system(model_name, 0);
    fprintf('%s PASS\n', cell_id);
end

runner_path = fullfile(project, 'run_first_order_matrix.m');
runner_stream = System.IO.File.OpenRead(runner_path);
runner_hasher = System.Security.Cryptography.SHA256.Create();
runner_bytes = runner_hasher.ComputeHash(runner_stream);
runner_hash = lower(reshape(dec2hex(uint8(runner_bytes), 2).', 1, []));
runner_hasher.Dispose();
runner_stream.Dispose();
assert(strcmp(runner_hash, initial_runner_hash), 'Runner identity changed during execution');

receipt = struct();
receipt.schema = 'veragrid.first-order-simulink-six-cell/1';
receipt.status = 'PASS';
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
receipt.runner_sha256 = runner_hash;
receipt.cell_count = size(cells, 1);
receipt.pass_count = pass_count;
receipt.fail_count = size(cells, 1) - pass_count;
receipt.step_s = 0.001;
receipt.stop_s = 1.2;
receipt.expected_samples = 1201;
receipt.boundary_convention = 'observe x[n], update/log u[n], hold on [t[n],t[n+1]), advance, observe x[n+1]';
receipt.cells = vertcat(cell_receipts{:});

receipt_handle = fopen(receipt_path, 'w', 'n', 'UTF-8');
assert(receipt_handle >= 0, 'Could not create %s', receipt_path);
fwrite(receipt_handle, jsonencode(receipt, PrettyPrint=true), 'char');
fwrite(receipt_handle, newline, 'char');
fclose(receipt_handle);
rmpath(fmu_dir);
fprintf('SIMULINK_RECEIPT=%s\n', receipt_path);
