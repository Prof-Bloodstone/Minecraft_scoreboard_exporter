#!/bin/bash
set -euo pipefail

# If first argument is a flag, run the script
if [ "$#" -eq 0 ] || [ "${1#-}" != "${1}" ]; then
  set -- mc_NBT_top_scores.py "${@}"
fi

# If running the script
if [ "${1}" = 'mc_NBT_top_scores.py' ]; then
  if [ "$#" -eq 1 ] && [ -f '/config.json' ]; then
    shift
    set -- mc_NBT_top_scores.py '--config' '/config.json' "${@}"
  fi
  if [ -n "${CRON_SCHEDULE:-}" ]; then
    if [ "$(id -u)" == 0 ]; then
      : "${CRON_USER:=minecraft}"
      if [ -n "${CRON_ID:-}" ]; then
        addgroup -g "${CRON_ID}" -S "${CRON_USER}"
        adduser -u "${CRON_ID}" -S "${CRON_USER}" -G "${CRON_USER}"
      fi
      printf '%s cd / && python3 -u %s\n' "${CRON_SCHEDULE}" "${*@Q}" | crontab -u "${CRON_USER}" -
      exec crond -f -L /dev/stdout
    else
      printf 'Not running as root when CRON_SCHEDULE is set - will not use cron\n' >&2
    fi
  fi
    exec python3 -u "${@}"
fi

# In case user wants to run something else
exec "${@}"
