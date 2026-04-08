#!/bin/bash
# Shared cleanup helpers for Safeguard run_*.sh scripts.
# Sourced from each run script — never executed directly.
#
# Provides:
#   kill_stale  — kill processes matching pgrep patterns (idempotent, no prompt)
#   assert_ports_clear — abort if listed ports are still held after cleanup
#
# Why a shared helper: every Safeguard run script needs the same behavior:
# (1) sweep stale processes from prior runs that orphaned across SSH/iTerm
# sessions, (2) refuse to silently kill non-Safeguard processes that happen
# to be holding the same ports. Inlining this in each script drifted out of
# sync. One source of truth here.

# Usage:
#   kill_stale "label" "pgrep pattern 1" "pgrep pattern 2" ...
#
# Args:
#   $1     = human label for log output ("validator", "demo client", etc.)
#   $2..$N = pgrep -f patterns to match against process command lines
#
# Behavior:
#   1. Collects unique PIDs matching ANY of the patterns
#   2. Skips this script's own PID (so a script doesn't kill itself)
#   3. Logs each victim with its truncated command line
#   4. SIGTERM, sleep 1, then SIGKILL any stragglers, sleep 1
#   5. No-op (silent) if nothing matches
kill_stale() {
    local label="$1"; shift
    local self_pid=$$
    local pids=""
    for pat in "$@"; do
        pids="$pids $(pgrep -f "$pat" 2>/dev/null || true)"
    done
    # Dedupe, drop blanks, drop our own PID
    pids=$(
        echo "$pids" | tr ' ' '\n' | sort -u | grep -v '^$' \
            | grep -v "^${self_pid}$" || true
    )
    if [ -z "$pids" ]; then
        return 0
    fi

    echo "Killing stale $label process(es):"
    for pid in $pids; do
        cmd=$(ps -p "$pid" -o command= 2>/dev/null | head -c 100 || echo "(unknown)")
        echo "  PID $pid  $cmd"
        kill "$pid" 2>/dev/null || true
    done
    sleep 1
    # Force-kill anything that didn't die gracefully
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    sleep 1
}

# Usage:
#   assert_ports_clear 9090 8080 ...
#
# Behavior:
#   - For each port, lsof to find any holders
#   - If anything is still holding a port, print the offenders and exit 1
#   - Caller is expected to have run kill_stale first; this is a backstop
#     for non-Safeguard processes that happen to be on the same ports
#   - Never silently kills unknown processes
assert_ports_clear() {
    local stuck=""
    for port in "$@"; do
        local pids
        pids=$(lsof -ti ":$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            stuck="$stuck $port"
        fi
    done
    if [ -z "$stuck" ]; then
        return 0
    fi

    echo "ERROR: port(s) still held by non-Safeguard process(es):"
    for port in $stuck; do
        local pids
        pids=$(lsof -ti ":$port" 2>/dev/null || true)
        echo "  port $port:"
        for pid in $pids; do
            cmd=$(ps -p "$pid" -o command= 2>/dev/null | head -c 100 || echo "(unknown)")
            echo "    PID $pid  $cmd"
        done
    done
    echo ""
    echo "Free the port(s) manually and re-run."
    exit 1
}
