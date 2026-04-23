#!/usr/bin/env bash

collect_descendants() {
  local pid="${1:-}"
  local child=""

  if [[ -z "$pid" ]]; then
    return 0
  fi

  while IFS= read -r child; do
    [[ -z "$child" ]] && continue
    printf '%s\n' "$child"
    collect_descendants "$child"
  done < <(pgrep -P "$pid" || true)
}

collect_process_targets() {
  local pid="${1:-}"

  if [[ -z "$pid" ]]; then
    return 0
  fi

  printf '%s\n' "$pid"
  collect_descendants "$pid"
}

process_tree_alive() {
  local pid="${1:-}"
  local child=""

  if [[ -z "$pid" ]]; then
    return 1
  fi

  if kill -0 -- "-$pid" 2>/dev/null; then
    return 0
  fi

  if kill -0 "$pid" 2>/dev/null; then
    return 0
  fi

  while IFS= read -r child; do
    if [[ -n "$child" ]] && kill -0 "$child" 2>/dev/null; then
      return 0
    fi
  done < <(collect_descendants "$pid")

  return 1
}

signal_process_tree() {
  local signal="${1:-TERM}"
  local pid="${2:-}"
  local -a descendants=()
  local child=""

  if [[ -z "$pid" ]]; then
    return
  fi

  while IFS= read -r child; do
    [[ -n "$child" ]] && descendants+=("$child")
  done < <(collect_descendants "$pid")

  kill "-$signal" -- "-$pid" 2>/dev/null || true

  if ((${#descendants[@]} > 0)); then
    local index=0
    for ((index=${#descendants[@]}-1; index>=0; index--)); do
      kill "-$signal" -- "-${descendants[index]}" 2>/dev/null || true
      kill "-$signal" "${descendants[index]}" 2>/dev/null || true
    done
  fi

  kill "-$signal" "$pid" 2>/dev/null || true
}
