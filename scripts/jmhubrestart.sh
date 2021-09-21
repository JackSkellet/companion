#!/bin/bash

if screen -ls | grep jmhub; then
        screen -X -S jmhub quit
fi
sudo -H -u pi screen -dm -S jmhub \
  $COMPANION_DIR/scripts/start_jmhub.sh
