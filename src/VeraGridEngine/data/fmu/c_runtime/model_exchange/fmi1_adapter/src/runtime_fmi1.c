#include "runtime_fmi1.h"

#include "generated_model.h"
#include "runtime_support.h"

static int vg_allowed_state(ModelInstance* instance, int mask) {
    return instance != NULL && (instance->state & mask) != 0;
}

static fmiStatus vg_state_error(ModelInstance* instance) {
    if (instance != NULL) {
        instance->state = VG_STATE_ERROR;
    }
    return fmiError;
}

static void vg_copy_event_info(
    const VgEventInfo* internal_event_info,
    fmiEventInfo* event_info
) {
    event_info->iterationConverged =
        internal_event_info->new_discrete_states_needed ? fmiFalse : fmiTrue;
    event_info->stateValueReferencesChanged = fmiFalse;
    event_info->stateValuesChanged = internal_event_info->values_changed;
    event_info->terminateSimulation = internal_event_info->terminate_simulation;
    event_info->upcomingTimeEvent = internal_event_info->next_event_time_defined;
    event_info->nextEventTime = internal_event_info->next_event_time;
}

fmiStatus status_from_result(int result) {
    return result == 0 ? fmiOK : fmiError;
}

const char* fmiGetModelTypesPlatform(void) {
    return fmiModelTypesPlatform;
}

const char* fmiGetVersion(void) {
    return fmiVersion;
}

fmiComponent fmiInstantiateModel(
    fmiString instanceName,
    fmiString guid,
    fmiCallbackFunctions functions,
    fmiBoolean loggingOn
) {
    VgMemoryCallbacks memory_callbacks;
    if (
        instanceName == NULL || guid == NULL ||
        functions.allocateMemory == NULL || functions.freeMemory == NULL
    ) {
        return NULL;
    }
    if (VG_MODEL_GUID[0] != '\0' && strcmp(VG_MODEL_GUID, guid) != 0) {
        return NULL;
    }
    memory_callbacks.allocate_memory = functions.allocateMemory;
    memory_callbacks.free_memory = functions.freeMemory;
    return (fmiComponent)model_instance_create(
        instanceName,
        &memory_callbacks,
        loggingOn
    );
}

void fmiFreeModelInstance(fmiComponent c) {
    model_instance_free((ModelInstance*)c);
}

fmiStatus fmiSetDebugLogging(fmiComponent c, fmiBoolean loggingOn) {
    ModelInstance* instance = (ModelInstance*)c;
    if (instance == NULL) {
        return fmiError;
    }
    instance->logging_on = loggingOn;
    return fmiOK;
}

fmiStatus fmiSetTime(fmiComponent c, fmiReal time) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_INSTANTIATED | VG_STATE_EVENT_MODE |
        VG_STATE_CONTINUOUS_TIME_MODE
    )) {
        return vg_state_error(instance);
    }
    return status_from_result(model_instance_set_time(instance, time));
}

fmiStatus fmiSetContinuousStates(
    fmiComponent c,
    const fmiReal x[],
    size_t nx
) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_INSTANTIATED | VG_STATE_EVENT_MODE |
        VG_STATE_CONTINUOUS_TIME_MODE
    )) {
        return vg_state_error(instance);
    }
    return status_from_result(
        model_instance_set_continuous_states(instance, x, nx)
    );
}

fmiStatus fmiCompletedIntegratorStep(
    fmiComponent c,
    fmiBoolean* callEventUpdate
) {
    int enter_event_mode = 0;
    int terminate_simulation = 0;
    ModelInstance* instance = (ModelInstance*)c;
    if (
        callEventUpdate == NULL ||
        !vg_allowed_state(instance, VG_STATE_CONTINUOUS_TIME_MODE)
    ) {
        return vg_state_error(instance);
    }
    if (
        model_instance_completed_integrator_step(
            instance,
            &enter_event_mode,
            &terminate_simulation
        ) != 0
    ) {
        return vg_state_error(instance);
    }
    *callEventUpdate =
        (enter_event_mode || terminate_simulation) ? fmiTrue : fmiFalse;
    return fmiOK;
}

fmiStatus fmiGetReal(
    fmiComponent c,
    const fmiValueReference vr[],
    size_t nvr,
    fmiReal value[]
) {
    size_t index;
    ModelInstance* instance = (ModelInstance*)c;
    if (instance == NULL || (nvr > 0u && (vr == NULL || value == NULL))) {
        return fmiError;
    }
    if (instance->initialized && instance->dirty && model_instance_sync(instance) != 0) {
        return vg_state_error(instance);
    }
    for (index = 0u; index < nvr; ++index) {
        if (generated_get_real(instance, vr[index], &value[index]) != 0) {
            return fmiError;
        }
    }
    return fmiOK;
}

fmiStatus fmiSetReal(
    fmiComponent c,
    const fmiValueReference vr[],
    size_t nvr,
    const fmiReal value[]
) {
    size_t index;
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_INSTANTIATED | VG_STATE_EVENT_MODE |
        VG_STATE_CONTINUOUS_TIME_MODE
    )) {
        return vg_state_error(instance);
    }
    if (nvr > 0u && (vr == NULL || value == NULL)) {
        return fmiError;
    }
    for (index = 0u; index < nvr; ++index) {
        if (generated_set_real(instance, vr[index], value[index]) != 0) {
            return fmiError;
        }
    }
    instance->dirty = fmiTrue;
    return fmiOK;
}

fmiStatus fmiGetInteger(fmiComponent c, const fmiValueReference vr[], size_t nvr, fmiInteger value[]) {
    (void)c; (void)vr; (void)nvr; (void)value; return fmiError;
}

fmiStatus fmiGetBoolean(fmiComponent c, const fmiValueReference vr[], size_t nvr, fmiBoolean value[]) {
    (void)c; (void)vr; (void)nvr; (void)value; return fmiError;
}

fmiStatus fmiGetString(fmiComponent c, const fmiValueReference vr[], size_t nvr, fmiString value[]) {
    (void)c; (void)vr; (void)nvr; (void)value; return fmiError;
}

fmiStatus fmiSetInteger(fmiComponent c, const fmiValueReference vr[], size_t nvr, const fmiInteger value[]) {
    (void)c; (void)vr; (void)nvr; (void)value; return fmiError;
}

fmiStatus fmiSetBoolean(fmiComponent c, const fmiValueReference vr[], size_t nvr, const fmiBoolean value[]) {
    (void)c; (void)vr; (void)nvr; (void)value; return fmiError;
}

fmiStatus fmiSetString(fmiComponent c, const fmiValueReference vr[], size_t nvr, const fmiString value[]) {
    (void)c; (void)vr; (void)nvr; (void)value; return fmiError;
}

fmiStatus fmiInitialize(
    fmiComponent c,
    fmiBoolean toleranceControlled,
    fmiReal relativeTolerance,
    fmiEventInfo* eventInfo
) {
    VgEventInfo internal_event_info;
    ModelInstance* instance = (ModelInstance*)c;
    if (
        eventInfo == NULL ||
        !vg_allowed_state(instance, VG_STATE_INSTANTIATED)
    ) {
        return vg_state_error(instance);
    }
    if (
        model_instance_setup_experiment(
            instance,
            toleranceControlled,
            relativeTolerance,
            instance->time,
            fmiFalse,
            0.0
        ) != 0 ||
        model_instance_initialize(instance) != 0 ||
        model_instance_new_discrete_states(instance, &internal_event_info) != 0
    ) {
        return vg_state_error(instance);
    }
    vg_copy_event_info(&internal_event_info, eventInfo);
    if (eventInfo->iterationConverged) {
        return status_from_result(
            model_instance_enter_continuous_time_mode(instance)
        );
    }
    return fmiOK;
}

fmiStatus fmiGetDerivatives(
    fmiComponent c,
    fmiReal derivatives[],
    size_t nx
) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE
    )) {
        return vg_state_error(instance);
    }
    return status_from_result(
        model_instance_get_derivatives(instance, derivatives, nx)
    );
}

fmiStatus fmiGetEventIndicators(
    fmiComponent c,
    fmiReal eventIndicators[],
    size_t ni
) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE
    )) {
        return vg_state_error(instance);
    }
    return status_from_result(
        model_instance_get_event_indicators(instance, eventIndicators, ni)
    );
}

fmiStatus fmiEventUpdate(
    fmiComponent c,
    fmiBoolean intermediateResults,
    fmiEventInfo* eventInfo
) {
    VgEventInfo internal_event_info;
    ModelInstance* instance = (ModelInstance*)c;
    (void)intermediateResults;
    if (
        eventInfo == NULL ||
        !vg_allowed_state(
            instance,
            VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE
        )
    ) {
        return vg_state_error(instance);
    }
    if (
        model_instance_enter_event_mode(instance) != 0 ||
        model_instance_new_discrete_states(instance, &internal_event_info) != 0
    ) {
        return vg_state_error(instance);
    }
    vg_copy_event_info(&internal_event_info, eventInfo);
    if (eventInfo->iterationConverged) {
        return status_from_result(
            model_instance_enter_continuous_time_mode(instance)
        );
    }
    return fmiOK;
}

fmiStatus fmiGetContinuousStates(
    fmiComponent c,
    fmiReal states[],
    size_t nx
) {
    ModelInstance* instance = (ModelInstance*)c;
    return status_from_result(
        model_instance_get_continuous_states(instance, states, nx)
    );
}

fmiStatus fmiGetNominalContinuousStates(
    fmiComponent c,
    fmiReal x_nominal[],
    size_t nx
) {
    ModelInstance* instance = (ModelInstance*)c;
    if (
        instance == NULL || nx != (size_t)VG_NUM_STATES ||
        (nx > 0u && x_nominal == NULL)
    ) {
        return fmiError;
    }
    if (nx > 0u) {
        memcpy(x_nominal, instance->nominals, sizeof(fmiReal) * nx);
    }
    return fmiOK;
}

fmiStatus fmiGetStateValueReferences(
    fmiComponent c,
    fmiValueReference vrx[],
    size_t nx
) {
    static const fmiValueReference state_value_references[] =
        VG_STATE_VALUE_REFERENCES;
    size_t index;
    if (
        c == NULL || nx != (size_t)VG_NUM_STATES ||
        (nx > 0u && vrx == NULL)
    ) {
        return fmiError;
    }
    for (index = 0u; index < nx; ++index) {
        vrx[index] = state_value_references[index];
    }
    return fmiOK;
}

fmiStatus fmiTerminate(fmiComponent c) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_ERROR
    )) {
        return vg_state_error(instance);
    }
    instance->terminated = fmiTrue;
    instance->state = VG_STATE_TERMINATED;
    return fmiOK;
}
