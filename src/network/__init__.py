"""
Network module for the blockchain implementation.
Handles peer-to-peer communication, message routing, and network management.
Includes Tor v3 support for enhanced privacy.
"""

from .protocol import Message, MessageType, Protocol
from .config import NetworkConfig
from .connection_manager import ConnectionManager, PeerConnection
from .message_handler import MessageHandler
from .sync_manager import SyncManager, SyncState
from .metrics import NetworkMetrics, PeerMetrics
from .security import SecurityManager
from .rate_limiter import RateLimiter, TokenBucket, PeerLimits
from .error_handler import (
    ErrorHandler,
    NetworkError,
    ErrorType,
    ErrorSeverity
)
from .tor_network import TorNetwork

__all__ = [
    'Message',
    'MessageType',
    'Protocol',
    'NetworkConfig',
    'ConnectionManager',
    'PeerConnection',
    'MessageHandler',
    'SyncManager',
    'SyncState',
    'NetworkMetrics',
    'PeerMetrics',
    'SecurityManager',
    'RateLimiter',
    'TokenBucket',
    'PeerLimits',
    'ErrorHandler',
    'NetworkError',
    'ErrorType',
    'ErrorSeverity',
    'TorNetwork',
    'initialize_network'
]

async def initialize_network(
    blockchain,
    validator=None,
    host="0.0.0.0",
    port=None
):
    """
    Initialize and start the network components.
    
    Args:
        blockchain: The blockchain instance
        validator: Optional validator instance
        host: Host to bind to (default: "0.0.0.0")
        port: Port to listen on (default: NetworkConfig.DEFAULT_PORT)
    
    Returns:
        tuple: (connection_manager, sync_manager, metrics, security_manager,
               rate_limiter, error_handler, tor_network)
    """
    # Initialize components
    metrics = NetworkMetrics()
    security_manager = SecurityManager()
    rate_limiter = RateLimiter()
    error_handler = ErrorHandler(metrics)
    
    # Initialize Tor if enabled
    tor_network = None
    if NetworkConfig.USE_TOR:
        tor_network = TorNetwork(
            hidden_service_dir=NetworkConfig.TOR_HIDDEN_SERVICE_DIR
        )
        try:
            await tor_network.start()
        except Exception as e:
            error_handler.handle_error(
                NetworkError(
                    error_type=ErrorType.INTERNAL_ERROR,
                    severity=ErrorSeverity.CRITICAL,
                    message=f"Failed to start Tor network: {str(e)}"
                )
            )
            raise
    
    # Create connection manager
    connection_manager = ConnectionManager(blockchain, validator)
    
    # Create sync manager
    sync_manager = SyncManager(blockchain, connection_manager, validator)
    
    # Start network components
    try:
        # Start connection manager
        await connection_manager.start(
            host=host,
            port=port or NetworkConfig.DEFAULT_PORT
        )
        
        # Start sync manager
        await sync_manager.start()
        
        return (
            connection_manager,
            sync_manager,
            metrics,
            security_manager,
            rate_limiter,
            error_handler,
            tor_network
        )
        
    except Exception as e:
        # Clean up on error
        await connection_manager.stop()
        await sync_manager.stop()
        if tor_network:
            await tor_network.stop()
        raise NetworkError(
            error_type=ErrorType.INTERNAL_ERROR,
            severity=ErrorSeverity.CRITICAL,
            message=f"Failed to initialize network: {str(e)}"
        ) 