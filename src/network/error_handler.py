from typing import Dict, Optional, List, Any, Callable
import time
import logging
from enum import Enum, auto
import structlog
from .protocol import Message, MessageType
from .metrics import NetworkMetrics

class ErrorType(Enum):
    """Types of network errors."""
    CONNECTION_ERROR = auto()
    PROTOCOL_ERROR = auto()
    AUTHENTICATION_ERROR = auto()
    RATE_LIMIT_ERROR = auto()
    VALIDATION_ERROR = auto()
    SYNC_ERROR = auto()
    PEER_ERROR = auto()
    INTERNAL_ERROR = auto()

class ErrorSeverity(Enum):
    """Severity levels for errors."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class NetworkError(Exception):
    """Custom exception for network errors."""
    
    def __init__(
        self,
        error_type: ErrorType,
        severity: ErrorSeverity,
        message: str,
        details: Optional[Dict] = None
    ):
        self.error_type = error_type
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.timestamp = time.time()
        super().__init__(message)

class ErrorHandler:
    """Handles network-related errors."""
    
    def __init__(self, metrics: NetworkMetrics):
        """Initialize the error handler."""
        self.logger = structlog.get_logger(__name__)
        self.metrics = metrics
        
        # Error counters
        self.error_counts: Dict[ErrorType, int] = {
            error_type: 0 for error_type in ErrorType
        }
        
        # Error history
        self.error_history: List[NetworkError] = []
        self.max_history_size = 1000
        
        # Error handlers
        self.error_handlers: Dict[ErrorType, List[Callable]] = {
            error_type: [] for error_type in ErrorType
        }
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default error handlers."""
        # Connection errors
        self.register_handler(
            ErrorType.CONNECTION_ERROR,
            self._handle_connection_error
        )
        
        # Protocol errors
        self.register_handler(
            ErrorType.PROTOCOL_ERROR,
            self._handle_protocol_error
        )
        
        # Authentication errors
        self.register_handler(
            ErrorType.AUTHENTICATION_ERROR,
            self._handle_auth_error
        )
        
        # Rate limit errors
        self.register_handler(
            ErrorType.RATE_LIMIT_ERROR,
            self._handle_rate_limit_error
        )
        
        # Validation errors
        self.register_handler(
            ErrorType.VALIDATION_ERROR,
            self._handle_validation_error
        )
        
        # Sync errors
        self.register_handler(
            ErrorType.SYNC_ERROR,
            self._handle_sync_error
        )
        
        # Peer errors
        self.register_handler(
            ErrorType.PEER_ERROR,
            self._handle_peer_error
        )
        
        # Internal errors
        self.register_handler(
            ErrorType.INTERNAL_ERROR,
            self._handle_internal_error
        )
    
    def register_handler(
        self,
        error_type: ErrorType,
        handler: Callable[[NetworkError], None]
    ) -> None:
        """Register a new error handler."""
        if error_type not in self.error_handlers:
            self.error_handlers[error_type] = []
        self.error_handlers[error_type].append(handler)
    
    def handle_error(
        self,
        error: NetworkError,
        peer_id: Optional[str] = None
    ) -> None:
        """Handle a network error."""
        try:
            # Update counters
            self.error_counts[error.error_type] += 1
            
            # Add to history
            self.error_history.append(error)
            if len(self.error_history) > self.max_history_size:
                self.error_history.pop(0)
            
            # Update metrics
            if peer_id:
                self.metrics.record_error(
                    peer_id,
                    error.error_type.name
                )
            
            # Log error
            self.logger.error(
                "Network error occurred",
                error_type=error.error_type.name,
                severity=error.severity.name,
                message=error.message,
                details=error.details,
                peer_id=peer_id
            )
            
            # Call registered handlers
            for handler in self.error_handlers.get(error.error_type, []):
                try:
                    handler(error)
                except Exception as e:
                    self.logger.error(
                        "Error in error handler",
                        handler=handler.__name__,
                        error=str(e)
                    )
            
        except Exception as e:
            self.logger.error(
                "Failed to handle error",
                error=str(e)
            )
    
    def _handle_connection_error(self, error: NetworkError) -> None:
        """Handle connection errors."""
        if error.severity >= ErrorSeverity.HIGH:
            # TODO: Implement connection recovery logic
            pass
    
    def _handle_protocol_error(self, error: NetworkError) -> None:
        """Handle protocol errors."""
        if error.severity >= ErrorSeverity.MEDIUM:
            # TODO: Implement protocol error recovery
            pass
    
    def _handle_auth_error(self, error: NetworkError) -> None:
        """Handle authentication errors."""
        if error.severity >= ErrorSeverity.HIGH:
            # TODO: Implement authentication retry logic
            pass
    
    def _handle_rate_limit_error(self, error: NetworkError) -> None:
        """Handle rate limit errors."""
        # Rate limit errors are handled by the rate limiter
        pass
    
    def _handle_validation_error(self, error: NetworkError) -> None:
        """Handle validation errors."""
        if error.severity >= ErrorSeverity.MEDIUM:
            # TODO: Implement validation error recovery
            pass
    
    def _handle_sync_error(self, error: NetworkError) -> None:
        """Handle synchronization errors."""
        if error.severity >= ErrorSeverity.HIGH:
            # TODO: Implement sync recovery logic
            pass
    
    def _handle_peer_error(self, error: NetworkError) -> None:
        """Handle peer-related errors."""
        if error.severity >= ErrorSeverity.HIGH:
            # TODO: Implement peer error recovery
            pass
    
    def _handle_internal_error(self, error: NetworkError) -> None:
        """Handle internal errors."""
        if error.severity >= ErrorSeverity.CRITICAL:
            # TODO: Implement internal error recovery
            pass
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts": {
                error_type.name: count
                for error_type, count in self.error_counts.items()
            },
            "recent_errors": [
                {
                    "type": error.error_type.name,
                    "severity": error.severity.name,
                    "message": error.message,
                    "timestamp": error.timestamp
                }
                for error in reversed(self.error_history[-10:])
            ]
        }
    
    def clear_error_history(self) -> None:
        """Clear error history."""
        self.error_history.clear()
        self.error_counts = {
            error_type: 0 for error_type in ErrorType
        } 