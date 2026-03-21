"""Message queue for distributed C2 task processing"""
import json
import time
from typing import Optional, Callable
import threading

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class TaskQueue:
    def __init__(self, redis_host='localhost', redis_port=6379):
        if REDIS_AVAILABLE:
            self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        else:
            self.redis = None
        self.local_queue = []
        self.workers = []
    
    def enqueue(self, queue_name: str, task: dict):
        """Add task to queue"""
        if self.redis:
            self.redis.rpush(queue_name, json.dumps(task))
        else:
            self.local_queue.append((queue_name, task))
    
    def dequeue(self, queue_name: str, timeout: int = 0) -> Optional[dict]:
        """Get task from queue"""
        if self.redis:
            result = self.redis.blpop(queue_name, timeout=timeout)
            if result:
                return json.loads(result[1])
        else:
            for i, (qname, task) in enumerate(self.local_queue):
                if qname == queue_name:
                    self.local_queue.pop(i)
                    return task
        return None
    
    def size(self, queue_name: str) -> int:
        """Get queue size"""
        if self.redis:
            return self.redis.llen(queue_name)
        return sum(1 for qname, _ in self.local_queue if qname == queue_name)
    
    def worker(self, queue_name: str, handler: Callable, count: int = 1):
        """Start worker threads"""
        def work():
            while True:
                task = self.dequeue(queue_name, timeout=1)
                if task:
                    try:
                        handler(task)
                    except Exception as e:
                        print(f"Worker error: {e}")
        
        for _ in range(count):
            t = threading.Thread(target=work, daemon=True)
            t.start()
            self.workers.append(t)

task_queue = TaskQueue()
