#!/usr/bin/env python3
"""
TRI-V3 Blockchain Node
Main entry point for the TRI-V3 node implementation.
"""

import asyncio
import logging
import sys
from pathlib import Path

from core.node import Node
from core.config import load_config
from network.server import P2PServer
from consensus.manager import ConsensusManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/node.log')
    ]
)
logger = logging.getLogger('tri-v3')

async def main():
    """Main entry point for the TRI-V3 node."""
    try:
        # Load configuration
        config = load_config()
        
        # Initialize components
        consensus_manager = ConsensusManager(config)
        node = Node(config, consensus_manager)
        server = P2PServer(node, config)
        
        # Start services
        await node.start()
        await server.start()
        
        # Wait for shutdown
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down TRI-V3 node...")
        await node.stop()
        await server.stop()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Ensure required directories exist
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    # Run the node
    asyncio.run(main()) 