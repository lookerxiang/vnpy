# encoding: utf-8
import re
import subprocess

if __name__ == '__main__':
    id_pos = -1
    id_list = []

    # 读取进程一览表
    output = subprocess.check_output(r'wmic process where (caption like "%python2%") get processid,commandline',
                                     universal_newlines=True)
    for line in output.split('\n'):
        line = line.strip()

        if not line:
            continue

        # 判断进程ID所在列
        if re.match(r'((CommandLine|ProcessId)\s*){2}', line):
            id_pos = 0 if line.split()[0].startswith('ProcessId') else -1
            continue

        id_list.append(line.split()[id_pos])

        # 停止各进程
        for target in id_list:
            subprocess.call(r'wmic process where processid="%s" call terminate' % target)
