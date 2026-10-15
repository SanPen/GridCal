/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "platform.h"

static HANDLE vg_windows_handle(intptr_t handle) {
    return (HANDLE)(uintptr_t)handle;
}

static int vg_windows_utf8_path(const char *path, wchar_t output[32768]) {
    int converted;
    if (path == NULL || output == NULL) {
        return 0;
    } else {
        converted = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, output, 32768);
        return converted > 0;
    }
}

static int vg_windows_file_identity(HANDLE handle, VgPlatformFileIdentity *identity) {
    uint8_t bytes[24];
    if (handle == NULL || handle == INVALID_HANDLE_VALUE || identity == NULL) {
        return 0;
    } else if (!GetFileInformationByHandleEx(
                   handle, (FILE_INFO_BY_HANDLE_CLASS)18, bytes, sizeof(bytes))) {
        return 0;
    } else {
        memcpy(&identity->device_identifier, bytes, 8);
        memcpy(identity->file_identifier, bytes + 8, 16);
        return 1;
    }
}

static int vg_platform_identity_equal(const VgPlatformFileIdentity *left,
                                      const VgPlatformFileIdentity *right) {
    if (left == NULL || right == NULL) {
        return 0;
    } else {
        return left->device_identifier == right->device_identifier
            && memcmp(left->file_identifier, right->file_identifier, 16) == 0;
    }
}

void vg_platform_channel_initialize(VgPlatformChannel *channel, const char *argument) {
    unsigned long long numeric_handle;
    char *end;
    if (channel != NULL) {
        channel->handle = -1;
        if (argument != NULL) {
            end = NULL;
            numeric_handle = _strtoui64(argument, &end, 10);
            if (end != argument && end != NULL && *end == '\0' && numeric_handle != 0
                    && numeric_handle <= (unsigned long long)UINTPTR_MAX) {
                channel->handle = (intptr_t)(uintptr_t)numeric_handle;
            } else {
                channel->handle = -1;
            }
        } else {
            channel->handle = -1;
        }
    } else {
        return;
    }
}

int vg_platform_channel_is_valid(const VgPlatformChannel *channel) {
    HANDLE handle;
    if (channel == NULL || channel->handle == -1) {
        return 0;
    } else {
        handle = vg_windows_handle(channel->handle);
        return handle != NULL && handle != INVALID_HANDLE_VALUE;
    }
}

int vg_platform_channel_read_some(VgPlatformChannel *channel, uint8_t *target,
                                  uint32_t capacity, uint32_t *received) {
    DWORD windows_received;
    BOOL result;
    if (!vg_platform_channel_is_valid(channel) || target == NULL || capacity == 0
            || received == NULL) {
        return 0;
    } else {
        windows_received = 0;
        result = ReadFile(vg_windows_handle(channel->handle), target, capacity,
                          &windows_received, NULL);
        *received = (uint32_t)windows_received;
        return result ? 1 : 0;
    }
}

int vg_platform_channel_read_exact(VgPlatformChannel *channel, uint8_t *target, uint64_t size) {
    uint64_t completed;
    if (!vg_platform_channel_is_valid(channel) || (target == NULL && size != 0)) {
        return 0;
    } else {
        completed = 0;
        while (completed < size) {
            uint32_t capacity = (uint32_t)((size - completed) > 1048576ULL
                ? 1048576ULL : (size - completed));
            uint32_t received = 0;
            if (!vg_platform_channel_read_some(channel, target + completed, capacity, &received)
                    || received == 0) {
                return 0;
            } else {
                completed += received;
            }
        }
        return 1;
    }
}

int vg_platform_channel_write_exact(VgPlatformChannel *channel, const uint8_t *source,
                                    uint64_t size) {
    uint64_t completed;
    if (!vg_platform_channel_is_valid(channel) || (source == NULL && size != 0)) {
        return 0;
    } else {
        completed = 0;
        while (completed < size) {
            DWORD chunk = (DWORD)((size - completed) > 1048576ULL
                ? 1048576ULL : (size - completed));
            DWORD written = 0;
            BOOL result = WriteFile(vg_windows_handle(channel->handle), source + completed,
                                    chunk, &written, NULL);
            if (!result || written == 0) {
                return 0;
            } else {
                completed += written;
            }
        }
        return 1;
    }
}

void vg_platform_channel_close(VgPlatformChannel *channel) {
    if (vg_platform_channel_is_valid(channel)) {
        CloseHandle(vg_windows_handle(channel->handle));
        channel->handle = -1;
    } else if (channel != NULL) {
        channel->handle = -1;
    } else {
        return;
    }
}

void vg_platform_file_initialize(VgPlatformFile *file) {
    if (file != NULL) {
        memset(file, 0, sizeof(*file));
        file->handle = -1;
    } else {
        return;
    }
}

int vg_platform_file_is_valid(const VgPlatformFile *file) {
    if (file == NULL || file->handle == -1) {
        return 0;
    } else {
        return vg_windows_handle(file->handle) != INVALID_HANDLE_VALUE;
    }
}

int vg_platform_verify_file(const char *path, uint64_t expected_size,
                            const uint8_t *expected_sha256, uint8_t actual_sha256[32],
                            VgPlatformFile *retained_file) {
    wchar_t wide_path[32768];
    HANDLE handle;
    LARGE_INTEGER file_size;
    VgPlatformSha256 hash_context;
    uint8_t *buffer;
    int valid;
    if (path == NULL || actual_sha256 == NULL || !vg_windows_utf8_path(path, wide_path)) {
        return 0;
    } else {
        handle = CreateFileW(wide_path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                             FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    }
    if (handle == INVALID_HANDLE_VALUE || !GetFileSizeEx(handle, &file_size)
            || file_size.QuadPart < 0
            || (expected_size != 0 && (uint64_t)file_size.QuadPart != expected_size)) {
        if (handle != INVALID_HANDLE_VALUE) {
            CloseHandle(handle);
        } else {
            return 0;
        }
        return 0;
    } else {
        buffer = (uint8_t *)malloc(1048576U);
    }
    if (buffer == NULL) {
        CloseHandle(handle);
        return 0;
    } else {
        vg_platform_sha256_initialize(&hash_context);
        valid = 1;
    }
    while (valid) {
        DWORD received = 0;
        BOOL reading = ReadFile(handle, buffer, 1048576U, &received, NULL);
        if (!reading) {
            valid = 0;
        } else if (received == 0) {
            break;
        } else {
            valid = vg_platform_sha256_update(&hash_context, buffer, received);
        }
    }
    free(buffer);
    if (valid) {
        valid = vg_platform_sha256_finalize(&hash_context, actual_sha256);
    } else {
        valid = 0;
    }
    if (valid && expected_sha256 != NULL) {
        valid = memcmp(expected_sha256, actual_sha256, 32) == 0;
    } else {
        /* No caller-provided digest needs comparison. */
    }
    if (valid && retained_file != NULL) {
        vg_platform_file_initialize(retained_file);
        valid = vg_windows_file_identity(handle, &retained_file->identity);
        if (valid) {
            retained_file->handle = (intptr_t)(uintptr_t)handle;
        } else {
            CloseHandle(handle);
        }
    } else {
        CloseHandle(handle);
    }
    return valid;
}

void vg_platform_file_close(VgPlatformFile *file) {
    if (vg_platform_file_is_valid(file)) {
        CloseHandle(vg_windows_handle(file->handle));
        vg_platform_file_initialize(file);
    } else if (file != NULL) {
        vg_platform_file_initialize(file);
    } else {
        return;
    }
}

int vg_platform_executable_hash(uint8_t sha256[32]) {
    wchar_t wide_path[32768];
    char utf8_path[32768];
    DWORD wide_size;
    int utf8_size;
    if (sha256 == NULL) {
        return 0;
    } else {
        wide_size = GetModuleFileNameW(NULL, wide_path, 32768);
    }
    if (wide_size == 0 || wide_size >= 32768) {
        return 0;
    } else {
        utf8_size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide_path, -1,
                                       utf8_path, 32768, NULL, NULL);
    }
    if (utf8_size <= 0) {
        return 0;
    } else {
        return vg_platform_verify_file(utf8_path, 0, NULL, sha256, NULL);
    }
}
void vg_platform_library_initialize(VgPlatformLibrary *library) {
    if (library != NULL) {
        memset(library, 0, sizeof(*library));
    } else {
        return;
    }
}

int vg_platform_library_open(const char *path, const VgPlatformFile *verified_file,
                             VgPlatformLibrary *library) {
    wchar_t wide_path[32768];
    wchar_t loaded_path[32768];
    HMODULE handle;
    HANDLE loaded_file;
    VgPlatformFileIdentity loaded_identity;
    int valid;
    if (path == NULL || !vg_platform_file_is_valid(verified_file) || library == NULL
            || !vg_windows_utf8_path(path, wide_path)) {
        return 0;
    } else {
        vg_platform_library_initialize(library);
        handle = LoadLibraryW(wide_path);
    }
    if (handle == NULL || GetModuleFileNameW(handle, loaded_path, 32768) == 0) {
        if (handle != NULL) {
            FreeLibrary(handle);
        } else {
            return 0;
        }
        return 0;
    } else {
        loaded_file = CreateFileW(loaded_path, FILE_READ_ATTRIBUTES, FILE_SHARE_READ, NULL,
                                  OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    }
    valid = loaded_file != INVALID_HANDLE_VALUE
        && vg_windows_file_identity(loaded_file, &loaded_identity)
        && vg_platform_identity_equal(&verified_file->identity, &loaded_identity);
    if (loaded_file != INVALID_HANDLE_VALUE) {
        CloseHandle(loaded_file);
    } else {
        valid = 0;
    }
    if (valid) {
        library->handle = (uintptr_t)handle;
        library->identity = loaded_identity;
    } else {
        FreeLibrary(handle);
    }
    return valid;
}

void *vg_platform_library_symbol(const VgPlatformLibrary *library, const char *symbol_name) {
    if (library == NULL || library->handle == 0 || symbol_name == NULL) {
        return NULL;
    } else {
        return (void *)GetProcAddress((HMODULE)library->handle, symbol_name);
    }
}

void vg_platform_library_close(VgPlatformLibrary *library) {
    if (library != NULL && library->handle != 0) {
        FreeLibrary((HMODULE)library->handle);
        vg_platform_library_initialize(library);
    } else if (library != NULL) {
        vg_platform_library_initialize(library);
    } else {
        return;
    }
}
void vg_platform_capture_initialize(VgPlatformCapture *capture) {
    if (capture != NULL) {
        capture->original_output = -1;
        capture->original_error = -1;
        capture->output_file = -1;
        capture->error_file = -1;
    } else {
        return;
    }
}

int vg_platform_capture_open(VgPlatformCapture *capture) {
    wchar_t temporary_directory[MAX_PATH];
    wchar_t output_path[MAX_PATH];
    wchar_t error_path[MAX_PATH];
    DWORD directory_size;
    HANDLE output_file;
    HANDLE error_file;
    if (capture == NULL) {
        return 0;
    } else {
        vg_platform_capture_initialize(capture);
        directory_size = GetTempPathW(MAX_PATH, temporary_directory);
    }
    if (directory_size == 0 || directory_size >= MAX_PATH
            || GetTempFileNameW(temporary_directory, L"vgx", 0, output_path) == 0
            || GetTempFileNameW(temporary_directory, L"vgx", 0, error_path) == 0) {
        return 0;
    } else {
        output_file = CreateFileW(output_path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
            FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, NULL);
        error_file = CreateFileW(error_path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
            FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, NULL);
    }
    DeleteFileW(output_path);
    DeleteFileW(error_path);
    if (output_file == INVALID_HANDLE_VALUE || error_file == INVALID_HANDLE_VALUE) {
        if (output_file != INVALID_HANDLE_VALUE) {
            CloseHandle(output_file);
        } else {
            output_file = INVALID_HANDLE_VALUE;
        }
        if (error_file != INVALID_HANDLE_VALUE) {
            CloseHandle(error_file);
        } else {
            error_file = INVALID_HANDLE_VALUE;
        }
        return 0;
    } else {
        capture->original_output = (intptr_t)(uintptr_t)GetStdHandle(STD_OUTPUT_HANDLE);
        capture->original_error = (intptr_t)(uintptr_t)GetStdHandle(STD_ERROR_HANDLE);
        capture->output_file = (intptr_t)(uintptr_t)output_file;
        capture->error_file = (intptr_t)(uintptr_t)error_file;
    }
    if (!SetStdHandle(STD_OUTPUT_HANDLE, output_file)
            || !SetStdHandle(STD_ERROR_HANDLE, error_file)) {
        vg_platform_capture_close(capture);
        return 0;
    } else {
        return 1;
    }
}

int vg_platform_capture_finish(VgPlatformCapture *capture, uint64_t maximum_size,
                               uint8_t **output_bytes, uint64_t *output_size,
                               uint8_t **error_bytes, uint64_t *error_size,
                               uint8_t *output_truncated, uint8_t *error_truncated) {
    HANDLE files[2];
    uint8_t **targets[2];
    uint64_t *sizes[2];
    uint8_t *truncations[2];
    uint32_t index;
    if (capture == NULL || capture->output_file == -1 || capture->error_file == -1
            || output_bytes == NULL || output_size == NULL || error_bytes == NULL
            || error_size == NULL || output_truncated == NULL || error_truncated == NULL) {
        return 0;
    } else {
        fflush(NULL);
    }
    if (!FlushFileBuffers(vg_windows_handle(capture->output_file))
            || !FlushFileBuffers(vg_windows_handle(capture->error_file))
            || !SetStdHandle(STD_OUTPUT_HANDLE, vg_windows_handle(capture->original_output))
            || !SetStdHandle(STD_ERROR_HANDLE, vg_windows_handle(capture->original_error))) {
        return 0;
    } else {
        files[0] = vg_windows_handle(capture->output_file);
        files[1] = vg_windows_handle(capture->error_file);
        targets[0] = output_bytes;
        targets[1] = error_bytes;
        sizes[0] = output_size;
        sizes[1] = error_size;
        truncations[0] = output_truncated;
        truncations[1] = error_truncated;
    }
    for (index = 0; index < 2U; ++index) {
        LARGE_INTEGER length;
        LARGE_INTEGER beginning;
        uint64_t retained_size;
        DWORD received;
        beginning.QuadPart = 0;
        if (!GetFileSizeEx(files[index], &length) || length.QuadPart < 0
                || !SetFilePointerEx(files[index], beginning, NULL, FILE_BEGIN)) {
            return 0;
        } else {
            retained_size = (uint64_t)length.QuadPart;
        }
        if (retained_size > maximum_size) {
            retained_size = maximum_size;
            *truncations[index] = 1;
        } else {
            *truncations[index] = 0;
        }
        *targets[index] = (uint8_t *)malloc((size_t)(retained_size == 0 ? 1 : retained_size));
        if (*targets[index] == NULL) {
            return 0;
        } else {
            *sizes[index] = 0;
        }
        while (*sizes[index] < retained_size) {
            DWORD capacity = (DWORD)((retained_size - *sizes[index]) > 1048576ULL
                ? 1048576ULL : (retained_size - *sizes[index]));
            received = 0;
            if (!ReadFile(files[index], *targets[index] + *sizes[index], capacity,
                          &received, NULL) || received == 0) {
                return 0;
            } else {
                *sizes[index] += received;
            }
        }
    }
    return 1;
}

void vg_platform_capture_close(VgPlatformCapture *capture) {
    if (capture != NULL) {
        if (capture->output_file != -1) {
            CloseHandle(vg_windows_handle(capture->output_file));
        } else {
            capture->output_file = -1;
        }
        if (capture->error_file != -1) {
            CloseHandle(vg_windows_handle(capture->error_file));
        } else {
            capture->error_file = -1;
        }
        vg_platform_capture_initialize(capture);
    } else {
        return;
    }
}
static int vg_windows_file_identity_and_path(HANDLE handle,
                                             VgPlatformFileIdentity *identity,
                                             wchar_t *final_path,
                                             uint32_t final_path_count) {
    DWORD path_size;
    if (!vg_windows_file_identity(handle, identity)
            || (final_path == NULL && final_path_count != 0)
            || (final_path != NULL && final_path_count == 0)) {
        return 0;
    } else if (final_path == NULL) {
        return 1;
    } else {
        path_size = GetFinalPathNameByHandleW(
            handle, final_path, final_path_count, FILE_NAME_NORMALIZED
        );
        return path_size > 0 && path_size < final_path_count;
    }
}

static int vg_platform_module_is_baseline(const VgPlatformModuleGuard *guard,
                                          const VgPlatformFileIdentity *identity) {
    uint32_t index;
    int found;
    if (guard == NULL || identity == NULL) {
        return 0;
    } else {
        index = 0;
        found = 0;
    }
    while (index < guard->baseline_count && !found) {
        found = vg_platform_identity_equal(&guard->baseline[index], identity);
        index += 1;
    }
    return found;
}

void vg_platform_module_guard_initialize(VgPlatformModuleGuard *guard) {
    if (guard != NULL) {
        memset(guard, 0, sizeof(*guard));
    } else {
        return;
    }
}

int vg_platform_module_guard_begin(VgPlatformModuleGuard *guard,
                                   uint64_t maximum_observations,
                                   const char *system_directory,
                                   const VgPlatformFileIdentity *expected_system_identity) {
    wchar_t wide_system_directory[32768];
    wchar_t canonical_system_directory[32768];
    HANDLE system_handle;
    HANDLE snapshot;
    MODULEENTRY32W entry;
    BOOL reading;
    DWORD enumeration_error;
    if (guard == NULL || maximum_observations == 0 || system_directory == NULL
            || expected_system_identity == NULL
            || !vg_windows_utf8_path(system_directory, wide_system_directory)) {
        return 0;
    } else {
        vg_platform_module_guard_initialize(guard);
        guard->maximum_observations = maximum_observations;
        guard->baseline_capacity = 4096U;
        guard->baseline = (VgPlatformFileIdentity *)calloc(
            guard->baseline_capacity, sizeof(VgPlatformFileIdentity)
        );
    }
    if (guard->baseline == NULL) {
        return 0;
    } else {
        system_handle = CreateFileW(
            wide_system_directory, FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL
        );
    }
    if (system_handle == INVALID_HANDLE_VALUE
            || !vg_windows_file_identity_and_path(
                system_handle, &guard->system_directory,
                canonical_system_directory, 32768U
            )) {
        if (system_handle != INVALID_HANDLE_VALUE) {
            CloseHandle(system_handle);
        } else {
            system_handle = INVALID_HANDLE_VALUE;
        }
        vg_platform_module_guard_close(guard);
        return 0;
    } else {
        CloseHandle(system_handle);
    }
    if (!vg_platform_identity_equal(
            &guard->system_directory, expected_system_identity
        ) || _wcsicmp(canonical_system_directory, wide_system_directory) != 0) {
        vg_platform_module_guard_close(guard);
        return 0;
    } else {
        guard->observation_count = 1;
    }
    if (guard->observation_count > guard->maximum_observations) {
        vg_platform_module_guard_close(guard);
        return 0;
    } else {
        snapshot = CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId()
        );
    }
    if (snapshot == INVALID_HANDLE_VALUE) {
        vg_platform_module_guard_close(guard);
        return 0;
    } else {
        memset(&entry, 0, sizeof(entry));
        entry.dwSize = sizeof(entry);
        reading = Module32FirstW(snapshot, &entry);
    }
    while (reading) {
        HANDLE module_file;
        if (guard->baseline_count >= guard->baseline_capacity) {
            CloseHandle(snapshot);
            vg_platform_module_guard_close(guard);
            return 0;
        } else {
            module_file = CreateFileW(
                entry.szExePath, FILE_READ_ATTRIBUTES,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                NULL, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, NULL
            );
        }
        if (module_file == INVALID_HANDLE_VALUE
                || !vg_windows_file_identity(
                    module_file, &guard->baseline[guard->baseline_count]
                )) {
            if (module_file != INVALID_HANDLE_VALUE) {
                CloseHandle(module_file);
            } else {
                module_file = INVALID_HANDLE_VALUE;
            }
            CloseHandle(snapshot);
            vg_platform_module_guard_close(guard);
            return 0;
        } else {
            CloseHandle(module_file);
            guard->baseline_count += 1;
            reading = Module32NextW(snapshot, &entry);
        }
    }
    enumeration_error = GetLastError();
    CloseHandle(snapshot);
    return enumeration_error == ERROR_NO_MORE_FILES;
}

int vg_platform_module_guard_validate(VgPlatformModuleGuard *guard,
                                      const VgPlatformFile *staged_library,
                                      const char *system_directory) {
    wchar_t wide_system_directory[32768];
    size_t system_length;
    HANDLE snapshot;
    MODULEENTRY32W entry;
    BOOL reading;
    DWORD enumeration_error;
    if (guard == NULL || guard->baseline == NULL
            || !vg_platform_file_is_valid(staged_library)
            || system_directory == NULL
            || !vg_windows_utf8_path(system_directory, wide_system_directory)
            || guard->observation_count == UINT64_MAX) {
        return 0;
    } else {
        guard->observation_count += 1;
        system_length = wcslen(wide_system_directory);
    }
    if (guard->observation_count > guard->maximum_observations) {
        return 0;
    } else {
        snapshot = CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId()
        );
    }
    if (snapshot == INVALID_HANDLE_VALUE) {
        return 0;
    } else {
        memset(&entry, 0, sizeof(entry));
        entry.dwSize = sizeof(entry);
        reading = Module32FirstW(snapshot, &entry);
    }
    while (reading) {
        HANDLE module_file;
        VgPlatformFileIdentity identity;
        wchar_t canonical_path[32768];
        int approved;
        module_file = CreateFileW(
            entry.szExePath, FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            NULL, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, NULL
        );
        if (module_file == INVALID_HANDLE_VALUE
                || !vg_windows_file_identity_and_path(
                    module_file, &identity, canonical_path, 32768U
                )) {
            if (module_file != INVALID_HANDLE_VALUE) {
                CloseHandle(module_file);
            } else {
                module_file = INVALID_HANDLE_VALUE;
            }
            CloseHandle(snapshot);
            return 0;
        } else {
            CloseHandle(module_file);
        }
        approved = vg_platform_module_is_baseline(guard, &identity)
            || vg_platform_identity_equal(&staged_library->identity, &identity);
        if (!approved) {
            approved = _wcsnicmp(
                canonical_path, wide_system_directory, system_length
            ) == 0 && canonical_path[system_length] == L'\\';
        } else {
            approved = 1;
        }
        if (!approved) {
            CloseHandle(snapshot);
            return 0;
        } else {
            reading = Module32NextW(snapshot, &entry);
        }
    }
    enumeration_error = GetLastError();
    CloseHandle(snapshot);
    return enumeration_error == ERROR_NO_MORE_FILES;
}

void vg_platform_module_guard_close(VgPlatformModuleGuard *guard) {
    if (guard != NULL) {
        free(guard->baseline);
        vg_platform_module_guard_initialize(guard);
    } else {
        return;
    }
}

const char *vg_platform_runtime_library_name(void) {
    return "kernel32.dll";
}