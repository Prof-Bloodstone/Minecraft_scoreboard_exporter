#!/bin/sh
set -eu

# If first argument is a flag, run the script
if [ "$#" -eq 0 ] || [ "${1#-}" != "${1}" ]; then
  set -- mc_NBT_top_scores.py "${@}"
fi

# If running the script
if [ "${1}" = 'mc_NBT_top_scores.py' ]; then
  exec python3 -u "${@}"
fi

# In case user wants to run something else
exec "${@}"
