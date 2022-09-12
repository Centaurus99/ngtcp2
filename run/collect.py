import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import numpy as np

import matplotlib as mpl
mpl.rcParams['figure.facecolor'] = '1.0'
mpl.rcParams['axes.facecolor'] = '1.0'

colors = sns.color_palette('deep')

logdir = "./run/logs/server_log"

flow_list = [128]
rtt_list = [20]
BDW_list = [24]
mul_list = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
            1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]

F1 = 'S-CUBIC'
F2 = 'S-CUBIC2'
F1_prefix = 'scubic'
F1_suffix = '_2.sqlog'
F2_prefix = 'scubic2'
F2_suffix = '_2.sqlog'


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


def load_qlog_analysize_congestion(logdir, filename, rtt, bdw, mul):
    x = []

    start_time = 0
    end_time = 0

    pkt_list = {}
    pkt_lost_time_map = {}

    bytes_sent_x = []
    bytes_sent = []
    bytes_sent_without_lost = []

    bytes_lost_early = []
    bytes_lost = []

    bytes_target = []
    bytes_target_up = []

    limit_by_sent_x = []
    limit_by_sent = []

    print("loading " + os.path.join(logdir, filename))
    with open(os.path.join(logdir, filename), 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            if 'name' not in data.keys():
                continue
            x.append(data['time'])

            if data['name'] == 'recovery:packet_lost':
                (length, time) = pkt_list[data['data']
                                          ['header']['packet_number']]
                if time not in pkt_lost_time_map.keys():
                    pkt_lost_time_map[time] = length
                else:
                    pkt_lost_time_map[time] += length

                if (bytes_sent_x[-1] == data['time']):
                    bytes_sent[-1] -= length
                    bytes_lost[-1] += length
                else:
                    bytes_sent_x.append(data['time'])
                    bytes_sent.append(-length)
                    bytes_sent_without_lost.append(0)
                    bytes_lost_early.append(0)
                    bytes_lost.append(length)

            elif data['name'] == 'transport:packet_received':
                if start_time == 0 and data['data']['frames'][0]['frame_type'] != 'crypto':
                    start_time = data['time']
                    bytes_sent_x.append(start_time)
                    bytes_sent.append(0)
                    bytes_sent_without_lost.append(0)
                    bytes_lost_early.append(0)
                    bytes_lost.append(0)

            elif data['name'] == 'transport:packet_sent':
                if start_time != 0:
                    if is_stream_fin(data):
                        end_time = data['time']
                    if end_time == 0 or has_stream(data):
                        pkt_list[data['data']['header']['packet_number']] = (
                            data['data']['raw']['length'], data['time'])
                        if (bytes_sent_x[-1] == data['time']):
                            bytes_sent[-1] += data['data']['raw']['length']
                            bytes_sent_without_lost[-1] += data['data']['raw']['length']
                        else:
                            bytes_sent_x.append(data['time'])
                            bytes_sent.append(data['data']['raw']['length'])
                            bytes_sent_without_lost.append(
                                data['data']['raw']['length'])
                            bytes_lost_early.append(0)
                            bytes_lost.append(0)
                    else:
                        print("skip non-stream packet {} after stream fin".format(
                            data['data']['header']['packet_number']))

    for i in range(1, len(bytes_sent_x)):
        bytes_lost_early[i] += bytes_lost_early[i-1]
        bytes_lost[i] += bytes_lost[i-1]
        bytes_sent[i] += bytes_sent[i-1]
        bytes_sent_without_lost[i] += bytes_sent_without_lost[i-1]
        if bytes_sent_x[i] in pkt_lost_time_map.keys():
            bytes_sent_without_lost[i] -= pkt_lost_time_map[bytes_sent_x[i]]
            bytes_lost_early[i] += pkt_lost_time_map[bytes_sent_x[i]]

    for i in range(len(bytes_sent_x)):
        bytes_lost[i] = -bytes_lost[i]
        bytes_lost_early[i] = -bytes_lost_early[i]

    bytes_target.append(0)
    bytes_target_up.append(mul * bdw * rtt * 125)
    for i in range(1, len(bytes_sent_x)):
        bytes_target.append(
            min(bytes_target[i-1] + mul * bdw * 125 * (bytes_sent_x[i] - bytes_sent_x[i-1]), bytes_sent_without_lost[i]))
        bytes_target_up.append(bytes_target[i] + bytes_target_up[0])

        if bytes_sent_without_lost[i] < bytes_target[i-1] + mul * bdw * 125 * (bytes_sent_x[i] - bytes_sent_x[i-1]):
            limit_by_sent_x.append(bytes_sent_x[i-1])
            limit_by_sent.append(bytes_sent_without_lost[i-1])
            limit_by_sent_x.append(bytes_sent_x[i])
            limit_by_sent.append(bytes_sent_without_lost[i])

    if bytes_sent_without_lost[-1] == bytes_target[-1]:
        bytes_sent_x.append(bytes_sent_x[-1])
        bytes_sent.append(bytes_sent[-1])
        bytes_sent_without_lost.append(bytes_sent_without_lost[-1])
        bytes_lost_early.append(bytes_lost_early[-1])
        bytes_lost.append(bytes_lost[-1])
        bytes_target.append(bytes_target[-1])
        bytes_target_up.append(bytes_target_up[-1])
    else:
        bytes_sent_x.append(
            (bytes_sent_without_lost[-1] - bytes_target[-1]) / (mul * bdw * 125) + bytes_sent_x[-1])
        bytes_sent.append(bytes_sent[-1])
        bytes_sent_without_lost.append(bytes_sent_without_lost[-1])
        bytes_lost_early.append(bytes_lost_early[-1])
        bytes_lost.append(bytes_lost[-1])
        bytes_target.append(bytes_sent_without_lost[-1])
        bytes_target_up.append(bytes_target[-1] + bytes_target_up[0])

    print("start_time:", start_time)

    return x, bytes_sent_x, bytes_sent, bytes_sent_without_lost, bytes_lost_early, bytes_lost, bytes_target, bytes_target_up, limit_by_sent_x, limit_by_sent


def collect(flow_size, rtt, bdw, mul):
    src = "flow{}k_rtt{}_base{}_mul{}".format(flow_size, rtt, bdw, mul)

    filename1 = F1_prefix + '_' + src + F1_suffix
    filename2 = F2_prefix + '_' + src + F2_suffix

    x_1, smoothed_rtt_1, latest_rtt_1, congestion_window_1, bytes_in_flight_1, ssthresh_x_1, ssthresh_1, packet_lost_1 = load_qlog_basic(
        logdir, filename1)

    x_2, smoothed_rtt_2, latest_rtt_2, congestion_window_2, bytes_in_flight_2, ssthresh_x_2, ssthresh_2, packet_lost_2 = load_qlog_basic(
        logdir, filename2)

    fig, ax = plt.subplots(
        nrows=10,
        gridspec_kw={'height_ratios': [3, 2, 2, 2, 2, 2, 2, 2, 2, 2]}
    )
    fig.set_figwidth(15)
    fig.set_figheight(40)
    fig.suptitle(
        "RTT: {} ms; BDP: {:.0f} Bytes -> {:.0f} Bytes; Bandwidth: {} Mbps -> {:.1f} Mbps ({:.0%})".format(
            rtt, bdw * rtt * 125, bdw * mul * rtt * 125, bdw, bdw * mul, mul), fontsize=20)
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
    plt.savefig(os.path.join(logdir, src + '.png'))


def analysize_congestion(flow_size, rtt, bdw, mul, show_sum=True):
    src = "flow{}k_rtt{}_base{}_mul{}".format(flow_size, rtt, bdw, mul)

    filename1 = F1_prefix + '_' + src + F1_suffix
    filename2 = F2_prefix + '_' + src + F2_suffix

    x_1,  bytes_sent_x_1, bytes_sent_1, bytes_sent_without_lost_1, bytes_lost_early_1, bytes_lost_1, bytes_target_1, bytes_target_up_1, limit_by_sent_x_1, limit_by_sent_1 = load_qlog_analysize_congestion(
        logdir, filename1, rtt, bdw, mul)

    x_2,  bytes_sent_x_2, bytes_sent_2, bytes_sent_without_lost_2, bytes_lost_early_2, bytes_lost_2, bytes_target_2, bytes_target_up_2, limit_by_sent_x_2, limit_by_sent_2 = load_qlog_analysize_congestion(
        logdir, filename2, rtt, bdw, mul)

    fig, ax = plt.subplots(
        nrows=2
    )
    fig.set_figwidth(15)
    fig.set_figheight(20)
    fig.suptitle(
        "RTT: {} ms; BDP: {:.0f} Bytes -> {:.0f} Bytes; Bandwidth: {} Mbps -> {:.1f} Mbps ({:.0%})".format(
            rtt, bdw * rtt * 125, bdw * mul * rtt * 125, bdw, bdw * mul, mul), fontsize=20)
    id = 0

    # ----- F1: Analysis -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].plot(limit_by_sent_x_1, limit_by_sent_1,
                color=colors[-4], linestyle="None", marker='v', markersize=7)

    ax[id].plot(bytes_sent_x_1, bytes_target_1, color=colors[-3],
                label='Target')
    ax[id].plot(bytes_sent_x_1, bytes_target_up_1,
                color=colors[-3], linestyle="--")
    if show_sum:
        ax[id].plot(bytes_sent_x_1, np.array(bytes_sent_1) -
                    np.array(bytes_lost_1), color=colors[-1], label='Bytes Sent')
    ax[id].plot(bytes_sent_x_1, bytes_sent_1, color=colors[0],
                label='Bytes Sent - Lost')
    ax[id].plot(bytes_sent_x_1, bytes_sent_without_lost_1,
                color=colors[0], linestyle=":")
    ax[id].plot(bytes_sent_x_1, bytes_lost_1, color=colors[3],
                label='Bytes Lost')
    ax[id].plot(bytes_sent_x_1, bytes_lost_early_1,
                color=colors[3],  linestyle=":")

    ax[id].axvline(x_1[0], color=colors[-3], linestyle="--")
    ax[id].axvline(bytes_sent_x_1[0], color=colors[-3], linestyle=":")
    ax[id].axvline(bytes_sent_x_1[-2], color=colors[-3], linestyle=":")

    ax[id].axvline(bytes_sent_x_1[-1], color=colors[0], linestyle=":")
    ax[id].axvline(x_1[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    offset_y += bytes_lost_early_1[-1]
    ax[id].text(bytes_sent_x_1[-1] + offset_x, offset_y, "Last pkt: {:.0f} ms".format(bytes_sent_x_1[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))
    ax[id].text(x_1[-1] + offset_x, offset_y, "F1: {:.0f} ms".format(x_1[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].set_xlim(0, max(x_1[-1], x_2[-1]))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Bytes')
    ax[id].set_title(F1 + ' Congestion Analysis', size=15)
    id += 1

    # ----- F2: Analysis -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].plot(limit_by_sent_x_2, limit_by_sent_2,
                color=colors[-4], linestyle="None", marker='v', markersize=7)

    ax[id].plot(bytes_sent_x_2, bytes_target_2, color=colors[-3],
                label='Target')
    ax[id].plot(bytes_sent_x_2, bytes_target_up_2,
                color=colors[-3], linestyle="--")
    if show_sum:
        ax[id].plot(bytes_sent_x_2, np.array(bytes_sent_2) -
                    np.array(bytes_lost_2), color=colors[-1], label='Bytes Sent')
    ax[id].plot(bytes_sent_x_2, bytes_sent_2, color=colors[0],
                label='Bytes Sent - Lost')
    ax[id].plot(bytes_sent_x_2, bytes_sent_without_lost_2,
                color=colors[0], linestyle=":")
    ax[id].plot(bytes_sent_x_2, bytes_lost_2, color=colors[3],
                label='Bytes Lost')
    ax[id].plot(bytes_sent_x_2, bytes_lost_early_2,
                color=colors[3],  linestyle=":")

    ax[id].axvline(x_2[0], color=colors[-3], linestyle="--")
    ax[id].axvline(bytes_sent_x_2[0], color=colors[-3], linestyle=":")
    ax[id].axvline(bytes_sent_x_2[-2], color=colors[-3], linestyle=":")

    ax[id].axvline(bytes_sent_x_2[-1], color=colors[0], linestyle=":")
    ax[id].axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    offset_y += bytes_lost_early_2[-1]
    ax[id].text(bytes_sent_x_2[-1] + offset_x, offset_y, "Last pkt: {:.0f} ms".format(bytes_sent_x_2[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))
    ax[id].text(x_2[-1] + offset_x, offset_y, "F2: {:.0f} ms".format(x_2[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].set_xlim(0, max(x_1[-1], x_2[-1]))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Bytes')
    ax[id].set_title(F2 + ' Congestion Analysis', size=15)
    id += 1

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.15, top=0.93)
    plt.savefig(os.path.join(logdir, src + '_analysis.png'))


for flow_size in flow_list:
    for rtt in rtt_list:
        for bdw in BDW_list:
            for mul in mul_list:
                collect(flow_size, rtt, bdw, mul)
                analysize_congestion(flow_size, rtt, bdw, mul)
