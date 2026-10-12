#ifndef MODEL_INSTANCE_H
#define MODEL_INSTANCE_H

#include "runtime_support.h"
#include "generated_metadata.h"

enum {
    VG_STATE_START_AND_END = 1,
    VG_STATE_INSTANTIATED = 2,
    VG_STATE_INITIALIZATION_MODE = 4,
    VG_STATE_STEP_COMPLETE = 8,
    VG_STATE_TERMINATED = 16,
    VG_STATE_ERROR = 32
};

typedef struct ModelInstance {
    VgMemoryCallbacks callbacks;
    const char* instance_name;
    char* instance_name_owned;
    int logging_on;
    int initialized;
    int terminated;
    int stop_time_defined;
    int state;
    double time;
    double start_time;
    double stop_time;
    double last_successful_time;
    double step_size;
    double current_step_size;
    double* states;
    double* algebraics;
    double* inputs;
    double* const_params;
    double* runtime_params;
    double* history;
    double* d_history;
    double* history2;
    double* residual;
    double* logic_reals;
    int* logic_ints;
} ModelInstance;

ModelInstance* model_instance_create(const char* instance_name, const VgMemoryCallbacks* callbacks, int logging_on);
void model_instance_free(ModelInstance* instance);
int model_instance_setup_experiment(ModelInstance* instance, double start_time, int stop_time_defined, double stop_time);
int model_instance_initialize(ModelInstance* instance);
int model_instance_do_step(ModelInstance* instance, double communication_step_size);
int model_instance_reset(ModelInstance* instance);
int solver_step(ModelInstance* instance, double step_size);
int model_instance_copy_string(ModelInstance* instance, const char* source, char** dest);

#endif
