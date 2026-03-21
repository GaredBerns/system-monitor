"""Database batch operations for C2 Server"""
from typing import List, Dict, Any
from contextlib import contextmanager
import sqlite3
from queue import Queue
import threading
import time

class ConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.pool.put(conn)
    
    @contextmanager
    def get_connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)

class BatchOperations:
    def __init__(self, pool: ConnectionPool, batch_size: int = 100):
        self.pool = pool
        self.batch_size = batch_size
        self.pending = []
        self.lock = threading.Lock()
        self.last_flush = time.time()
        
    def add(self, query: str, params: tuple):
        with self.lock:
            self.pending.append((query, params))
            if len(self.pending) >= self.batch_size:
                self.flush()
    
    def flush(self):
        with self.lock:
            if not self.pending:
                return
            
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                for query, params in self.pending:
                    cursor.execute(query, params)
                conn.commit()
            
            self.pending.clear()
            self.last_flush = time.time()
    
    def auto_flush(self, interval: int = 5):
        if time.time() - self.last_flush > interval:
            self.flush()

def bulk_insert(conn, table: str, records: List[Dict[str, Any]]):
    if not records:
        return
    
    columns = list(records[0].keys())
    placeholders = ','.join(['?' for _ in columns])
    query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
    
    cursor = conn.cursor()
    cursor.executemany(query, [tuple(r[c] for c in columns) for r in records])
    conn.commit()

def bulk_update(conn, table: str, records: List[Dict[str, Any]], key_column: str):
    if not records:
        return
    
    columns = [c for c in records[0].keys() if c != key_column]
    set_clause = ','.join([f"{c}=?" for c in columns])
    query = f"UPDATE {table} SET {set_clause} WHERE {key_column}=?"
    
    cursor = conn.cursor()
    cursor.executemany(query, [tuple(list(r[c] for c in columns) + [r[key_column]]) for r in records])
    conn.commit()
