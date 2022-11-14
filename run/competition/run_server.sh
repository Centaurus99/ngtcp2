#!/bin/bash

# ./build/examples/server '*' 40200 ./run/data/server.key ./run/data/server.crt --qlog-dir ./run/competition/server_log -q --cc scubic2 > ./run/competition/server.log 2>&1 &
# ./build/examples/server '*' 40201 ./run/data/server.key ./run/data/server.crt --qlog-dir ./run/competition/server2_log -q --cc cubic > ./run/competition/server2.log 2>&1 &

./build/examples/server '*' 40200 ./run/data/server.key ./run/data/server.crt -q --cc scubic2 > ./run/competition/server.log 2>&1 &
./build/examples/server '*' 40201 ./run/data/server.key ./run/data/server.crt -q --cc cubic > ./run/competition/server2.log 2>&1 &
