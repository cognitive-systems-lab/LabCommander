import daemon

import time

iterations = 5

def doit():
    for i in range(iterations):
        print(i)
        time.sleep(1)
    print("finish")


with daemon.DaemonContext():
    doit()
