#!/usr/bin/env bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
#
# install_on_linux.sh
#
# Installs VeraGrid on a Linux desktop system by:
# - Creating a dedicated virtual environment in $HOME (under ~/.local/share/veragrid/venv).
# - Installing the veragrid package into the virtual environment.
# - Installing the application icon into ~/.local/share/veragrid/ and standard icon directories.
# - Creating the desktop entry at $HOME/.local/share/applications/veragrid.desktop.
# - Associating .veragrid and .gridcal files with VeraGrid via shared-mime-info and xdg-mime.
# - Registering the desktop entry using update-desktop-database.

set -euo pipefail

# Check if the operating system platform is Linux
check_linux_platform() {
    local os_name
    os_name="$(uname -s)"
    if [ "${os_name}" != "Linux" ]; then
        echo "Error: This installer is intended for Linux platforms only (detected: ${os_name})."
        return 1
    else
        return 0
    fi
}

# Test whether a Python executable candidate can invoke venv and ensurepip
test_python_candidate() {
    local candidate="$1"
    if [ -x "${candidate}" ]; then
        if "${candidate}" -c "import venv, ensurepip" >/dev/null 2>&1; then
            return 0
        else
            return 1
        fi
    else
        return 1
    fi
}

# Find a suitable system Python 3 interpreter
find_system_python() {
    local candidate
    local found=""

    # Check standard system paths first
    for candidate in "/usr/bin/python3" "/usr/local/bin/python3"; do
        if [ -z "${found}" ]; then
            if test_python_candidate "${candidate}"; then
                found="${candidate}"
            else
                :
            fi
        else
            :
        fi
    done

    # Check python3 in current PATH
    if [ -z "${found}" ]; then
        local which_python
        which_python="$(command -v python3 || true)"
        if [ -n "${which_python}" ]; then
            if test_python_candidate "${which_python}"; then
                found="${which_python}"
            else
                :
            fi
        else
            :
        fi
    else
        :
    fi

    # Check base python from existing environment if python314 or similar exists
    if [ -z "${found}" ]; then
        local user_python="${HOME}/python314/bin/python3"
        if test_python_candidate "${user_python}"; then
            found="${user_python}"
        else
            :
        fi
    else
        :
    fi

    if [ -n "${found}" ]; then
        echo "${found}"
        return 0
    else
        echo "Error: Could not locate a working system Python interpreter to create the virtual environment." >&2
        return 1
    fi
}

# Create or update virtual environment
create_virtual_environment() {
    local venv_dir="$1"
    local python_bin="$2"
    local system_site_packages="$3"

    local parent_dir
    parent_dir="$(dirname "${venv_dir}")"
    if [ ! -d "${parent_dir}" ]; then
        mkdir -p "${parent_dir}"
    else
        :
    fi

    echo "Creating virtual environment at: ${venv_dir}"
    echo "Using base Python interpreter: ${python_bin}"

    local venv_cmd=("${python_bin}" "-m" "venv")
    if [ "${system_site_packages}" = "true" ]; then
        venv_cmd+=("--system-site-packages")
    else
        :
    fi
    venv_cmd+=("${venv_dir}")

    "${venv_cmd[@]}"

    local venv_python="${venv_dir}/bin/python3"
    if [ -x "${venv_python}" ]; then
        echo "Virtual environment created successfully at: ${venv_dir}"
        return 0
    else
        echo "Error: Virtual environment python executable not found at: ${venv_python}" >&2
        return 1
    fi
}

# Install target package using pip inside the virtual environment
install_package_into_venv() {
    local venv_python="$1"
    local package_target="$2"

    echo "Upgrading pip in the virtual environment..."
    if "${venv_python}" -m pip install --upgrade pip; then
        echo "pip is up to date."
    else
        echo "Notice: pip upgrade did not complete successfully; continuing with package installation."
    fi

    echo "Installing '${package_target}' into the virtual environment..."
    if "${venv_python}" -m pip install --no-user --disable-pip-version-check "${package_target}"; then
        echo "Successfully installed '${package_target}' into the virtual environment."
        return 0
    else
        echo "Error: pip install failed for '${package_target}'." >&2
        return 1
    fi
}

# Locate and copy VeraGrid application icons
resolve_and_copy_icon() {
    local target_app_dir="$1"
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [ ! -d "${target_app_dir}" ]; then
        mkdir -p "${target_app_dir}"
    else
        :
    fi

    local dest_icon="${target_app_dir}/veragrid.png"
    local found_source=""

    # Candidate source icon paths
    local candidates=(
        "${script_dir}/../pics/VeraGrid_icon.png"
        "${script_dir}/VeraGrid/Gui/Icons/icons/VeraGrid_icon.png"
        "${HOME}/.cache/veragrid/veragrid.png"
        "${dest_icon}"
    )

    local candidate
    for candidate in "${candidates[@]}"; do
        if [ -z "${found_source}" ]; then
            if [ -f "${candidate}" ]; then
                found_source="${candidate}"
            else
                :
            fi
        else
            :
        fi
    done

    if [ -n "${found_source}" ]; then
        if [ "${found_source}" != "${dest_icon}" ]; then
            cp -f "${found_source}" "${dest_icon}"
        else
            :
        fi

        # Also copy to standard XDG hicolor icon theme apps directory
        local hicolor_app_dir="${HOME}/.local/share/icons/hicolor/256x256/apps"
        if [ ! -d "${hicolor_app_dir}" ]; then
            mkdir -p "${hicolor_app_dir}"
        else
            :
        fi
        cp -f "${dest_icon}" "${hicolor_app_dir}/veragrid.png"

        echo "${dest_icon}"
        return 0
    else
        echo "Warning: Could not locate VeraGrid icon file." >&2
        echo ""
        return 0
    fi
}

# Create desktop entry file
create_desktop_entry() {
    local desktop_file="$1"
    local venv_dir="$2"
    local icon_file="$3"
    local terminal_flag="$4"

    local parent_dir
    parent_dir="$(dirname "${desktop_file}")"
    if [ ! -d "${parent_dir}" ]; then
        mkdir -p "${parent_dir}"
    else
        :
    fi

    local veragrid_bin="${venv_dir}/bin/veragrid"
    local exec_cmd=""
    if [ -x "${veragrid_bin}" ]; then
        exec_cmd="${veragrid_bin} %F"
    else
        local venv_python="${venv_dir}/bin/python3"
        exec_cmd="${venv_python} -c \"from VeraGrid.ExecuteVeraGrid import runVeraGrid; runVeraGrid()\" %F"
    fi

    local terminal_str="true"
    if [ "${terminal_flag}" = "false" ]; then
        terminal_str="false"
    else
        terminal_str="true"
    fi

    local icon_str="veragrid"
    if [ -n "${icon_file}" ]; then
        icon_str="${icon_file}"
    else
        icon_str="veragrid"
    fi

    cat << EOF > "${desktop_file}"
[Desktop Entry]
Version=1.1
Type=Application
Name=VeraGrid
GenericName=Power Systems Simulator
Comment=Power Systems simulation program intended for professional use and research
Icon=${icon_str}
Exec=${exec_cmd}
Terminal=${terminal_str}
Actions=
MimeType=application/x-veragrid;application/x-gridcal;
Categories=Science;Engineering;
StartupNotify=true
StartupWMClass=veragrid
EOF

    chmod 0755 "${desktop_file}"
    echo "Created desktop entry at: ${desktop_file}"

    # Validate desktop file if desktop-file-validate is available
    if command -v desktop-file-validate >/dev/null 2>&1; then
        if desktop-file-validate "${desktop_file}"; then
            echo "Desktop entry validation passed successfully."
        else
            echo "Warning: Desktop file validation produced warnings." >&2
        fi
    else
        :
    fi

    # Update desktop database if update-desktop-database is available
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "${parent_dir}" >/dev/null 2>&1 || true
        echo "Updated desktop application database."
    else
        :
    fi

    return 0
}

# Register MIME types for .veragrid and .gridcal files
register_mime_types() {
    local icon_file="$1"

    local mime_packages_dir="${HOME}/.local/share/mime/packages"
    if [ ! -d "${mime_packages_dir}" ]; then
        mkdir -p "${mime_packages_dir}"
    else
        :
    fi

    local mime_file="${mime_packages_dir}/veragrid.xml"
    cat << 'EOF' > "${mime_file}"
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
    <mime-type type="application/x-veragrid">
        <comment>VeraGrid Project</comment>
        <glob pattern="*.veragrid" weight="65"/>
        <icon name="application-x-veragrid"/>
    </mime-type>
    <mime-type type="application/x-gridcal">
        <comment>GridCal Project</comment>
        <glob pattern="*.gridcal" weight="65"/>
        <glob pattern="*.dgridcal" weight="65"/>
        <icon name="application-x-gridcal"/>
    </mime-type>
</mime-info>
EOF
    echo "Created MIME type definition at: ${mime_file}"

    # Copy mime icon to standard hicolor mimetypes directory if icon is provided
    if [ -n "${icon_file}" ] && [ -f "${icon_file}" ]; then
        local mimetypes_icon_dir="${HOME}/.local/share/icons/hicolor/256x256/mimetypes"
        if [ ! -d "${mimetypes_icon_dir}" ]; then
            mkdir -p "${mimetypes_icon_dir}"
        else
            :
        fi
        cp -f "${icon_file}" "${mimetypes_icon_dir}/application-x-veragrid.png"
        cp -f "${icon_file}" "${mimetypes_icon_dir}/application-x-gridcal.png"
    else
        :
    fi

    # Update the user MIME database
    local mime_base_dir="${HOME}/.local/share/mime"
    if command -v update-mime-database >/dev/null 2>&1; then
        update-mime-database "${mime_base_dir}" >/dev/null 2>&1 || true
        echo "Updated user MIME database successfully."
    else
        :
    fi

    # Associate veragrid.desktop with MIME types using xdg-mime
    if command -v xdg-mime >/dev/null 2>&1; then
        local mime_type
        for mime_type in "application/x-veragrid" "application/x-gridcal"; do
            xdg-mime default veragrid.desktop "${mime_type}" >/dev/null 2>&1 || true
            echo "Associated ${mime_type} files with veragrid.desktop via xdg-mime."
        done
    else
        :
    fi

    return 0
}

# Main installation controller
main() {
    local venv_dir="${HOME}/.local/share/veragrid/venv"
    local desktop_file="${HOME}/.local/share/applications/veragrid.desktop"
    local python_bin=""
    local package_target="veragrid"
    local system_site_packages="true"
    local terminal="true"
    local skip_pip="false"
    local associate_mime="true"

    # Parse command line options
    while [ $# -gt 0 ]; do
        case "$1" in
            --venv-dir)
                venv_dir="$2"
                shift 2
                ;;
            --desktop-file)
                desktop_file="$2"
                shift 2
                ;;
            --python)
                python_bin="$2"
                shift 2
                ;;
            --package)
                package_target="$2"
                shift 2
                ;;
            --no-system-site-packages)
                system_site_packages="false"
                shift 1
                ;;
            --no-terminal)
                terminal="false"
                shift 1
                ;;
            --skip-pip)
                skip_pip="true"
                shift 1
                ;;
            --no-mime)
                associate_mime="false"
                shift 1
                ;;
            -h|--help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --venv-dir DIR             Virtual environment directory (default: ~/.local/share/veragrid/venv)"
                echo "  --desktop-file FILE        Desktop file destination (default: ~/.local/share/applications/veragrid.desktop)"
                echo "  --python PATH              Base Python interpreter"
                echo "  --package TARGET           Pip package specification (default: 'veragrid')"
                echo "  --no-system-site-packages  Do not include system site packages"
                echo "  --no-terminal              Set Terminal=false in the desktop entry"
                echo "  --skip-pip                 Skip pip package installation"
                echo "  --no-mime                  Skip .veragrid and .gridcal file association"
                echo "  -h, --help                 Show this help message"
                return 0
                ;;
            *)
                echo "Error: Unknown argument: $1" >&2
                return 1
                ;;
        esac
    done

    echo "============================================================"
    echo "Starting VeraGrid Linux Installation"
    echo "============================================================"

    # Step 1: Verify platform
    if ! check_linux_platform; then
        return 1
    else
        :
    fi

    # Step 2: Determine base Python interpreter
    if [ -z "${python_bin}" ]; then
        python_bin="$(find_system_python)"
        if [ -z "${python_bin}" ]; then
            return 1
        else
            :
        fi
    else
        if [ ! -x "${python_bin}" ]; then
            echo "Error: Specified Python interpreter does not exist or is not executable: ${python_bin}" >&2
            return 1
        else
            :
        fi
    fi

    # Step 3: Create virtual environment
    if ! create_virtual_environment "${venv_dir}" "${python_bin}" "${system_site_packages}"; then
        return 2
    else
        :
    fi

    # Step 4: Install package via pip unless skipped
    if [ "${skip_pip}" != "true" ]; then
        local venv_python="${venv_dir}/bin/python3"
        if ! install_package_into_venv "${venv_python}" "${package_target}"; then
            echo "Warning: Package installation via pip reported an error." >&2
        else
            :
        fi
    else
        echo "Skipping pip package installation as requested."
    fi

    # Step 5: Resolve and install icon
    local target_app_dir
    target_app_dir="$(dirname "${venv_dir}")"
    local icon_file
    icon_file="$(resolve_and_copy_icon "${target_app_dir}")"

    # Step 6: Create desktop entry
    if ! create_desktop_entry "${desktop_file}" "${venv_dir}" "${icon_file}" "${terminal}"; then
        echo "Error: Failed to create desktop entry." >&2
        return 3
    else
        :
    fi

    # Step 7: Register file associations
    if [ "${associate_mime}" = "true" ]; then
        register_mime_types "${icon_file}"
        echo "Registered .veragrid and .gridcal file associations successfully."
    else
        echo "Skipping MIME type registration as requested."
    fi

    echo "============================================================"
    echo "VeraGrid Linux Installation Completed Successfully!"
    echo "Virtual environment: ${venv_dir}"
    echo "Desktop entry:       ${desktop_file}"
    if [ -n "${icon_file}" ]; then
        echo "Application icon:    ${icon_file}"
    else
        :
    fi
    echo "File associations:   .veragrid, .gridcal -> VeraGrid"
    echo "============================================================"

    return 0
}

main "$@"
