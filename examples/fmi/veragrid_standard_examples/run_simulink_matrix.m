% Execute all standard-example Simulink models and retain raw evidence.

project = fileparts(mfilename('fullpath'));
catalog = fullfile(project, 'catalog');
model_dir = fullfile(project, 'models');
trace_dir = fullfile(project, 'traces');
signature_dir = fullfile(project, 'signatures');
receipt_path = fullfile(project, 'simulink-run-receipt.json');
cells = jsondecode(fileread(fullfile(project, 'execution-cells.json')));
build_receipt = jsondecode(fileread(fullfile(project, 'model-build-receipt.json')));
assert(strcmp(version('-release'), '2025b'), 'MATLAB R2025b is required');
assert(license('test', 'MATLAB') && license('test', 'SIMULINK'), 'MATLAB and Simulink licenses are required');
assert(numel(cells) == 18 && build_receipt.model_count == 18, 'Incomplete authenticated build');
assert(~isfolder(trace_dir) && ~isfolder(signature_dir) && ~isfile(receipt_path), 'Refusing to overwrite run evidence');
mkdir(trace_dir);
mkdir(signature_dir);
addpath(genpath(catalog));
cell_receipts = cell(18, 1);

for cell_index = 1:18
    cell_data = cells(cell_index);
    model_data = build_receipt.models(cell_index);
    model_path = fullfile(model_dir, model_data.model_file);
    assert(isfile(model_path), 'Missing model %s', model_path);
    model_stream = System.IO.File.OpenRead(model_path);
    model_hasher = System.Security.Cryptography.SHA256.Create();
    model_bytes = model_hasher.ComputeHash(model_stream);
    model_hash = lower(reshape(dec2hex(uint8(model_bytes), 2).', 1, []));
    model_hasher.Dispose();
    model_stream.Dispose();
    assert(strcmp(model_hash, model_data.model_sha256), 'Model hash mismatch');
    input_path = fullfile(catalog, strrep(cell_data.input_csv, '/', filesep));
    reference_path = fullfile(catalog, strrep(cell_data.reference_csv, '/', filesep));
    input_table = readtable(input_path, 'VariableNamingRule', 'preserve');
    reference_table = readtable(reference_path, 'VariableNamingRule', 'preserve');
    stop_time = reference_table.time(end);
    sample_count = round(stop_time / 0.001) + 1;
    target_time = (0:sample_count - 1).' * 0.001;
    input_values = zeros(sample_count, numel(cell_data.input_names));
    schedule_time = input_table.time;
    for sample_index = 1:sample_count
        eligible_rows = find(schedule_time <= target_time(sample_index) + 5e-13);
        assert(~isempty(eligible_rows), 'Input schedule does not cover t=0');
        schedule_row = eligible_rows(end);
        for input_index = 1:numel(cell_data.input_names)
            input_name = char(cell_data.input_names(input_index));
            input_values(sample_index, input_index) = input_table.(input_name)(schedule_row);
        end
    end
    input_dataset = Simulink.SimulationData.Dataset;
    for input_index = 1:numel(cell_data.input_names)
        input_name = char(cell_data.input_names(input_index));
        input_series = timeseries(input_values(:, input_index), target_time);
        input_series.Name = input_name;
        input_series.DataInfo.Interpolation = tsdata.interpolation('zoh');
        input_dataset = input_dataset.addElement(input_series, input_name);
    end
    load_system(model_path);
    simulation_input = Simulink.SimulationInput(model_data.model_name);
    simulation_input = simulation_input.setExternalInput(input_dataset);
    simulation_input = simulation_input.setModelParameter('StopTime', num2str(stop_time, 17));
    simulation_output = sim(simulation_input);
    output_values = zeros(sample_count, numel(cell_data.output_names));
    max_time_error = 0;
    for output_index = 1:numel(cell_data.output_names)
        output_name = char(cell_data.output_names(output_index));
        output_series = simulation_output.get(output_name);
        assert(isa(output_series, 'timeseries'), 'Missing output %s', output_name);
        output_time = double(output_series.Time(:));
        output_data = double(squeeze(output_series.Data));
        assert(numel(output_time) == sample_count && numel(output_data) == sample_count, 'Unexpected raw sample count');
        output_time_error = max(abs(output_time - target_time));
        max_time_error = max(max_time_error, output_time_error);
        assert(output_time_error <= 5e-12 && all(isfinite(output_data)), 'Invalid output lattice');
        output_values(:, output_index) = output_data(:);
    end
    trace_name = [cell_data.model_name '.csv'];
    trace_path = fullfile(trace_dir, trace_name);
    trace_handle = fopen(trace_path, 'w', 'n', 'UTF-8');
    assert(trace_handle >= 0, 'Cannot create trace');
    fprintf(trace_handle, 'time');
    for input_index = 1:numel(cell_data.input_names)
        fprintf(trace_handle, ',%s', char(cell_data.input_names(input_index)));
    end
    for output_index = 1:numel(cell_data.output_names)
        fprintf(trace_handle, ',%s', char(cell_data.output_names(output_index)));
    end
    fprintf(trace_handle, '\n');
    for sample_index = 1:sample_count
        fprintf(trace_handle, '%.17g', target_time(sample_index));
        fprintf(trace_handle, ',%.17g', input_values(sample_index, :));
        fprintf(trace_handle, ',%.17g', output_values(sample_index, :));
        fprintf(trace_handle, '\n');
    end
    fclose(trace_handle);

    % A separate single-channel pulse establishes wiring observability.
    signature_stop = 0.6;
    signature_count = 601;
    signature_time = (0:signature_count - 1).' * 0.001;
    baseline_values = repmat(input_values(1, :), signature_count, 1);
    baseline_dataset = Simulink.SimulationData.Dataset;
    for input_index = 1:numel(cell_data.input_names)
        input_name = char(cell_data.input_names(input_index));
        baseline_series = timeseries(baseline_values(:, input_index), signature_time);
        baseline_series.Name = input_name;
        baseline_series.DataInfo.Interpolation = tsdata.interpolation('zoh');
        baseline_dataset = baseline_dataset.addElement(baseline_series, input_name);
    end
    baseline_input = Simulink.SimulationInput(model_data.model_name);
    baseline_input = baseline_input.setExternalInput(baseline_dataset);
    baseline_input = baseline_input.setModelParameter('StopTime', num2str(signature_stop, 17));
    baseline_output = sim(baseline_input);
    baseline_response = zeros(signature_count, numel(cell_data.output_names));
    for output_index = 1:numel(cell_data.output_names)
        output_name = char(cell_data.output_names(output_index));
        baseline_series = baseline_output.get(output_name);
        assert(max(abs(double(baseline_series.Time(:)) - signature_time)) <= 5e-12, 'Invalid baseline lattice');
        baseline_response(:, output_index) = double(squeeze(baseline_series.Data));
    end
    signature_receipts = cell(numel(cell_data.input_names), 1);
    for pulse_index = 1:numel(cell_data.input_names)
        pulse_name = char(cell_data.input_names(pulse_index));
        if strcmp(cell_data.family, 'GENSAL')
            if strcmp(pulse_name, 'IdPu_GENSAL') || strcmp(pulse_name, 'IqPu_GENSAL')
                pulse_amplitude = 0.10;
            else
                pulse_amplitude = 0.50;
            end
        elseif strcmp(cell_data.family, 'TGOV1')
            if strcmp(pulse_name, 'OmegaPu_TGOV1')
                pulse_amplitude = 0.01;
            else
                pulse_amplitude = 0.05;
            end
        else
            if strcmp(pulse_name, 'UsPu_ESDC2A')
                pulse_amplitude = 0.05;
            else
                pulse_amplitude = 0.02;
            end
        end
        pulse_values = baseline_values;
        pulse_selector = signature_time >= 0.2 & signature_time < 0.4;
        pulse_values(pulse_selector, pulse_index) = pulse_values(pulse_selector, pulse_index) + pulse_amplitude;
        pulse_dataset = Simulink.SimulationData.Dataset;
        for input_index = 1:numel(cell_data.input_names)
            input_name = char(cell_data.input_names(input_index));
            pulse_series = timeseries(pulse_values(:, input_index), signature_time);
            pulse_series.Name = input_name;
            pulse_series.DataInfo.Interpolation = tsdata.interpolation('zoh');
            pulse_dataset = pulse_dataset.addElement(pulse_series, input_name);
        end
        pulse_input = Simulink.SimulationInput(model_data.model_name);
        pulse_input = pulse_input.setExternalInput(pulse_dataset);
        pulse_input = pulse_input.setModelParameter('StopTime', num2str(signature_stop, 17));
        pulse_output = sim(pulse_input);
        signature_values = zeros(signature_count, numel(cell_data.output_names));
        for output_index = 1:numel(cell_data.output_names)
            output_name = char(cell_data.output_names(output_index));
            pulse_series = pulse_output.get(output_name);
            assert(max(abs(double(pulse_series.Time(:)) - signature_time)) <= 5e-12, 'Invalid pulse lattice');
            signature_values(:, output_index) = double(squeeze(pulse_series.Data)) - baseline_response(:, output_index);
        end
        signature_name = [cell_data.model_name '__' pulse_name '.csv'];
        signature_path = fullfile(signature_dir, signature_name);
        signature_handle = fopen(signature_path, 'w', 'n', 'UTF-8');
        assert(signature_handle >= 0, 'Cannot create signature trace');
        fprintf(signature_handle, 'time');
        for output_index = 1:numel(cell_data.output_names)
            fprintf(signature_handle, ',delta_%s', char(cell_data.output_names(output_index)));
        end
        fprintf(signature_handle, '\n');
        for sample_index = 1:signature_count
            fprintf(signature_handle, '%.17g', signature_time(sample_index));
            fprintf(signature_handle, ',%.17g', signature_values(sample_index, :));
            fprintf(signature_handle, '\n');
        end
        fclose(signature_handle);
        signature_receipt = struct();
        signature_receipt.input = pulse_name;
        signature_receipt.amplitude = pulse_amplitude;
        signature_receipt.trace = signature_name;
        signature_receipt.maximum_response = max(abs(signature_values), [], 'all');
        signature_receipts{pulse_index} = signature_receipt;
    end
    close_system(model_data.model_name, 0);
    trace_stream = System.IO.File.OpenRead(trace_path);
    trace_hasher = System.Security.Cryptography.SHA256.Create();
    trace_bytes = trace_hasher.ComputeHash(trace_stream);
    trace_hash = lower(reshape(dec2hex(uint8(trace_bytes), 2).', 1, []));
    trace_hasher.Dispose();
    trace_stream.Dispose();
    cell_receipt = struct();
    cell_receipt.model_name = cell_data.model_name;
    cell_receipt.family = cell_data.family;
    cell_receipt.fmi_version = cell_data.fmi_version;
    cell_receipt.interface = cell_data.interface;
    cell_receipt.trace = trace_name;
    cell_receipt.trace_sha256 = trace_hash;
    cell_receipt.sample_count = sample_count;
    cell_receipt.max_time_error = max_time_error;
    cell_receipt.signatures = vertcat(signature_receipts{:});
    cell_receipt.status = 'EXECUTED_NOT_VALIDATED';
    cell_receipts{cell_index} = cell_receipt;
    fprintf('%s EXECUTED\n', cell_data.model_name);
end

receipt = struct();
receipt.schema = 'veragrid.standard-simulink-run/1';
receipt.status = 'EXECUTED_NOT_VALIDATED';
receipt.created_utc = char(datetime('now', 'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
receipt.host = char(java.net.InetAddress.getLocalHost.getHostName);
receipt.user = char(System.Security.Principal.WindowsIdentity.GetCurrent().Name);
receipt.matlab_release = version('-release');
receipt.matlab_version = version;
receipt.matlab_license = logical(license('test', 'MATLAB'));
receipt.simulink_license = logical(license('test', 'SIMULINK'));
receipt.cell_count = 18;
receipt.cells = vertcat(cell_receipts{:});
receipt_handle = fopen(receipt_path, 'w', 'n', 'UTF-8');
assert(receipt_handle >= 0, 'Cannot create run receipt');
fwrite(receipt_handle, jsonencode(receipt, PrettyPrint=true), 'char');
fwrite(receipt_handle, newline, 'char');
fclose(receipt_handle);
rmpath(genpath(catalog));
fprintf('SIMULINK_RUN_RECEIPT=%s\n', receipt_path);
