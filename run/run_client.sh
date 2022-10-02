#!/bin/bash

DATA_FILE=$1
port=$2

./build/examples/client $MAHIMAHI_BASE $port https://$MAHIMAHI_BASE:$port${DATA_FILE:1} -q --exit-on-all-streams-close --max-stream-data-bidi-local=10M
echo "Closing Client"
sleep 5