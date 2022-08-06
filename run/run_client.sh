#!/bin/bash

DATA_FILE=$1

./build/examples/client $MAHIMAHI_BASE 2333 https://$MAHIMAHI_BASE:2333${DATA_FILE:1} -q --exit-on-all-streams-close
sleep 5