#include "runtime_fmi3.h"

#include "generated_metadata.h"
#include "generated_model.h"
#include "runtime_support.h"

static int vg_allowed_state(ModelInstance* instance, int mask) {
    return instance != NULL && (instance->state & mask) != 0;
}

static fmi3Status vg_state_error(ModelInstance* instance) {
    if (instance != NULL) {
        instance->state = VG_STATE_ERROR;
    }
    return fmi3Error;
}


static int vg_token_matches(const char* token) {
    size_t index = 0u;
    if (token == NULL) {
        return 0;
    }
    while (VG_MODEL_GUID[index] != '\0' || token[index] != '\0') {
        if (VG_MODEL_GUID[index] != token[index]) {
            return 0;
        }
        index += 1u;
    }
    return 1;
}

const char* fmi3GetVersion(void) {
    return fmi3Version;
}

fmi3Status fmi3SetDebugLogging(fmi3Instance instance, fmi3Boolean loggingOn, size_t nCategories, const fmi3String categories[]) {
    ModelInstance* model = (ModelInstance*)instance;
    (void)nCategories;
    (void)categories;
    if (model != NULL) {
        model->logging_on = loggingOn;
        return fmi3OK;
    }
    return fmi3Error;
}

fmi3Instance fmi3InstantiateModelExchange(fmi3String instanceName, fmi3String instantiationToken, fmi3String resourcePath, fmi3Boolean visible, fmi3Boolean loggingOn, fmi3InstanceEnvironment instanceEnvironment, fmi3LogMessageCallback logMessage) {
    VgMemoryCallbacks memory_callbacks;
    (void)resourcePath;
    (void)visible;
    (void)instanceEnvironment;
    (void)logMessage;
    if (instanceName == NULL || !vg_token_matches(instantiationToken)) {
        return NULL;
    }
    memory_callbacks.allocate_memory = NULL;
    memory_callbacks.free_memory = NULL;
    return (fmi3Instance)model_instance_create(instanceName, &memory_callbacks, loggingOn);
}

fmi3Instance fmi3InstantiateCoSimulation(fmi3String instanceName, fmi3String instantiationToken, fmi3String resourcePath, fmi3Boolean visible, fmi3Boolean loggingOn, fmi3Boolean eventModeUsed, fmi3Boolean earlyReturnAllowed, const fmi3ValueReference requiredIntermediateVariables[], size_t nRequiredIntermediateVariables, fmi3InstanceEnvironment instanceEnvironment, fmi3LogMessageCallback logMessage, fmi3IntermediateUpdateCallback intermediateUpdate) {
    (void)instanceName;
    (void)instantiationToken;
    (void)resourcePath;
    (void)visible;
    (void)loggingOn;
    (void)eventModeUsed;
    (void)earlyReturnAllowed;
    (void)requiredIntermediateVariables;
    (void)nRequiredIntermediateVariables;
    (void)instanceEnvironment;
    (void)logMessage;
    (void)intermediateUpdate;
    return NULL;
}

fmi3Instance fmi3InstantiateScheduledExecution(fmi3String instanceName, fmi3String instantiationToken, fmi3String resourcePath, fmi3Boolean visible, fmi3Boolean loggingOn, fmi3InstanceEnvironment instanceEnvironment, fmi3LogMessageCallback logMessage, fmi3ClockUpdateCallback clockUpdate, fmi3LockPreemptionCallback lockPreemption, fmi3UnlockPreemptionCallback unlockPreemption) {
    (void)instanceName;
    (void)instantiationToken;
    (void)resourcePath;
    (void)visible;
    (void)loggingOn;
    (void)instanceEnvironment;
    (void)logMessage;
    (void)clockUpdate;
    (void)lockPreemption;
    (void)unlockPreemption;
    return NULL;
}

void fmi3FreeInstance(fmi3Instance instance) {
    model_instance_free((ModelInstance*)instance);
}

fmi3Status fmi3EnterInitializationMode(fmi3Instance instance, fmi3Boolean toleranceDefined, fmi3Float64 tolerance, fmi3Float64 startTime, fmi3Boolean stopTimeDefined, fmi3Float64 stopTime) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_INSTANTIATED)) {
        return vg_state_error(model);
    }
    if (stopTimeDefined && stopTime <= startTime) {
        return vg_state_error(model);
    }
    if (model_instance_setup_experiment(model, toleranceDefined, tolerance, startTime, stopTimeDefined, stopTime) != 0) {
        return vg_state_error(model);
    }
    model->state = VG_STATE_INITIALIZATION_MODE;
    return fmi3OK;
}

fmi3Status fmi3ExitInitializationMode(fmi3Instance instance) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_INITIALIZATION_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_initialize(model) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3EnterEventMode(fmi3Instance instance) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_enter_event_mode(model) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3Terminate(fmi3Instance instance) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_ERROR)) {
        return vg_state_error(model);
    }
    model->terminated = 1;
    model->state = VG_STATE_TERMINATED;
    return fmi3OK;
}

fmi3Status fmi3Reset(fmi3Instance instance) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_INSTANTIATED | VG_STATE_INITIALIZATION_MODE | VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_TERMINATED | VG_STATE_ERROR)) {
        return vg_state_error(model);
    }
    return model_instance_reset(model) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3GetFloat64(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, fmi3Float64 values[], size_t nValues) {
    ModelInstance* model = (ModelInstance*)instance;
    size_t index;
    if (!vg_allowed_state(model, VG_STATE_INITIALIZATION_MODE | VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_TERMINATED)) {
        return vg_state_error(model);
    }
    if (nValues != nValueReferences || (nValues > 0u && (valueReferences == NULL || values == NULL))) {
        return fmi3Error;
    }
    if (model->initialized && model->dirty && model_instance_sync(model) != 0) {
        return vg_state_error(model);
    }
    for (index = 0u; index < nValueReferences; ++index) {
        if (generated_get_real(model, valueReferences[index], &values[index]) != 0) {
            return fmi3Error;
        }
    }
    return fmi3OK;
}

fmi3Status fmi3SetFloat64(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const fmi3Float64 values[], size_t nValues) {
    ModelInstance* model = (ModelInstance*)instance;
    size_t index;
    if (!vg_allowed_state(model, VG_STATE_INSTANTIATED | VG_STATE_INITIALIZATION_MODE | VG_STATE_EVENT_MODE | VG_STATE_CONTINUOUS_TIME_MODE)) {
        return vg_state_error(model);
    }
    if (nValues != nValueReferences || (nValues > 0u && (valueReferences == NULL || values == NULL))) {
        return fmi3Error;
    }
    for (index = 0u; index < nValueReferences; ++index) {
        if (generated_set_real(model, valueReferences[index], values[index]) != 0) {
            return fmi3Error;
        }
    }
    model->dirty = 1;
    return fmi3OK;
}

#define VG_UNSUPPORTED_GETTER(NAME, VALUE_TYPE) \
fmi3Status NAME(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, VALUE_TYPE values[], size_t nValues) { \
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)values; (void)nValues; return fmi3Error; \
}

#define VG_UNSUPPORTED_SETTER(NAME, VALUE_TYPE) \
fmi3Status NAME(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const VALUE_TYPE values[], size_t nValues) { \
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)values; (void)nValues; return fmi3Error; \
}

VG_UNSUPPORTED_GETTER(fmi3GetFloat32, fmi3Float32)
VG_UNSUPPORTED_GETTER(fmi3GetInt8, fmi3Int8)
VG_UNSUPPORTED_GETTER(fmi3GetUInt8, fmi3UInt8)
VG_UNSUPPORTED_GETTER(fmi3GetInt16, fmi3Int16)
VG_UNSUPPORTED_GETTER(fmi3GetUInt16, fmi3UInt16)
VG_UNSUPPORTED_GETTER(fmi3GetInt32, fmi3Int32)
VG_UNSUPPORTED_GETTER(fmi3GetUInt32, fmi3UInt32)
VG_UNSUPPORTED_GETTER(fmi3GetInt64, fmi3Int64)
VG_UNSUPPORTED_GETTER(fmi3GetUInt64, fmi3UInt64)
VG_UNSUPPORTED_GETTER(fmi3GetBoolean, fmi3Boolean)
VG_UNSUPPORTED_GETTER(fmi3GetString, fmi3String)
VG_UNSUPPORTED_SETTER(fmi3SetFloat32, fmi3Float32)
VG_UNSUPPORTED_SETTER(fmi3SetInt8, fmi3Int8)
VG_UNSUPPORTED_SETTER(fmi3SetUInt8, fmi3UInt8)
VG_UNSUPPORTED_SETTER(fmi3SetInt16, fmi3Int16)
VG_UNSUPPORTED_SETTER(fmi3SetUInt16, fmi3UInt16)
VG_UNSUPPORTED_SETTER(fmi3SetInt32, fmi3Int32)
VG_UNSUPPORTED_SETTER(fmi3SetUInt32, fmi3UInt32)
VG_UNSUPPORTED_SETTER(fmi3SetInt64, fmi3Int64)
VG_UNSUPPORTED_SETTER(fmi3SetUInt64, fmi3UInt64)
VG_UNSUPPORTED_SETTER(fmi3SetBoolean, fmi3Boolean)
VG_UNSUPPORTED_SETTER(fmi3SetString, fmi3String)

fmi3Status fmi3GetBinary(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, size_t valueSizes[], fmi3Binary values[], size_t nValues) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)valueSizes; (void)values; (void)nValues;
    return fmi3Error;
}

fmi3Status fmi3GetClock(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, fmi3Clock values[]) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)values;
    return fmi3Error;
}

fmi3Status fmi3SetBinary(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const size_t valueSizes[], const fmi3Binary values[], size_t nValues) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)valueSizes; (void)values; (void)nValues;
    return fmi3Error;
}

fmi3Status fmi3SetClock(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const fmi3Clock values[]) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)values;
    return fmi3Error;
}

fmi3Status fmi3GetNumberOfVariableDependencies(fmi3Instance instance, fmi3ValueReference valueReference, size_t* nDependencies) {
    (void)instance; (void)valueReference;
    if (nDependencies != NULL) {
        *nDependencies = 0u;
    }
    return fmi3Error;
}

fmi3Status fmi3GetVariableDependencies(fmi3Instance instance, fmi3ValueReference dependent, size_t elementIndicesOfDependent[], fmi3ValueReference independents[], size_t elementIndicesOfIndependents[], fmi3DependencyKind dependencyKinds[], size_t nDependencies) {
    (void)instance; (void)dependent; (void)elementIndicesOfDependent; (void)independents; (void)elementIndicesOfIndependents; (void)dependencyKinds; (void)nDependencies;
    return fmi3Error;
}

fmi3Status fmi3GetFMUState(fmi3Instance instance, fmi3FMUState* FMUState) {
    (void)instance;
    if (FMUState != NULL) {
        *FMUState = NULL;
    }
    return fmi3Error;
}

fmi3Status fmi3SetFMUState(fmi3Instance instance, fmi3FMUState FMUState) {
    (void)instance; (void)FMUState;
    return fmi3Error;
}

fmi3Status fmi3FreeFMUState(fmi3Instance instance, fmi3FMUState* FMUState) {
    (void)instance;
    if (FMUState != NULL) {
        *FMUState = NULL;
    }
    return fmi3Error;
}

fmi3Status fmi3SerializedFMUStateSize(fmi3Instance instance, fmi3FMUState FMUState, size_t* size) {
    (void)instance; (void)FMUState;
    if (size != NULL) {
        *size = 0u;
    }
    return fmi3Error;
}

fmi3Status fmi3SerializeFMUState(fmi3Instance instance, fmi3FMUState FMUState, fmi3Byte serializedState[], size_t size) {
    (void)instance; (void)FMUState; (void)serializedState; (void)size;
    return fmi3Error;
}

fmi3Status fmi3DeserializeFMUState(fmi3Instance instance, const fmi3Byte serializedState[], size_t size, fmi3FMUState* FMUState) {
    (void)instance; (void)serializedState; (void)size;
    if (FMUState != NULL) {
        *FMUState = NULL;
    }
    return fmi3Error;
}

fmi3Status fmi3GetDirectionalDerivative(fmi3Instance instance, const fmi3ValueReference unknowns[], size_t nUnknowns, const fmi3ValueReference knowns[], size_t nKnowns, const fmi3Float64 seed[], size_t nSeed, fmi3Float64 sensitivity[], size_t nSensitivity) {
    (void)instance; (void)unknowns; (void)nUnknowns; (void)knowns; (void)nKnowns; (void)seed; (void)nSeed; (void)sensitivity; (void)nSensitivity;
    return fmi3Error;
}

fmi3Status fmi3GetAdjointDerivative(fmi3Instance instance, const fmi3ValueReference unknowns[], size_t nUnknowns, const fmi3ValueReference knowns[], size_t nKnowns, const fmi3Float64 seed[], size_t nSeed, fmi3Float64 sensitivity[], size_t nSensitivity) {
    (void)instance; (void)unknowns; (void)nUnknowns; (void)knowns; (void)nKnowns; (void)seed; (void)nSeed; (void)sensitivity; (void)nSensitivity;
    return fmi3Error;
}

#define VG_UNSUPPORTED_INSTANCE_FUNCTION(NAME) \
fmi3Status NAME(fmi3Instance instance) { (void)instance; return fmi3Error; }

VG_UNSUPPORTED_INSTANCE_FUNCTION(fmi3EnterConfigurationMode)
VG_UNSUPPORTED_INSTANCE_FUNCTION(fmi3ExitConfigurationMode)
VG_UNSUPPORTED_INSTANCE_FUNCTION(fmi3EvaluateDiscreteStates)

fmi3Status fmi3UpdateDiscreteStates(
    fmi3Instance instance,
    fmi3Boolean* discreteStatesNeedUpdate,
    fmi3Boolean* terminateSimulation,
    fmi3Boolean* nominalsOfContinuousStatesChanged,
    fmi3Boolean* valuesOfContinuousStatesChanged,
    fmi3Boolean* nextEventTimeDefined,
    fmi3Float64* nextEventTime) {
    ModelInstance* model = (ModelInstance*)instance;
    VgEventInfo event_info;
    int result;
    if (!vg_allowed_state(model, VG_STATE_EVENT_MODE)) {
        return vg_state_error(model);
    }
    if (discreteStatesNeedUpdate == NULL || terminateSimulation == NULL ||
        nominalsOfContinuousStatesChanged == NULL ||
        valuesOfContinuousStatesChanged == NULL || nextEventTimeDefined == NULL ||
        nextEventTime == NULL) {
        return fmi3Error;
    }
    result = model_instance_new_discrete_states(model, &event_info);
    *discreteStatesNeedUpdate = event_info.new_discrete_states_needed;
    *terminateSimulation = event_info.terminate_simulation;
    *nominalsOfContinuousStatesChanged = event_info.nominals_changed;
    *valuesOfContinuousStatesChanged = event_info.values_changed;
    *nextEventTimeDefined = event_info.next_event_time_defined;
    *nextEventTime = event_info.next_event_time;
    return result == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3EnterContinuousTimeMode(fmi3Instance instance) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_EVENT_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_enter_continuous_time_mode(model) == 0 ? fmi3OK : vg_state_error(model);
}

VG_UNSUPPORTED_INSTANCE_FUNCTION(fmi3EnterStepMode)

#define VG_UNSUPPORTED_DECIMAL_GETTER(NAME, VALUE_TYPE) \
fmi3Status NAME(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, VALUE_TYPE values[]) { \
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)values; return fmi3Error; \
}

fmi3Status fmi3GetIntervalDecimal(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, fmi3Float64 intervals[], fmi3IntervalQualifier qualifiers[]) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)intervals; (void)qualifiers; return fmi3Error;
}
fmi3Status fmi3GetIntervalFraction(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, fmi3UInt64 counters[], fmi3UInt64 resolutions[], fmi3IntervalQualifier qualifiers[]) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)counters; (void)resolutions; (void)qualifiers; return fmi3Error;
}
VG_UNSUPPORTED_DECIMAL_GETTER(fmi3GetShiftDecimal, fmi3Float64)
fmi3Status fmi3GetShiftFraction(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, fmi3UInt64 counters[], fmi3UInt64 resolutions[]) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)counters; (void)resolutions; return fmi3Error;
}

#define VG_UNSUPPORTED_DECIMAL_SETTER(NAME, VALUE_TYPE) \
fmi3Status NAME(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const VALUE_TYPE values[]) { \
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)values; return fmi3Error; \
}

VG_UNSUPPORTED_DECIMAL_SETTER(fmi3SetIntervalDecimal, fmi3Float64)
fmi3Status fmi3SetIntervalFraction(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const fmi3UInt64 counters[], const fmi3UInt64 resolutions[]) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)counters; (void)resolutions; return fmi3Error;
}
VG_UNSUPPORTED_DECIMAL_SETTER(fmi3SetShiftDecimal, fmi3Float64)
fmi3Status fmi3SetShiftFraction(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const fmi3UInt64 counters[], const fmi3UInt64 resolutions[]) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)counters; (void)resolutions; return fmi3Error;
}

fmi3Status fmi3CompletedIntegratorStep(fmi3Instance instance, fmi3Boolean noSetFMUStatePriorToCurrentPoint, fmi3Boolean* enterEventMode, fmi3Boolean* terminateSimulation) {
    ModelInstance* model = (ModelInstance*)instance;
    int internal_enter_event_mode = 0;
    int internal_terminate_simulation = 0;
    int result;
    (void)noSetFMUStatePriorToCurrentPoint;
    if (!vg_allowed_state(model, VG_STATE_CONTINUOUS_TIME_MODE)) {
        return vg_state_error(model);
    }
    if (enterEventMode == NULL || terminateSimulation == NULL) {
        return fmi3Error;
    }
    result = model_instance_completed_integrator_step(model, &internal_enter_event_mode, &internal_terminate_simulation);
    *enterEventMode = internal_enter_event_mode != 0 ? fmi3True : fmi3False;
    *terminateSimulation = internal_terminate_simulation != 0 ? fmi3True : fmi3False;
    return result == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3SetTime(fmi3Instance instance, fmi3Float64 time) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_EVENT_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_set_time(model, time) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3SetContinuousStates(fmi3Instance instance, const fmi3Float64 continuousStates[], size_t nContinuousStates) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_EVENT_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_set_continuous_states(model, continuousStates, nContinuousStates) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3GetContinuousStateDerivatives(fmi3Instance instance, fmi3Float64 derivatives[], size_t nContinuousStates) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_EVENT_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_get_derivatives(model, derivatives, nContinuousStates) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3GetEventIndicators(fmi3Instance instance, fmi3Float64 eventIndicators[], size_t nEventIndicators) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_EVENT_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_get_event_indicators(model, eventIndicators, nEventIndicators) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3GetContinuousStates(fmi3Instance instance, fmi3Float64 continuousStates[], size_t nContinuousStates) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_CONTINUOUS_TIME_MODE | VG_STATE_EVENT_MODE)) {
        return vg_state_error(model);
    }
    return model_instance_get_continuous_states(model, continuousStates, nContinuousStates) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3GetNominalsOfContinuousStates(fmi3Instance instance, fmi3Float64 nominals[], size_t nContinuousStates) {
    ModelInstance* model = (ModelInstance*)instance;
    if (model == NULL || (nContinuousStates > 0u && nominals == NULL) || nContinuousStates != (size_t)VG_NUM_STATES) {
        return fmi3Error;
    }
    if (nContinuousStates > 0u) {
        memcpy(nominals, model->nominals, sizeof(fmi3Float64) * nContinuousStates);
    }
    return fmi3OK;
}

fmi3Status fmi3GetNumberOfEventIndicators(fmi3Instance instance, size_t* nEventIndicators) {
    if (instance == NULL || nEventIndicators == NULL) {
        return fmi3Error;
    }
    *nEventIndicators = (size_t)VG_NUM_EVENT_INDICATORS;
    return fmi3OK;
}

fmi3Status fmi3GetNumberOfContinuousStates(fmi3Instance instance, size_t* nContinuousStates) {
    if (instance == NULL || nContinuousStates == NULL) {
        return fmi3Error;
    }
    *nContinuousStates = (size_t)VG_NUM_STATES;
    return fmi3OK;
}

fmi3Status fmi3GetOutputDerivatives(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const fmi3Int32 orders[], fmi3Float64 values[], size_t nValues) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)orders; (void)values; (void)nValues; return fmi3Error;
}

fmi3Status fmi3DoStep(fmi3Instance instance, fmi3Float64 currentCommunicationPoint, fmi3Float64 communicationStepSize, fmi3Boolean noSetFMUStatePriorToCurrentPoint, fmi3Boolean* eventHandlingNeeded, fmi3Boolean* terminateSimulation, fmi3Boolean* earlyReturn, fmi3Float64* lastSuccessfulTime) {
    (void)instance;
    (void)communicationStepSize;
    (void)noSetFMUStatePriorToCurrentPoint;
    if (eventHandlingNeeded != NULL) {
        *eventHandlingNeeded = fmi3False;
    }
    if (terminateSimulation != NULL) {
        *terminateSimulation = fmi3False;
    }
    if (earlyReturn != NULL) {
        *earlyReturn = fmi3False;
    }
    if (lastSuccessfulTime != NULL) {
        *lastSuccessfulTime = currentCommunicationPoint;
    }
    return fmi3Error;
}

fmi3Status fmi3ActivateModelPartition(fmi3Instance instance, fmi3ValueReference clockReference, fmi3Float64 activationTime) {
    (void)instance; (void)clockReference; (void)activationTime; return fmi3Error;
}
