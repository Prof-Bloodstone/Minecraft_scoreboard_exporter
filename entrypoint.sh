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
    printf '%s python3 -u %s\n' "${CRON_SCHEDULE}" "$(printf "'%s' " "${@}")" | crontab -
    exec crond -f -L /dev/stdout
  else
    exec python3 -u "${@}"
  fi
fi

# In case user wants to run something else
exec "${@}"
