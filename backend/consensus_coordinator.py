"""
Raft Consensus Implementation
Distributed consensus algorithm for leader election and log replication
"""
import time
import random
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import socket

logger = logging.getLogger(__name__)

class NodeState(Enum):
    """Node states in Raft"""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

@dataclass
class LogEntry:
    """Raft log entry"""
    term: int
    index: int
    command: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class NodeInfo:
    """Cluster node information"""
    node_id: str
    host: str
    port: int
    state: NodeState = NodeState.FOLLOWER
    last_heartbeat: datetime = field(default_factory=datetime.now)

class RaftNode:
    """
    Raft consensus node implementation
    
    Features:
    - Leader election
    - Log replication
    - Safety guarantees
    - Membership changes
    """
    
    def __init__(self, node_id: str, cluster_nodes: List[Dict[str, Any]]):
        self.node_id = node_id
        self.state = NodeState.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []
        self.commit_index = 0
        self.last_applied = 0
        
        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Cluster
        self.cluster_nodes = {n["node_id"]: NodeInfo(**n) for n in cluster_nodes}
        self.leader_id: Optional[str] = None
        
        # Timing
        self.election_timeout = random.uniform(150, 300) / 1000  # 150-300ms
        self.heartbeat_interval = 50 / 1000  # 50ms
        self.last_heartbeat = time.time()
        
        # Threads
        self._running = False
        self._election_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_commit: Optional[Callable] = None
        self.on_leader_change: Optional[Callable] = None
    
    def start(self):
        """Start the Raft node"""
        self._running = True
        self._election_thread = threading.Thread(target=self._election_timer, daemon=True)
        self._election_thread.start()
        logger.info(f"Node {self.node_id} started as {self.state.value}")
    
    def stop(self):
        """Stop the Raft node"""
        self._running = False
        if self._election_thread:
            self._election_thread.join(timeout=1)
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1)
        logger.info(f"Node {self.node_id} stopped")
    
    def _election_timer(self):
        """Election timeout monitor"""
        while self._running:
            if self.state != NodeState.LEADER:
                elapsed = time.time() - self.last_heartbeat
                if elapsed > self.election_timeout:
                    self._start_election()
            time.sleep(0.01)
    
    def _start_election(self):
        """Start leader election"""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        
        logger.info(f"Node {self.node_id} starting election for term {self.current_term}")
        
        votes_received = 1  # Vote for self
        votes_needed = (len(self.cluster_nodes) + 1) // 2 + 1
        
        # Request votes from other nodes
        for node_id in self.cluster_nodes:
            if node_id == self.node_id:
                continue
            
            vote_granted = self._request_vote(node_id)
            if vote_granted:
                votes_received += 1
            
            if votes_received >= votes_needed:
                self._become_leader()
                return
        
        # Election failed, revert to follower
        if self.state == NodeState.CANDIDATE:
            self.state = NodeState.FOLLOWER
            logger.info(f"Node {self.node_id} election failed")
    
    def _request_vote(self, node_id: str) -> bool:
        """Request vote from a node"""
        try:
            node = self.cluster_nodes[node_id]
            last_log_index = len(self.log) - 1
            last_log_term = self.log[-1].term if self.log else 0
            
            request = {
                "type": "RequestVote",
                "term": self.current_term,
                "candidate_id": self.node_id,
                "last_log_index": last_log_index,
                "last_log_term": last_log_term
            }
            
            response = self._send_rpc(node, request)
            
            if response and response.get("vote_granted"):
                logger.debug(f"Vote granted by {node_id}")
                return True
            
            if response and response.get("term", 0) > self.current_term:
                self._step_down(response["term"])
            
        except Exception as e:
            logger.error(f"Error requesting vote from {node_id}: {e}")
        
        return False
    
    def _become_leader(self):
        """Transition to leader state"""
        self.state = NodeState.LEADER
        self.leader_id = self.node_id
        
        # Initialize leader state
        for node_id in self.cluster_nodes:
            self.next_index[node_id] = len(self.log)
            self.match_index[node_id] = 0
        
        logger.info(f"Node {self.node_id} became leader for term {self.current_term}")
        
        if self.on_leader_change:
            self.on_leader_change(self.node_id)
        
        # Start heartbeat thread
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        
        self._heartbeat_thread = threading.Thread(target=self._send_heartbeats, daemon=True)
        self._heartbeat_thread.start()
    
    def _send_heartbeats(self):
        """Send periodic heartbeats to followers"""
        while self._running and self.state == NodeState.LEADER:
            for node_id in self.cluster_nodes:
                if node_id == self.node_id:
                    continue
                self._send_append_entries(node_id)
            time.sleep(self.heartbeat_interval)
    
    def _send_append_entries(self, node_id: str):
        """Send AppendEntries RPC to a follower"""
        try:
            node = self.cluster_nodes[node_id]
            prev_log_index = self.next_index[node_id] - 1
            prev_log_term = self.log[prev_log_index].term if prev_log_index >= 0 else 0
            
            entries = self.log[self.next_index[node_id]:]
            
            request = {
                "type": "AppendEntries",
                "term": self.current_term,
                "leader_id": self.node_id,
                "prev_log_index": prev_log_index,
                "prev_log_term": prev_log_term,
                "entries": [self._serialize_entry(e) for e in entries],
                "leader_commit": self.commit_index
            }
            
            response = self._send_rpc(node, request)
            
            if response:
                if response.get("success"):
                    if entries:
                        self.next_index[node_id] += len(entries)
                        self.match_index[node_id] = self.next_index[node_id] - 1
                        self._update_commit_index()
                else:
                    self.next_index[node_id] = max(0, self.next_index[node_id] - 1)
                
                if response.get("term", 0) > self.current_term:
                    self._step_down(response["term"])
        
        except Exception as e:
            logger.error(f"Error sending append entries to {node_id}: {e}")
    
    def _update_commit_index(self):
        """Update commit index based on majority"""
        if self.state != NodeState.LEADER:
            return
        
        for n in range(self.commit_index + 1, len(self.log)):
            if self.log[n].term != self.current_term:
                continue
            
            replicated_count = 1  # Leader has it
            for node_id in self.cluster_nodes:
                if self.match_index.get(node_id, 0) >= n:
                    replicated_count += 1
            
            if replicated_count >= (len(self.cluster_nodes) + 1) // 2 + 1:
                self.commit_index = n
                self._apply_committed_entries()
    
    def _apply_committed_entries(self):
        """Apply committed log entries"""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied]
            
            if self.on_commit:
                self.on_commit(entry.command)
            
            logger.debug(f"Applied entry {self.last_applied}: {entry.command}")
    
    def _step_down(self, new_term: int):
        """Step down to follower"""
        self.current_term = new_term
        self.state = NodeState.FOLLOWER
        self.voted_for = None
        self.leader_id = None
        logger.info(f"Node {self.node_id} stepped down to follower")
    
    def _send_rpc(self, node: NodeInfo, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send RPC to a node"""
        try:
            # Simulate network call
            # In production, use actual RPC (gRPC, HTTP, etc.)
            return {"success": True, "term": self.current_term}
        except Exception as e:
            logger.error(f"RPC error to {node.node_id}: {e}")
            return None
    
    def _serialize_entry(self, entry: LogEntry) -> Dict[str, Any]:
        """Serialize log entry"""
        return {
            "term": entry.term,
            "index": entry.index,
            "command": entry.command,
            "timestamp": entry.timestamp.isoformat()
        }
    
    def append_entry(self, command: Dict[str, Any]) -> bool:
        """Append entry to log (leader only)"""
        if self.state != NodeState.LEADER:
            logger.warning("Only leader can append entries")
            return False
        
        entry = LogEntry(
            term=self.current_term,
            index=len(self.log),
            command=command
        )
        self.log.append(entry)
        logger.info(f"Leader appended entry {entry.index}")
        return True
    
    def handle_request_vote(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RequestVote RPC"""
        term = request["term"]
        candidate_id = request["candidate_id"]
        last_log_index = request["last_log_index"]
        last_log_term = request["last_log_term"]
        
        if term > self.current_term:
            self._step_down(term)
        
        vote_granted = False
        
        if term >= self.current_term:
            if self.voted_for is None or self.voted_for == candidate_id:
                my_last_index = len(self.log) - 1
                my_last_term = self.log[-1].term if self.log else 0
                
                if (last_log_term > my_last_term or 
                    (last_log_term == my_last_term and last_log_index >= my_last_index)):
                    self.voted_for = candidate_id
                    self.last_heartbeat = time.time()
                    vote_granted = True
        
        return {
            "term": self.current_term,
            "vote_granted": vote_granted
        }
    
    def handle_append_entries(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle AppendEntries RPC"""
        term = request["term"]
        leader_id = request["leader_id"]
        prev_log_index = request["prev_log_index"]
        prev_log_term = request["prev_log_term"]
        entries = request["entries"]
        leader_commit = request["leader_commit"]
        
        if term > self.current_term:
            self._step_down(term)
        
        if term >= self.current_term:
            self.state = NodeState.FOLLOWER
            self.leader_id = leader_id
            self.last_heartbeat = time.time()
        
        success = False
        
        if term == self.current_term:
            if prev_log_index < 0 or (
                prev_log_index < len(self.log) and 
                self.log[prev_log_index].term == prev_log_term
            ):
                # Append entries
                insert_index = prev_log_index + 1
                for i, entry_data in enumerate(entries):
                    entry = LogEntry(
                        term=entry_data["term"],
                        index=entry_data["index"],
                        command=entry_data["command"]
                    )
                    if insert_index + i < len(self.log):
                        self.log[insert_index + i] = entry
                    else:
                        self.log.append(entry)
                
                if leader_commit > self.commit_index:
                    self.commit_index = min(leader_commit, len(self.log) - 1)
                    self._apply_committed_entries()
                
                success = True
        
        return {
            "term": self.current_term,
            "success": success
        }
    
    def get_state(self) -> Dict[str, Any]:
        """Get current node state"""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "leader_id": self.leader_id,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied
        }

class ConsensusCoordinator:
    """Coordinator for managing Raft cluster"""
    
    def __init__(self):
        self.nodes: Dict[str, RaftNode] = {}
        self.cluster_config: List[Dict[str, Any]] = []
    
    def add_node(self, node_id: str, host: str, port: int):
        """Add node to cluster"""
        node_config = {"node_id": node_id, "host": host, "port": port}
        self.cluster_config.append(node_config)
        
        node = RaftNode(node_id, self.cluster_config)
        self.nodes[node_id] = node
        logger.info(f"Added node {node_id} to cluster")
    
    def start_cluster(self):
        """Start all nodes"""
        for node in self.nodes.values():
            node.start()
        logger.info("Cluster started")
    
    def stop_cluster(self):
        """Stop all nodes"""
        for node in self.nodes.values():
            node.stop()
        logger.info("Cluster stopped")
    
    def get_leader(self) -> Optional[str]:
        """Get current leader"""
        for node in self.nodes.values():
            if node.state == NodeState.LEADER:
                return node.node_id
        return None
    
    def get_cluster_state(self) -> Dict[str, Any]:
        """Get cluster state"""
        return {
            "nodes": {nid: n.get_state() for nid, n in self.nodes.items()},
            "leader": self.get_leader()
        }
