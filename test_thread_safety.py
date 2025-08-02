#!/usr/bin/env python3

import sqlite3
import threading
import queue
import time
from datetime import datetime

class ThreadSafeDatabaseManager:
    """Thread-safe database manager using a worker thread and queue"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.operation_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        # Initialize database in worker thread
        self._execute_operation('init_db', None, None)
    
    def _worker(self):
        """Worker thread that handles all database operations"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode for better concurrency
        
        while True:
            try:
                operation = self.operation_queue.get(timeout=1)
                if operation is None:  # Shutdown signal
                    break
                
                op_type, query, params = operation
                
                try:
                    if op_type == 'init_db':
                        cursor = conn.cursor()
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS print_history (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                url TEXT NOT NULL,
                                print_type TEXT,
                                qr_data TEXT,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                status TEXT DEFAULT 'completed'
                            )
                        ''')
                        conn.commit()
                        self.result_queue.put(('success', None))
                        
                    elif op_type == 'insert':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        conn.commit()
                        self.result_queue.put(('success', cursor.lastrowid))
                        
                    elif op_type == 'update':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        conn.commit()
                        self.result_queue.put(('success', cursor.rowcount))
                        
                    elif op_type == 'delete':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        conn.commit()
                        self.result_queue.put(('success', cursor.rowcount))
                        
                    elif op_type == 'select':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        results = cursor.fetchall()
                        self.result_queue.put(('success', results))
                        
                    elif op_type == 'select_one':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        result = cursor.fetchone()
                        self.result_queue.put(('success', result))
                        
                except Exception as e:
                    self.result_queue.put(('error', str(e)))
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.result_queue.put(('error', str(e)))
        
        conn.close()
    
    def _execute_operation(self, op_type, query, params, timeout=5):
        """Execute a database operation and return the result"""
        self.operation_queue.put((op_type, query, params))
        
        try:
            status, result = self.result_queue.get(timeout=timeout)
            if status == 'error':
                raise Exception(f"Database error: {result}")
            return result
        except queue.Empty:
            raise Exception("Database operation timed out")
    
    def insert(self, query, params):
        """Insert data and return the last row id"""
        return self._execute_operation('insert', query, params)
    
    def update(self, query, params):
        """Update data and return the number of affected rows"""
        return self._execute_operation('update', query, params)
    
    def delete(self, query, params):
        """Delete data and return the number of affected rows"""
        return self._execute_operation('delete', query, params)
    
    def select(self, query, params=None):
        """Select multiple rows"""
        return self._execute_operation('select', query, params or ())
    
    def select_one(self, query, params=None):
        """Select a single row"""
        return self._execute_operation('select_one', query, params or ())
    
    def close(self):
        """Close the database manager"""
        self.operation_queue.put(None)
        self.worker_thread.join(timeout=2)

def test_concurrent_operations(db_manager, thread_id):
    """Test concurrent database operations"""
    try:
        print(f"Thread {thread_id}: Starting operations")
        
        # Insert test data
        for i in range(3):
            row_id = db_manager.insert('''
                INSERT INTO print_history (url, print_type, qr_data, status)
                VALUES (?, ?, ?, ?)
            ''', (f'https://test-thread{thread_id}-{i}.com', 'label', f'label:test{i}', 'processing'))
            print(f"Thread {thread_id}: Inserted row {row_id}")
            
        # Update status
        affected = db_manager.update('''
            UPDATE print_history 
            SET status = 'completed' 
            WHERE url LIKE ?
        ''', (f'%thread{thread_id}%',))
        print(f"Thread {thread_id}: Updated {affected} rows")
        
        # Select data
        results = db_manager.select('''
            SELECT COUNT(*) FROM print_history 
            WHERE url LIKE ?
        ''', (f'%thread{thread_id}%',))
        print(f"Thread {thread_id}: Found {results[0][0]} records")
        
        print(f"Thread {thread_id}: All operations completed successfully")
        return True
        
    except Exception as e:
        print(f"Thread {thread_id}: Error - {e}")
        return False

def main():
    print("Testing SQLite thread safety...")
    
    # Clean up any existing test database
    import os
    if os.path.exists('test_thread_safety.db'):
        os.remove('test_thread_safety.db')
    
    # Create thread-safe database manager
    db_manager = ThreadSafeDatabaseManager('test_thread_safety.db')
    
    # Test concurrent access with multiple threads
    threads = []
    results = []
    
    def worker(thread_id):
        result = test_concurrent_operations(db_manager, thread_id)
        results.append(result)
    
    print("Starting 5 concurrent threads...")
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # Check final results
    total_records = db_manager.select('SELECT COUNT(*) FROM print_history')
    print(f"\nFinal results:")
    print(f"- Total records in database: {total_records[0][0]}")
    print(f"- All threads successful: {all(results)}")
    
    # Show some sample data
    sample_data = db_manager.select('SELECT url, status FROM print_history LIMIT 5')
    print(f"- Sample records:")
    for url, status in sample_data:
        print(f"  {url} -> {status}")
    
    # Clean up
    db_manager.close()
    
    if all(results) and total_records[0][0] == 15:  # 5 threads * 3 inserts each
        print("\n✅ SQLite thread safety test PASSED!")
        print("The ThreadSafeDatabaseManager successfully handles concurrent operations.")
    else:
        print("\n❌ SQLite thread safety test FAILED!")
        print("Some operations failed or data is inconsistent.")

if __name__ == "__main__":
    main()