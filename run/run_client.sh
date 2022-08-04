#!/bin/bash

./build/examples/client $MAHIMAHI_BASE 2333 https://$MAHIMAHI_BASE:2333/run/data/1M.file -q --exit-on-all-streams-close
sleep 5