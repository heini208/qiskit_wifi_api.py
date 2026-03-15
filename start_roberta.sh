#!/bin/bash
#v2
set -euo pipefail

ROBERTA_DIR="/home/pi/roberta/openroberta-lab"
QISKIT_DIR="/home/pi/roberta/qiskit_wifi_api.py"
VENV_ACTIVATE="/home/pi/roberta/qiskit_wifi_api.py/.venv/bin/activate"
QISKIT_APP="/home/pi/roberta/qiskit_wifi_api.py/qiskit_wifi_api.py"

PGIDFILE="/tmp/roberta_qiskit_terminals.pgids"

kill_previous() {
  if [[ -f "$PGIDFILE" ]]; then
    echo "Checking for previous instances..."
    while IFS= read -r pgid; do
      [[ -z "${pgid:-}" ]] && continue
      # Check if the process group exists
      if kill -0 "-$pgid" 2>/dev/null; then
        echo "Stopping previous instance (pgid=$pgid)..."
        kill "-$pgid" 2>/dev/null || true
      fi
    done < "$PGIDFILE"

    sleep 1

    while IFS= read -r pgid; do
      [[ -z "${pgid:-}" ]] && continue
      if kill -0 "-$pgid" 2>/dev/null; then
        echo "Force stopping (pgid=$pgid)..."
        kill -KILL "-$pgid" 2>/dev/null || true
      fi
    done < "$PGIDFILE"

    rm -f "$PGIDFILE"
  fi
}

start_terminal() {
  local workdir="$1"
  local cmd="$2"

  setsid lxterminal --working-directory="$workdir" \
    --command "bash -lc \"echo \$\$ >> '$PGIDFILE'; $cmd; exec bash\"" \
    >/dev/null 2>&1 &
}

kill_previous

start_terminal "$ROBERTA_DIR" "./ora.sh start-from-git"
sleep 1
start_terminal "$QISKIT_DIR" "source '$VENV_ACTIVATE'; python '$QISKIT_APP'"

echo "Started. Terminals are recording their PIDs to $PGIDFILE."