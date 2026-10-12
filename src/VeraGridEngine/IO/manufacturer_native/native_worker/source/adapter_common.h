/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#ifndef VERAGRID_MANUFACTURER_ADAPTER_COMMON_H
#define VERAGRID_MANUFACTURER_ADAPTER_COMMON_H

#include <stdint.h>

typedef struct VgNativeAdapterLimits {
    uint32_t maximum_instances;
    uint32_t maximum_ports;
    uint32_t maximum_parameters;
    uint64_t maximum_scalar_slots;
    uint64_t maximum_state_scalars;
    uint64_t maximum_instance_bytes;
    uint64_t maximum_frame_bytes;
} VgNativeAdapterLimits;

#endif