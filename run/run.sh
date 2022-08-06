#!/bin/bash

log_dir="./run/logs/server_log"


DATA_SIZE_MB=1
DATA_FILE="./run/data/"$DATA_SIZE_MB"M.file"

dd if=/dev/zero of=$DATA_FILE bs=1M count=$DATA_SIZE_MB &> /dev/null
echo "Data Size: $DATA_SIZE_MB MB"

for DELAY in 10
do
    for BDW_MUL in 1
    do
        echo "------------------------------------------------------------"
        BASE_RTT=`echo | awk "{print 2*$DELAY}"`
        echo "Base RTT: $BASE_RTT ms"
        BASE_BDW=`echo | awk "{print 12*$BDW_MUL}"`
        echo "Base Bandwidth: $BASE_BDW Mbps"

        python3 ./run/gen_traces.py $BDW_MUL

        # for mul in 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1 1.2 1.3 1.4 1.5 1.6 1.7 1.8 1.9 2.0
        for mul in 0.3 1.0 1.7
        do
            echo "----------------------------------------"
            echo "Testing mul $mul"
            echo "Starting server"
            ./build/examples/server '*' 2333 ./run/data/server.key ./run/data/server.crt --qlog-dir ./run/logs/server_log/ -q --cc scubic > ./run/logs/server.log 2>&1 &
            PID=$!
            sleep 2

            echo "Running client"
            echo "--------------------"
            RTT=`echo | awk "{print 2*$DELAY}"`
            BDP=`echo | awk "{print 1500*2*$DELAY*$BDW_MUL}"`
            BDW=`echo | awk "{print 12*$BDW_MUL}"`
            echo "RTT: $RTT ms"
            echo "BDP: $BDP Bytes"
            echo "Bandwidth: $BDW Mbps"
            mm-delay $DELAY mm-link --downlink-queue=droptail --downlink-queue-args=bytes=$BDP ./run/traces/1.0.trace ./run/traces/1.0.trace ./run/run_client.sh $DATA_FILE
            filename=$(ls -lt $log_dir | awk {'print $9'} | grep -v ^$ | head -n 1)
            newname="server_flow"$DATA_SIZE_MB"m_rtt"$BASE_RTT"_base"$BASE_BDW"_mul"$mul"_1.sqlog"
            echo "$filename -> $newname"
            mv $log_dir/$filename $log_dir/$newname

            echo "--------------------"
            RTT=`echo | awk "{print 2*$DELAY}"`
            BDP=`echo | awk "{print 1500*2*$DELAY*$BDW_MUL*$mul}"`
            BDW=`echo | awk "{print 12*$BDW_MUL*$mul}"`
            echo "RTT: $RTT ms"
            echo "BDP: $BDP Bytes"
            echo "Bandwidth: $BDW Mbps"
            mm-delay $DELAY mm-link --downlink-queue=droptail --downlink-queue-args=bytes=$BDP ./run/traces/$mul.trace ./run/traces/$mul.trace ./run/run_client.sh $DATA_FILE
            filename=$(ls -lt $log_dir | awk {'print $9'} | grep -v ^$ | head -n 1)
            newname="server_flow"$DATA_SIZE_MB"m_rtt"$BASE_RTT"_base"$BASE_BDW"_mul"$mul"_2.sqlog"
            echo "$filename -> $newname"
            mv $log_dir/$filename $log_dir/$newname

            echo "--------------------"
            echo "Stopping server"
            sleep 10
            set +m kill -9 $PID
            echo "Done"
        done
    done
done

echo "------------------------------------------------------------"
echo "clean data file $DATA_FILE"
rm $DATA_FILE