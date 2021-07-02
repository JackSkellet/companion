#!/bin/bash

screen -X -S jmhub quit
sudo -H -u pi screen -dm -S jmhub $COMPANION_DIR/scripts/start_jmhub.sh