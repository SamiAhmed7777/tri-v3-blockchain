from typing import Optional, Dict, List, Tuple
import os
import time
import asyncio
import logging
import stem
from stem.control import Controller
from stem.process import launch_tor_with_config
import structlog
from .config import NetworkConfig
from .error_handler import NetworkError, ErrorType, ErrorSeverity

class TorNetwork:
    """Manages Tor network connectivity for the blockchain."""
    
    def __init__(self, hidden_service_dir: str = "hidden_service"):
        """Initialize Tor network manager."""
        self.logger = structlog.get_logger(__name__)
        self.hidden_service_dir = hidden_service_dir
        self.controller: Optional[Controller] = None
        self.service_id: Optional[str] = None
        self.peers: Dict[str, str] = {}  # onion_address -> peer_id
        
        # Tor configuration
        self.tor_config = {
            'SocksPort': str(NetworkConfig.TOR_SOCKS_PORT),
            'ControlPort': str(NetworkConfig.TOR_CONTROL_PORT),
            'DataDirectory': 'tor_data',
            'Log': [
                'NOTICE stdout',
                'ERR file tor_error.log',
            ],
            'CircuitBuildTimeout': '10',
            'NumEntryGuards': '4',
            'KeepalivePeriod': '60',
        }
    
    async def start(self) -> None:
        """Start Tor process and create hidden service."""
        try:
            # Launch Tor process
            self.tor_process = launch_tor_with_config(
                config=self.tor_config,
                take_ownership=True
            )
            
            # Connect to Tor controller
            self.controller = Controller.from_port(
                port=NetworkConfig.TOR_CONTROL_PORT
            )
            await self.controller.authenticate()
            
            # Create hidden service
            self.service_id = await self._create_hidden_service()
            
            self.logger.info(
                "Tor network started",
                service_id=self.service_id
            )
            
        except Exception as e:
            self.logger.error("Failed to start Tor network", error=str(e))
            raise NetworkError(
                error_type=ErrorType.INTERNAL_ERROR,
                severity=ErrorSeverity.CRITICAL,
                message=f"Failed to start Tor network: {str(e)}"
            )
    
    async def stop(self) -> None:
        """Stop Tor process and cleanup."""
        try:
            if self.controller:
                await self.controller.close()
            if hasattr(self, 'tor_process'):
                self.tor_process.kill()
            
        except Exception as e:
            self.logger.error("Error stopping Tor network", error=str(e))
    
    async def _create_hidden_service(self) -> str:
        """Create a Tor hidden service."""
        try:
            # Ensure hidden service directory exists
            os.makedirs(self.hidden_service_dir, exist_ok=True)
            
            # Create v3 hidden service
            response = await self.controller.create_ephemeral_hidden_service(
                {NetworkConfig.DEFAULT_PORT: NetworkConfig.TOR_SERVICE_PORT},
                key_type='NEW',
                key_content='ED25519-V3',
                await_publication=True
            )
            
            return response.service_id
            
        except Exception as e:
            self.logger.error(
                "Failed to create hidden service",
                error=str(e)
            )
            raise
    
    async def connect_to_peer(self, onion_address: str) -> bool:
        """Connect to a peer through Tor."""
        try:
            # Validate onion address
            if not self._validate_onion_address(onion_address):
                raise ValueError(f"Invalid onion address: {onion_address}")
            
            # TODO: Implement Tor circuit creation and connection
            # This will be implemented in the next update
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to connect to peer",
                peer=onion_address,
                error=str(e)
            )
            return False
    
    def _validate_onion_address(self, address: str) -> bool:
        """Validate a v3 onion address."""
        if not address.endswith('.onion'):
            return False
        
        # V3 addresses are 56 characters long (excluding .onion)
        if len(address[:-6]) != 56:
            return False
        
        return True
    
    async def get_circuit_status(self) -> List[Dict]:
        """Get status of Tor circuits."""
        try:
            circuits = await self.controller.get_circuits()
            return [
                {
                    'id': circuit.id,
                    'status': circuit.status,
                    'purpose': circuit.purpose,
                    'path': [node.fingerprint for node in circuit.path],
                    'build_flags': circuit.build_flags,
                    'is_built': circuit.is_built,
                    'age': time.time() - circuit.created
                }
                for circuit in circuits
            ]
        except Exception as e:
            self.logger.error("Failed to get circuit status", error=str(e))
            return []
    
    async def create_new_circuit(self) -> bool:
        """Create a new Tor circuit."""
        try:
            await self.controller.new_circuit(
                purpose='GENERAL',
                await_build=True
            )
            return True
        except Exception as e:
            self.logger.error("Failed to create new circuit", error=str(e))
            return False
    
    def get_network_status(self) -> Dict:
        """Get Tor network status."""
        try:
            return {
                'service_id': self.service_id,
                'onion_address': f"{self.service_id}.onion",
                'connected_peers': len(self.peers),
                'is_active': bool(self.controller and self.controller.is_alive()),
                'bootstrap_status': self.controller.get_info('status/bootstrap-phase'),
                'version': self.controller.get_version()
            }
        except Exception as e:
            self.logger.error("Failed to get network status", error=str(e))
            return {
                'error': str(e)
            } 