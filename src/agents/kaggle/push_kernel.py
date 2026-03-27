#!/usr/bin/env python3
import sys, json, time, random, os
sys.path.insert(0, '/mnt/F/C2_server-main')
from src.agents.kaggle.datasets import push_kernel_json

# Unique slug with random suffix to avoid 409 conflict
slug = f'markvega555239/monitor-{int(time.time())}-{random.randint(1000,9999)}'

# Load notebook from same directory
notebook_path = os.path.join(os.path.dirname(__file__), "notebook-debug.ipynb")
with open(notebook_path, "r") as f:
    notebook = json.load(f)

result = push_kernel_json(
    username='markvega555239',
    api_key='41fedf6f7360d8c9247a553ca4fe6c5d',
    notebook_content=json.dumps(notebook),
    kernel_slug=slug,
    title='Resource Monitor',
    enable_internet=True,
    dataset_sources=['markvega555239/resource-monitor'],
    log_fn=print
)
print('Success:', result.get('success'))
print('Kernel:', slug)
