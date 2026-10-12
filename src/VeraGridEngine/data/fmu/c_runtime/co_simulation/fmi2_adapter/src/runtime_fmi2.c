#include "runtime_fmi2.h"

#include "generated_metadata.h"
#include "generated_model.h"
#include "runtime_support.h"

static int vg_allowed_state(ModelInstance* instance, int mask) {
    return instance != NULL && (instance->state & mask) != 0;
}

static fmi2Status vg_state_error(ModelInstance* instance, const char* function_name) {
    (void)function_name;
    if (instance != NULL) {
        instance->state = VG_STATE_ERROR;
    }
    return fmi2Error;
}

static int vg_close(double a, double b) {
    double scale = fabs(a);
    if (fabs(b) > scale) {
        scale = fabs(b);
    }
    return fabs(a - b) <= (1e-12 * (1.0 + scale));
}

fmi2Status status_from_result(int result) {
    return result == 0 ? fmi2OK : fmi2Error;
}

const char* fmi2GetTypesPlatform(void) {
    return fmi2TypesPlatform;
}

const char* fmi2GetVersion(void) {
    return fmi2Version;
}

fmi2Status fmi2SetDebugLogging(fmi2Component c, fmi2Boolean loggingOn, size_t nCategories, const fmi2String categories[]) {
    ModelInstance* instance = (ModelInstance*)c;
    (void)nCategories;
    (void)categories;
    if (instance == NULL) {
        return fmi2Error;
    }
    instance->logging_on = loggingOn;
    return fmi2OK;
}

fmi2Component fmi2Instantiate(
    fmi2String instanceName,
    fmi2Type fmuType,
    fmi2String fmuGUID,
    fmi2String fmuResourceLocation,
    const fmi2CallbackFunctions* functions,
    fmi2Boolean visible,
    fmi2Boolean loggingOn
) {
    (void)fmuResourceLocation;
    (void)visible;
    if (instanceName == NULL || functions == NULL) {
        return NULL;
    }
    if (fmuType != fmi2CoSimulation) {
        return NULL;
    }
    if (fmuGUID == NULL) {
        return NULL;
    }
    if (VG_MODEL_GUID[0] != '\0') {
        size_t index = 0u;
        while (VG_MODEL_GUID[index] != '\0' || fmuGUID[index] != '\0') {
            if (VG_MODEL_GUID[index] != fmuGUID[index]) {
                return NULL;
            }
            index += 1u;
        }
    }
    VgMemoryCallbacks memory_callbacks;
    memory_callbacks.allocate_memory = functions->allocateMemory;
    memory_callbacks.free_memory = functions->freeMemory;
    return (fmi2Component)model_instance_create(instanceName, &memory_callbacks, loggingOn);
}

void fmi2FreeInstance(fmi2Component c) {
    model_instance_free((ModelInstance*)c);
}

fmi2Status fmi2SetupExperiment(fmi2Component c, fmi2Boolean toleranceDefined, fmi2Real tolerance, fmi2Real startTime, fmi2Boolean stopTimeDefined, fmi2Real stopTime) {
    ModelInstance* instance = (ModelInstance*)c;
    (void)toleranceDefined;
    (void)tolerance;
    if (!vg_allowed_state(instance, VG_STATE_INSTANTIATED)) {
        return vg_state_error(instance, "fmi2SetupExperiment illegal state");
    }
    if (stopTimeDefined && stopTime <= startTime) {
        return vg_state_error(instance, "fmi2SetupExperiment invalid stop time");
    }
    return status_from_result(model_instance_setup_experiment(instance, startTime, stopTimeDefined, stopTime));
}

fmi2Status fmi2EnterInitializationMode(fmi2Component c) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_INSTANTIATED)) {
        return vg_state_error(instance, "fmi2EnterInitializationMode illegal state");
    }
    instance->state = VG_STATE_INITIALIZATION_MODE;
    return fmi2OK;
}

fmi2Status fmi2ExitInitializationMode(fmi2Component c) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_INITIALIZATION_MODE)) {
        return vg_state_error(instance, "fmi2ExitInitializationMode illegal state");
    }
    return status_from_result(model_instance_initialize(instance));
}

fmi2Status fmi2Terminate(fmi2Component c) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_STEP_COMPLETE | VG_STATE_ERROR)) {
        return vg_state_error(instance, "fmi2Terminate illegal state");
    }
    instance->terminated = fmi2True;
    instance->state = VG_STATE_TERMINATED;
    return fmi2OK;
}

fmi2Status fmi2Reset(fmi2Component c) {
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_INSTANTIATED | VG_STATE_INITIALIZATION_MODE | VG_STATE_STEP_COMPLETE | VG_STATE_TERMINATED | VG_STATE_ERROR)) {
        return vg_state_error(instance, "fmi2Reset illegal state");
    }
    return status_from_result(model_instance_reset(instance));
}

fmi2Status fmi2GetReal(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2Real value[]) {
    size_t i;
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_INITIALIZATION_MODE | VG_STATE_STEP_COMPLETE | VG_STATE_TERMINATED)) {
        return vg_state_error(instance, "fmi2GetReal illegal state");
    }
    if ((nvr > 0u) && (vr == NULL || value == NULL)) {
        return fmi2Error;
    }
    for (i = 0u; i < nvr; ++i) {
        if (generated_get_real(instance, vr[i], &value[i]) != 0) {
            return fmi2Error;
        }
    }
    return fmi2OK;
}

fmi2Status fmi2GetInteger(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2Integer value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetBoolean(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2Boolean value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetString(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2String value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2SetReal(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Real value[]) {
    size_t i;
    ModelInstance* instance = (ModelInstance*)c;
    if (!vg_allowed_state(instance, VG_STATE_INSTANTIATED | VG_STATE_INITIALIZATION_MODE | VG_STATE_STEP_COMPLETE)) {
        return vg_state_error(instance, "fmi2SetReal illegal state");
    }
    if ((nvr > 0u) && (vr == NULL || value == NULL)) {
        return fmi2Error;
    }
    for (i = 0u; i < nvr; ++i) {
        if (generated_set_real(instance, vr[i], value[i]) != 0) {
            return fmi2Error;
        }
    }
    return fmi2OK;
}

fmi2Status fmi2SetInteger(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Integer value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2SetBoolean(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Boolean value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2SetString(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2String value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetFMUstate(fmi2Component c, fmi2FMUstate* FMUstate) {
    (void)c;
    if (FMUstate != NULL) {
        *FMUstate = NULL;
    }
    return fmi2Error;
}

fmi2Status fmi2SetFMUstate(fmi2Component c, fmi2FMUstate FMUstate) {
    (void)c;
    (void)FMUstate;
    return fmi2Error;
}

fmi2Status fmi2FreeFMUstate(fmi2Component c, fmi2FMUstate* FMUstate) {
    (void)c;
    if (FMUstate != NULL) {
        *FMUstate = NULL;
    }
    return fmi2Error;
}

fmi2Status fmi2SerializedFMUstateSize(fmi2Component c, fmi2FMUstate FMUstate, size_t* size) {
    (void)c;
    (void)FMUstate;
    if (size != NULL) {
        *size = 0u;
    }
    return fmi2Error;
}

fmi2Status fmi2SerializeFMUstate(fmi2Component c, fmi2FMUstate FMUstate, fmi2Byte serializedState[], size_t size) {
    (void)c;
    (void)FMUstate;
    (void)serializedState;
    (void)size;
    return fmi2Error;
}

fmi2Status fmi2DeSerializeFMUstate(fmi2Component c, const fmi2Byte serializedState[], size_t size, fmi2FMUstate* FMUstate) {
    (void)c;
    (void)serializedState;
    (void)size;
    if (FMUstate != NULL) {
        *FMUstate = NULL;
    }
    return fmi2Error;
}

fmi2Status fmi2GetDirectionalDerivative(fmi2Component c, const fmi2ValueReference vUnknown_ref[], size_t nUnknown, const fmi2ValueReference vKnown_ref[], size_t nKnown, const fmi2Real dvKnown[], fmi2Real dvUnknown[]) {
    (void)c;
    (void)vUnknown_ref;
    (void)nUnknown;
    (void)vKnown_ref;
    (void)nKnown;
    (void)dvKnown;
    (void)dvUnknown;
    return fmi2Error;
}

fmi2Status fmi2EnterEventMode(fmi2Component c) {
    (void)c;
    return fmi2Error;
}

fmi2Status fmi2NewDiscreteStates(fmi2Component c, fmi2EventInfo* eventInfo) {
    (void)c;
    if (eventInfo != NULL) {
        eventInfo->newDiscreteStatesNeeded = fmi2False;
        eventInfo->terminateSimulation = fmi2False;
        eventInfo->nominalsOfContinuousStatesChanged = fmi2False;
        eventInfo->valuesOfContinuousStatesChanged = fmi2False;
        eventInfo->nextEventTimeDefined = fmi2False;
        eventInfo->nextEventTime = 0.0;
    }
    return fmi2Error;
}

fmi2Status fmi2EnterContinuousTimeMode(fmi2Component c) {
    (void)c;
    return fmi2Error;
}

fmi2Status fmi2CompletedIntegratorStep(fmi2Component c, fmi2Boolean noSetFMUStatePriorToCurrentPoint, fmi2Boolean* enterEventMode, fmi2Boolean* terminateSimulation) {
    (void)c;
    (void)noSetFMUStatePriorToCurrentPoint;
    if (enterEventMode != NULL) {
        *enterEventMode = fmi2False;
    }
    if (terminateSimulation != NULL) {
        *terminateSimulation = fmi2False;
    }
    return fmi2Error;
}

fmi2Status fmi2SetTime(fmi2Component c, fmi2Real time) {
    (void)c;
    (void)time;
    return fmi2Error;
}

fmi2Status fmi2SetContinuousStates(fmi2Component c, const fmi2Real x[], size_t nx) {
    (void)c;
    (void)x;
    (void)nx;
    return fmi2Error;
}

fmi2Status fmi2GetDerivatives(fmi2Component c, fmi2Real derivatives[], size_t nx) {
    (void)c;
    (void)derivatives;
    (void)nx;
    return fmi2Error;
}

fmi2Status fmi2GetEventIndicators(fmi2Component c, fmi2Real eventIndicators[], size_t ni) {
    (void)c;
    (void)eventIndicators;
    (void)ni;
    return fmi2Error;
}

fmi2Status fmi2GetContinuousStates(fmi2Component c, fmi2Real states[], size_t nx) {
    (void)c;
    (void)states;
    (void)nx;
    return fmi2Error;
}

fmi2Status fmi2GetNominalsOfContinuousStates(fmi2Component c, fmi2Real x_nominal[], size_t nx) {
    (void)c;
    (void)x_nominal;
    (void)nx;
    return fmi2Error;
}

fmi2Status fmi2SetRealInputDerivatives(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Integer order[], const fmi2Real value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)order;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetRealOutputDerivatives(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Integer order[], fmi2Real value[]) {
    (void)c;
    (void)vr;
    (void)nvr;
    (void)order;
    (void)value;
    return fmi2Error;
}

fmi2Status fmi2DoStep(fmi2Component c, fmi2Real currentCommunicationPoint, fmi2Real communicationStepSize, fmi2Boolean noSetFMUStatePriorToCurrentPoint) {
    ModelInstance* instance = (ModelInstance*)c;
    (void)noSetFMUStatePriorToCurrentPoint;
    if (!vg_allowed_state(instance, VG_STATE_STEP_COMPLETE)) {
        return vg_state_error(instance, "fmi2DoStep illegal state");
    }
    if (communicationStepSize <= 0.0) {
        return vg_state_error(instance, "fmi2DoStep non-positive step size");
    }
    if (!vg_close(currentCommunicationPoint, instance->time)) {
        return vg_state_error(instance, "fmi2DoStep communication point mismatch");
    }
    if (instance->stop_time_defined && (currentCommunicationPoint + communicationStepSize) > instance->stop_time && !vg_close(currentCommunicationPoint + communicationStepSize, instance->stop_time)) {
        return vg_state_error(instance, "fmi2DoStep exceeds stop time");
    }
    return status_from_result(model_instance_do_step(instance, communicationStepSize));
}

fmi2Status fmi2CancelStep(fmi2Component c) {
    (void)c;
    return fmi2Error;
}

fmi2Status fmi2GetStatus(fmi2Component c, const fmi2StatusKind s, fmi2Status* value) {
    (void)c;
    (void)s;
    if (value != NULL) {
        *value = fmi2OK;
    }
    return fmi2Discard;
}

fmi2Status fmi2GetRealStatus(fmi2Component c, const fmi2StatusKind s, fmi2Real* value) {
    ModelInstance* instance = (ModelInstance*)c;
    if (value == NULL || instance == NULL) {
        return fmi2Error;
    }
    if (s == fmi2LastSuccessfulTime) {
        *value = instance->last_successful_time;
        return fmi2OK;
    }
    *value = 0.0;
    return fmi2Discard;
}

fmi2Status fmi2GetIntegerStatus(fmi2Component c, const fmi2StatusKind s, fmi2Integer* value) {
    (void)c;
    (void)s;
    if (value != NULL) {
        *value = 0;
    }
    return fmi2Discard;
}

fmi2Status fmi2GetBooleanStatus(fmi2Component c, const fmi2StatusKind s, fmi2Boolean* value) {
    ModelInstance* instance = (ModelInstance*)c;
    if (value == NULL || instance == NULL) {
        return fmi2Error;
    }
    if (s == fmi2Terminated) {
        *value = instance->terminated;
        return fmi2OK;
    }
    *value = fmi2False;
    return fmi2Discard;
}

fmi2Status fmi2GetStringStatus(fmi2Component c, const fmi2StatusKind s, fmi2String* value) {
    (void)c;
    (void)s;
    if (value != NULL) {
        *value = "";
    }
    return fmi2Discard;
}
