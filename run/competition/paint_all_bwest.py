import os
import time
import re
import matplotlib.pyplot as plt
import seaborn as sns

colors = sns.color_palette('tab20')

# os.system("./build/examples/client 100.64.0.2 40201 https://100.64.0.2:40201/run/data/5M.bin -q --exit-on-all-streams-close --max-stream-data-bidi-local=10M &")
# time.sleep(1)
# os.system("./build/examples/client 100.64.0.2 40200 https://100.64.0.2:40200/run/data/5M.bin -q --exit-on-all-streams-close --max-stream-data-bidi-local=10M")


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
            if line.startswith("-- BWEST:"):
                if (line.startswith("rtt_samples[0]")):
                    continue
                ts.append(int(re.search(r"ts=([0-9.]+)", line)[1]))
                delivery_rate.append(
                    float(re.search(r"delivery_rate=([0-9.]+)", line)[1]))
                BBR_btl_bw.append(
                    float(re.search(r"BBR_btl_bw=([0-9.]+)", line)[1]))
                BBR_max_btl_bw.append(
                    float(re.search(r"BBR_max_btl_bw=([0-9.]+)", line)[1]))
                WestWood_bw_est.append(
                    float(re.search(r"WestWood_bw_est=([0-9.]+)", line)[1]))
                WestWood_max_bw_est.append(
                    float(re.search(r"WestWood_max_bw_est=([0-9.]+)", line)[1]))
                GCBE_smooth_btl_bw_max.append(
                    float(re.search(r"GCBE_smooth_btl_bw_max=([0-9.]+)", line)[1]))
                GCBE_max_gcbe_bw.append(
                    float(re.search(r"GCBE_max_gcbe_bw=([0-9.]+)", line)[1]))

    base_ts = ts[0]
    ts = [(t - base_ts)/1e6 for t in ts]
    delivery_rate = [round(8 * dr / 1000 / 1000, 6) for dr in delivery_rate]
    BBR_btl_bw = [round(8 * bbr / 1000 / 1000, 6) for bbr in BBR_btl_bw]
    BBR_max_btl_bw = [round(8 * bbr / 1000 / 1000, 6)
                      for bbr in BBR_max_btl_bw]
    WestWood_bw_est = [round(8 * ww / 1000 / 1000, 6)
                       for ww in WestWood_bw_est]
    WestWood_max_bw_est = [round(8 * ww / 1000 / 1000, 6)
                           for ww in WestWood_max_bw_est]
    GCBE_smooth_btl_bw_max = [round(8 * gcbe / 1000 / 1000, 6)
                              for gcbe in GCBE_smooth_btl_bw_max]
    GCBE_max_gcbe_bw = [round(8 * gcbe / 1000 / 1000, 6)
                        for gcbe in GCBE_max_gcbe_bw]

    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    ax.grid(linestyle=":", axis='y')
    ax.set_title(log_file)
    ax.set_xlabel("Tims (ms)")
    ax.set_ylabel("Bw Est (Mbps)")
    ax.plot(ts, delivery_rate, label="delivery_rate", color=colors[0])
    ax.plot(ts, BBR_max_btl_bw, label="BBR_max_btl_bw", color=colors[3])
    ax.plot(ts, BBR_btl_bw, label="BBR_btl_bw", color=colors[2])
    ax.plot(ts, WestWood_max_bw_est,
            label="WestWood_max_bw_est", color=colors[5])
    ax.plot(ts, WestWood_bw_est, label="WestWood_bw_est", color=colors[4])
    ax.plot(ts, GCBE_max_gcbe_bw, label="GCBE_max_gcbe_bw", color=colors[7])
    ax.plot(ts, GCBE_smooth_btl_bw_max,
            label="GCBE_smooth_btl_bw_max", color=colors[6])

    ax.legend()

    plt.savefig(log_file[:-3] + "png")


collect("./run/competition/server.log")
collect("./run/competition/server2.log")
