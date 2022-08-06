import matplotlib.pyplot as plt
import seaborn as sns
import json
import os

colors = sns.color_palette('deep')

logdir = "./run/logs/server_log"

flow_list = [1]
rtt_list = [20]
BDW_list = [12]
mul_list = [0.3, 1.0, 1.7]


def get_offset(ax_, x, y):
    trans1 = ax_.transAxes
    trans2 = ax_.transData.inverted()
    x0, y0 = trans2.transform(trans1.transform((0, 0)))
    x1, y1 = trans2.transform(trans1.transform((x, y)))
    return x1 - x0, y1 - y0


def collect(flow_size, rtt, bdw, mul):
    src = "server_flow{}m_rtt{}_base{}_mul{}".format(flow_size, rtt, bdw, mul)
    x_1 = []
    smoothed_rtt_1 = []
    latest_rtt_1 = []
    congestion_window_1 = []
    bytes_in_flight_1 = []

    ssthresh_x_1 = []
    ssthresh_1 = []

    packet_lost_1 = {}

    x_2 = []
    smoothed_rtt_2 = []
    latest_rtt_2 = []
    congestion_window_2 = []
    bytes_in_flight_2 = []

    ssthresh_x_2 = []
    ssthresh_2 = []

    packet_lost_2 = {}

    print("loading " + os.path.join(logdir, src + '_1.sqlog'))
    with open(os.path.join(logdir, src + '_1.sqlog'), 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            if 'name' not in data.keys():
                continue
            if data['name'] == 'recovery:metrics_updated':
                x_1.append(data['time'])
                smoothed_rtt_1.append(data['data']['smoothed_rtt'])
                latest_rtt_1.append(data['data']['latest_rtt'])
                congestion_window_1.append(
                    data['data']['congestion_window'])
                bytes_in_flight_1.append(
                    data['data']['bytes_in_flight'])
                if 'ssthresh' in data['data']:
                    ssthresh_x_1.append(data['time'])
                    ssthresh_1.append(data['data']['ssthresh'])
            elif data['name'] == 'recovery:packet_lost':
                if data['time'] not in packet_lost_1:
                    packet_lost_1[data['time']] = 0
                packet_lost_1[data['time']] += 1

    print("loading " + os.path.join(logdir, src + '_2.sqlog'))
    with open(os.path.join(logdir, src + '_2.sqlog'), 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            if 'name' not in data.keys():
                continue
            if data['name'] == 'recovery:metrics_updated':
                x_2.append(data['time'])
                smoothed_rtt_2.append(data['data']['smoothed_rtt'])
                latest_rtt_2.append(data['data']['latest_rtt'])
                congestion_window_2.append(
                    data['data']['congestion_window'])
                bytes_in_flight_2.append(
                    data['data']['bytes_in_flight'])
                if 'ssthresh' in data['data']:
                    ssthresh_x_2.append(data['time'])
                    ssthresh_2.append(data['data']['ssthresh'])
            elif data['name'] == 'recovery:packet_lost':
                if data['time'] not in packet_lost_2:
                    packet_lost_2[data['time']] = 0
                packet_lost_2[data['time']] += 1

    fig, ax = plt.subplots(
        nrows=6,
        gridspec_kw={'height_ratios': [2, 1, 1, 2, 2, 2]}
    )
    fig.set_figwidth(15)
    fig.set_figheight(25)
    fig.suptitle(
        "RTT: {} ms; BDP: {:.0f} Bytes -> {:.0f} Bytes; Bandwidth: {} Mbps -> {:.1f} Mbps ({:.0%})".format(
            rtt, bdw * rtt * 125, bdw * mul * rtt * 125, bdw, bdw * mul, mul), fontsize=20)
    id = 0

    # ----- Flow 1 vs Flow 2: CWnd and Packet Lost -----
    ax_2 = ax[id].twinx()
    ax[id].yaxis.tick_right()
    ax[id].yaxis.set_label_position("right")
    ax_2.yaxis.tick_left()
    ax_2.yaxis.set_label_position("left")
    ax_2.grid(linestyle=":", axis='y')

    ax_2.plot(x_1, congestion_window_1,
              color=colors[1], label='congestion_window_1')
    ax_2.plot(x_2, congestion_window_2,
              color=colors[0], label='congestion_window_2')

    ax_2.set_ylim(0)
    ax_2.axvline(x_2[0], color=colors[-3], linestyle="--")

    ax_2.axvline(x_1[-1], color=colors[1], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_1[-1] + offset_x, offset_y, "F1: {:.0f} ms".format(x_1[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax_2.axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_2[-1] + offset_x, offset_y, "F2: {:.0f} ms".format(x_2[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    width = get_offset(ax_2, 0.002, 0.5)[0]
    ax[id].bar(list(packet_lost_1.keys()), list(
        packet_lost_1.values()), width=width, color=colors[-2], label='packet_lost_1')
    ax[id].bar(list(packet_lost_2.keys()), list(
        packet_lost_2.values()), width=width, color=colors[-1], label='packet_lost_2')

    lines, labels = ax[id].get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax[id].legend(lines2 + lines, labels2 + labels)

    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Packet Lost (pkts)')
    ax_2.set_ylabel('CWnd (bytes)')
    ax[id].set_title('Flow 2: RTT', size=15)
    ax[id].set_title('Flow 1 vs Flow 2: CWnd and Packet Lost', size=15)
    id += 1

    RTT_MAX = max(latest_rtt_1[10:] + latest_rtt_2[10:])
    # ----- Flow 1 vs Flow 2: Latest RTT -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].set_ylim(0, RTT_MAX * 1.1)
    ax[id].plot(x_1, latest_rtt_1, color=colors[1], label='latest_rtt_1')
    ax[id].plot(x_2, latest_rtt_2, color=colors[0], label='latest_rtt_2')

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
    ax[id].set_title('Flow 1 vs Flow 2: Latest RTT', size=15)
    id += 1

    # ----- Flow 1 vs Flow 2: Smoothed RTT -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].set_ylim(0, RTT_MAX * 1.1)
    ax[id].plot(x_1, smoothed_rtt_1, color=colors[1], label='smoothed_rtt_1')
    ax[id].plot(x_2, smoothed_rtt_2, color=colors[0], label='smoothed_rtt_2')

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
    ax[id].set_title('Flow 1 vs Flow 2: Smoothed RTT', size=15)
    id += 1

    # ----- Flow 1 vs Flow 2: Bytes in Flight -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].plot(x_1, bytes_in_flight_1, color=colors[1],
                label='bytes_in_flight_1')
    ax[id].plot(x_2, bytes_in_flight_2, color=colors[0],
                label='bytes_in_flight_2')

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
    ax[id].set_ylabel('Bytes in Flight (pkts)')
    ax[id].set_title('Flow 1 vs Flow 2: Bytes in Flight', size=15)
    id += 1

    # ----- Flow 2: CWnd and Packet Lost -----
    ax_2 = ax[id].twinx()
    ax[id].yaxis.tick_right()
    ax[id].yaxis.set_label_position("right")
    ax_2.yaxis.tick_left()
    ax_2.yaxis.set_label_position("left")
    ax_2.grid(linestyle=":", axis='y')

    ax_2.plot(x_2, congestion_window_2,
              color=colors[0], label='congestion_window_2')
    ax_2.set_ylim(0)
    ax_2.axvline(x_2[0], color=colors[-3], linestyle="--")
    ax_2.axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax_2, 0.005, 0.5)
    ax_2.text(x_2[-1] + offset_x, offset_y, "{:.0f} ms".format(x_2[-1]),
              va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].bar(list(packet_lost_2.keys()), list(packet_lost_2.values()), width=get_offset(
        ax_2, 0.002, 0.5)[0], color=colors[3], label='packet_lost_2')

    lines, labels = ax[id].get_legend_handles_labels()
    lines2, labels2 = ax_2.get_legend_handles_labels()
    ax[id].legend(lines2 + lines, labels2 + labels)

    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('Packet Lost (pkts)')
    ax_2.set_ylabel('CWnd (bytes)')
    ax[id].set_title('Flow 2: CWnd and Packet Lost', size=15)
    id += 1

    # ----- Flow 2: RTT -----
    ax[id].grid(linestyle=":", axis='y')

    ax[id].set_ylim(0, max(latest_rtt_2[10:]) * 1.1)
    ax[id].plot(x_2, latest_rtt_2, color=colors[0], label='latest_rtt_2')
    ax[id].plot(x_2, smoothed_rtt_2, color=colors[1], label='smoothed_rtt_2')

    ax[id].set_ylim(0)
    ax[id].axvline(x_2[0], color=colors[-3], linestyle="--")
    ax[id].axvline(x_2[-1], color=colors[0], linestyle="--")
    offset_x, offset_y = get_offset(ax[id], 0.005, 0.5)
    ax[id].text(x_2[-1] + offset_x, offset_y, "{:.0f} ms".format(x_2[-1]),
                va='center', rotation='vertical', bbox=dict(facecolor='white', alpha=0.6, edgecolor='white'))

    ax[id].legend()
    ax[id].set_xlabel('Time (ms)')
    ax[id].set_ylabel('RTT (ms)')
    ax[id].set_title('Flow 2: RTT', size=15)
    id += 1

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.3, top=0.95)
    plt.savefig(os.path.join(logdir, src + '.png'))


for flow_size in flow_list:
    for rtt in rtt_list:
        for bdw in BDW_list:
            for mul in mul_list:
                collect(flow_size, rtt, bdw, mul)
