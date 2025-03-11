import time
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging
import structlog
from .config import NetworkConfig

@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: float
    fill_rate: float
    tokens: float = field(init=False)
    last_update: float = field(init=False)
    
    def __post_init__(self):
        self.tokens = self.capacity
        self.last_update = time.time()
    
    def consume(self, tokens: float) -> bool:
        """Consume tokens from the bucket."""
        now = time.time()
        
        # Add tokens based on time elapsed
        elapsed = now - self.last_update
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.fill_rate
        )
        self.last_update = now
        
        # Check if enough tokens are available
        if tokens <= self.tokens:
            self.tokens -= tokens
            return True
        
        return False

@dataclass
class PeerLimits:
    """Rate limits for a single peer."""
    node_id: str
    message_bucket: TokenBucket
    bandwidth_bucket: TokenBucket
    request_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    blocked_until: float = 0

class RateLimiter:
    """Manages rate limiting for network operations."""
    
    def __init__(self):
        """Initialize the rate limiter."""
        self.logger = structlog.get_logger(__name__)
        self.peers: Dict[str, PeerLimits] = {}
        
        # Default limits
        self.default_message_rate = 100  # messages per second
        self.default_bandwidth_rate = 1024 * 1024  # 1MB per second
        self.burst_multiplier = 2.0  # Allow bursts up to 2x the normal rate
        
        # Request tracking
        self.request_window = 60  # 1 minute
        self.max_requests_per_window = 1000
        
        # Blocking
        self.block_duration = 300  # 5 minutes
        self.violation_threshold = 3
        
        # Track overall network usage
        self.global_message_bucket = TokenBucket(
            capacity=self.default_message_rate * 10,  # 10x for all peers combined
            fill_rate=self.default_message_rate * 10
        )
        self.global_bandwidth_bucket = TokenBucket(
            capacity=self.default_bandwidth_rate * 10,
            fill_rate=self.default_bandwidth_rate * 10
        )
    
    def add_peer(self, node_id: str) -> None:
        """Add a new peer to rate limit."""
        if node_id not in self.peers:
            self.peers[node_id] = PeerLimits(
                node_id=node_id,
                message_bucket=TokenBucket(
                    capacity=self.default_message_rate * self.burst_multiplier,
                    fill_rate=self.default_message_rate
                ),
                bandwidth_bucket=TokenBucket(
                    capacity=self.default_bandwidth_rate * self.burst_multiplier,
                    fill_rate=self.default_bandwidth_rate
                )
            )
            self.logger.info("Added rate limits for peer", peer_id=node_id)
    
    def remove_peer(self, node_id: str) -> None:
        """Remove a peer from rate limiting."""
        self.peers.pop(node_id, None)
    
    def is_allowed(
        self,
        node_id: str,
        message_type: str,
        size: int
    ) -> Tuple[bool, Optional[str]]:
        """Check if an operation is allowed under rate limits."""
        try:
            # Check if peer exists
            if node_id not in self.peers:
                return False, "Peer not registered"
            
            peer = self.peers[node_id]
            now = time.time()
            
            # Check if peer is blocked
            if peer.blocked_until > now:
                return False, f"Peer blocked for {peer.blocked_until - now:.1f} seconds"
            
            # Check global limits first
            if not self.global_message_bucket.consume(1):
                return False, "Global message rate limit exceeded"
            
            if not self.global_bandwidth_bucket.consume(size):
                return False, "Global bandwidth limit exceeded"
            
            # Check peer-specific limits
            if not peer.message_bucket.consume(1):
                return False, "Peer message rate limit exceeded"
            
            if not peer.bandwidth_bucket.consume(size):
                return False, "Peer bandwidth limit exceeded"
            
            # Track request
            peer.request_history.append((now, message_type, size))
            
            # Check request frequency
            self._check_request_frequency(peer)
            
            return True, None
            
        except Exception as e:
            self.logger.error(
                "Error checking rate limits",
                peer_id=node_id,
                error=str(e)
            )
            return False, f"Internal error: {str(e)}"
    
    def _check_request_frequency(self, peer: PeerLimits) -> None:
        """Check request frequency and block if necessary."""
        now = time.time()
        window_start = now - self.request_window
        
        # Remove old requests
        while (
            peer.request_history and
            peer.request_history[0][0] < window_start
        ):
            peer.request_history.popleft()
        
        # Check request count in window
        if len(peer.request_history) > self.max_requests_per_window:
            self._block_peer(peer)
    
    def _block_peer(self, peer: PeerLimits) -> None:
        """Block a peer for repeated violations."""
        now = time.time()
        
        if peer.blocked_until > now:
            # Already blocked, extend duration
            peer.blocked_until = now + (self.block_duration * 2)
        else:
            # New block
            peer.blocked_until = now + self.block_duration
        
        self.logger.warning(
            "Blocked peer for rate limit violations",
            peer_id=peer.node_id,
            duration=peer.blocked_until - now
        )
    
    def update_limits(
        self,
        node_id: str,
        message_rate: Optional[float] = None,
        bandwidth_rate: Optional[float] = None
    ) -> bool:
        """Update rate limits for a peer."""
        try:
            if node_id not in self.peers:
                return False
            
            peer = self.peers[node_id]
            
            if message_rate is not None:
                peer.message_bucket = TokenBucket(
                    capacity=message_rate * self.burst_multiplier,
                    fill_rate=message_rate
                )
            
            if bandwidth_rate is not None:
                peer.bandwidth_bucket = TokenBucket(
                    capacity=bandwidth_rate * self.burst_multiplier,
                    fill_rate=bandwidth_rate
                )
            
            self.logger.info(
                "Updated rate limits for peer",
                peer_id=node_id,
                message_rate=message_rate,
                bandwidth_rate=bandwidth_rate
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Error updating rate limits",
                peer_id=node_id,
                error=str(e)
            )
            return False
    
    def get_peer_stats(self, node_id: str) -> Optional[Dict]:
        """Get rate limiting statistics for a peer."""
        if node_id not in self.peers:
            return None
        
        peer = self.peers[node_id]
        now = time.time()
        
        return {
            "node_id": peer.node_id,
            "message_tokens": peer.message_bucket.tokens,
            "bandwidth_tokens": peer.bandwidth_bucket.tokens,
            "requests_in_window": len(peer.request_history),
            "is_blocked": peer.blocked_until > now,
            "block_remaining": max(0, peer.blocked_until - now)
        }
    
    def get_global_stats(self) -> Dict:
        """Get global rate limiting statistics."""
        return {
            "global_message_tokens": self.global_message_bucket.tokens,
            "global_bandwidth_tokens": self.global_bandwidth_bucket.tokens,
            "total_peers": len(self.peers),
            "blocked_peers": sum(
                1 for p in self.peers.values()
                if p.blocked_until > time.time()
            )
        } 