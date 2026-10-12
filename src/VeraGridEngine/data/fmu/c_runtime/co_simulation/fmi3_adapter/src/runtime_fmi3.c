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

static int vg_close(double first, double second) {
    double scale = fabs(first);
    if (fabs(second) > scale) {
        scale = fabs(second);
    }
    return fabs(first - second) <= (1e-12 * (1.0 + scale));
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
    (void)instanceName;
    (void)instantiationToken;
    (void)resourcePath;
    (void)visible;
    (void)loggingOn;
    (void)instanceEnvironment;
    (void)logMessage;
    return NULL;
}

fmi3Instance fmi3InstantiateCoSimulation(fmi3String instanceName, fmi3String instantiationToken, fmi3String resourcePath, fmi3Boolean visible, fmi3Boolean loggingOn, fmi3Boolean eventModeUsed, fmi3Boolean earlyReturnAllowed, const fmi3ValueReference requiredIntermediateVariables[], size_t nRequiredIntermediateVariables, fmi3InstanceEnvironment instanceEnvironment, fmi3LogMessageCallback logMessage, fmi3IntermediateUpdateCallback intermediateUpdate) {
    VgMemoryCallbacks memory_callbacks;
    (void)resourcePath;
    (void)visible;
    (void)instanceEnvironment;
    (void)logMessage;
    (void)intermediateUpdate;
    if (instanceName == NULL || !vg_token_matches(instantiationToken)) {
        return NULL;
    }
    if (eventModeUsed || earlyReturnAllowed) {
        return NULL;
    }
    if (nRequiredIntermediateVariables > 0u) {
        return NULL;
    }
    (void)requiredIntermediateVariables;
    memory_callbacks.allocate_memory = NULL;
    memory_callbacks.free_memory = NULL;
    return (fmi3Instance)model_instance_create(instanceName, &memory_callbacks, loggingOn);
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
    (void)toleranceDefined;
    (void)tolerance;
    if (!vg_allowed_state(model, VG_STATE_INSTANTIATED)) {
        return vg_state_error(model);
    }
    if (stopTimeDefined && stopTime <= startTime) {
        return vg_state_error(model);
    }
    if (model_instance_setup_experiment(model, startTime, stopTimeDefined, stopTime) != 0) {
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
    return vg_state_error((ModelInstance*)instance);
}

fmi3Status fmi3Terminate(fmi3Instance instance) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_STEP_COMPLETE | VG_STATE_ERROR)) {
        return vg_state_error(model);
    }
    model->terminated = 1;
    model->state = VG_STATE_TERMINATED;
    return fmi3OK;
}

fmi3Status fmi3Reset(fmi3Instance instance) {
    ModelInstance* model = (ModelInstance*)instance;
    if (!vg_allowed_state(model, VG_STATE_INSTANTIATED | VG_STATE_INITIALIZATION_MODE | VG_STATE_STEP_COMPLETE | VG_STATE_TERMINATED | VG_STATE_ERROR)) {
        return vg_state_error(model);
    }
    return model_instance_reset(model) == 0 ? fmi3OK : vg_state_error(model);
}

fmi3Status fmi3GetFloat64(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, fmi3Float64 values[], size_t nValues) {
    ModelInstance* model = (ModelInstance*)instance;
    size_t index;
    if (!vg_allowed_state(model, VG_STATE_INITIALIZATION_MODE | VG_STATE_STEP_COMPLETE | VG_STATE_TERMINATED)) {
        return vg_state_error(model);
    }
    if (nValues != nValueReferences || (nValues > 0u && (valueReferences == NULL || values == NULL))) {
        return fmi3Error;
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
    if (!vg_allowed_state(model, VG_STATE_INSTANTIATED | VG_STATE_INITIALIZATION_MODE | VG_STATE_STEP_COMPLETE)) {
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
    (void)instance;
    if (discreteStatesNeedUpdate == NULL || terminateSimulation == NULL ||
        nominalsOfContinuousStatesChanged == NULL ||
        valuesOfContinuousStatesChanged == NULL || nextEventTimeDefined == NULL ||
        nextEventTime == NULL) {
        return fmi3Error;
    }
    *discreteStatesNeedUpdate = fmi3False;
    *terminateSimulation = fmi3False;
    *nominalsOfContinuousStatesChanged = fmi3False;
    *valuesOfContinuousStatesChanged = fmi3False;
    *nextEventTimeDefined = fmi3False;
    *nextEventTime = 0.0;
    return fmi3Error;
}

VG_UNSUPPORTED_INSTANCE_FUNCTION(fmi3EnterContinuousTimeMode)
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
    (void)instance; (void)noSetFMUStatePriorToCurrentPoint;
    if (enterEventMode != NULL) {
        *enterEventMode = fmi3False;
    }
    if (terminateSimulation != NULL) {
        *terminateSimulation = fmi3False;
    }
    return fmi3Error;
}

fmi3Status fmi3SetTime(fmi3Instance instance, fmi3Float64 time) {
    (void)instance; (void)time; return fmi3Error;
}
fmi3Status fmi3SetContinuousStates(fmi3Instance instance, const fmi3Float64 continuousStates[], size_t nContinuousStates) {
    (void)instance; (void)continuousStates; (void)nContinuousStates; return fmi3Error;
}
fmi3Status fmi3GetContinuousStateDerivatives(fmi3Instance instance, fmi3Float64 derivatives[], size_t nContinuousStates) {
    (void)instance; (void)derivatives; (void)nContinuousStates; return fmi3Error;
}
fmi3Status fmi3GetEventIndicators(fmi3Instance instance, fmi3Float64 eventIndicators[], size_t nEventIndicators) {
    (void)instance; (void)eventIndicators; (void)nEventIndicators; return fmi3Error;
}
fmi3Status fmi3GetContinuousStates(fmi3Instance instance, fmi3Float64 continuousStates[], size_t nContinuousStates) {
    (void)instance; (void)continuousStates; (void)nContinuousStates; return fmi3Error;
}
fmi3Status fmi3GetNominalsOfContinuousStates(fmi3Instance instance, fmi3Float64 nominals[], size_t nContinuousStates) {
    (void)instance; (void)nominals; (void)nContinuousStates; return fmi3Error;
}
fmi3Status fmi3GetNumberOfEventIndicators(fmi3Instance instance, size_t* nEventIndicators) {
    (void)instance; if (nEventIndicators != NULL) { *nEventIndicators = 0u; } return fmi3Error;
}
fmi3Status fmi3GetNumberOfContinuousStates(fmi3Instance instance, size_t* nContinuousStates) {
    (void)instance; if (nContinuousStates != NULL) { *nContinuousStates = 0u; } return fmi3Error;
}

fmi3Status fmi3GetOutputDerivatives(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences, const fmi3Int32 orders[], fmi3Float64 values[], size_t nValues) {
    (void)instance; (void)valueReferences; (void)nValueReferences; (void)orders; (void)values; (void)nValues; return fmi3Error;
}

fmi3Status fmi3DoStep(fmi3Instance instance, fmi3Float64 currentCommunicationPoint, fmi3Float64 communicationStepSize, fmi3Boolean noSetFMUStatePriorToCurrentPoint, fmi3Boolean* eventHandlingNeeded, fmi3Boolean* terminateSimulation, fmi3Boolean* earlyReturn, fmi3Float64* lastSuccessfulTime) {
    ModelInstance* model = (ModelInstance*)instance;
    (void)noSetFMUStatePriorToCurrentPoint;
    if (eventHandlingNeeded == NULL || terminateSimulation == NULL || earlyReturn == NULL || lastSuccessfulTime == NULL) {
        return fmi3Error;
    }
    *eventHandlingNeeded = fmi3False;
    *terminateSimulation = fmi3False;
    *earlyReturn = fmi3False;
    *lastSuccessfulTime = currentCommunicationPoint;
    if (!vg_allowed_state(model, VG_STATE_STEP_COMPLETE) || communicationStepSize <= 0.0) {
        return vg_state_error(model);
    }
    if (!vg_close(currentCommunicationPoint, model->time)) {
        return vg_state_error(model);
    }
    if (model->stop_time_defined && currentCommunicationPoint + communicationStepSize > model->stop_time && !vg_close(currentCommunicationPoint + communicationStepSize, model->stop_time)) {
        return vg_state_error(model);
    }
    if (model_instance_do_step(model, communicationStepSize) != 0) {
        return vg_state_error(model);
    }
    *lastSuccessfulTime = model->last_successful_time;
    return fmi3OK;
}

fmi3Status fmi3ActivateModelPartition(fmi3Instance instance, fmi3ValueReference clockReference, fmi3Float64 activationTime) {
    (void)instance; (void)clockReference; (void)activationTime; return fmi3Error;
}
