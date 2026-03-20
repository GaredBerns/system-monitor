#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/F/C2_server')
from autoreg_worker import kaggle_login

logs = []
def log(msg):
    logs.append(msg)
    print(msg, flush=True)

result = kaggle_login("62s0odfwdxfu@usa.priyo.edu.pl", "7i2xlAvZ$K&7", log)
