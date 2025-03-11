from typing import Dict, List, Optional, Set
import asyncio
import aiohttp
from datetime import datetime
import json

class Peer:
    """Represents a peer in the P2P network."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.id = f"{host}:{port}"
        self.connected_peers: Set[str] = set()
        self.last_seen: Dict[str, datetime] = {}
        self.is_active = False
    
    async def start(self):
        """Start the peer server."""
        self.server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )
        self.is_active = True
        
        # Start peer discovery
        asyncio.create_task(self.discover_peers())
        
        await self.server.serve_forever()
    
    async def stop(self):
        """Stop the peer server."""
        self.is_active = False
        self.server.close()
        await self.server.wait_closed()
    
    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming peer connections."""
        peer_addr = writer.get_extra_info('peername')
        peer_id = f"{peer_addr[0]}:{peer_addr[1]}"
        
        try:
            data = await reader.read()
            message = json.loads(data.decode())
            
            if message["type"] == "PEER_DISCOVERY":
                await self.handle_peer_discovery(message, peer_id)
            elif message["type"] == "PEER_LIST":
                await self.handle_peer_list(message)
            elif message["type"] == "HEARTBEAT":
                await self.handle_heartbeat(peer_id)
            
            response = {"status": "ok"}
            writer.write(json.dumps(response).encode())
            await writer.drain()
            
        except Exception as e:
            print(f"Error handling connection from {peer_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def connect_to_peer(self, peer_id: str):
        """Connect to a new peer."""
        if peer_id in self.connected_peers or peer_id == self.id:
            return
            
        host, port = peer_id.split(":")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{host}:{port}/connect",
                    json={"peer_id": self.id}
                ) as response:
                    if response.status == 200:
                        self.connected_peers.add(peer_id)
                        self.last_seen[peer_id] = datetime.utcnow()
        except Exception as e:
            print(f"Failed to connect to peer {peer_id}: {e}")
    
    async def discover_peers(self):
        """Periodically discover new peers."""
        while self.is_active:
            message = {
                "type": "PEER_DISCOVERY",
                "peer_id": self.id,
                "peers": list(self.connected_peers)
            }
            
            # Broadcast to all connected peers
            for peer_id in self.connected_peers.copy():
                try:
                    host, port = peer_id.split(":")
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"http://{host}:{port}/discover",
                            json=message
                        ) as response:
                            if response.status == 200:
                                self.last_seen[peer_id] = datetime.utcnow()
                except Exception:
                    # Remove unresponsive peers
                    self.connected_peers.remove(peer_id)
                    self.last_seen.pop(peer_id, None)
            
            await asyncio.sleep(60)  # Discover every minute
    
    async def handle_peer_discovery(self, message: Dict, sender_id: str):
        """Handle peer discovery messages."""
        self.connected_peers.add(sender_id)
        self.last_seen[sender_id] = datetime.utcnow()
        
        # Connect to new peers
        for peer_id in message["peers"]:
            await self.connect_to_peer(peer_id)
    
    async def handle_peer_list(self, message: Dict):
        """Handle peer list updates."""
        for peer_id in message["peers"]:
            await self.connect_to_peer(peer_id)
    
    async def handle_heartbeat(self, peer_id: str):
        """Handle peer heartbeat messages."""
        self.last_seen[peer_id] = datetime.utcnow()
    
    async def broadcast(self, message: Dict):
        """Broadcast a message to all connected peers."""
        for peer_id in self.connected_peers.copy():
            try:
                host, port = peer_id.split(":")
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"http://{host}:{port}/message",
                        json=message
                    ) as response:
                        if response.status == 200:
                            self.last_seen[peer_id] = datetime.utcnow()
            except Exception:
                # Remove unresponsive peers
                self.connected_peers.remove(peer_id)
                self.last_seen.pop(peer_id, None) 