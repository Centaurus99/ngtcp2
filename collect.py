import matplotlib.pyplot as plt
import json
import os

logdir = "./run/logs/server_log"

src_list = [
    'server_0.1',
    'server_0.2',
    'server_0.3',
    'server_0.4',
    'server_0.5',
    'server_0.6',
    'server_0.7',
    'server_0.8',
    'server_0.9',
    'server_1.0',
    'server_1.1',
    'server_1.2',
    'server_1.3',
    'server_1.4',
    'server_1.5',
    'server_1.6',
    'server_1.7',
    'server_1.8',
    'server_1.9',
    'server_2.0',
]

for src in src_list:
    x_1 = []
    smoothed_rtt_1 = []
    latest_rtt_1 = []
    congestion_window_1 = []
    bytes_in_flight_1 = []

    x_2 = []
    smoothed_rtt_2 = []
    latest_rtt_2 = []
    congestion_window_2 = []
    bytes_in_flight_2 = []

    print("loading " + os.path.join(logdir, src + '_1.sqlog'))
    with open(os.path.join(logdir, src + '_1.sqlog'), 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            if 'name' in data.keys() and data['name'] == 'recovery:metrics_updated':
                x_1.append(data['time'])
                smoothed_rtt_1.append(data['data']['smoothed_rtt'])
                latest_rtt_1.append(data['data']['latest_rtt'])
                congestion_window_1.append(
                    data['data']['congestion_window'])
                bytes_in_flight_1.append(
                    data['data']['bytes_in_flight'])

    print("loading " + os.path.join(logdir, src + '_2.sqlog'))
    with open(os.path.join(logdir, src + '_2.sqlog'), 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            if 'name' in data.keys() and data['name'] == 'recovery:metrics_updated':
                x_2.append(data['time'])
                smoothed_rtt_2.append(data['data']['smoothed_rtt'])
                latest_rtt_2.append(data['data']['latest_rtt'])
                congestion_window_2.append(
                    data['data']['congestion_window'])
                bytes_in_flight_2.append(
                    data['data']['bytes_in_flight'])

    plt.figure(figsize=(10, 8))
    plt.subplot(2, 2, 1)
    plt.plot(x_1, congestion_window_1, label='congestion_window_1')
    plt.plot(x_2, congestion_window_2, label='congestion_window_2')
    plt.legend()
    plt.subplot(2, 2, 2)
    plt.plot(x_1, bytes_in_flight_1, label='bytes_in_flight_1')
    plt.plot(x_2, bytes_in_flight_2, label='bytes_in_flight_2')
    plt.legend()
    plt.subplot(2, 2, 3)
    plt.plot(x_1, latest_rtt_1, label='latest_rtt_1')
    plt.plot(x_2, latest_rtt_2, label='latest_rtt_2')
    plt.legend()
    plt.subplot(2, 2, 4)
    plt.plot(x_1, smoothed_rtt_1, label='smoothed_rtt_1')
    plt.plot(x_2, smoothed_rtt_2, label='smoothed_rtt_2')
    plt.legend()

    plt.savefig(os.path.join(logdir, src + '.png'))
