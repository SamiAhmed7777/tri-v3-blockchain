from typing import Dict, List, Optional, Set
import asyncio
import aiohttp
from datetime import datetime
from ..core.blockchain import Blockchain
from ..core.transaction import Transaction
from ..core.block import Block
from ..consensus.validator import Validator

class Node:
    """Represents a node in the blockchain network."""
    
    def __init__(self, host: str, port: int, validator: Optional[Validator] = None):
        self.host = host
        self.port = port
        self.blockchain = Blockchain()
        self.validator = validator
        self.peers: Set[str] = set()  # Set of peer URLs
        self.pending_transactions: List[Transaction] = []
        self.syncing = False
    
    async def start(self):
        """Start the node server."""
        self.server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )
        
        await self.server.serve_forever()
    
    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connections."""
        data = await reader.read()
        message = data.decode()
        
        # Handle different message types
        if message.startswith("BLOCK:"):
            await self.handle_new_block(message[6:])
        elif message.startswith("TRANSACTION:"):
            await self.handle_new_transaction(message[12:])
        elif message.startswith("PEER:"):
            await self.handle_new_peer(message[5:])
        
        writer.close()
        await writer.wait_closed()
    
    async def broadcast(self, message: str):
        """Broadcast a message to all peers."""
        async with aiohttp.ClientSession() as session:
            for peer in self.peers:
                try:
                    async with session.post(peer, data=message) as response:
                        await response.text()
                except Exception as e:
                    print(f"Failed to broadcast to {peer}: {e}")
    
    async def sync_blockchain(self):
        """Synchronize blockchain with peers."""
        if self.syncing:
            return
            
        self.syncing = True
        try:
            async with aiohttp.ClientSession() as session:
                for peer in self.peers:
                    try:
                        async with session.get(f"{peer}/blockchain") as response:
                            chain_data = await response.json()
                            # Validate and update chain if necessary
                            if len(chain_data) > len(self.blockchain.chain):
                                # Verify the chain
                                new_chain = self.validate_chain(chain_data)
                                if new_chain:
                                    self.blockchain.chain = new_chain
                    except Exception as e:
                        print(f"Failed to sync with {peer}: {e}")
        finally:
            self.syncing = False
    
    def validate_chain(self, chain_data: List[dict]) -> Optional[List[Block]]:
        """Validate a blockchain from peer."""
        new_chain = []
        for block_data in chain_data:
            block = Block(
                index=block_data["index"],
                timestamp=datetime.fromisoformat(block_data["timestamp"]),
                transactions=block_data["transactions"],
                previous_hash=block_data["previous_hash"],
                nonce=block_data["nonce"],
                hash=block_data["hash"]
            )
            new_chain.append(block)
        
        # Validate the chain
        for i in range(1, len(new_chain)):
            if not self.validator.validate_block(new_chain[i], new_chain[i-1]):
                return None
        
        return new_chain
    
    async def add_transaction(self, transaction: Transaction):
        """Add a new transaction and broadcast it."""
        if self.validator and self.validator.validate_transaction(transaction):
            self.pending_transactions.append(transaction)
            await self.broadcast(f"TRANSACTION:{transaction.to_dict()}")
    
    async def add_block(self, block: Block):
        """Add a new block and broadcast it."""
        if self.validator and self.validator.validate_block(block, self.blockchain.latest_block):
            self.blockchain.chain.append(block)
            await self.broadcast(f"BLOCK:{block.__dict__}")
    
    async def mine_block(self):
        """Mine a new block if node is a validator."""
        if not self.validator or not self.pending_transactions:
            return
            
        block = self.validator.create_block(
            self.pending_transactions,
            self.blockchain.latest_block
        )
        
        await self.add_block(block)
        self.pending_transactions = [] 