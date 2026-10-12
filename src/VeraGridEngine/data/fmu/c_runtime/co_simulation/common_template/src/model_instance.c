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

static int* allocate_int_vector(const VgMemoryCallbacks* callbacks, size_t count) {
    if (count == 0u) {
        return NULL;
    }
    return (int*)vg_calloc(callbacks, count, sizeof(int));
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
    instance->step_size = VG_FIXED_STEP;
    instance->current_step_size = VG_FIXED_STEP;
    instance->states = allocate_vector(callbacks, VG_NUM_STATES);
    instance->algebraics = allocate_vector(callbacks, VG_NUM_ALGEBRAICS);
    instance->inputs = allocate_vector(callbacks, VG_NUM_INPUTS);
    instance->const_params = allocate_vector(callbacks, VG_NUM_CONST_PARAMS);
    instance->runtime_params = allocate_vector(callbacks, VG_NUM_RUNTIME_PARAMS);
    instance->history = allocate_vector(callbacks, VG_NUM_CONTINUOUS_VARS);
    instance->d_history = allocate_vector(callbacks, VG_NUM_CONTINUOUS_VARS);
    instance->history2 = allocate_vector(callbacks, VG_NUM_CONTINUOUS_VARS);
    instance->residual = allocate_vector(callbacks, VG_NUM_RESIDUALS);
    instance->logic_reals = allocate_vector(callbacks, VG_LOGIC_REAL_SLOTS);
    instance->logic_ints = allocate_int_vector(callbacks, VG_LOGIC_INT_SLOTS);
    generated_set_start_values(instance);
    return instance;
}

void model_instance_free(ModelInstance* instance) {
    if (instance == NULL) {
        return;
    }
    vg_free(&instance->callbacks, instance->instance_name_owned);
    vg_free(&instance->callbacks, instance->states);
    vg_free(&instance->callbacks, instance->algebraics);
    vg_free(&instance->callbacks, instance->inputs);
    vg_free(&instance->callbacks, instance->const_params);
    vg_free(&instance->callbacks, instance->runtime_params);
    vg_free(&instance->callbacks, instance->history);
    vg_free(&instance->callbacks, instance->d_history);
    vg_free(&instance->callbacks, instance->history2);
    vg_free(&instance->callbacks, instance->residual);
    vg_free(&instance->callbacks, instance->logic_reals);
    vg_free(&instance->callbacks, instance->logic_ints);
    vg_free(&instance->callbacks, instance);
}

int model_instance_setup_experiment(ModelInstance* instance, double start_time, int stop_time_defined, double stop_time) {
    if (instance == NULL) {
        return 1;
    }
    instance->time = start_time;
    instance->start_time = start_time;
    instance->stop_time_defined = stop_time_defined;
    instance->stop_time = stop_time;
    instance->last_successful_time = start_time;
    return 0;
}

int model_instance_initialize(ModelInstance* instance) {
    size_t i;
    size_t history_index;
    if (instance == NULL) {
        return 1;
    }
    generated_eval_init(instance);
    history_index = 0u;
    for (i = 0u; i < (size_t)VG_NUM_STATES; ++i, ++history_index) {
        if (instance->history != NULL) {
            instance->history[history_index] = instance->states[i];
        }
        if (instance->history2 != NULL) {
            instance->history2[history_index] = instance->states[i];
        }
        if (instance->d_history != NULL) {
            instance->d_history[history_index] = 0.0;
        }
    }
    for (i = 0u; i < (size_t)VG_NUM_ALGEBRAICS; ++i, ++history_index) {
        if (instance->history != NULL) {
            instance->history[history_index] = instance->algebraics[i];
        }
        if (instance->history2 != NULL) {
            instance->history2[history_index] = instance->algebraics[i];
        }
        if (instance->d_history != NULL) {
            instance->d_history[history_index] = 0.0;
        }
    }
    generated_eval_discrete_init(instance);
    generated_procedural_update(instance, instance->time);
    generated_eval_outputs(instance);
    instance->initialized = 1;
    instance->state = VG_STATE_STEP_COMPLETE;
    instance->last_successful_time = instance->time;
    return 0;
}

int model_instance_do_step(ModelInstance* instance, double communication_step_size) {
    double remaining;
    if (instance == NULL || instance->terminated || !instance->initialized) {
        return 1;
    }
    remaining = communication_step_size;
    while (remaining > 1e-15) {
        double step = instance->step_size;
        double next_event = generated_procedural_next_event(instance, instance->time, instance->time + step);
        if (step > remaining) {
            step = remaining;
        }
        if (!isnan(next_event) && next_event > instance->time && next_event < instance->time + step) {
            step = next_event - instance->time;
        }
        instance->current_step_size = step;
        if (solver_step(instance, step) != 0) {
            return 2;
        }
        instance->time += step;
        instance->last_successful_time = instance->time;
        generated_procedural_update(instance, instance->time);
        generated_eval_outputs(instance);
        remaining -= step;
    }
    return 0;
}

int model_instance_reset(ModelInstance* instance) {
    if (instance == NULL) {
        return 1;
    }
    memset(instance->states, 0, sizeof(double) * VG_NUM_STATES);
    memset(instance->algebraics, 0, sizeof(double) * VG_NUM_ALGEBRAICS);
    memset(instance->inputs, 0, sizeof(double) * VG_NUM_INPUTS);
    memset(instance->const_params, 0, sizeof(double) * VG_NUM_CONST_PARAMS);
    memset(instance->runtime_params, 0, sizeof(double) * VG_NUM_RUNTIME_PARAMS);
    memset(instance->history, 0, sizeof(double) * VG_NUM_CONTINUOUS_VARS);
    memset(instance->d_history, 0, sizeof(double) * VG_NUM_CONTINUOUS_VARS);
    memset(instance->history2, 0, sizeof(double) * VG_NUM_CONTINUOUS_VARS);
    memset(instance->logic_reals, 0, sizeof(double) * VG_LOGIC_REAL_SLOTS);
    memset(instance->logic_ints, 0, sizeof(int) * VG_LOGIC_INT_SLOTS);
    generated_set_start_values(instance);
    instance->time = instance->start_time;
    instance->last_successful_time = instance->start_time;
    instance->initialized = 0;
    instance->terminated = 0;
    instance->state = VG_STATE_INSTANTIATED;
    return 0;
}
