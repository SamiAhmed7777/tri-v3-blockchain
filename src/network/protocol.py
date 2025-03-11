from typing import Dict, Any, Optional
import json
from enum import Enum
from dataclasses import dataclass

class MessageType(Enum):
    """Enum for different types of network messages."""
    HANDSHAKE = "handshake"
    BLOCK = "block"
    TRANSACTION = "transaction"
    PEER_DISCOVERY = "peer_discovery"
    PEER_LIST = "peer_list"
    HEARTBEAT = "heartbeat"
    CHAIN_REQUEST = "chain_request"
    CHAIN_RESPONSE = "chain_response"
    ERROR = "error"

@dataclass
class Message:
    """Represents a network message."""
    type: MessageType
    data: Dict[str, Any]
    sender: str
    timestamp: float
    signature: Optional[str] = None

class Protocol:
    """Implements the network protocol."""
    
    VERSION = "1.0.0"
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    
    @staticmethod
    def encode_message(message: Message) -> bytes:
        """Encode a message to bytes."""
        message_dict = {
            "type": message.type.value,
            "data": message.data,
            "sender": message.sender,
            "timestamp": message.timestamp,
            "signature": message.signature,
            "version": Protocol.VERSION
        }
        return json.dumps(message_dict).encode()
    
    @staticmethod
    def decode_message(data: bytes) -> Message:
        """Decode bytes to a message."""
        try:
            message_dict = json.loads(data.decode())
            
            # Verify protocol version
            if message_dict.get("version") != Protocol.VERSION:
                raise ValueError(f"Unsupported protocol version: {message_dict.get('version')}")
            
            return Message(
                type=MessageType(message_dict["type"]),
                data=message_dict["data"],
                sender=message_dict["sender"],
                timestamp=message_dict["timestamp"],
                signature=message_dict.get("signature")
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid message format: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required field: {e}")
    
    @staticmethod
    def create_handshake(node_id: str, timestamp: float) -> Message:
        """Create a handshake message."""
        return Message(
            type=MessageType.HANDSHAKE,
            data={"node_id": node_id},
            sender=node_id,
            timestamp=timestamp
        )
    
    @staticmethod
    def create_block_message(block_data: Dict[str, Any], node_id: str, timestamp: float) -> Message:
        """Create a block message."""
        return Message(
            type=MessageType.BLOCK,
            data=block_data,
            sender=node_id,
            timestamp=timestamp
        )
    
    @staticmethod
    def create_transaction_message(tx_data: Dict[str, Any], node_id: str, timestamp: float) -> Message:
        """Create a transaction message."""
        return Message(
            type=MessageType.TRANSACTION,
            data=tx_data,
            sender=node_id,
            timestamp=timestamp
        )
    
    @staticmethod
    def create_peer_discovery(node_id: str, peers: list, timestamp: float) -> Message:
        """Create a peer discovery message."""
        return Message(
            type=MessageType.PEER_DISCOVERY,
            data={"peers": peers},
            sender=node_id,
            timestamp=timestamp
        )
    
    @staticmethod
    def create_error_message(error: str, node_id: str, timestamp: float) -> Message:
        """Create an error message."""
        return Message(
            type=MessageType.ERROR,
            data={"error": error},
            sender=node_id,
            timestamp=timestamp
        ) 