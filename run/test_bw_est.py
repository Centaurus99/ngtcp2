#!/usr/bin/python3

import os
import re
from tqdm import tqdm
import json

basedir = "./run/work"
run_file = "./run/worker.sh"

if (os.path.exists(os.path.join(basedir, "threads", "logs")) == False):
    os.makedirs(os.path.join(basedir, "threads", "logs"))

BASE_BW_MUL_list = [2]
DATA_SIZE_KB_list = [1024]
loss_list = [0.0]
DELAY_1_list = [20]
DELAY_2_list = DELAY_1_list
bw_mul_list = [1.0]
cc_list = ['scubic2']
port = 40200
rounds = 500

for BASE_BW_MUL in BASE_BW_MUL_list:
    for DATA_SIZE_KB in DATA_SIZE_KB_list:
        for loss in loss_list:
            for DELAY_1 in DELAY_1_list:
                DELAY_2 = DELAY_1
                for bw_mul in bw_mul_list:
                    for cc in cc_list:
                        logfile = os.path.join(
                            basedir, "threads", "logs", "worker{}.log".format(port))
                        command = run_file + " {} {} {} {} {} {} {}".format(
                            DATA_SIZE_KB, BASE_BW_MUL, bw_mul, DELAY_1, DELAY_2, loss, cc)
                        command = command + \
                            " {} {} > {} 2>&1".format(
                                port, 1, logfile)
                        server_log = os.path.join(
                            basedir, "threads", "worker{}".format(port), "server.log")
                        bw_est_groudtruth = BASE_BW_MUL * 12
                        bw_est_logfile = os.path.join(
                            basedir, "threads", "worker{}".format(port), "bw_est_bw{}.log".format(bw_est_groudtruth))
                        print("Running {}".format(command))

                        with open(bw_est_logfile, 'a') as f_bw_est:
                            pbar = tqdm(range(rounds), desc="To bw_est_bw{}.log".format(
                                bw_est_groudtruth))
                            for i in pbar:
                                os.system(command)

                                bw_est_list = []
                                with open(server_log, 'r') as f:
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

                                pbar.set_postfix_str(
                                    "bw_est={:.2f} Mbits/s".format(bw_est_list[-1]))
                                f_bw_est.write(json.dumps(bw_est_list) + '\n')
                                f_bw_est.flush()
