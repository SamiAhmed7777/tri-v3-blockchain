"""
Tests for the TRI-V3 node implementation.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from src.core.node import Node
from src.core.config import load_config
from src.consensus.manager import ConsensusManager

@pytest.fixture
async def node():
    """Create a test node instance."""
    config = load_config("tests/data/test_config.conf")
    consensus_manager = ConsensusManager(config)
    node = Node(config, consensus_manager)
    await node.start()
    yield node
    await node.stop()

@pytest.mark.asyncio
async def test_node_startup(node):
    """Test that the node starts up correctly."""
    assert node.is_running()
    assert node.peer_count() == 0

@pytest.mark.asyncio
async def test_node_shutdown(node):
    """Test that the node shuts down correctly."""
    await node.stop()
    assert not node.is_running()

@pytest.mark.asyncio
async def test_peer_connection():
    """Test peer connection handling."""
    config = load_config("tests/data/test_config.conf")
    consensus_manager = Mock()
    node = Node(config, consensus_manager)
    
    # Mock peer connection
    peer = Mock()
    await node.add_peer(peer)
    assert node.peer_count() == 1
    
    # Test peer disconnection
    await node.remove_peer(peer)
    assert node.peer_count() == 0

@pytest.mark.asyncio
async def test_block_validation():
    """Test block validation."""
    config = load_config("tests/data/test_config.conf")
    consensus_manager = Mock()
    node = Node(config, consensus_manager)
    
    # Mock block data
    block = Mock()
    block.validate.return_value = True
    
    # Test block validation
    assert await node.validate_block(block)
    
    # Test invalid block
    block.validate.return_value = False
    assert not await node.validate_block(block)

@pytest.mark.asyncio
async def test_transaction_validation():
    """Test transaction validation."""
    config = load_config("tests/data/test_config.conf")
    consensus_manager = Mock()
    node = Node(config, consensus_manager)
    
    # Mock transaction data
    transaction = Mock()
    transaction.validate.return_value = True
    
    # Test transaction validation
    assert await node.validate_transaction(transaction)
    
    # Test invalid transaction
    transaction.validate.return_value = False
    assert not await node.validate_transaction(transaction) 