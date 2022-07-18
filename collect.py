import matplotlib.pyplot as plt
import json
import os

logdir = "./build/examples/server_log"

if os.path.exists(logdir):
    # root 所指的是当前正在遍历的这个文件夹的本身的地址
    # dirs 是一个 list，内容是该文件夹中所有的目录的名字(不包括子目录)
    # files 同样是 list, 内容是该文件夹中所有的文件(不包括子目录)
    for root, dirs, files in os.walk(logdir):
        for file in files:
            src_file = os.path.join(root, file)
            if (src_file[-6:] == ".sqlog"):
                print(src_file)
                x = []
                smoothed_rtt = []
                latest_rtt = []
                congestion_window = []
                bytes_in_flight = []
                with open(src_file, 'r') as f:
                    for line in f:
                        data = json.loads(line.strip())
                        if 'name' in data.keys() and data['name'] == 'recovery:metrics_updated':
                            x.append(data['time'])
                            smoothed_rtt.append(data['data']['smoothed_rtt'])
                            latest_rtt.append(data['data']['latest_rtt'])
                            congestion_window.append(
                                data['data']['congestion_window'])
                            bytes_in_flight.append(
                                data['data']['bytes_in_flight'])
                plt.figure(figsize=(10, 5))
                plt.subplot(2, 2, 1)
                plt.plot(x, latest_rtt, label='latest_rtt')
                plt.plot(x, smoothed_rtt, label='smoothed_rtt')
                plt.legend()
                plt.subplot(2, 2, 2)
                plt.plot(x, congestion_window, label='congestion_window')
                plt.legend()
                plt.subplot(2, 2, 3)
                plt.plot(x, bytes_in_flight, label='bytes_in_flight')
                plt.legend()
                plt.savefig(src_file[:-6]+'.png')
