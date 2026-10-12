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

static int vg_close(double a, double b) {
    double scale = fabs(a);
    if (fabs(b) > scale) {
        scale = fabs(b);
    }
    return fabs(a - b) <= (1e-12 * (1.0 + scale));
}

fmiStatus status_from_result(int result) {
    return result == 0 ? fmiOK : fmiError;
}

const char* fmiGetTypesPlatform(void) {
    return fmiPlatform;
}

const char* fmiGetVersion(void) {
    return fmiVersion;
}

fmiStatus fmiSetDebugLogging(fmiComponent c, fmiBoolean loggingOn) {
    ModelInstance* instance = (ModelInstance*)c;
    if (instance == NULL) {
        return fmiError;
    }
    instance->logging_on = loggingOn;
    return fmiOK;
}

fmiComponent fmiInstantiateSlave(
    fmiString instanceName,
    fmiString fmuGUID,
    fmiString fmuLocation,
    fmiString mimeType,
    fmiReal timeout,
    fmiBoolean visible,
    fmiBoolean interactive,
    fmiCallbackFunctions functions,
    fmiBoolean loggingOn
) {
    VgMemoryCallbacks memory_callbacks;
    (void)fmuLocation;
    (void)mimeType;
    (void)timeout;
    (void)visible;
    (void)interactive;
    if (
        instanceName == NULL || fmuGUID == NULL ||
        functions.allocateMemory == NULL || functions.freeMemory == NULL
    ) {
        return NULL;
    }
    if (VG_MODEL_GUID[0] != '\0' && strcmp(VG_MODEL_GUID, fmuGUID) != 0) {
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

fmiStatus fmiInitializeSlave(
    fmiComponent c,
    fmiReal tStart,
    fmiBoolean stopTimeDefined,
    fmiReal tStop
) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_INSTANTIATED)) {
        return vg_state_error(instance);
    }
    if (stopTimeDefined && tStop <= tStart) {
        return vg_state_error(instance);
    }
    if (
        model_instance_setup_experiment(
            instance,
            tStart,
            stopTimeDefined,
            tStop
        ) != 0
    ) {
        return vg_state_error(instance);
    }
    return status_from_result(model_instance_initialize(instance));
}

fmiStatus fmiTerminateSlave(fmiComponent c) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_STEP_COMPLETE | VG_STATE_ERROR)) {
        return vg_state_error(instance);
    }
    instance->terminated = fmiTrue;
    instance->state = VG_STATE_TERMINATED;
    return fmiOK;
}

fmiStatus fmiResetSlave(fmiComponent c) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_INSTANTIATED | VG_STATE_STEP_COMPLETE |
        VG_STATE_TERMINATED | VG_STATE_ERROR
    )) {
        return vg_state_error(instance);
    }
    return status_from_result(model_instance_reset(instance));
}

void fmiFreeSlaveInstance(fmiComponent c) {
    model_instance_free((ModelInstance*)c);
}

fmiStatus fmiGetReal(
    fmiComponent c,
    const fmiValueReference vr[],
    size_t nvr,
    fmiReal value[]
) {
    size_t index;
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(
        instance,
        VG_STATE_INSTANTIATED | VG_STATE_STEP_COMPLETE | VG_STATE_TERMINATED
    )) {
        return vg_state_error(instance);
    }
    if (nvr > 0u && (vr == NULL || value == NULL)) {
        return fmiError;
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
    if (!vg_allowed_state(instance, VG_STATE_INSTANTIATED | VG_STATE_STEP_COMPLETE)) {
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

fmiStatus fmiSetRealInputDerivatives(
    fmiComponent c,
    const fmiValueReference vr[],
    size_t nvr,
    const fmiInteger order[],
    const fmiReal value[]
) {
    (void)c; (void)vr; (void)nvr; (void)order; (void)value; return fmiError;
}

fmiStatus fmiGetRealOutputDerivatives(
    fmiComponent c,
    const fmiValueReference vr[],
    size_t nvr,
    const fmiInteger order[],
    fmiReal value[]
) {
    (void)c; (void)vr; (void)nvr; (void)order; (void)value; return fmiError;
}

fmiStatus fmiCancelStep(fmiComponent c) {
    (void)c;
    return fmiError;
}

fmiStatus fmiDoStep(
    fmiComponent c,
    fmiReal currentCommunicationPoint,
    fmiReal communicationStepSize,
    fmiBoolean newStep
) {
    ModelInstance* instance = (ModelInstance*)c;
    (void)newStep;
    if (!vg_allowed_state(instance, VG_STATE_STEP_COMPLETE)) {
        return vg_state_error(instance);
    }
    if (communicationStepSize <= 0.0) {
        return vg_state_error(instance);
    }
    if (!vg_close(currentCommunicationPoint, instance->time)) {
        return vg_state_error(instance);
    }
    if (
        instance->stop_time_defined &&
        currentCommunicationPoint + communicationStepSize > instance->stop_time &&
        !vg_close(
            currentCommunicationPoint + communicationStepSize,
            instance->stop_time
        )
    ) {
        return vg_state_error(instance);
    }
    return status_from_result(
        model_instance_do_step(instance, communicationStepSize)
    );
}

fmiStatus fmiGetStatus(fmiComponent c, const fmiStatusKind s, fmiStatus* value) {
    (void)c; (void)s;
    if (value != NULL) {
        *value = fmiOK;
    }
    return fmiDiscard;
}

fmiStatus fmiGetRealStatus(fmiComponent c, const fmiStatusKind s, fmiReal* value) {
    ModelInstance* instance = (ModelInstance*)c;
    if (value == NULL || instance == NULL) {
        return fmiError;
    }
    if (s == fmiLastSuccessfulTime) {
        *value = instance->last_successful_time;
        return fmiOK;
    }
    *value = 0.0;
    return fmiDiscard;
}

fmiStatus fmiGetIntegerStatus(fmiComponent c, const fmiStatusKind s, fmiInteger* value) {
    (void)c; (void)s;
    if (value != NULL) {
        *value = 0;
    }
    return fmiDiscard;
}

fmiStatus fmiGetBooleanStatus(fmiComponent c, const fmiStatusKind s, fmiBoolean* value) {
    (void)c; (void)s;
    if (value != NULL) {
        *value = fmiFalse;
    }
    return fmiDiscard;
}

fmiStatus fmiGetStringStatus(fmiComponent c, const fmiStatusKind s, fmiString* value) {
    (void)c; (void)s;
    if (value != NULL) {
        *value = "";
    }
    return fmiDiscard;
}
