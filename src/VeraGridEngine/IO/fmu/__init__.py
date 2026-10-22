# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Public FMI import and device-integration operations."""

from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmiThreeFloat64ConfigurationValue,
    FmiThreeUInt64ConfigurationValue,
    FmuFloat64ParameterValue,
    FmuImportConfig,
    FmuRefBinding,
    FmuVariableBinding,
    resolve_fmi_three_initialization_float64_binding_layout,
    validate_bindings,
)
from VeraGridEngine.IO.fmu.model_description import (
    FmuInterfaceMode,
    FmuModelDescription,
    FmuVariableDescription,
    FmuVariableType,
    choose_fmu_mode,
    list_fmu_variable_names,
    read_fmu_model_description,
    select_declared_fmu_interface,
)
from VeraGridEngine.IO.fmu.host import FmuRuntimeHost, open_fmu_runtime_host
from VeraGridEngine.IO.fmu.worker_host import FmiThreeWorkerHostLimits
from VeraGridEngine.IO.fmu.Elements.device_configuration import (
    FmuCsDeviceConfigRecord,
    FmuMeDeviceConfigRecord,
    dump_fmu_cs_device_config,
    dump_fmu_me_device_config,
    load_fmu_cs_device_config,
    load_fmu_me_device_config,
)
from VeraGridEngine.IO.fmu.co_simulation import (
    FmuCsDeviceAdapter,
    FmuCsDeviceSpec,
    FmuCsDomain,
    advance_rms_fmu_cs_devices,
    build_emt_fmu_cs_injection_template,
    build_rms_fmu_cs_injection_template,
    close_rms_fmu_cs_devices,
    finalize_emt_fmu_cs_devices,
    initialize_rms_fmu_cs_devices,
    queue_emt_fmu_cs_device,
    register_emt_fmu_cs_device,
    register_rms_fmu_cs_device,
)
from VeraGridEngine.IO.fmu.model_exchange import (
    FmuMeDeviceAdapter,
    FmuMeDeviceSpec,
    FmuMeDomain,
    advance_rms_fmu_me_devices,
    build_emt_fmu_me_injection_template,
    build_fmu_me_device_spec,
    build_rms_fmu_me_injection_template,
    close_rms_fmu_me_devices,
    finalize_emt_fmu_me_devices,
    initialize_rms_fmu_me_devices,
    queue_emt_fmu_me_device,
    register_emt_fmu_me_device,
    register_rms_fmu_me_device,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    CompositeEmtBoundaryUpdater,
    build_emt_boundary_updater,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    attach_emt_fmu_cs_device,
    attach_emt_fmu_me_device,
    attach_rms_fmu_cs_device,
    attach_rms_fmu_me_device,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    append_fmu_parameter_entries,
    configure_fmu_template,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
    attach_fmu_to_device,
)
