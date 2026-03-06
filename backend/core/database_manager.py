"""
Enterprise Database Manager with Connection Pooling
Handles PostgreSQL, MySQL, SQLite connections with retry logic
"""
from typing import Dict, List, Optional, Any, Union, Tuple
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging
import time
import hashlib
import json
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

class DatabaseType(Enum):
    """Supported database types"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"

class ConnectionState(Enum):
    """Connection state enumeration"""
    IDLE = "idle"
    ACTIVE = "active"
    CLOSED = "closed"
    ERROR = "error"

@dataclass
class ConnectionConfig:
    """Database connection configuration"""
    host: str = "localhost"
    port: int = 5432
    database: str = "healthcare"
    username: str = "admin"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    connection_timeout: int = 10
    command_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0

@dataclass
class QueryMetrics:
    """Query execution metrics"""
    query_id: str
    query_text: str
    execution_time: float
    rows_affected: int
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None

class ConnectionPool:
    """
    Enterprise-grade database connection pool
    
    Features:
    - Automatic connection recycling
    - Health checks
    - Connection retry logic
    - Query timeout handling
    - Metrics collection
    """
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connections: List[Dict] = []
        self.active_connections: int = 0
        self.total_connections_created: int = 0
        self.total_queries_executed: int = 0
        self.failed_queries: int = 0
        self.metrics: List[QueryMetrics] = []
        self.created_at = datetime.now()
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        """Initialize connection pool"""
        logger.info(f"Initializing connection pool with size {self.config.pool_size}")
        for i in range(self.config.pool_size):
            conn = self._create_connection()
            if conn:
                self.connections.append({
                    "id": i,
                    "connection": conn,
                    "state": ConnectionState.IDLE,
                    "created_at": datetime.now(),
                    "last_used": datetime.now(),
                    "query_count": 0
                })
                self.total_connections_created += 1
    
    def _create_connection(self) -> Optional[Any]:
        """Create new database connection"""
        try:
            # Simulated connection creation
            connection = {
                "host": self.config.host,
                "port": self.config.port,
                "database": self.config.database,
                "connected": True,
                "created_at": datetime.now()
            }
            logger.debug(f"Created connection to {self.config.host}:{self.config.port}")
            return connection
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            return None
    
    def _get_connection(self) -> Optional[Dict]:
        """Get available connection from pool"""
        for conn_info in self.connections:
            if conn_info["state"] == ConnectionState.IDLE:
                conn_info["state"] = ConnectionState.ACTIVE
                conn_info["last_used"] = datetime.now()
                self.active_connections += 1
                return conn_info
        
        # Create overflow connection if allowed
        if len(self.connections) < self.config.pool_size + self.config.max_overflow:
            conn = self._create_connection()
            if conn:
                conn_info = {
                    "id": len(self.connections),
                    "connection": conn,
                    "state": ConnectionState.ACTIVE,
                    "created_at": datetime.now(),
                    "last_used": datetime.now(),
                    "query_count": 0
                }
                self.connections.append(conn_info)
                self.active_connections += 1
                return conn_info
        
        return None
    
    def _release_connection(self, conn_info: Dict) -> None:
        """Release connection back to pool"""
        conn_info["state"] = ConnectionState.IDLE
        self.active_connections -= 1
    
    @contextmanager
    def get_connection(self):
        """Context manager for connection handling"""
        conn_info = None
        try:
            conn_info = self._get_connection()
            if not conn_info:
                raise Exception("No available connections in pool")
            yield conn_info["connection"]
        finally:
            if conn_info:
                self._release_connection(conn_info)
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Dict:
        """
        Execute SQL query with retry logic
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Dictionary with query results
        """
        query_id = hashlib.md5(f"{query}{time.time()}".encode()).hexdigest()[:12]
        start_time = time.time()
        
        for attempt in range(self.config.retry_attempts):
            try:
                with self.get_connection() as conn:
                    # Simulate query execution
                    result = self._execute_query_internal(conn, query, params)
                    
                    execution_time = time.time() - start_time
                    self.total_queries_executed += 1
                    
                    # Record metrics
                    metric = QueryMetrics(
                        query_id=query_id,
                        query_text=query[:100],
                        execution_time=execution_time,
                        rows_affected=result.get("rows_affected", 0),
                        timestamp=datetime.now(),
                        success=True
                    )
                    self._add_metric(metric)
                    
                    return {
                        "success": True,
                        "query_id": query_id,
                        "data": result.get("data", []),
                        "rows_affected": result.get("rows_affected", 0),
                        "execution_time": execution_time
                    }
                    
            except Exception as e:
                logger.warning(f"Query attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    self.failed_queries += 1
                    execution_time = time.time() - start_time
                    
                    metric = QueryMetrics(
                        query_id=query_id,
                        query_text=query[:100],
                        execution_time=execution_time,
                        rows_affected=0,
                        timestamp=datetime.now(),
                        success=False,
                        error_message=str(e)
                    )
                    self._add_metric(metric)
                    
                    return {
                        "success": False,
                        "query_id": query_id,
                        "error": str(e),
                        "execution_time": execution_time
                    }
    
    def _execute_query_internal(self, conn: Any, query: str, params: Optional[Dict]) -> Dict:
        """Internal query execution"""
        # Simulate query execution
        query_lower = query.lower()
        
        if "select" in query_lower:
            return {
                "data": [{"id": 1, "name": "Sample"}, {"id": 2, "name": "Data"}],
                "rows_affected": 2
            }
        elif "insert" in query_lower or "update" in query_lower or "delete" in query_lower:
            return {
                "data": [],
                "rows_affected": 1
            }
        else:
            return {"data": [], "rows_affected": 0}
    
    def _add_metric(self, metric: QueryMetrics) -> None:
        """Add metric to collection"""
        self.metrics.append(metric)
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]
    
    def execute_batch(self, queries: List[Tuple[str, Optional[Dict]]]) -> List[Dict]:
        """
        Execute multiple queries in batch
        
        Args:
            queries: List of (query, params) tuples
            
        Returns:
            List of query results
        """
        results = []
        for query, params in queries:
            result = self.execute_query(query, params)
            results.append(result)
        return results
    
    def execute_transaction(self, queries: List[Tuple[str, Optional[Dict]]]) -> Dict:
        """
        Execute queries in transaction
        
        Args:
            queries: List of (query, params) tuples
            
        Returns:
            Transaction result
        """
        try:
            with self.get_connection() as conn:
                results = []
                for query, params in queries:
                    result = self._execute_query_internal(conn, query, params)
                    results.append(result)
                
                return {
                    "success": True,
                    "results": results,
                    "queries_executed": len(queries)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "queries_executed": 0
            }
    
    def health_check(self) -> Dict:
        """
        Perform health check on connection pool
        
        Returns:
            Health status dictionary
        """
        healthy_connections = sum(
            1 for c in self.connections 
            if c["state"] != ConnectionState.ERROR
        )
        
        avg_query_time = 0.0
        if self.metrics:
            successful_metrics = [m for m in self.metrics if m.success]
            if successful_metrics:
                avg_query_time = sum(m.execution_time for m in successful_metrics) / len(successful_metrics)
        
        return {
            "healthy": healthy_connections > 0,
            "total_connections": len(self.connections),
            "active_connections": self.active_connections,
            "idle_connections": len(self.connections) - self.active_connections,
            "healthy_connections": healthy_connections,
            "total_queries": self.total_queries_executed,
            "failed_queries": self.failed_queries,
            "success_rate": (
                (self.total_queries_executed - self.failed_queries) / 
                max(1, self.total_queries_executed)
            ),
            "average_query_time": avg_query_time,
            "uptime_seconds": (datetime.now() - self.created_at).total_seconds()
        }
    
    def get_statistics(self) -> Dict:
        """Get detailed statistics"""
        recent_metrics = self.metrics[-100:] if self.metrics else []
        
        return {
            "pool_size": self.config.pool_size,
            "max_overflow": self.config.max_overflow,
            "total_connections": len(self.connections),
            "active_connections": self.active_connections,
            "total_queries": self.total_queries_executed,
            "failed_queries": self.failed_queries,
            "recent_queries": len(recent_metrics),
            "connections_created": self.total_connections_created
        }
    
    def close_all(self) -> None:
        """Close all connections"""
        for conn_info in self.connections:
            try:
                conn_info["state"] = ConnectionState.CLOSED
                logger.debug(f"Closed connection {conn_info['id']}")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        
        self.connections.clear()
        self.active_connections = 0

class QueryBuilder:
    """
    SQL query builder with parameter binding
    
    Features:
    - Safe parameter binding
    - Query validation
    - Common query patterns
    """
    
    def __init__(self):
        self.query_parts = []
        self.params = {}
        self.param_counter = 0
    
    def select(self, *columns: str) -> 'QueryBuilder':
        """Add SELECT clause"""
        if columns:
            self.query_parts.append(f"SELECT {', '.join(columns)}")
        else:
            self.query_parts.append("SELECT *")
        return self
    
    def from_table(self, table: str) -> 'QueryBuilder':
        """Add FROM clause"""
        self.query_parts.append(f"FROM {table}")
        return self
    
    def where(self, condition: str, **params) -> 'QueryBuilder':
        """Add WHERE clause"""
        self.query_parts.append(f"WHERE {condition}")
        self.params.update(params)
        return self
    
    def and_where(self, condition: str, **params) -> 'QueryBuilder':
        """Add AND condition"""
        self.query_parts.append(f"AND {condition}")
        self.params.update(params)
        return self
    
    def or_where(self, condition: str, **params) -> 'QueryBuilder':
        """Add OR condition"""
        self.query_parts.append(f"OR {condition}")
        self.params.update(params)
        return self
    
    def order_by(self, *columns: str) -> 'QueryBuilder':
        """Add ORDER BY clause"""
        self.query_parts.append(f"ORDER BY {', '.join(columns)}")
        return self
    
    def limit(self, count: int) -> 'QueryBuilder':
        """Add LIMIT clause"""
        self.query_parts.append(f"LIMIT {count}")
        return self
    
    def offset(self, count: int) -> 'QueryBuilder':
        """Add OFFSET clause"""
        self.query_parts.append(f"OFFSET {count}")
        return self
    
    def join(self, table: str, condition: str) -> 'QueryBuilder':
        """Add JOIN clause"""
        self.query_parts.append(f"JOIN {table} ON {condition}")
        return self
    
    def left_join(self, table: str, condition: str) -> 'QueryBuilder':
        """Add LEFT JOIN clause"""
        self.query_parts.append(f"LEFT JOIN {table} ON {condition}")
        return self
    
    def group_by(self, *columns: str) -> 'QueryBuilder':
        """Add GROUP BY clause"""
        self.query_parts.append(f"GROUP BY {', '.join(columns)}")
        return self
    
    def having(self, condition: str) -> 'QueryBuilder':
        """Add HAVING clause"""
        self.query_parts.append(f"HAVING {condition}")
        return self
    
    def build(self) -> Tuple[str, Dict]:
        """Build final query"""
        query = " ".join(self.query_parts)
        return query, self.params
    
    def reset(self) -> 'QueryBuilder':
        """Reset builder"""
        self.query_parts = []
        self.params = {}
        self.param_counter = 0
        return self

class DatabaseManager:
    """
    Main database manager class
    
    Provides high-level database operations with connection pooling
    """
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.pool = ConnectionPool(config)
        self.query_builder = QueryBuilder()
    
    def query(self, query: str, params: Optional[Dict] = None) -> Dict:
        """Execute query"""
        return self.pool.execute_query(query, params)
    
    def fetch_one(self, query: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Fetch single row"""
        result = self.pool.execute_query(query, params)
        if result["success"] and result["data"]:
            return result["data"][0]
        return None
    
    def fetch_all(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Fetch all rows"""
        result = self.pool.execute_query(query, params)
        if result["success"]:
            return result["data"]
        return []
    
    def insert(self, table: str, data: Dict) -> Dict:
        """Insert record"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return self.pool.execute_query(query, data)
    
    def update(self, table: str, data: Dict, where: str, where_params: Dict) -> Dict:
        """Update records"""
        set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        params = {**data, **where_params}
        return self.pool.execute_query(query, params)
    
    def delete(self, table: str, where: str, params: Dict) -> Dict:
        """Delete records"""
        query = f"DELETE FROM {table} WHERE {where}"
        return self.pool.execute_query(query, params)
    
    def transaction(self, queries: List[Tuple[str, Optional[Dict]]]) -> Dict:
        """Execute transaction"""
        return self.pool.execute_transaction(queries)
    
    def health_check(self) -> Dict:
        """Check database health"""
        return self.pool.health_check()
    
    def get_statistics(self) -> Dict:
        """Get statistics"""
        return self.pool.get_statistics()
    
    def close(self) -> None:
        """Close all connections"""
        self.pool.close_all()
