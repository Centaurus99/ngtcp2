#!/bin/bash

log_dir="./run/logs/server_log"

python3 ./run/gen_traces.py 1

for mul in 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1 1.2 1.3 1.4 1.5 1.6 1.7 1.8 1.9 2.0
do
    sleep 0.1
    echo "Testing $mul"
    echo "Starting server"
    ./build/examples/server '*' 2333 ./run/data/server.key ./run/data/server.crt --qlog-dir ./run/logs/server_log/ -q --cc scubic > ./run/logs/server.log 2>&1 &
    PID=$!
    sleep 2

    echo "Running client"
    mm-delay 100 mm-link --downlink-queue=droptail --downlink-queue-args=bytes=300000 ./run/traces/1.0.trace ./run/traces/1.0.trace ./run/run_client.sh
    filename=$(ls -lt $log_dir | awk {'print $9'} | grep -v ^$ | head -n 1)
    echo "$filename -> server_"$mul"_1.sqlog"
    mv $log_dir/$filename $log_dir/server_"$mul"_1.sqlog

    mm-delay 100 mm-link --downlink-queue=droptail --downlink-queue-args=bytes=300000 ./run/traces/$mul.trace ./run/traces/$mul.trace ./run/run_client.sh
    filename=$(ls -lt $log_dir | awk {'print $9'} | grep -v ^$ | head -n 1)
    echo "$filename -> server_"$mul"_1.sqlog"
    mv $log_dir/$filename $log_dir/server_"$mul"_2.sqlog

    echo "Stopping server"
    sleep 10
    kill -9 $PID
    echo "Done"
done

