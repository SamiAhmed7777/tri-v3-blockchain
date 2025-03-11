from typing import Dict, Any, Callable, Optional
import logging
from .protocol import Message, MessageType
from .config import NetworkConfig
from ..core.blockchain import Blockchain
from ..core.transaction import Transaction
from ..core.block import Block
from ..consensus.validator import Validator

class MessageHandler:
    """Handles different types of network messages."""
    
    def __init__(self, blockchain: Blockchain, validator: Optional[Validator] = None):
        """Initialize the message handler."""
        self.blockchain = blockchain
        self.validator = validator
        self.handlers: Dict[MessageType, Callable] = {
            MessageType.HANDSHAKE: self.handle_handshake,
            MessageType.BLOCK: self.handle_block,
            MessageType.TRANSACTION: self.handle_transaction,
            MessageType.PEER_DISCOVERY: self.handle_peer_discovery,
            MessageType.PEER_LIST: self.handle_peer_list,
            MessageType.HEARTBEAT: self.handle_heartbeat,
            MessageType.CHAIN_REQUEST: self.handle_chain_request,
            MessageType.CHAIN_RESPONSE: self.handle_chain_response,
            MessageType.ERROR: self.handle_error
        }
        self.logger = logging.getLogger(__name__)
    
    async def handle_message(self, message: Message) -> Optional[Message]:
        """Handle an incoming message."""
        try:
            if message.type not in self.handlers:
                raise ValueError(f"Unknown message type: {message.type}")
            
            handler = self.handlers[message.type]
            return await handler(message)
            
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return Message(
                type=MessageType.ERROR,
                data={"error": str(e)},
                sender=NetworkConfig.get_node_id(),
                timestamp=message.timestamp
            )
    
    async def handle_handshake(self, message: Message) -> Optional[Message]:
        """Handle a handshake message."""
        try:
            node_id = message.data.get("node_id")
            if not node_id:
                raise ValueError("Missing node_id in handshake message")
            
            # TODO: Implement handshake validation and peer registration
            return Message(
                type=MessageType.HANDSHAKE,
                data={"node_id": NetworkConfig.get_node_id()},
                sender=NetworkConfig.get_node_id(),
                timestamp=message.timestamp
            )
        except Exception as e:
            self.logger.error(f"Error handling handshake: {e}")
            return None
    
    async def handle_block(self, message: Message) -> Optional[Message]:
        """Handle a block message."""
        try:
            block_data = message.data
            block = Block(**block_data)
            
            if self.validator and not self.validator.validate_block(block):
                raise ValueError("Invalid block")
            
            # Add block to blockchain
            self.blockchain.add_block(block)
            
            return None
        except Exception as e:
            self.logger.error(f"Error handling block: {e}")
            return None
    
    async def handle_transaction(self, message: Message) -> Optional[Message]:
        """Handle a transaction message."""
        try:
            tx_data = message.data
            transaction = Transaction(**tx_data)
            
            if self.validator and not self.validator.validate_transaction(transaction):
                raise ValueError("Invalid transaction")
            
            # Add transaction to pending transactions
            self.blockchain.add_transaction(transaction)
            
            return None
        except Exception as e:
            self.logger.error(f"Error handling transaction: {e}")
            return None
    
    async def handle_peer_discovery(self, message: Message) -> Optional[Message]:
        """Handle a peer discovery message."""
        try:
            peers = message.data.get("peers", [])
            
            # TODO: Implement peer discovery logic
            return Message(
                type=MessageType.PEER_LIST,
                data={"peers": []},  # Return known peers
                sender=NetworkConfig.get_node_id(),
                timestamp=message.timestamp
            )
        except Exception as e:
            self.logger.error(f"Error handling peer discovery: {e}")
            return None
    
    async def handle_peer_list(self, message: Message) -> Optional[Message]:
        """Handle a peer list message."""
        try:
            peers = message.data.get("peers", [])
            
            # TODO: Implement peer list handling
            return None
        except Exception as e:
            self.logger.error(f"Error handling peer list: {e}")
            return None
    
    async def handle_heartbeat(self, message: Message) -> Optional[Message]:
        """Handle a heartbeat message."""
        try:
            # TODO: Implement heartbeat handling
            return Message(
                type=MessageType.HEARTBEAT,
                data={},
                sender=NetworkConfig.get_node_id(),
                timestamp=message.timestamp
            )
        except Exception as e:
            self.logger.error(f"Error handling heartbeat: {e}")
            return None
    
    async def handle_chain_request(self, message: Message) -> Optional[Message]:
        """Handle a chain request message."""
        try:
            # TODO: Implement chain request handling
            return Message(
                type=MessageType.CHAIN_RESPONSE,
                data={"chain": self.blockchain.to_dict()},
                sender=NetworkConfig.get_node_id(),
                timestamp=message.timestamp
            )
        except Exception as e:
            self.logger.error(f"Error handling chain request: {e}")
            return None
    
    async def handle_chain_response(self, message: Message) -> Optional[Message]:
        """Handle a chain response message."""
        try:
            chain_data = message.data.get("chain")
            if not chain_data:
                raise ValueError("Missing chain data in response")
            
            # TODO: Implement chain validation and synchronization
            return None
        except Exception as e:
            self.logger.error(f"Error handling chain response: {e}")
            return None
    
    async def handle_error(self, message: Message) -> Optional[Message]:
        """Handle an error message."""
        try:
            error = message.data.get("error")
            self.logger.error(f"Received error message: {error}")
            return None
        except Exception as e:
            self.logger.error(f"Error handling error message: {e}")
            return None 