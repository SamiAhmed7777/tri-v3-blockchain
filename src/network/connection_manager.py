import asyncio
import logging
from typing import Dict, Set, Optional, List
import time
from .protocol import Message, MessageType, Protocol
from .config import NetworkConfig
from .message_handler import MessageHandler
from ..core.blockchain import Blockchain
from ..consensus.validator import Validator

class PeerConnection:
    """Represents a connection to a peer."""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, node_id: str):
        self.reader = reader
        self.writer = writer
        self.node_id = node_id
        self.last_seen = time.time()
        self.is_active = True
    
    async def send_message(self, message: Message) -> None:
        """Send a message to the peer."""
        try:
            data = Protocol.encode_message(message)
            self.writer.write(len(data).to_bytes(4, byteorder='big'))
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            raise ConnectionError(f"Failed to send message: {e}")
    
    async def receive_message(self) -> Optional[Message]:
        """Receive a message from the peer."""
        try:
            # Read message length
            length_bytes = await self.reader.readexactly(4)
            length = int.from_bytes(length_bytes, byteorder='big')
            
            if length > NetworkConfig.MAX_MESSAGE_SIZE:
                raise ValueError(f"Message size {length} exceeds maximum {NetworkConfig.MAX_MESSAGE_SIZE}")
            
            # Read message data
            data = await self.reader.readexactly(length)
            return Protocol.decode_message(data)
        except asyncio.IncompleteReadError:
            raise ConnectionError("Connection closed by peer")
        except Exception as e:
            raise ConnectionError(f"Failed to receive message: {e}")
    
    def close(self) -> None:
        """Close the connection."""
        self.is_active = False
        self.writer.close()

class ConnectionManager:
    """Manages peer connections and message routing."""
    
    def __init__(self, blockchain: Blockchain, validator: Optional[Validator] = None):
        """Initialize the connection manager."""
        self.blockchain = blockchain
        self.validator = validator
        self.message_handler = MessageHandler(blockchain, validator)
        self.peers: Dict[str, PeerConnection] = {}
        self.pending_connections: Set[str] = set()
        self.server: Optional[asyncio.Server] = None
        self.logger = logging.getLogger(__name__)
    
    async def start(self, host: str = "0.0.0.0", port: int = NetworkConfig.DEFAULT_PORT) -> None:
        """Start the connection manager."""
        try:
            self.server = await asyncio.start_server(
                self.handle_connection, host, port
            )
            
            self.logger.info(f"Server started on {host}:{port}")
            
            # Start background tasks
            asyncio.create_task(self.maintain_connections())
            asyncio.create_task(self.discover_peers())
            
            async with self.server:
                await self.server.serve_forever()
                
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the connection manager."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close all peer connections
        for peer in self.peers.values():
            peer.close()
        
        self.peers.clear()
        self.pending_connections.clear()
    
    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle an incoming connection."""
        try:
            # Perform handshake
            handshake = await self.perform_handshake(reader, writer)
            if not handshake:
                writer.close()
                return
            
            node_id = handshake.data["node_id"]
            
            # Create peer connection
            peer = PeerConnection(reader, writer, node_id)
            self.peers[node_id] = peer
            
            # Handle messages from peer
            while peer.is_active:
                try:
                    message = await peer.receive_message()
                    if message:
                        response = await self.message_handler.handle_message(message)
                        if response:
                            await peer.send_message(response)
                except ConnectionError:
                    break
                
        except Exception as e:
            self.logger.error(f"Error handling connection: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def perform_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Optional[Message]:
        """Perform handshake with a new peer."""
        try:
            # Send handshake
            handshake = Message(
                type=MessageType.HANDSHAKE,
                data={"node_id": NetworkConfig.get_node_id()},
                sender=NetworkConfig.get_node_id(),
                timestamp=time.time()
            )
            
            data = Protocol.encode_message(handshake)
            writer.write(len(data).to_bytes(4, byteorder='big'))
            writer.write(data)
            await writer.drain()
            
            # Receive handshake
            length_bytes = await reader.readexactly(4)
            length = int.from_bytes(length_bytes, byteorder='big')
            
            if length > NetworkConfig.MAX_MESSAGE_SIZE:
                raise ValueError(f"Handshake size {length} exceeds maximum {NetworkConfig.MAX_MESSAGE_SIZE}")
            
            data = await reader.readexactly(length)
            return Protocol.decode_message(data)
            
        except Exception as e:
            self.logger.error(f"Handshake failed: {e}")
            return None
    
    async def connect_to_peer(self, host: str, port: int) -> bool:
        """Connect to a peer."""
        try:
            if f"{host}:{port}" in self.pending_connections:
                return False
            
            self.pending_connections.add(f"{host}:{port}")
            
            reader, writer = await asyncio.open_connection(host, port)
            
            # Perform handshake
            handshake = await self.perform_handshake(reader, writer)
            if not handshake:
                writer.close()
                return False
            
            node_id = handshake.data["node_id"]
            
            # Create peer connection
            peer = PeerConnection(reader, writer, node_id)
            self.peers[node_id] = peer
            
            self.logger.info(f"Connected to peer {node_id} at {host}:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to peer {host}:{port}: {e}")
            return False
        finally:
            self.pending_connections.discard(f"{host}:{port}")
    
    async def broadcast_message(self, message: Message) -> None:
        """Broadcast a message to all peers."""
        for peer in list(self.peers.values()):
            try:
                await peer.send_message(message)
            except Exception as e:
                self.logger.error(f"Failed to broadcast message to peer {peer.node_id}: {e}")
                peer.close()
                del self.peers[peer.node_id]
    
    async def maintain_connections(self) -> None:
        """Maintain peer connections."""
        while True:
            try:
                # Remove inactive peers
                for node_id, peer in list(self.peers.items()):
                    if not peer.is_active or time.time() - peer.last_seen > NetworkConfig.CONNECTION_TIMEOUT:
                        peer.close()
                        del self.peers[node_id]
                
                # Connect to bootstrap nodes if needed
                if len(self.peers) < NetworkConfig.MIN_PEERS_FOR_SYNC:
                    for node in NetworkConfig.get_bootstrap_nodes():
                        try:
                            host, port = node.split(":")
                            await self.connect_to_peer(host, int(port))
                        except Exception as e:
                            self.logger.error(f"Failed to connect to bootstrap node {node}: {e}")
                
                await asyncio.sleep(NetworkConfig.PING_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in maintain_connections: {e}")
                await asyncio.sleep(1)
    
    async def discover_peers(self) -> None:
        """Discover new peers."""
        while True:
            try:
                if self.peers:
                    # Send peer discovery message to random peer
                    peer = next(iter(self.peers.values()))
                    message = Message(
                        type=MessageType.PEER_DISCOVERY,
                        data={"peers": []},
                        sender=NetworkConfig.get_node_id(),
                        timestamp=time.time()
                    )
                    await peer.send_message(message)
                
                await asyncio.sleep(NetworkConfig.PEER_DISCOVERY_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in discover_peers: {e}")
                await asyncio.sleep(1) 