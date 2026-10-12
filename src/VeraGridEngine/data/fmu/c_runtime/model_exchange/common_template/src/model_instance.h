#ifndef MODEL_INSTANCE_H
#define MODEL_INSTANCE_H

#include "runtime_support.h"
#include "generated_metadata.h"

enum {
    VG_STATE_INSTANTIATED = 1,
    VG_STATE_INITIALIZATION_MODE = 2,
    VG_STATE_EVENT_MODE = 4,
    VG_STATE_CONTINUOUS_TIME_MODE = 8,
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
    int dirty;
    int state;
    double time;
    double start_time;
    double stop_time;
    double relative_tolerance;
    double last_successful_time;
    double* states;
    double* derivatives;
    double* algebraics;
    double* inputs;
    double* const_params;
    double* runtime_params;
    double* nominals;
    double* event_indicators;
    double* time_events;
    size_t time_event_count;
    double* logic_reals;
    int* logic_ints;
} ModelInstance;

ModelInstance* model_instance_create(const char* instance_name, const VgMemoryCallbacks* callbacks, int logging_on);
void model_instance_free(ModelInstance* instance);
int model_instance_setup_experiment(ModelInstance* instance, int tolerance_defined, double tolerance, double start_time, int stop_time_defined, double stop_time);
int model_instance_initialize(ModelInstance* instance);
int model_instance_reset(ModelInstance* instance);
int model_instance_sync(ModelInstance* instance);
int model_instance_set_time(ModelInstance* instance, double time);
int model_instance_set_continuous_states(ModelInstance* instance, const double x[], size_t nx);
int model_instance_get_continuous_states(ModelInstance* instance, double x[], size_t nx);
int model_instance_get_derivatives(ModelInstance* instance, double dx[], size_t nx);
int model_instance_get_event_indicators(ModelInstance* instance, double z[], size_t ni);
int model_instance_completed_integrator_step(ModelInstance* instance, int* enter_event_mode, int* terminate_simulation);
int model_instance_enter_event_mode(ModelInstance* instance);
int model_instance_new_discrete_states(ModelInstance* instance, VgEventInfo* event_info);
int model_instance_enter_continuous_time_mode(ModelInstance* instance);
int solver_solve_algebraics(ModelInstance* instance);
int model_instance_copy_string(ModelInstance* instance, const char* source, char** dest);

#endif
