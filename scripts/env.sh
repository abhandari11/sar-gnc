# Source me:  source scripts/env.sh
# Isolates this shell from ROS/PX4/colcon state, then activates the project venv.
# Affects only the current shell; no global config is touched.

_SARGNC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"

unset PYTHONPATH PYTHONHOME PYTHONSTARTUP
unset AMENT_PREFIX_PATH AMENT_CURRENT_PREFIX COLCON_PREFIX_PATH CMAKE_PREFIX_PATH
unset ACADOS_SOURCE_DIR LD_LIBRARY_PATH
for _v in $(env | grep -oE '^(ROS|RMW|PX4|GZ|GAZEBO|IGN|FASTRTPS|CYCLONEDDS|COLCON|AMENT)[A-Za-z0-9_]*' ); do
  unset "$_v"
done
unset _v

# Drop ROS / workspace entries from PATH.
PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vE '/opt/ros|ros2_workspace|px4_ws|acados' | paste -sd: -)"
export PATH

# Keep every cache inside the project tree; ignore ~/.local site-packages.
export PYTHONNOUSERSITE=1
export MPLBACKEND=Agg
export MPLCONFIGDIR="$_SARGNC_ROOT/.cache/matplotlib"
export NUMBA_CACHE_DIR="$_SARGNC_ROOT/.cache/numba"
export NUMBA_THREADING_LAYER=omp
export PIP_CACHE_DIR="$_SARGNC_ROOT/.cache/pip"
export XDG_CACHE_HOME="$_SARGNC_ROOT/.cache"
export TMPDIR="$_SARGNC_ROOT/.cache/tmp"; mkdir -p "$TMPDIR"
export GH_CONFIG_DIR="$_SARGNC_ROOT/.gh"
export BROWSER_PATH="$_SARGNC_ROOT/.cache/chrome/chrome-linux64/chrome"  # kaleido static export
export SARGNC_ROOT="$_SARGNC_ROOT"

if [ -f "$_SARGNC_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$_SARGNC_ROOT/.venv/bin/activate"
else
  echo "sar-gnc: no venv yet; create it with: python3 -m venv $_SARGNC_ROOT/.venv" >&2
fi
unset _SARGNC_ROOT
