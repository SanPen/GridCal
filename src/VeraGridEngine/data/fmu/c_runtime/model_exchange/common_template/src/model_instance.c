#include "model_instance.h"

#include "generated_model.h"
#include "runtime_support.h"

static void* vg_calloc(const VgMemoryCallbacks* callbacks, size_t count, size_t size) {
    if (callbacks != NULL && callbacks->allocate_memory != NULL) {
        return callbacks->allocate_memory(count, size);
    }
    return calloc(count, size);
}

static void vg_free(const VgMemoryCallbacks* callbacks, void* ptr) {
    if (ptr == NULL) {
        return;
    }
    if (callbacks != NULL && callbacks->free_memory != NULL) {
        callbacks->free_memory(ptr);
        return;
    }
    free(ptr);
}

static double* allocate_vector(const VgMemoryCallbacks* callbacks, size_t count) {
    if (count == 0u) {
        return NULL;
    }
    return (double*)vg_calloc(callbacks, count, sizeof(double));
}

static void zero_vector(double* data, size_t count) {
    if (data != NULL && count > 0u) {
        memset(data, 0, sizeof(double) * count);
    }
}

int model_instance_copy_string(ModelInstance* instance, const char* source, char** dest) {
    size_t length;
    char* text;
    if (dest == NULL) {
        return 1;
    }
    *dest = NULL;
    if (source == NULL) {
        return 0;
    }
    length = strlen(source);
    text = (char*)vg_calloc(instance != NULL ? &instance->callbacks : NULL, length + 1u, sizeof(char));
    if (text == NULL) {
        return 1;
    }
    memcpy(text, source, length + 1u);
    *dest = text;
    return 0;
}

ModelInstance* model_instance_create(const char* instance_name, const VgMemoryCallbacks* callbacks, int logging_on) {
    size_t i;
    ModelInstance* instance = (ModelInstance*)vg_calloc(callbacks, 1u, sizeof(ModelInstance));
    if (instance == NULL) {
        return NULL;
    }
    if (callbacks != NULL) {
        instance->callbacks = *callbacks;
    }
    if (model_instance_copy_string(instance, instance_name, &instance->instance_name_owned) != 0) {
        vg_free(&instance->callbacks, instance);
        return NULL;
    }
    instance->instance_name = instance->instance_name_owned;
    instance->logging_on = logging_on;
    instance->state = VG_STATE_INSTANTIATED;
    instance->dirty = 1;
    instance->relative_tolerance = VG_RELATIVE_TOLERANCE;
    instance->states = allocate_vector(&instance->callbacks, VG_NUM_STATES);
    instance->derivatives = allocate_vector(&instance->callbacks, VG_NUM_DERIVATIVES);
    instance->algebraics = allocate_vector(&instance->callbacks, VG_NUM_ALGEBRAICS);
    instance->inputs = allocate_vector(&instance->callbacks, VG_NUM_INPUTS);
    instance->const_params = allocate_vector(&instance->callbacks, VG_NUM_CONST_PARAMS);
    instance->runtime_params = allocate_vector(&instance->callbacks, VG_NUM_RUNTIME_PARAMS);
    instance->nominals = allocate_vector(&instance->callbacks, VG_NUM_STATES);
    instance->event_indicators = allocate_vector(&instance->callbacks, VG_NUM_EVENT_INDICATORS);
    instance->time_events = allocate_vector(&instance->callbacks, VG_LOGIC_ENTRY_COUNT * 2u);
    instance->time_event_count = 0u;
    instance->logic_reals = allocate_vector(&instance->callbacks, VG_LOGIC_REAL_SLOTS);
    instance->logic_ints = (int*)vg_calloc(&instance->callbacks, VG_LOGIC_INT_SLOTS, sizeof(int));
    for (i = 0u; i < (size_t)VG_NUM_STATES; ++i) {
        instance->nominals[i] = 1.0;
    }
    generated_set_start_values(instance);
    return instance;
}

void model_instance_free(ModelInstance* instance) {
    if (instance == NULL) {
        return;
    }
    vg_free(&instance->callbacks, instance->instance_name_owned);
    vg_free(&instance->callbacks, instance->states);
    vg_free(&instance->callbacks, instance->derivatives);
    vg_free(&instance->callbacks, instance->algebraics);
    vg_free(&instance->callbacks, instance->inputs);
    vg_free(&instance->callbacks, instance->const_params);
    vg_free(&instance->callbacks, instance->runtime_params);
    vg_free(&instance->callbacks, instance->nominals);
    vg_free(&instance->callbacks, instance->event_indicators);
    vg_free(&instance->callbacks, instance->time_events);
    vg_free(&instance->callbacks, instance->logic_reals);
    vg_free(&instance->callbacks, instance->logic_ints);
    vg_free(&instance->callbacks, instance);
}

int model_instance_setup_experiment(ModelInstance* instance, int tolerance_defined, double tolerance, double start_time, int stop_time_defined, double stop_time) {
    if (instance == NULL) {
        return 1;
    }
    instance->time = start_time;
    instance->start_time = start_time;
    instance->stop_time_defined = stop_time_defined;
    instance->stop_time = stop_time;
    instance->relative_tolerance = tolerance_defined ? tolerance : VG_RELATIVE_TOLERANCE;
    instance->last_successful_time = start_time;
    instance->dirty = 1;
    return 0;
}

int model_instance_sync(ModelInstance* instance) {
    if (instance == NULL) {
        return 1;
    }
    if (solver_solve_algebraics(instance) != 0) {
        return 2;
    }
    generated_get_derivatives(instance, instance->derivatives);
    generated_get_event_indicators(instance, instance->event_indicators);
    instance->dirty = 0;
    instance->last_successful_time = instance->time;
    return 0;
}

int model_instance_initialize(ModelInstance* instance) {
    if (instance == NULL) {
        return 1;
    }
    generated_eval_init(instance);
    generated_eval_initial_derivatives(instance);
    generated_procedural_apply_initial(instance);
    instance->initialized = 1;
    instance->terminated = 0;
    instance->dirty = 1;
    if (model_instance_sync(instance) != 0) {
        return 2;
    }
    instance->state = VG_STATE_EVENT_MODE;
    return 0;
}

int model_instance_reset(ModelInstance* instance) {
    size_t i;
    if (instance == NULL) {
        return 1;
    }
    zero_vector(instance->states, VG_NUM_STATES);
    zero_vector(instance->derivatives, VG_NUM_DERIVATIVES);
    zero_vector(instance->algebraics, VG_NUM_ALGEBRAICS);
    zero_vector(instance->inputs, VG_NUM_INPUTS);
    zero_vector(instance->const_params, VG_NUM_CONST_PARAMS);
    zero_vector(instance->runtime_params, VG_NUM_RUNTIME_PARAMS);
    zero_vector(instance->event_indicators, VG_NUM_EVENT_INDICATORS);
    zero_vector(instance->time_events, VG_LOGIC_ENTRY_COUNT * 2u);
    instance->time_event_count = 0u;
    zero_vector(instance->logic_reals, VG_LOGIC_REAL_SLOTS);
    if (instance->logic_ints != NULL && VG_LOGIC_INT_SLOTS > 0) memset(instance->logic_ints, 0, sizeof(int) * VG_LOGIC_INT_SLOTS);
    for (i = 0u; i < (size_t)VG_NUM_STATES; ++i) {
        instance->nominals[i] = 1.0;
    }
    generated_set_start_values(instance);
    instance->time = instance->start_time;
    instance->last_successful_time = instance->start_time;
    instance->initialized = 0;
    instance->terminated = 0;
    instance->dirty = 1;
    instance->state = VG_STATE_INSTANTIATED;
    return 0;
}

int model_instance_set_time(ModelInstance* instance, double time) {
    if (instance == NULL) {
        return 1;
    }
    instance->time = time;
    instance->dirty = 1;
    return 0;
}

int model_instance_set_continuous_states(ModelInstance* instance, const double x[], size_t nx) {
    if (instance == NULL || ((nx > 0u) && x == NULL) || nx != (size_t)VG_NUM_STATES) {
        return 1;
    }
    if (nx > 0u) {
        memcpy(instance->states, x, sizeof(double) * nx);
    }
    instance->dirty = 1;
    return 0;
}

int model_instance_get_continuous_states(ModelInstance* instance, double x[], size_t nx) {
    if (instance == NULL || ((nx > 0u) && x == NULL) || nx != (size_t)VG_NUM_STATES) {
        return 1;
    }
    if (nx > 0u) {
        memcpy(x, instance->states, sizeof(double) * nx);
    }
    return 0;
}

int model_instance_get_derivatives(ModelInstance* instance, double dx[], size_t nx) {
    if (instance == NULL || ((nx > 0u) && dx == NULL) || nx != (size_t)VG_NUM_DERIVATIVES) {
        return 1;
    }
    if (instance->dirty && model_instance_sync(instance) != 0) {
        return 2;
    }
    if (nx > 0u) {
        memcpy(dx, instance->derivatives, sizeof(double) * nx);
    }
    return 0;
}

int model_instance_get_event_indicators(ModelInstance* instance, double z[], size_t ni) {
    if (instance == NULL || ((ni > 0u) && z == NULL) || ni != (size_t)VG_NUM_EVENT_INDICATORS) {
        return 1;
    }
    if (instance->dirty && model_instance_sync(instance) != 0) {
        return 2;
    }
    if (ni > 0u) {
        memcpy(z, instance->event_indicators, sizeof(double) * ni);
    }
    return 0;
}

int model_instance_completed_integrator_step(ModelInstance* instance, int* enter_event_mode, int* terminate_simulation) {
    if (instance == NULL) {
        return 1;
    }
    if (enter_event_mode != NULL) {
        *enter_event_mode = 0;
    }
    if (terminate_simulation != NULL) {
        *terminate_simulation = 0;
    }
    instance->last_successful_time = instance->time;
    return 0;
}

int model_instance_enter_event_mode(ModelInstance* instance) {
    if (instance == NULL) {
        return 1;
    }
    instance->state = VG_STATE_EVENT_MODE;
    return 0;
}

int model_instance_new_discrete_states(ModelInstance* instance, VgEventInfo* event_info) {
    size_t event_index;
    if (instance == NULL || event_info == NULL) {
        return 1;
    }
    if (instance->dirty && model_instance_sync(instance) != 0) {
        return 2;
    }
    if (generated_procedural_new_discrete_states(instance)) {
        instance->dirty = 1;
    }
    if (instance->dirty && model_instance_sync(instance) != 0) {
        return 2;
    }
    event_info->new_discrete_states_needed = 0;
    event_info->terminate_simulation = 0;
    event_info->nominals_changed = 0;
    event_info->values_changed = 0;
    event_info->next_event_time_defined = 0;
    event_info->next_event_time = 0.0;
    for (event_index = 0u; event_index < instance->time_event_count; ++event_index) {
        double candidate_time = instance->time_events[event_index];
        if (candidate_time > instance->time &&
            (!event_info->next_event_time_defined || candidate_time < event_info->next_event_time)) {
            event_info->next_event_time_defined = 1;
            event_info->next_event_time = candidate_time;
        }
    }
    return 0;
}

int model_instance_enter_continuous_time_mode(ModelInstance* instance) {
    if (instance == NULL) {
        return 1;
    }
    if (instance->dirty && model_instance_sync(instance) != 0) {
        return 2;
    }
    instance->state = VG_STATE_CONTINUOUS_TIME_MODE;
    return 0;
}
