from math import ceil
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import numpy as np
from scipy import stats
from time import sleep

import matplotlib as mpl
mpl.rcParams['figure.facecolor'] = '1.0'
mpl.rcParams['axes.facecolor'] = '1.0'

colors = sns.color_palette('deep')
dark_colors = sns.color_palette('dark')

basedir = "./run/work"
if (os.path.exists(os.path.join(basedir, "pic")) == False):
    os.makedirs(os.path.join(basedir, "pic"))

BASE_BW_MUL_list = [2]
DATA_SIZE_KB_list = [1024]
loss_list = [0.0]
DELAY_1_list = [20]
DELAY_2_list = DELAY_1_list
bw_mul_list = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
               1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]
# bw_mul_list = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
# bw_mul_list = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]
cc_list = ['fixed', 'cubic', 'scubic', 'scubic2', ]
repeats = 10


def get_path(BASE_BW_MUL, DATA_SIZE_KB, loss, DELAY_1, DELAY_2, bw_mul, cc):
    return os.path.join(basedir, "worker_final", "{}_flow{}k_rtt{}to{}_bw{}_bw_mul{}_loss{}".format(
        cc, DATA_SIZE_KB, 2 * DELAY_1, 2 * DELAY_2, 12 * BASE_BW_MUL, bw_mul, loss))


def confidence_95(val_list):
    val_np = np.array(val_list)
    mean = np.mean(val_np)
    tsem = stats.tsem(val_np, ddof=1)  # 均值标准差
    if (tsem == 0):
        interval = (mean, mean)
    else:
        interval = stats.t.interval(
            0.95, len(val_list)-1, mean, tsem)  # 求总体均值置信区间
    return mean, interval


def get_offset(ax_, x, y):
    trans1 = ax_.transAxes
    trans2 = ax_.transData.inverted()
    x0, y0 = trans2.transform(trans1.transform((0, 0)))
    x1, y1 = trans2.transform(trans1.transform((x, y)))
    return x1 - x0, y1 - y0


def load_qlog_basic(logdir, filename):
    x = []
    smoothed_rtt = []
    latest_rtt = []
    congestion_window = []
    bytes_in_flight = []

    ssthresh_x = []
    ssthresh = []

    packet_lost = {}

    print("loading " + os.path.join(logdir, filename))
    with open(os.path.join(logdir, filename), 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            if 'name' not in data.keys():
                continue

            if data['name'] == 'recovery:metrics_updated':
                x.append(data['time'])
                smoothed_rtt.append(data['data']['smoothed_rtt'])
                latest_rtt.append(data['data']['latest_rtt'])
                congestion_window.append(
                    data['data']['congestion_window'])
                bytes_in_flight.append(
                    data['data']['bytes_in_flight'])
                if 'ssthresh' in data['data']:
                    ssthresh_x.append(data['time'])
                    ssthresh.append(data['data']['ssthresh'])

            elif data['name'] == 'recovery:packet_lost':
                if data['time'] not in packet_lost:
                    packet_lost[data['time']] = 0
                packet_lost[data['time']] += 1

    print("packet lost sum:", sum(packet_lost.values()))

    return x, smoothed_rtt, latest_rtt, congestion_window, bytes_in_flight, ssthresh_x, ssthresh, packet_lost


def load_qlog_metric(logdir):

    FCT_list = []
    lost_bytes_list = []

    # print(logdir)
    for i in range(1, repeats + 1):
        try:
            pkt_list = {}
            FCT = 0
            lost_bytes = 0

            # print("{}_2.sqlog".format(i))
            with open(os.path.join(logdir, "{}_2.sqlog".format(i)), 'r') as f:
                for line in f:
                    data = json.loads(line.strip())
                    if 'name' not in data.keys():
                        continue
                    FCT = data['time']

                    if data['name'] == 'recovery:packet_lost':
                        (length, time) = pkt_list[data['data']
                                                  ['header']['packet_number']]
                        lost_bytes += length
                    elif data['name'] == 'transport:packet_sent':
                        pkt_list[data['data']['header']['packet_number']] = (
                            data['data']['raw']['length'], data['time'])

            FCT_list.append(FCT)
            lost_bytes_list.append(lost_bytes)

        except:
            print("------------------")
            print("Name: ", logdir)
            print("Error: " + "{}_2.sqlog".format(i))
            sleep(1)

    if len(FCT_list) != repeats:
        print("Warning: not enough data. ({}/{})".format(len(FCT_list), repeats))

    if (len(FCT_list) != len(lost_bytes_list)):
        print("Error: FCT_list and lost_bytes_list not match.")
        exit(-1)

    # # HACK: 去除最大值
    # max_fct = max(FCT_list)
    # max_index = FCT_list.index(max_fct)
    # del FCT_list[max_index]
    # del lost_bytes_list[max_index]

    return FCT_list, lost_bytes_list


def has_stream(data):
    frames = data['data']['frames']
    for frame in frames:
        if frame['frame_type'] == 'stream':
            return True
    return False


def is_stream_fin(data):
    frames = data['data']['frames']
    for frame in frames:
        if frame['frame_type'] == 'stream' and 'fin' in frame and frame['fin'] == True:
            return True
    return False


def collect(logdir, title):
    F1 = 'F1'
    F2 = 'F2'
    x_1, smoothed_rtt_1, latest_rtt_1, congestion_window_1, bytes_in_flight_1, ssthresh_x_1, ssthresh_1, packet_lost_1 = load_qlog_basic(
        logdir, "1_1.sqlog")

    x_2, smoothed_rtt_2, latest_rtt_2, congestion_window_2, bytes_in_flight_2, ssthresh_x_2, ssthresh_2, packet_lost_2 = load_qlog_basic(
        logdir, "1_2.sqlog")

    fig, ax = plt.subplots(
        nrows=10,
        gridspec_kw={'height_ratios': [3, 2, 2, 2, 2, 2, 2, 2, 2, 2]}
    )
    fig.set_figwidth(15)
    fig.set_figheight(40)
    fig.suptitle(title, fontsize=20)
    id = 0

    # ----- F1 vs F2: CWnd and Packet Lost -----
    ax_2 = ax[id].twinx()
    ax[id].yaxis.tick_right()
    ax[id].yaxis.set_label_position("right")
    ax_2.yaxis.tick_left()
    ax_2.yaxis.set_label_position("left")
    ax_2.grid(linestyle=":", axis='y')

    ax_2.plot(x_1, congestion_window_1,
              color=colors[1], label='CWnd ' + F1)
    ax_2.plot(x_2, congestion_window_2,
              color=colors[0], label='CWnd ' + F2)

    ax_2.set_ylim(0)
    ax_2.axvline(x_2[0], color=colors[-3], linestyle="--")

    ax_2.axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_1[-1] + offset_x, offset_y, F1 + ": {:.0f} ms".format(x_1[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax_2.axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_2[-1] + offset_x, offset_y, F2 + ": {:.0f} ms".format(x_2[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    width = get_offset(ax_2, 0.002, 0.5)[0]
    ax[id].bar(list(packet_lost_1.keys()), list(
        packet_lost_1.values()), width=width, color=colors[-2], label='Packet Lost ' + F1)
    ax[id].bar(list(packet_lost_2.keys()), list(
        packet_lost_2.values()), width=width, color=colors[-1], label='Packet Lost ' + F2)

    lines, labels = ax[id].get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax[id].legend(lines2 + lines, labels2 + labels)

    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Packet Lost (pkts)')
    ax_2.set_ylabel('CWnd (Bytes)')
    ax[id].set_title(
        '{} vs {}: CWnd and Packet Lost'.format(F1, F2), size=15)
    id += 1

    # ----- F1 vs F2: Bytes in Flight -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].plot(x_1, bytes_in_flight_1, color=colors[1],
                label='Bytes in Flight ' + F1)
    ax[id].plot(x_2, bytes_in_flight_2, color=colors[0],
                label='Bytes in Flight ' + F2)

    ax[id].set_ylim(0)
    ax[id].axvline(x_2[0], color=colors[-3], linestyle="--")

    ax[id].axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_1[-1] + offset_x, offset_y, "F1: {:.0f} ms".format(x_1[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_2[-1] + offset_x, offset_y, "F2: {:.0f} ms".format(x_2[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Bytes in Flight (Bytes)')
    ax[id].set_title('{} vs {}: Bytes in Flight'.format(F1, F2), size=15)
    id += 1

    RTT_MAX = max(latest_rtt_1[10:] + latest_rtt_2[10:])
    # ----- F1 vs F2: Latest RTT -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].set_ylim(0, RTT_MAX * 1.1)
    ax[id].plot(x_1, latest_rtt_1, color=colors[1],
                label='Latest RTT ' + F1)
    ax[id].plot(x_2, latest_rtt_2, color=colors[0],
                label='Latest RTT ' + F2)

    ax[id].set_ylim(0)
    ax[id].axvline(x_2[0], color=colors[-3], linestyle="--")

    ax[id].axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_1[-1] + offset_x, offset_y, "F1: {:.0f} ms".format(x_1[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_2[-1] + offset_x, offset_y, "F2: {:.0f} ms".format(x_2[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Latest RTT (ms)')
    ax[id].set_title('{} vs {}: Latest RTT'.format(F1, F2), size=15)
    id += 1

    # ----- F1 vs F2: Smoothed RTT -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].set_ylim(0, RTT_MAX * 1.1)
    ax[id].plot(x_1, smoothed_rtt_1, color=colors[1],
                label='Smoothed RTT ' + F1)
    ax[id].plot(x_2, smoothed_rtt_2, color=colors[0],
                label='Smoothed RTT ' + F2)

    ax[id].set_ylim(0)
    ax[id].axvline(x_2[0], color=colors[-3], linestyle="--")

    ax[id].axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_1[-1] + offset_x, offset_y, "F1: {:.0f} ms".format(x_1[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_2[-1] + offset_x, offset_y, "F2: {:.0f} ms".format(x_2[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Smoothed RTT (ms)')
    ax[id].set_title('{} vs {}: Smoothed RTT'.format(F1, F2), size=15)
    id += 1

    # ----- F1: CWnd and Packet Lost -----
    ax_2 = ax[id].twinx()
    ax[id].yaxis.tick_right()
    ax[id].yaxis.set_label_position("right")
    ax_2.yaxis.tick_left()
    ax_2.yaxis.set_label_position("left")
    ax_2.grid(linestyle=":", axis='y')

    ax_2.plot(x_1, congestion_window_1,
              color=colors[1], label='CWnd ' + F1)
    ax_2.set_ylim(0)
    ax_2.axvline(x_1[0], color=colors[-3], linestyle="--")
    ax_2.axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_1[-1] + offset_x, offset_y, "{:.0f} ms".format(x_1[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].bar(list(packet_lost_1.keys()), list(packet_lost_1.values()), width=get_offset(
        ax_2, 0.002, 0.5)[0], color=colors[-2], label='Packet Lost ' + F1)

    lines, labels = ax[id].get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax[id].legend(lines2 + lines, labels2 + labels)

    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Packet Lost (pkts)')
    ax_2.set_ylabel('CWnd (Bytes)')
    ax[id].set_title(F1 + ': CWnd and Packet Lost', size=15)
    id += 1

    # ----- F1: Bytes in Flight -----
    ax_2 = ax[id].twinx()
    ax[id].yaxis.tick_right()
    ax[id].yaxis.set_label_position("right")
    ax_2.yaxis.tick_left()
    ax_2.yaxis.set_label_position("left")
    ax_2.grid(linestyle=":", axis='y')

    ax_2.plot(x_1, bytes_in_flight_1,
              color=colors[1], label='Bytes in Flight ' + F1)
    ax_2.set_ylim(0)
    ax_2.axvline(x_1[0], color=colors[-3], linestyle="--")
    ax_2.axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_1[-1] + offset_x, offset_y, "{:.0f} ms".format(x_1[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].bar(list(packet_lost_1.keys()), list(packet_lost_1.values()), width=get_offset(
        ax_2, 0.002, 0.5)[0], color=colors[-2], label='Packet Lost ' + F1)

    lines, labels = ax[id].get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax[id].legend(lines2 + lines, labels2 + labels)

    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Packet Lost (pkts)')
    ax_2.set_ylabel('Bytes in Flight (Bytes)')
    ax[id].set_title(F1 + ': Bytes in Flight', size=15)
    id += 1

    # ----- F1: RTT -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].set_ylim(0, max(latest_rtt_1[10:]) * 1.1)
    ax[id].plot(x_1, latest_rtt_1, color=colors[1], label='Latest RTT ' + F1)
    ax[id].plot(x_1, smoothed_rtt_1, color=colors[2],
                label='Smoothed RTT ' + F1)

    ax[id].set_ylim(0)
    ax[id].axvline(x_1[0], color=colors[-3], linestyle="--")
    ax[id].axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_1[-1] + offset_x, offset_y, "{:.0f} ms".format(x_1[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('RTT (ms)')
    ax[id].set_title(F1 + ': RTT', size=15)
    id += 1

    # ----- F2: CWnd and Packet Lost -----
    ax_2 = ax[id].twinx()
    ax[id].yaxis.tick_right()
    ax[id].yaxis.set_label_position("right")
    ax_2.yaxis.tick_left()
    ax_2.yaxis.set_label_position("left")
    ax_2.grid(linestyle=":", axis='y')

    ax_2.plot(x_2, congestion_window_2,
              color=colors[0], label='CWnd ' + F2)
    ax_2.set_ylim(0)
    ax_2.axvline(x_2[0], color=colors[-3], linestyle="--")
    ax_2.axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_2[-1] + offset_x, offset_y, "{:.0f} ms".format(x_2[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].bar(list(packet_lost_2.keys()), list(packet_lost_2.values()), width=get_offset(
        ax_2, 0.002, 0.5)[0], color=colors[3], label='Packet Lost ' + F2)

    lines, labels = ax[id].get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax[id].legend(lines2 + lines, labels2 + labels)

    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Packet Lost (pkts)')
    ax_2.set_ylabel('CWnd (Bytes)')
    ax[id].set_title(F2 + ': CWnd and Packet Lost', size=15)
    id += 1

    # ----- F2: Bytes in Flight -----
    ax_2 = ax[id].twinx()
    ax[id].yaxis.tick_right()
    ax[id].yaxis.set_label_position("right")
    ax_2.yaxis.tick_left()
    ax_2.yaxis.set_label_position("left")
    ax_2.grid(linestyle=":", axis='y')

    ax_2.plot(x_2, bytes_in_flight_2,
              color=colors[0], label='CWnd ' + F2)
    ax_2.set_ylim(0)
    ax_2.axvline(x_2[0], color=colors[-3], linestyle="--")
    ax_2.axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_2[-1] + offset_x, offset_y, "{:.0f} ms".format(x_2[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].bar(list(packet_lost_2.keys()), list(packet_lost_2.values()), width=get_offset(
        ax_2, 0.002, 0.5)[0], color=colors[3], label='Packet Lost ' + F2)

    lines, labels = ax[id].get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax[id].legend(lines2 + lines, labels2 + labels)

    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Packet Lost (pkts)')
    ax_2.set_ylabel('Bytes in Flight (Bytes)')
    ax[id].set_title(F2 + ': Bytes in Flight', size=15)
    id += 1

    # ----- F2: RTT -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].set_ylim(0, max(latest_rtt_2[10:]) * 1.1)
    ax[id].plot(x_2, latest_rtt_2, color=colors[0], label='Latest RTT ' + F2)
    ax[id].plot(x_2, smoothed_rtt_2, color=colors[2],
                label='Smoothed RTT ' + F2)

    ax[id].set_ylim(0)
    ax[id].axvline(x_2[0], color=colors[-3], linestyle="--")
    ax[id].axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_2[-1] + offset_x, offset_y, "{:.0f} ms".format(x_2[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('RTT (ms)')
    ax[id].set_title(F2 + ': RTT', size=15)
    id += 1

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.3, top=0.95)
    plt.savefig(logdir + '.png')


def compare_fct_and_lost(BASE_BW_MUL, DATA_SIZE_KB, loss, DELAY_1, DELAY_2):
    title = "Base Bandwidth: {} Mbps; Flow Size: {} KB; RTT: {} ms".format(
        12 * BASE_BW_MUL, DATA_SIZE_KB, 2 * DELAY_1)
    name = "bw_mul_{}_data_size_{}_loss_{}_delay_{}_{}".format(
        BASE_BW_MUL, DATA_SIZE_KB, loss, DELAY_1, DELAY_2)
    fig, ax_2 = plt.subplots(1, 1, figsize=(18, 9))
    fig.suptitle(title, fontsize=20)
    ax = ax_2.twinx()
    ax.yaxis.tick_left()
    ax.yaxis.set_label_position("left")
    ax_2.yaxis.tick_right()
    ax_2.yaxis.set_label_position("right")
    ax_2.grid(linestyle=":", axis='y')

    ax_ymax = 0
    ax_2_ymax = 0

    bar_color = [colors[2], colors[3], colors[1], colors[0], ]
    bar_dark_color = [dark_colors[2], dark_colors[3],
                      dark_colors[1], dark_colors[0], ]
    plot_color = [colors[2], colors[3], colors[1], colors[0], ]

    marker = ['v', 's', 'o', 'x', ]

    global last_repeats
    global repeats

    for index, cc in enumerate(cc_list):
        x = []
        fct_mean = []
        fct_err = []
        lost_mean = []
        lost_err = []
        if (cc == 'fixed'):
            last_repeats = repeats
            repeats = 1
        for bw_mul in bw_mul_list:
            logdir = get_path(BASE_BW_MUL, DATA_SIZE_KB, loss,
                              DELAY_1, DELAY_2, bw_mul, cc)
            fct, lost = load_qlog_metric(logdir)

            if (repeats == 1):
                print("Warning: only one repeat for {}!".format(logdir))
                fct.append(fct[0])
                lost.append(lost[0])

            print(cc, bw_mul, " FCT: ", fct, confidence_95(fct))
            print(cc, bw_mul, "LOST: ", lost, confidence_95(lost))
            fct = confidence_95(fct)
            lost = confidence_95(lost)

            x.append(bw_mul)
            fct_mean.append(fct[0])
            lost_mean.append(lost[0])
            fct_err.append(fct[1][1] - fct[0])
            lost_err.append(lost[1][1] - lost[0])

        if (cc == 'fixed'):
            repeats = last_repeats

        ax_ymax = max(ax_ymax, max(fct_mean))
        ax_2_ymax = max(ax_2_ymax, max(lost_mean))

        err_attr = {"elinewidth": 1,
                    "ecolor": bar_dark_color[index], "capsize": 4}
        bar_width = 0.02
        ax_2.bar(np.array(x) - 4 * bar_width / 2 + index * bar_width, lost_mean, yerr=lost_err,
                 error_kw=err_attr, color=bar_color[index], width=bar_width, label=cc.upper()+" Lost Bytes")

        ax.plot(x, fct_mean, color=plot_color[index], label=cc.upper(
        ) + " FCT", marker=marker[index], markersize=7)
        ax.fill_between(x, np.array(fct_mean) - np.array(fct_err), np.array(
            fct_mean) + np.array(fct_err), color=plot_color[index], alpha=0.1)

    ax_ymax = ceil(1.0 * ax_ymax / 100) * 100
    ax_2_ymax = ceil(2 * ax_2_ymax / 100000) * 100000
    ax.set_ylim(0, ax_ymax)
    ax_2.set_ylim(0, ax_2_ymax)

    ax.set_xticks(bw_mul_list)
    ax.set_yticks(np.linspace(ax.get_ybound()[0], ax.get_ybound()[1], 11))
    ax_2.set_yticks(np.linspace(ax_2.get_ybound()[
                    0], ax_2.get_ybound()[1], 11))

    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, prop={'size': 12})

    ax_2.set_xlabel('Bandwidth Multiplier', size=15)
    ax.set_ylabel('FCT (ms)', size=13)
    ax_2.set_ylabel('Lost Bytes', size=13)

    ax.tick_params(labelsize=11)
    ax_2.tick_params(labelsize=11)

    plt.tight_layout()
    plt.savefig(os.path.join(basedir, "pic", name + '.png'))


for BASE_BW_MUL in BASE_BW_MUL_list:
    for DATA_SIZE_KB in DATA_SIZE_KB_list:
        for loss in loss_list:
            for DELAY_1 in DELAY_1_list:
                DELAY_2 = DELAY_1
                print("---------- BASE_BW_MUL: {}, DATA_SIZE_KB: {}, loss: {}, DELAY_1: {}, DELAY_2: {}".format(
                    BASE_BW_MUL, DATA_SIZE_KB, loss, DELAY_1, DELAY_2))
                compare_fct_and_lost(
                    BASE_BW_MUL, DATA_SIZE_KB, loss, DELAY_1, DELAY_2)
                print("")

# collect(get_path(2, 1024, 0.0, 20, 20, 0.1, 'fixed'), 'fixed')

# for cc in cc_list:
#     for bw_mul in bw_mul_list:
#         name = get_path(
#             BASE_BW_MUL, DATA_SIZE_KB, loss, DELAY_1, DELAY_2, bw_mul, cc, port)
#         title = "RTT: {} ms -> {} ms; Bandwidth: {} Mbps -> {:.1f} Mbps; BDP: {:.0f} Bytes -> {:.0f} Bytes ({:.0%} Bandwidth)".format(
#             2 * DELAY_1, 2 * DELAY_2, 12 * BASE_BW_MUL, 12 * BASE_BW_MUL * bw_mul, 12 * BASE_BW_MUL * 2 * DELAY_1 * 125, 12 * BASE_BW_MUL * 2 * DELAY_2 * 125, bw_mul)
#         FCT, lost = load_qlog_metric(name)
#         print(FCT, confidence_95(FCT))
#         print(lost, confidence_95(lost))
