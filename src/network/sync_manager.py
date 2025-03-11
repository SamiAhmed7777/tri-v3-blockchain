import asyncio
import logging
from typing import List, Optional, Dict, Any
import time
from .protocol import Message, MessageType
from .config import NetworkConfig
from .connection_manager import ConnectionManager
from ..core.blockchain import Blockchain
from ..core.block import Block
from ..consensus.validator import Validator

class SyncState:
    """Represents the synchronization state."""
    
    def __init__(self):
        self.is_syncing = False
        self.last_sync = 0
        self.sync_height = 0
        self.target_height = 0
        self.sync_peers: List[str] = []

class SyncManager:
    """Manages blockchain synchronization between nodes."""
    
    def __init__(
        self,
        blockchain: Blockchain,
        connection_manager: ConnectionManager,
        validator: Optional[Validator] = None
    ):
        """Initialize the sync manager."""
        self.blockchain = blockchain
        self.connection_manager = connection_manager
        self.validator = validator
        self.state = SyncState()
        self.logger = logging.getLogger(__name__)
    
    async def start(self) -> None:
        """Start the sync manager."""
        try:
            # Start background tasks
            asyncio.create_task(self.periodic_sync())
            
        except Exception as e:
            self.logger.error(f"Failed to start sync manager: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the sync manager."""
        self.state.is_syncing = False
    
    async def periodic_sync(self) -> None:
        """Periodically check and sync blockchain."""
        while True:
            try:
                if not self.state.is_syncing and self.should_sync():
                    await self.sync_blockchain()
                
                await asyncio.sleep(NetworkConfig.PEER_DISCOVERY_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in periodic sync: {e}")
                await asyncio.sleep(1)
    
    def should_sync(self) -> bool:
        """Determine if blockchain should be synced."""
        # Check if enough time has passed since last sync
        if time.time() - self.state.last_sync < NetworkConfig.PEER_DISCOVERY_INTERVAL:
            return False
        
        # Check if we have enough peers
        if len(self.connection_manager.peers) < NetworkConfig.MIN_PEERS_FOR_SYNC:
            return False
        
        return True
    
    async def sync_blockchain(self) -> None:
        """Synchronize blockchain with peers."""
        try:
            self.state.is_syncing = True
            self.state.sync_peers = list(self.connection_manager.peers.keys())
            
            # Request chain info from peers
            chain_heights = await self.get_peer_chain_heights()
            if not chain_heights:
                return
            
            # Find the highest chain
            max_height = max(chain_heights.values())
            if max_height <= self.blockchain.get_height():
                return
            
            # Select peer with highest chain
            sync_peer = max(chain_heights.items(), key=lambda x: x[1])[0]
            
            # Sync blocks from peer
            await self.sync_blocks_from_peer(sync_peer, max_height)
            
        except Exception as e:
            self.logger.error(f"Error syncing blockchain: {e}")
        finally:
            self.state.is_syncing = False
            self.state.last_sync = time.time()
    
    async def get_peer_chain_heights(self) -> Dict[str, int]:
        """Get chain heights from peers."""
        heights: Dict[str, int] = {}
        
        for node_id, peer in self.connection_manager.peers.items():
            try:
                # Request chain info
                message = Message(
                    type=MessageType.CHAIN_REQUEST,
                    data={},
                    sender=NetworkConfig.get_node_id(),
                    timestamp=time.time()
                )
                
                await peer.send_message(message)
                response = await peer.receive_message()
                
                if response and response.type == MessageType.CHAIN_RESPONSE:
                    chain_data = response.data.get("chain", {})
                    height = chain_data.get("height", 0)
                    if height > 0:
                        heights[node_id] = height
                
            except Exception as e:
                self.logger.error(f"Failed to get chain height from peer {node_id}: {e}")
        
        return heights
    
    async def sync_blocks_from_peer(self, peer_id: str, target_height: int) -> None:
        """Sync blocks from a specific peer."""
        try:
            peer = self.connection_manager.peers.get(peer_id)
            if not peer:
                return
            
            current_height = self.blockchain.get_height()
            self.state.sync_height = current_height
            self.state.target_height = target_height
            
            while current_height < target_height and self.state.is_syncing:
                # Request next batch of blocks
                message = Message(
                    type=MessageType.BLOCK_REQUEST,
                    data={
                        "start_height": current_height + 1,
                        "end_height": min(
                            current_height + NetworkConfig.MAX_BLOCKS_PER_REQUEST,
                            target_height
                        )
                    },
                    sender=NetworkConfig.get_node_id(),
                    timestamp=time.time()
                )
                
                await peer.send_message(message)
                response = await peer.receive_message()
                
                if not response or response.type != MessageType.BLOCK_RESPONSE:
                    raise ValueError("Invalid response from peer")
                
                # Process received blocks
                blocks_data = response.data.get("blocks", [])
                for block_data in blocks_data:
                    block = Block(**block_data)
                    
                    # Validate block
                    if self.validator and not self.validator.validate_block(block):
                        raise ValueError(f"Invalid block at height {block.index}")
                    
                    # Add block to blockchain
                    self.blockchain.add_block(block)
                    current_height = block.index
                    self.state.sync_height = current_height
                
                # Update progress
                self.logger.info(
                    f"Synced blocks: {current_height}/{target_height} "
                    f"({(current_height/target_height)*100:.2f}%)"
                )
            
        except Exception as e:
            self.logger.error(f"Failed to sync blocks from peer {peer_id}: {e}")
            self.state.is_syncing = False
    
    def get_sync_progress(self) -> Dict[str, Any]:
        """Get current sync progress."""
        return {
            "is_syncing": self.state.is_syncing,
            "sync_height": self.state.sync_height,
            "target_height": self.state.target_height,
            "progress": (
                (self.state.sync_height / self.state.target_height) * 100
                if self.state.target_height > 0
                else 0
            ),
            "peers": len(self.state.sync_peers)
        } 