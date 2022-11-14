#!/usr/bin/python3

import os
import time
import re
import json
from tqdm import tqdm

rounds = 1000
server_log = "./run/competition/server.log"
server2_log = "./run/competition/server2.log"
bw_est_logfile = "./run/competition/bw_est_bw.log"

with open(bw_est_logfile, 'a') as f_bw_est:
    with open(server_log, 'r') as f:
        pbar = tqdm(range(rounds), desc="To bw_est_bw.log")
        for i in pbar:
            bw_est_list = []
            os.system("./build/examples/client 100.64.0.2 40201 https://100.64.0.2:40201/run/data/5M.bin -q --exit-on-all-streams-close --max-stream-data-bidi-local=10M &")
            pbar.set_description_str("Started client 1")
            time.sleep(1)
            pbar.set_description_str("Running client 2")
            os.system("./build/examples/client 100.64.0.2 40200 https://100.64.0.2:40200/run/data/5M.bin -q --exit-on-all-streams-close --max-stream-data-bidi-local=10M")
            pbar.set_description_str("Done")
            line = f.readline()
            while line:
                if line.startswith("rtt_samples"):
                    if (line.startswith("rtt_samples[0]")):
                        line = f.readline()
                        continue
                    bw_est = float(re.findall(
                        r"btl_bw_estimated=([0-9.]+)", line)[0])
                    bw_est = round(
                        8 * bw_est / 1000 / 1000, 6)
                    bw_est_list.append(bw_est)
                    if (line.startswith("rtt_samples[5]")):
                        break
                line = f.readline()

            pbar.set_postfix_str(
                "bw_est={:.2f} Mbits/s".format(bw_est_list[-1]))
            f_bw_est.write(json.dumps(bw_est_list) + '\n')
            f_bw_est.flush()


def collect(log_file):
    ts = []
    delivery_rate = []
    BBR_btl_bw = []
    BBR_max_btl_bw = []
    WestWood_bw_est = []
    WestWood_max_bw_est = []
    GCBE_smooth_btl_bw_max = []
    GCBE_max_gcbe_bw = []
    with open(log_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith("rtt_samples"):
                if (line.startswith("rtt_samples[0]")):
                    continue
                bw_est = float(re.findall(
                    r"btl_bw_estimated=([0-9.]+)", line)[0])
                bw_est = round(
                    8 * bw_est / 1000 / 1000, 6)
                bw_est_list.append(bw_est)
