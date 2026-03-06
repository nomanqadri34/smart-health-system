"""
Distributed Lock Manager
Provides distributed locking mechanisms using Redis backend
"""
import redis
import time
import uuid
import threading
import logging
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LockStatus(Enum):
    """Lock status enumeration"""
    ACQUIRED = "acquired"
    RELEASED = "released"
    EXPIRED = "expired"
    FAILED = "failed"

@dataclass
class LockInfo:
    """Lock information"""
    lock_id: str
    resource: str
    owner: str
    acquired_at: datetime
    expires_at: datetime
    ttl: int
    status: LockStatus

class DistributedLockManager:
    """
    Distributed lock manager using Redis
    
    Features:
    - Automatic lock expiration
    - Lock renewal
    - Deadlock prevention
    - Fair locking
    - Lock monitoring
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.locks: Dict[str, LockInfo] = {}
        self.lock_prefix = "dlock:"
        self.default_ttl = 30
        self._renewal_threads: Dict[str, threading.Thread] = {}
        self._stop_renewal: Dict[str, threading.Event] = {}
        
    def acquire_lock(self, resource: str, ttl: int = None, 
                    timeout: int = 10, retry_interval: float = 0.1) -> Optional[str]:
        """
        Acquire a distributed lock
        
        Args:
            resource: Resource to lock
            ttl: Time to live in seconds
            timeout: Max time to wait for lock
            retry_interval: Retry interval in seconds
            
        Returns:
            Lock ID if acquired, None otherwise
        """
        ttl = ttl or self.default_ttl
        lock_id = str(uuid.uuid4())
        owner = f"{os.getpid()}_{threading.get_ident()}"
        key = f"{self.lock_prefix}{resource}"
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Try to acquire lock using SET NX EX
            acquired = self.redis_client.set(
                key, 
                json.dumps({"lock_id": lock_id, "owner": owner}),
                nx=True,
                ex=ttl
            )
            
            if acquired:
                lock_info = LockInfo(
                    lock_id=lock_id,
                    resource=resource,
                    owner=owner,
                    acquired_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(seconds=ttl),
                    ttl=ttl,
                    status=LockStatus.ACQUIRED
                )
                self.locks[lock_id] = lock_info
                logger.info(f"Lock acquired: {resource} by {owner}")
                return lock_id
                
            time.sleep(retry_interval)
        
        logger.warning(f"Failed to acquire lock: {resource}")
        return None
    
    def release_lock(self, lock_id: str) -> bool:
        """Release a distributed lock"""
        if lock_id not in self.locks:
            logger.warning(f"Lock not found: {lock_id}")
            return False
            
        lock_info = self.locks[lock_id]
        key = f"{self.lock_prefix}{lock_info.resource}"
        
        # Lua script for atomic release
        lua_script = """
        local key = KEYS[1]
        local lock_data = ARGV[1]
        local current = redis.call('GET', key)
        if current == lock_data then
            return redis.call('DEL', key)
        end
        return 0
        """
        
        lock_data = json.dumps({
            "lock_id": lock_id,
            "owner": lock_info.owner
        })
        
        result = self.redis_client.eval(lua_script, 1, key, lock_data)
        
        if result:
            lock_info.status = LockStatus.RELEASED
            self._stop_lock_renewal(lock_id)
            logger.info(f"Lock released: {lock_info.resource}")
            return True
        
        logger.warning(f"Failed to release lock: {lock_id}")
        return False
    
    def renew_lock(self, lock_id: str, ttl: int = None) -> bool:
        """Renew lock expiration"""
        if lock_id not in self.locks:
            return False
            
        lock_info = self.locks[lock_id]
        ttl = ttl or lock_info.ttl
        key = f"{self.lock_prefix}{lock_info.resource}"
        
        # Extend expiration
        result = self.redis_client.expire(key, ttl)
        
        if result:
            lock_info.expires_at = datetime.now() + timedelta(seconds=ttl)
            logger.debug(f"Lock renewed: {lock_info.resource}")
            return True
        
        return False
    
    def start_auto_renewal(self, lock_id: str, interval: int = 10):
        """Start automatic lock renewal"""
        if lock_id not in self.locks:
            return
            
        stop_event = threading.Event()
        self._stop_renewal[lock_id] = stop_event
        
        def renewal_worker():
            while not stop_event.is_set():
                if not self.renew_lock(lock_id):
                    logger.error(f"Failed to renew lock: {lock_id}")
                    break
                stop_event.wait(interval)
        
        thread = threading.Thread(target=renewal_worker, daemon=True)
        thread.start()
        self._renewal_threads[lock_id] = thread
    
    def _stop_lock_renewal(self, lock_id: str):
        """Stop automatic renewal"""
        if lock_id in self._stop_renewal:
            self._stop_renewal[lock_id].set()
            if lock_id in self._renewal_threads:
                self._renewal_threads[lock_id].join(timeout=1)
                del self._renewal_threads[lock_id]
            del self._stop_renewal[lock_id]
    
    @contextmanager
    def lock(self, resource: str, ttl: int = None, timeout: int = 10):
        """Context manager for distributed lock"""
        lock_id = self.acquire_lock(resource, ttl, timeout)
        if not lock_id:
            raise TimeoutError(f"Failed to acquire lock: {resource}")
        
        try:
            yield lock_id
        finally:
            self.release_lock(lock_id)
    
    def get_lock_info(self, lock_id: str) -> Optional[LockInfo]:
        """Get lock information"""
        return self.locks.get(lock_id)
    
    def is_locked(self, resource: str) -> bool:
        """Check if resource is locked"""
        key = f"{self.lock_prefix}{resource}"
        return self.redis_client.exists(key) > 0
    
    def get_lock_owner(self, resource: str) -> Optional[str]:
        """Get current lock owner"""
        key = f"{self.lock_prefix}{resource}"
        data = self.redis_client.get(key)
        if data:
            lock_data = json.loads(data)
            return lock_data.get("owner")
        return None
    
    def force_release(self, resource: str) -> bool:
        """Force release a lock (admin operation)"""
        key = f"{self.lock_prefix}{resource}"
        result = self.redis_client.delete(key)
        logger.warning(f"Force released lock: {resource}")
        return result > 0
    
    def cleanup_expired_locks(self):
        """Clean up expired locks from memory"""
        now = datetime.now()
        expired = [
            lock_id for lock_id, info in self.locks.items()
            if info.expires_at < now
        ]
        for lock_id in expired:
            self.locks[lock_id].status = LockStatus.EXPIRED
            self._stop_lock_renewal(lock_id)
            logger.info(f"Cleaned up expired lock: {lock_id}")
    
    def get_all_locks(self) -> List[LockInfo]:
        """Get all active locks"""
        return list(self.locks.values())
    
    def get_lock_stats(self) -> Dict[str, Any]:
        """Get lock statistics"""
        total = len(self.locks)
        by_status = {}
        for info in self.locks.values():
            status = info.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_locks": total,
            "by_status": by_status,
            "active_renewals": len(self._renewal_threads)
        }

class FairLockManager(DistributedLockManager):
    """Fair lock manager with FIFO queue"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        super().__init__(redis_url)
        self.queue_prefix = "dlock_queue:"
    
    def acquire_lock(self, resource: str, ttl: int = None, 
                    timeout: int = 10, retry_interval: float = 0.1) -> Optional[str]:
        """Acquire lock with FIFO fairness"""
        lock_id = str(uuid.uuid4())
        queue_key = f"{self.queue_prefix}{resource}"
        
        # Add to queue
        self.redis_client.rpush(queue_key, lock_id)
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if we're first in queue
            first = self.redis_client.lindex(queue_key, 0)
            
            if first == lock_id:
                # Try to acquire lock
                result = super().acquire_lock(resource, ttl, 0)
                if result:
                    # Remove from queue
                    self.redis_client.lpop(queue_key)
                    return result
            
            time.sleep(retry_interval)
        
        # Remove from queue on timeout
        self.redis_client.lrem(queue_key, 1, lock_id)
        return None

class ReentrantLockManager(DistributedLockManager):
    """Reentrant lock manager"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        super().__init__(redis_url)
        self.reentrant_counts: Dict[str, int] = {}
    
    def acquire_lock(self, resource: str, ttl: int = None,
                    timeout: int = 10, retry_interval: float = 0.1) -> Optional[str]:
        """Acquire reentrant lock"""
        owner = f"{os.getpid()}_{threading.get_ident()}"
        
        # Check if already owned
        for lock_id, info in self.locks.items():
            if info.resource == resource and info.owner == owner:
                self.reentrant_counts[lock_id] = self.reentrant_counts.get(lock_id, 1) + 1
                logger.debug(f"Reentrant lock: {resource} count={self.reentrant_counts[lock_id]}")
                return lock_id
        
        # Acquire new lock
        lock_id = super().acquire_lock(resource, ttl, timeout, retry_interval)
        if lock_id:
            self.reentrant_counts[lock_id] = 1
        return lock_id
    
    def release_lock(self, lock_id: str) -> bool:
        """Release reentrant lock"""
        if lock_id not in self.reentrant_counts:
            return False
        
        self.reentrant_counts[lock_id] -= 1
        
        if self.reentrant_counts[lock_id] > 0:
            logger.debug(f"Reentrant release: {lock_id} count={self.reentrant_counts[lock_id]}")
            return True
        
        del self.reentrant_counts[lock_id]
        return super().release_lock(lock_id)

class ReadWriteLockManager:
    """Read-write lock manager"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.read_prefix = "rlock:"
        self.write_prefix = "wlock:"
    
    def acquire_read_lock(self, resource: str, ttl: int = 30) -> Optional[str]:
        """Acquire read lock (shared)"""
        lock_id = str(uuid.uuid4())
        key = f"{self.read_prefix}{resource}"
        
        # Increment reader count
        self.redis_client.hincrby(key, "readers", 1)
        self.redis_client.hset(key, lock_id, "1")
        self.redis_client.expire(key, ttl)
        
        logger.info(f"Read lock acquired: {resource}")
        return lock_id
    
    def release_read_lock(self, resource: str, lock_id: str) -> bool:
        """Release read lock"""
        key = f"{self.read_prefix}{resource}"
        
        self.redis_client.hdel(key, lock_id)
        readers = self.redis_client.hincrby(key, "readers", -1)
        
        if readers <= 0:
            self.redis_client.delete(key)
        
        logger.info(f"Read lock released: {resource}")
        return True
    
    def acquire_write_lock(self, resource: str, ttl: int = 30, 
                          timeout: int = 10) -> Optional[str]:
        """Acquire write lock (exclusive)"""
        lock_id = str(uuid.uuid4())
        write_key = f"{self.write_prefix}{resource}"
        read_key = f"{self.read_prefix}{resource}"
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check no readers
            readers = self.redis_client.hget(read_key, "readers")
            if readers and int(readers) > 0:
                time.sleep(0.1)
                continue
            
            # Try to acquire write lock
            acquired = self.redis_client.set(write_key, lock_id, nx=True, ex=ttl)
            if acquired:
                logger.info(f"Write lock acquired: {resource}")
                return lock_id
            
            time.sleep(0.1)
        
        return None
    
    def release_write_lock(self, resource: str, lock_id: str) -> bool:
        """Release write lock"""
        key = f"{self.write_prefix}{resource}"
        
        current = self.redis_client.get(key)
        if current == lock_id:
            self.redis_client.delete(key)
            logger.info(f"Write lock released: {resource}")
            return True
        
        return False

def create_lock_manager(lock_type: str = "standard", **kwargs) -> DistributedLockManager:
    """Factory function to create lock managers"""
    managers = {
        "standard": DistributedLockManager,
        "fair": FairLockManager,
        "reentrant": ReentrantLockManager,
    }
    
    manager_class = managers.get(lock_type, DistributedLockManager)
    return manager_class(**kwargs)
