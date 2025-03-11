import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
import logging
from prometheus_client import Counter, Gauge, Histogram
import structlog

@dataclass
class PeerMetrics:
    """Metrics for a single peer."""
    node_id: str
    connected_at: float
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    latency_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    errors: int = 0
    last_seen: float = field(default_factory=time.time)

class NetworkMetrics:
    """Collects and manages network metrics."""
    
    def __init__(self):
        """Initialize network metrics."""
        self.peers: Dict[str, PeerMetrics] = {}
        self.logger = structlog.get_logger(__name__)
        
        # Prometheus metrics
        self.connected_peers = Gauge(
            'blockchain_connected_peers',
            'Number of connected peers'
        )
        
        self.messages_total = Counter(
            'blockchain_messages_total',
            'Total number of messages',
            ['type', 'direction']
        )
        
        self.bytes_total = Counter(
            'blockchain_bytes_total',
            'Total number of bytes',
            ['direction']
        )
        
        self.message_size = Histogram(
            'blockchain_message_size_bytes',
            'Size of messages in bytes',
            ['type']
        )
        
        self.message_latency = Histogram(
            'blockchain_message_latency_seconds',
            'Message processing latency in seconds',
            ['type']
        )
        
        self.peer_errors = Counter(
            'blockchain_peer_errors_total',
            'Total number of peer errors',
            ['peer_id', 'error_type']
        )
    
    def add_peer(self, node_id: str) -> None:
        """Add a new peer to track."""
        if node_id not in self.peers:
            self.peers[node_id] = PeerMetrics(
                node_id=node_id,
                connected_at=time.time()
            )
            self.connected_peers.inc()
            self.logger.info("peer_connected", peer_id=node_id)
    
    def remove_peer(self, node_id: str) -> None:
        """Remove a peer from tracking."""
        if node_id in self.peers:
            del self.peers[node_id]
            self.connected_peers.dec()
            self.logger.info("peer_disconnected", peer_id=node_id)
    
    def record_message_sent(
        self,
        node_id: str,
        message_type: str,
        size: int,
        latency: float
    ) -> None:
        """Record metrics for a sent message."""
        if node_id in self.peers:
            peer = self.peers[node_id]
            peer.messages_sent += 1
            peer.bytes_sent += size
            peer.last_seen = time.time()
            
            self.messages_total.labels(type=message_type, direction='sent').inc()
            self.bytes_total.labels(direction='sent').inc(size)
            self.message_size.labels(type=message_type).observe(size)
            self.message_latency.labels(type=message_type).observe(latency)
            
            self.logger.debug(
                "message_sent",
                peer_id=node_id,
                type=message_type,
                size=size,
                latency=latency
            )
    
    def record_message_received(
        self,
        node_id: str,
        message_type: str,
        size: int,
        latency: float
    ) -> None:
        """Record metrics for a received message."""
        if node_id in self.peers:
            peer = self.peers[node_id]
            peer.messages_received += 1
            peer.bytes_received += size
            peer.last_seen = time.time()
            peer.latency_samples.append(latency)
            
            self.messages_total.labels(type=message_type, direction='received').inc()
            self.bytes_total.labels(direction='received').inc(size)
            self.message_size.labels(type=message_type).observe(size)
            self.message_latency.labels(type=message_type).observe(latency)
            
            self.logger.debug(
                "message_received",
                peer_id=node_id,
                type=message_type,
                size=size,
                latency=latency
            )
    
    def record_error(self, node_id: str, error_type: str) -> None:
        """Record a peer error."""
        if node_id in self.peers:
            peer = self.peers[node_id]
            peer.errors += 1
            
            self.peer_errors.labels(
                peer_id=node_id,
                error_type=error_type
            ).inc()
            
            self.logger.warning(
                "peer_error",
                peer_id=node_id,
                error_type=error_type
            )
    
    def get_peer_stats(self, node_id: str) -> Optional[Dict]:
        """Get statistics for a specific peer."""
        if node_id not in self.peers:
            return None
        
        peer = self.peers[node_id]
        avg_latency = (
            sum(peer.latency_samples) / len(peer.latency_samples)
            if peer.latency_samples
            else 0
        )
        
        return {
            "node_id": peer.node_id,
            "connected_duration": time.time() - peer.connected_at,
            "messages_sent": peer.messages_sent,
            "messages_received": peer.messages_received,
            "bytes_sent": peer.bytes_sent,
            "bytes_received": peer.bytes_received,
            "average_latency": avg_latency,
            "errors": peer.errors,
            "last_seen": time.time() - peer.last_seen
        }
    
    def get_network_stats(self) -> Dict:
        """Get overall network statistics."""
        total_messages_sent = sum(p.messages_sent for p in self.peers.values())
        total_messages_received = sum(p.messages_received for p in self.peers.values())
        total_bytes_sent = sum(p.bytes_sent for p in self.peers.values())
        total_bytes_received = sum(p.bytes_received for p in self.peers.values())
        total_errors = sum(p.errors for p in self.peers.values())
        
        # Calculate average latency across all peers
        all_latencies = [
            sample
            for peer in self.peers.values()
            for sample in peer.latency_samples
        ]
        avg_network_latency = (
            sum(all_latencies) / len(all_latencies)
            if all_latencies
            else 0
        )
        
        return {
            "connected_peers": len(self.peers),
            "total_messages_sent": total_messages_sent,
            "total_messages_received": total_messages_received,
            "total_bytes_sent": total_bytes_sent,
            "total_bytes_received": total_bytes_received,
            "average_network_latency": avg_network_latency,
            "total_errors": total_errors
        }
    
    def get_peer_list(self) -> List[Dict]:
        """Get a list of all peer statistics."""
        return [
            self.get_peer_stats(node_id)
            for node_id in self.peers.keys()
        ] 