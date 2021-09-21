#!/bin/bash

if screen -ls | grep jmhub; then
        screen -X -S jmhub quit
fi