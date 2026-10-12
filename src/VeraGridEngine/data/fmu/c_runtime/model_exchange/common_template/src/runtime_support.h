#ifndef RUNTIME_SUPPORT_H
#define RUNTIME_SUPPORT_H

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef void* (*VgAllocateMemory)(size_t count, size_t size);
typedef void (*VgFreeMemory)(void* memory);

typedef struct VgMemoryCallbacks {
    VgAllocateMemory allocate_memory;
    VgFreeMemory free_memory;
} VgMemoryCallbacks;

typedef struct VgEventInfo {
    int new_discrete_states_needed;
    int terminate_simulation;
    int nominals_changed;
    int values_changed;
    int next_event_time_defined;
    double next_event_time;
} VgEventInfo;

#ifndef NAN
#define NAN (0.0 / 0.0)
#endif

#ifndef isnan
#define isnan(x) ((x) != (x))
#endif

#endif
