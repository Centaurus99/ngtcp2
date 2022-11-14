#!/usr/bin/python3

import os
import matplotlib.pyplot as plt
import seaborn as sns
import json
import numpy as np

colors = sns.color_palette('deep')
dark_colors = sns.color_palette('dark')

basedir = "./run/competition"

BASE_BW_MUL_list = [2]
port = 40200
COL_NUM = 5
LABLE_SLICE = 2
SLICE_CEIL = 4
SLICE = 5 * LABLE_SLICE


for BASE_BW_MUL in BASE_BW_MUL_list:
    bw_est_groudtruth = BASE_BW_MUL * 12
    bw_est_logfile = os.path.join(basedir, "bw_est_bw.log")
    with open(bw_est_logfile, 'r') as f_bw_est:
        lines = f_bw_est.readlines()
        bw_est_all = [[] for i in range(COL_NUM)]
        for line in lines:
            bw_est_list = json.loads(line)
            for i in range(COL_NUM):
                bw_est_all[i].append(bw_est_list[i])

    fig, ax = plt.subplots(COL_NUM, 1, figsize=(8, 4*COL_NUM))

    x = [bw_est_groudtruth/SLICE * i for i in range(SLICE*SLICE_CEIL+1)]
    xticks = [bw_est_groudtruth/LABLE_SLICE *
              i for i in range(LABLE_SLICE*SLICE_CEIL+1)]
    x.append(x[-1] + bw_est_groudtruth/SLICE)
    xticks.append(x[-1])

    for i in range(COL_NUM):
        ax[i].grid(linestyle=":", axis='y')
        ax[i].set_title("1000samples; {}ack".format(i+2))
        ax[i].set_xlabel("bw_est")
        ax[i].set_ylabel("count")
        ax[i].set_ylim(0, 400)
        _, bins, patches = ax[i].hist(np.clip(np.array(bw_est_all[i]), x[0], x[-1]),
                                      bins=x, color=colors[0])
        ax[i].axvline(bw_est_groudtruth, color=colors[-3], linestyle="--")

        ax[i].set_xticks(xticks)
        ax[i].set_xticklabels(xticks[:-1]+[r"$\infty$"])

    plt.tight_layout()
    plt.savefig(os.path.join(
        basedir, "bw_est_comp_bw{}_{}pc.png".format(bw_est_groudtruth, SLICE)))
