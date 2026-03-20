#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/F/C2_server')
from autoreg_worker import kaggle_login

logs = []
def log(msg):
    logs.append(msg)
    print(msg, flush=True)

result = kaggle_login("utp5jzpj7kuo@bseee.okcx.edu.rs", "h6Il3!ru6%CK", log)
