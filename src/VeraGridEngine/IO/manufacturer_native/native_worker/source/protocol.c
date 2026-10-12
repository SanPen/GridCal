/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#include <stddef.h>
#include <stdint.h>

#include "protocol.h"

int vg_native_bounded_text_size(const char *text, uint64_t maximum_size,
                                uint64_t *text_size) {
    uint64_t index;
    if (text == NULL || maximum_size == 0 || text_size == NULL) {
        return 0;
    } else {
        index = 0;
    }
    while (index < maximum_size && text[index] != '\0') {
        index += 1;
    }
    if (index >= maximum_size) {
        return 0;
    } else {
        *text_size = index;
        return 1;
    }
}