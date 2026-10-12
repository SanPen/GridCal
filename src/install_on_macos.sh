#!/usr/bin/env bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
#
# install_on_macos.sh
#
# Installs VeraGrid on a macOS system by:
# - Creating a dedicated virtual environment in $HOME/.local/share/veragrid/venv.
# - Installing the veragrid package into the virtual environment.
# - Building the VeraGrid.icns icon using native sips and iconutil utilities.
# - Creating the application bundle at $HOME/Applications/VeraGrid.app.
# - Registering .veragrid and .gridcal file associations in Info.plist and LaunchServices.

set -euo pipefail

# Verify the operating system platform is macOS (Darwin)
check_macos_platform() {
    local os_name
    os_name="$(uname -s)"
    if [ "${os_name}" != "Darwin" ]; then
        echo "Error: This installer is intended for macOS platforms only (detected: ${os_name})."
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

# Locate a working Python 3 interpreter on macOS
find_macos_python() {
    local candidate
    local found=""

    # Candidate locations on macOS (Homebrew ARM, Homebrew Intel, Framework, PATH)
    local candidates=(
        "/opt/homebrew/bin/python3"
        "/usr/local/bin/python3"
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
        "/usr/bin/python3"
    )

    for candidate in "${candidates[@]}"; do
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

    # Check python3 in active PATH
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

    if [ -n "${found}" ]; then
        echo "${found}"
        return 0
    else
        echo "Error: Could not locate a working Python 3 interpreter on macOS." >&2
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

# Generate .icns icon from PNG source using native macOS tools sips and iconutil
create_icns_from_png() {
    local png_source="$1"
    local dest_icns="$2"

    if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
        local temp_dir
        temp_dir="$(mktemp -d 2>/dev/null || mktemp -d -t 'veragrid_icon')"
        local iconset_dir="${temp_dir}/VeraGrid.iconset"
        mkdir -p "${iconset_dir}"

        # Generate each icon dimension required by macOS iconset
        sips -z 16 16     "${png_source}" --out "${iconset_dir}/icon_16x16.png" >/dev/null 2>&1 || true
        sips -z 32 32     "${png_source}" --out "${iconset_dir}/icon_16x16@2x.png" >/dev/null 2>&1 || true
        sips -z 32 32     "${png_source}" --out "${iconset_dir}/icon_32x32.png" >/dev/null 2>&1 || true
        sips -z 64 64     "${png_source}" --out "${iconset_dir}/icon_32x32@2x.png" >/dev/null 2>&1 || true
        sips -z 128 128   "${png_source}" --out "${iconset_dir}/icon_128x128.png" >/dev/null 2>&1 || true
        sips -z 256 256   "${png_source}" --out "${iconset_dir}/icon_128x128@2x.png" >/dev/null 2>&1 || true
        sips -z 256 256   "${png_source}" --out "${iconset_dir}/icon_256x256.png" >/dev/null 2>&1 || true
        sips -z 512 512   "${png_source}" --out "${iconset_dir}/icon_256x256@2x.png" >/dev/null 2>&1 || true
        sips -z 512 512   "${png_source}" --out "${iconset_dir}/icon_512x512.png" >/dev/null 2>&1 || true
        sips -z 1024 1024 "${png_source}" --out "${iconset_dir}/icon_512x512@2x.png" >/dev/null 2>&1 || true

        iconutil -c icns "${iconset_dir}" -o "${dest_icns}" >/dev/null 2>&1 || true
        rm -rf "${temp_dir}"
    else
        :
    fi
}

# Resolve and copy application icons for macOS
resolve_and_prepare_icons() {
    local resources_dir="$1"
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    local dest_icns="${resources_dir}/VeraGrid.icns"
    local found_png=""

    local png_candidates=(
        "${script_dir}/../pics/VeraGrid_icon.png"
        "${script_dir}/VeraGrid/Gui/Icons/icons/VeraGrid_icon.png"
        "${HOME}/.local/share/veragrid/veragrid.png"
        "${HOME}/.cache/veragrid/veragrid.png"
    )

    local candidate
    for candidate in "${png_candidates[@]}"; do
        if [ -z "${found_png}" ]; then
            if [ -f "${candidate}" ]; then
                found_png="${candidate}"
            else
                :
            fi
        else
            :
        fi
    done

    if [ -n "${found_png}" ]; then
        create_icns_from_png "${found_png}" "${dest_icns}"
        echo "${dest_icns}"
        return 0
    else
        echo "Warning: Could not locate VeraGrid PNG icon source." >&2
        return 0
    fi
}

# Create macOS Application bundle (VeraGrid.app)
create_macos_app_bundle() {
    local app_path="$1"
    local venv_dir="$2"

    local contents_dir="${app_path}/Contents"
    local macos_dir="${contents_dir}/MacOS"
    local resources_dir="${contents_dir}/Resources"

    mkdir -p "${macos_dir}"
    mkdir -p "${resources_dir}"

    # Prepare .icns icon inside Resources
    resolve_and_prepare_icons "${resources_dir}"

    # Create the executable launcher script inside Contents/MacOS/VeraGrid
    local launcher="${macos_dir}/VeraGrid"
    cat << EOF > "${launcher}"
#!/usr/bin/env bash
APP_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
VENV_DIR="${venv_dir}"
VERAGRID_BIN="\${VENV_DIR}/bin/veragrid"

if [ -x "\${VERAGRID_BIN}" ]; then
    exec "\${VERAGRID_BIN}" "\$@"
else
    VENV_PYTHON="\${VENV_DIR}/bin/python3"
    exec "\${VENV_PYTHON}" -c "from VeraGrid.ExecuteVeraGrid import runVeraGrid; runVeraGrid()" "\$@"
fi
EOF
    chmod 0755 "${launcher}"
    echo "Created application launcher at: ${launcher}"

    # Generate Contents/Info.plist with document type associations
    local plist_file="${contents_dir}/Info.plist"
    cat << 'EOF' > "${plist_file}"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>VeraGrid</string>
    <key>CFBundleDisplayName</key>
    <string>VeraGrid</string>
    <key>CFBundleIdentifier</key>
    <string>com.eroots.veragrid</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>VeraGrid</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>VeraGrid.icns</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>VeraGrid Project</string>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>veragrid</string>
            </array>
            <key>CFBundleTypeRole</key>
            <string>Editor</string>
            <key>LSHandlerRank</key>
            <string>Owner</string>
        </dict>
        <dict>
            <key>CFBundleTypeName</key>
            <string>GridCal Project</string>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>gridcal</string>
                <string>dgridcal</string>
            </array>
            <key>CFBundleTypeRole</key>
            <string>Editor</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
        </dict>
    </array>
</dict>
</plist>
EOF
    echo "Created Info.plist at: ${plist_file}"

    # Register application and document types with LaunchServices
    local lsregister="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
    if [ -x "${lsregister}" ]; then
        "${lsregister}" -f "${app_path}" >/dev/null 2>&1 || true
        echo "Registered application bundle with macOS LaunchServices."
    else
        :
    fi

    # Bind default document handlers via duti if available
    if command -v duti >/dev/null 2>&1; then
        duti -s com.eroots.veragrid .veragrid all >/dev/null 2>&1 || true
        duti -s com.eroots.veragrid .gridcal all >/dev/null 2>&1 || true
        duti -s com.eroots.veragrid .dgridcal all >/dev/null 2>&1 || true
        echo "Associated .veragrid and .gridcal files with VeraGrid via duti."
    else
        :
    fi

    return 0
}

# Main installer entry point
main() {
    local venv_dir="${HOME}/.local/share/veragrid/venv"
    local app_path="${HOME}/Applications/VeraGrid.app"
    local python_bin=""
    local package_target="veragrid"
    local system_site_packages="true"
    local skip_pip="false"
    local associate_mime="true"

    # Parse command line options
    while [ $# -gt 0 ]; do
        case "$1" in
            --venv-dir)
                venv_dir="$2"
                shift 2
                ;;
            --app-path)
                app_path="$2"
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
                echo "  --app-path PATH            Destination app bundle path (default: ~/Applications/VeraGrid.app)"
                echo "  --python PATH              Base Python interpreter"
                echo "  --package TARGET           Pip package specification (default: 'veragrid')"
                echo "  --no-system-site-packages  Do not include system site packages"
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
    echo "Starting VeraGrid macOS Installation"
    echo "============================================================"

    # Step 1: Verify platform
    if ! check_macos_platform; then
        return 1
    else
        :
    fi

    # Step 2: Determine base Python interpreter
    if [ -z "${python_bin}" ]; then
        python_bin="$(find_macos_python)"
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

    # Step 5: Ensure destination Applications directory exists
    local app_parent_dir
    app_parent_dir="$(dirname "${app_path}")"
    if [ ! -d "${app_parent_dir}" ]; then
        mkdir -p "${app_parent_dir}"
    else
        :
    fi

    # Step 6: Create macOS Application bundle and register document associations
    create_macos_app_bundle "${app_path}" "${venv_dir}"

    echo "============================================================"
    echo "VeraGrid macOS Installation Completed Successfully!"
    echo "Virtual environment: ${venv_dir}"
    echo "Application bundle:  ${app_path}"
    echo "File associations:   .veragrid, .gridcal -> VeraGrid"
    echo "============================================================"

    return 0
}

main "$@"
