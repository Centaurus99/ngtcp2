import argparse
from math import ceil, floor

FILE_DIR = './run/traces/'
MAX_MUL = 2

parser = argparse.ArgumentParser()
parser.add_argument('multiple', type=int,
                    help='Multiples of 12Mbps bandwidth')
args = parser.parse_args()


def write_to_file(filename, time_list):
    with open(FILE_DIR + filename, 'w') as f:
        for i in time_list:
            f.write(str(i) + '\n')


time_list = []
for i in range(10):
    time_list = time_list + [i + 1] * args.multiple * MAX_MUL

for i in range(1, 10 * MAX_MUL + 1):
    length = args.multiple * i
    now_list = [time_list[floor((j + 1) * len(time_list) / length) - 1]
                for j in range(length)]
    write_to_file(str(i / 10) + '.trace', now_list)
    # print(i, length, now_list)
