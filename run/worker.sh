#!/bin/bash

DATA_SIZE_KB=$1
BASE_BW_MUL=$2
bw_mul=$3
DELAY_1=$4
DELAY_2=$5 
loss=$6
cc=$7
port=$8
repeats=$9

echo "------------------------------------------------------------"

echo "Data Size: $DATA_SIZE_KB KB"

BASE_BW=`echo | awk "{print 12*$BASE_BW_MUL}"`
NEW_BW=`echo | awk "{print 12*$BASE_BW_MUL*$bw_mul}"`
echo "Bandwidth: $BASE_BW Mbps --> $NEW_BW Mbps"

BASE_RTT=`echo | awk "{print 2*$DELAY_1}"`
NEW_RTT=`echo | awk "{print 2*$DELAY_2}"`
echo "RTT: $BASE_RTT ms --> $NEW_RTT ms"

workdir="./run/work/threads/worker"$port"/"$cc"_flow"$DATA_SIZE_KB"k_rtt"$BASE_RTT"to"$NEW_RTT"_bw"$BASE_BW"_bw_mul"$bw_mul"_loss"$loss
mkdir -p $workdir
finaldir="./run/work/worker_final/"
mkdir -p $finaldir

DATA_FILE=$workdir/$DATA_SIZE_KB"K.bin"
dd if=/dev/zero of=$DATA_FILE bs=1K count=$DATA_SIZE_KB &> /dev/null


for i in `seq 1 $repeats`;
do

    echo "--------------------"
    echo "Starting "$cc" server"
    ./build/examples/server '*' $port ./run/data/server.key ./run/data/server.crt --qlog-dir $workdir -q --cc $cc > $workdir/../server.log 2>&1 &
    PID=$!
    sleep 2

    echo "Running client"
    echo "--------------------"
    BDP=`echo | awk "{print 1500*2*$DELAY_1*$BASE_BW_MUL}"`
    echo "Bandwidth: $BASE_BW Mbps"
    echo "RTT: $BASE_RTT ms"
    echo "BDP: $BDP Bytes"
    mm-loss downlink $loss mm-loss uplink $loss mm-delay $DELAY_1 mm-link --downlink-queue=droptail --downlink-queue-args=bytes=$BDP ./run/traces/1.0.trace ./run/traces/1.0.trace ./run/run_client.sh $DATA_FILE $port
    filename=$(ls -lt $workdir | awk {'print $9'} | grep -v ^$ | head -n 1)
    newname=$i"_1.sqlog"
    echo "$filename -> $newname"
    mv $workdir/$filename $workdir/$newname

    echo "--------------------"
    BDP=`echo | awk "{print 1500*2*$DELAY_2*$BASE_BW_MUL*$bw_mul}"`
    echo "Bandwidth: $NEW_BW Mbps"
    echo "RTT: $NEW_RTT ms"
    echo "BDP: $BDP Bytes"
    mm-loss downlink $loss mm-loss uplink $loss mm-delay $DELAY_2 mm-link --downlink-queue=droptail --downlink-queue-args=bytes=$BDP ./run/traces/$bw_mul.trace ./run/traces/$bw_mul.trace ./run/run_client.sh $DATA_FILE $port
    filename=$(ls -lt $workdir | awk {'print $9'} | grep -v ^$ | head -n 1)
    newname=$i"_2.sqlog"
    echo "$filename -> $newname"
    mv $workdir/$filename $workdir/$newname

    echo "--------------------"
    echo "Stopping server"
    sleep 10
    kill -9 $PID
    echo "Done"

done

echo "------------------------------------------------------------"
echo "clean data file $DATA_FILE"
rm $DATA_FILE

mv -f $workdir $finaldir
echo "$workdir -> $finaldir"
