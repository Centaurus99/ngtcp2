#!/usr/bin/python3

import os
from queue import Queue
import threading
import time

basedir = "./run/work"
run_file = "./run/worker.sh"

if (os.path.exists(os.path.join(basedir, "threads", "logs")) == False):
    os.makedirs(os.path.join(basedir, "threads", "logs"))

BASE_BW_MUL_list = [2]
DATA_SIZE_KB_list = [1024]
loss_list = [0.0]
DELAY_1_list = [20]
DELAY_2_list = DELAY_1_list
bw_mul_list = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
               1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]
cc_list = ['cubic', 'scubic', 'scubic2']
# cc_list = ['fixed']
port_range = [40200, 40220]
repeats = 10


class Worker(threading.Thread):
    def __init__(self, queue, port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue
        self.port = port
        self.logfile = os.path.join(
            basedir, "threads", "logs", "worker{}.log".format(self.port))
        os.system('date +"%Y-%m-%d %H:%M:%S" > {}'.format(self.logfile))

    def run(self):
        while True:
            command = self.queue.get()
            command = command + \
                " {} {} >> {} 2>&1".format(self.port, repeats, self.logfile)
            print("Running {}".format(command))
            os.system(command)
            print("Done {}".format(command))
            self.queue.task_done()


if __name__ == "__main__":
    queue = Queue((port_range[1] - port_range[0]) * 2)
    for port in range(port_range[0], port_range[1]):
        worker = Worker(queue, port)
        worker.daemon = True
        worker.start()

    for BASE_BW_MUL in BASE_BW_MUL_list:
        for DATA_SIZE_KB in DATA_SIZE_KB_list:
            for loss in loss_list:
                for DELAY_1 in DELAY_1_list:
                    DELAY_2 = DELAY_1
                    for bw_mul in bw_mul_list:
                        for cc in cc_list:
                            command = run_file + " {} {} {} {} {} {} {}".format(
                                DATA_SIZE_KB, BASE_BW_MUL, bw_mul, DELAY_1, DELAY_2, loss, cc)
                            queue.put(command)
                            time.sleep(1)

    queue.join()

    print("Done")
