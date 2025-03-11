from dataclasses import dataclass
from typing import List, Optional
import os
from dotenv import load_dotenv

@dataclass
class NetworkConfig:
    """Network configuration settings."""
    
    # Load environment variables
    load_dotenv()
    
    # Network settings
    DEFAULT_PORT = int(os.getenv("DEFAULT_PORT", 8333))
    MAX_PEERS = int(os.getenv("MAX_PEERS", 10))
    PING_INTERVAL = int(os.getenv("PING_INTERVAL", 30))  # seconds
    PEER_DISCOVERY_INTERVAL = int(os.getenv("PEER_DISCOVERY_INTERVAL", 300))  # seconds
    CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", 10))  # seconds
    
    # Protocol settings
    PROTOCOL_VERSION = "1.0.0"
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    
    # Security settings
    MIN_PEERS_FOR_SYNC = 3
    MAX_BLOCK_SIZE = 1024 * 1024  # 1MB
    MAX_TRANSACTIONS_PER_BLOCK = 1000
    
    # Tor settings
    USE_TOR = os.getenv("USE_TOR", "true").lower() == "true"
    TOR_SOCKS_PORT = int(os.getenv("TOR_SOCKS_PORT", 9050))
    TOR_CONTROL_PORT = int(os.getenv("TOR_CONTROL_PORT", 9051))
    TOR_SERVICE_PORT = int(os.getenv("TOR_SERVICE_PORT", 8334))
    TOR_CONTROL_PASSWORD = os.getenv("TOR_CONTROL_PASSWORD", "")
    TOR_DATA_DIR = os.getenv("TOR_DATA_DIR", "tor_data")
    TOR_HIDDEN_SERVICE_DIR = os.getenv("TOR_HIDDEN_SERVICE_DIR", "hidden_service")
    
    # Bootstrap nodes (Tor and clearnet)
    BOOTSTRAP_NODES: List[str] = [
        node.strip() 
        for node in os.getenv("BOOTSTRAP_NODES", "").split(",") 
        if node.strip()
    ]
    
    # Tor bootstrap nodes (onion addresses)
    TOR_BOOTSTRAP_NODES: List[str] = [
        node.strip()
        for node in os.getenv("TOR_BOOTSTRAP_NODES", "").split(",")
        if node.strip() and node.strip().endswith(".onion")
    ]
    
    # Network identity
    NODE_ID = os.getenv("NODE_ID", "")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate the configuration."""
        if not cls.NODE_ID:
            raise ValueError("NODE_ID must be set in environment variables")
        
        if cls.DEFAULT_PORT < 1024 or cls.DEFAULT_PORT > 65535:
            raise ValueError("DEFAULT_PORT must be between 1024 and 65535")
        
        if cls.MAX_PEERS < 1:
            raise ValueError("MAX_PEERS must be greater than 0")
        
        if cls.PING_INTERVAL < 1:
            raise ValueError("PING_INTERVAL must be greater than 0")
        
        if cls.PEER_DISCOVERY_INTERVAL < 1:
            raise ValueError("PEER_DISCOVERY_INTERVAL must be greater than 0")
        
        if cls.CONNECTION_TIMEOUT < 1:
            raise ValueError("CONNECTION_TIMEOUT must be greater than 0")
        
        if cls.USE_TOR:
            if cls.TOR_SOCKS_PORT < 1024 or cls.TOR_SOCKS_PORT > 65535:
                raise ValueError("TOR_SOCKS_PORT must be between 1024 and 65535")
            
            if cls.TOR_CONTROL_PORT < 1024 or cls.TOR_CONTROL_PORT > 65535:
                raise ValueError("TOR_CONTROL_PORT must be between 1024 and 65535")
            
            if cls.TOR_SERVICE_PORT < 1024 or cls.TOR_SERVICE_PORT > 65535:
                raise ValueError("TOR_SERVICE_PORT must be between 1024 and 65535")
        
        return True
    
    @classmethod
    def get_bootstrap_nodes(cls) -> List[str]:
        """Get the list of bootstrap nodes."""
        if cls.USE_TOR:
            return cls.TOR_BOOTSTRAP_NODES
        return cls.BOOTSTRAP_NODES
    
    @classmethod
    def get_node_id(cls) -> str:
        """Get the node ID."""
        return cls.NODE_ID
    
    @classmethod
    def get_default_port(cls) -> int:
        """Get the default port."""
        return cls.DEFAULT_PORT
    
    @classmethod
    def get_max_peers(cls) -> int:
        """Get the maximum number of peers."""
        return cls.MAX_PEERS
    
    @classmethod
    def get_ping_interval(cls) -> int:
        """Get the ping interval in seconds."""
        return cls.PING_INTERVAL
    
    @classmethod
    def get_peer_discovery_interval(cls) -> int:
        """Get the peer discovery interval in seconds."""
        return cls.PEER_DISCOVERY_INTERVAL
    
    @classmethod
    def get_connection_timeout(cls) -> int:
        """Get the connection timeout in seconds."""
        return cls.CONNECTION_TIMEOUT 