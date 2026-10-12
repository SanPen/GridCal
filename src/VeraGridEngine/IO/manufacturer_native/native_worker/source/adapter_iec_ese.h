/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#ifndef VERAGRID_ADAPTER_IEC_ESE_H
#define VERAGRID_ADAPTER_IEC_ESE_H

#include <stdint.h>

#include "adapter_common.h"
#include "platform.h"

typedef union EseExtension {
    double real64;
    void *pointer;
    uint8_t bytes[8];
} EseExtension;

typedef struct EseSignal {
    const char *name;
    const char *path;
    int32_t width;
} EseSignal;

typedef struct EseParameter {
    const char *name;
    const char *description;
    const char *unit;
    double default_value;
    double minimum_value;
    double maximum_value;
} EseParameter;

typedef struct EseModelInfo {
    uint8_t release[4];
    const char *name;
    const char *version;
    const char *description;
    const char *version_control;
    const char *general;
    const char *created;
    const char *creator;
    const char *modified_date;
    const char *modified_by;
    const char *modified_comment;
    const char *modified_history;
    const char *generated;
    const char *solver;
    double sample_time;
    int32_t input_count;
    const EseSignal *inputs;
    int32_t output_count;
    const EseSignal *outputs;
    int32_t parameter_count;
    const EseParameter *parameters;
    int32_t continuous_states;
    int32_t miscellaneous_bytes;
    uint32_t checksum[4];
    const char *last_error;
    uint8_t mode;
    uint8_t loadflow;
    EseExtension extension;
} EseModelInfo;

typedef struct EseInstanceAbi {
    double *inputs;
    double *outputs;
    double *parameters;
    double *continuous_states;
    double *derivatives;
    uint8_t *miscellaneous;
    const char *last_error;
    const char *last_general;
    uint8_t verbose;
    EseExtension extension;
} EseInstanceAbi;

typedef const EseModelInfo *(VG_PLATFORM_CDECL *EseGetInfo)(void);
typedef EseInstanceAbi *(VG_PLATFORM_CDECL *EseCreate)(uint32_t use_internal_solver,
                                                       double ta);
typedef const char *(VG_PLATFORM_CDECL *EseCall)(EseInstanceAbi *instance);
typedef const char *(VG_PLATFORM_CDECL *EseOutputs)(EseInstanceAbi *instance,
                                                    uint32_t major_step);

typedef struct EseInstance {
    char *identifier;
    EseInstanceAbi *abi;
    uint32_t input_count;
    uint32_t output_count;
    uint8_t started;
    uint8_t terminated;
} EseInstance;

typedef struct VgIecEseAdapter {
    VgNativeAdapterLimits limits;
    const EseModelInfo *info;
    EseCreate create;
    EseCall check_parameters;
    EseCall initialize;
    EseOutputs outputs;
    EseCall update;
    EseCall terminate;
    EseInstance **instances;
    uint32_t instance_count;
} VgIecEseAdapter;

void vg_iec_ese_initialize_adapter(VgIecEseAdapter *adapter);
int vg_iec_ese_bind(const VgPlatformLibrary *library,
                    const VgNativeAdapterLimits *limits,
                    VgIecEseAdapter *adapter);
int vg_iec_ese_copy_model_info(VgIecEseAdapter *adapter,
                               uint8_t **payload,
                               uint64_t *payload_size);
int32_t vg_iec_ese_print_info(VgIecEseAdapter *adapter);
int vg_iec_ese_initialize(VgIecEseAdapter *adapter,
                          const uint8_t *payload,
                          uint64_t payload_size,
                          uint8_t **response,
                          uint64_t *response_size);
int vg_iec_ese_sample(VgIecEseAdapter *adapter,
                      const uint8_t *payload,
                      uint64_t payload_size,
                      uint8_t **response,
                      uint64_t *response_size);
int vg_iec_ese_close(VgIecEseAdapter *adapter,
                     const uint8_t *payload,
                     uint64_t payload_size,
                     uint8_t **response,
                     uint64_t *response_size);
void vg_iec_ese_destroy(VgIecEseAdapter *adapter);

#endif