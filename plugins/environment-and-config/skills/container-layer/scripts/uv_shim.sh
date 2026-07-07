#!/bin/bash
# uv shim — wraps the real uv binary, captures pip install commands
# to a Containerfile for reproducibility.
#
# Usage:
#   source /path/to/uv_shim.sh /path/to/Containerfile
#
# After sourcing, `uv pip install foo` will:
#   1. Run the real uv pip install foo
#   2. Append `RUN uv pip install foo` to the Containerfile
#
# To bypass the shim: use the full path to uv directly.

_CONTAINERFILE="${1:-}"
_REAL_UV="$(which uv 2>/dev/null)"

if [ -z "$_REAL_UV" ]; then
    echo "uv_shim: ERROR — uv not found in PATH" >&2
    return 1 2>/dev/null || exit 1
fi

if [ -z "$_CONTAINERFILE" ]; then
    echo "uv_shim: ERROR — must specify Containerfile path" >&2
    echo "  Usage: source uv_shim.sh /path/to/Containerfile" >&2
    return 1 2>/dev/null || exit 1
fi

uv() {
    # Pass through to real uv
    "$_REAL_UV" "$@"
    local exit_code=$?
    
    # If it was a successful pip install, capture it
    if [ $exit_code -eq 0 ]; then
        # Check if this is a pip install command
        local is_pip_install=0
        local args_after_install=""
        local seen_pip=0
        local seen_install=0
        
        for arg in "$@"; do
            if [ "$seen_install" -eq 1 ]; then
                # Skip flags like --system, --break-system-packages
                case "$arg" in
                    --system|--break-system-packages|--quiet|-q)
                        ;;
                    *)
                        args_after_install="$args_after_install $arg"
                        ;;
                esac
            fi
            [ "$arg" = "pip" ] && seen_pip=1
            [ "$seen_pip" -eq 1 ] && [ "$arg" = "install" ] && seen_install=1 && is_pip_install=1
        done
        
        if [ "$is_pip_install" -eq 1 ] && [ -n "$args_after_install" ]; then
            local install_line="RUN uv pip install --system$args_after_install"
            
            # Check if this line already exists in the Containerfile
            if [ -f "$_CONTAINERFILE" ]; then
                if ! grep -qF "$install_line" "$_CONTAINERFILE"; then
                    echo "$install_line" >> "$_CONTAINERFILE"
                    echo "uv_shim: captured → $install_line" >&2
                fi
            else
                echo "$install_line" >> "$_CONTAINERFILE"
                echo "uv_shim: created Containerfile with → $install_line" >&2
            fi
        fi
    fi
    
    return $exit_code
}

echo "uv_shim: active — installs will be captured to $_CONTAINERFILE"
