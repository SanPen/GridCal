/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#ifndef VERAGRID_ADAPTER_IEEE_CIGRE_V1_0_H
#define VERAGRID_ADAPTER_IEEE_CIGRE_V1_0_H

#include <stdint.h>

#include "adapter_common.h"
#include "platform.h"

typedef union VgV10Extension {
    int8_t i8[8];
    uint8_t u8[8];
    int16_t i16[4];
    uint16_t u16[4];
    int32_t i32[2];
    uint32_t u32[2];
    char chars[8];
    float f32[2];
    double f64;
    void *pointer;
} VgV10Extension;

typedef struct VgV10InputSignal {
    const char *name;
    const char *block_path;
    int32_t width;
    const char *unit;
    int32_t semantic;
} VgV10InputSignal;

typedef struct VgV10OutputSignal {
    const char *name;
    const char *block_path;
    int32_t width;
    const char *unit;
    int32_t semantic;
} VgV10OutputSignal;

typedef struct VgV10Parameter {
    const char *name;
    const char *description;
    const char *unit;
    double default_value;
    double minimum_value;
    double maximum_value;
    int32_t fixed_value;
} VgV10Parameter;

typedef struct VgV10ModelInfo {
    uint8_t api_release[4];
    const char *model_name;
    const char *model_version;
    const char *model_description;
    const char *version_control_info;
    const char *general_information;
    const char *model_created;
    const char *model_creator;
    const char *model_last_modified_date;
    const char *model_last_modified_by;
    const char *model_modified_comment;
    const char *model_modified_history;
    const char *code_generated_on;
    const char *included_solver;
    double sample_time;
    int32_t input_count;
    const VgV10InputSignal *inputs;
    int32_t output_count;
    const VgV10OutputSignal *outputs;
    int32_t parameter_count;
    const VgV10Parameter *parameters;
    int32_t continuous_state_count;
    int32_t miscellaneous_state_bytes;
    uint32_t checksum[4];
    const char *last_error_message;
    uint8_t model_mode;
    uint8_t loadflow_flag;
    int32_t int_state_count;
    int32_t float_state_count;
    int32_t double_state_count;
    VgV10Extension extension;
} VgV10ModelInfo;

typedef struct VgV10InstanceAbi {
    double *inputs;
    double *outputs;
    double *parameters;
    double *continuous_states;
    double *state_derivatives;
    uint8_t *miscellaneous_states;
    const char *last_error_message;
    const char *last_general_message;
    uint8_t verbose_level;
    int32_t *int_states;
    float *float_states;
    double *double_states;
    VgV10Extension extension;
} VgV10InstanceAbi;

typedef const VgV10ModelInfo *(VG_PLATFORM_CDECL *VgV10GetInfo)(void);
typedef const char *(VG_PLATFORM_CDECL *VgV10Call)(VgV10InstanceAbi *instance);
typedef const char *(VG_PLATFORM_CDECL *VgV10Outputs)(VgV10InstanceAbi *instance,
                                                      uint32_t major_step);
typedef const char *(VG_PLATFORM_CDECL *VgV10PrintInfo)(void);

typedef struct VgV10Instance {
    char *identifier;
    VgV10InstanceAbi abi;
    double *inputs;
    double *outputs;
    double *parameters;
    double *continuous_states;
    double *state_derivatives;
    uint8_t *miscellaneous_states;
    int32_t *int_states;
    float *float_states;
    double *double_states;
    uint32_t input_count;
    uint32_t output_count;
    uint8_t started;
    uint8_t terminated;
} VgV10Instance;

typedef struct VgIeeeCigreV10Adapter {
    VgNativeAdapterLimits limits;
    const VgV10ModelInfo *info;
    VgV10Call check_parameters;
    VgV10Call initialize;
    VgV10Outputs outputs;
    VgV10Call update;
    VgV10Call terminate;
    VgV10PrintInfo print_info;
    VgV10Instance **instances;
    uint32_t instance_count;
} VgIeeeCigreV10Adapter;

void vg_ieee_cigre_v1_0_initialize_adapter(VgIeeeCigreV10Adapter *adapter);
int vg_ieee_cigre_v1_0_bind(const VgPlatformLibrary *library,
                            const VgNativeAdapterLimits *limits,
                            VgIeeeCigreV10Adapter *adapter);
int vg_ieee_cigre_v1_0_copy_model_info(VgIeeeCigreV10Adapter *adapter,
                                       uint8_t **payload,
                                       uint64_t *payload_size);
int32_t vg_ieee_cigre_v1_0_print_info(VgIeeeCigreV10Adapter *adapter);
int vg_ieee_cigre_v1_0_initialize(VgIeeeCigreV10Adapter *adapter,
                                  const uint8_t *payload,
                                  uint64_t payload_size,
                                  uint8_t **response,
                                  uint64_t *response_size);
int vg_ieee_cigre_v1_0_sample(VgIeeeCigreV10Adapter *adapter,
                              const uint8_t *payload,
                              uint64_t payload_size,
                              uint8_t **response,
                              uint64_t *response_size);
int vg_ieee_cigre_v1_0_close(VgIeeeCigreV10Adapter *adapter,
                             const uint8_t *payload,
                             uint64_t payload_size,
                             uint8_t **response,
                             uint64_t *response_size);
void vg_ieee_cigre_v1_0_destroy(VgIeeeCigreV10Adapter *adapter);

#endif