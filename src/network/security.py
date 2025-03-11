import os
import time
from typing import Dict, Optional, Tuple
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidKey, InvalidSignature
import structlog
from .config import NetworkConfig

class SecurityManager:
    """Manages network security operations."""
    
    def __init__(self):
        """Initialize the security manager."""
        self.logger = structlog.get_logger(__name__)
        
        # Generate or load node key pair
        self.private_key, self.public_key = self._load_or_generate_keys()
        
        # Session keys for peers
        self.session_keys: Dict[str, bytes] = {}
        
        # Peer public keys
        self.peer_keys: Dict[str, ec.EllipticCurvePublicKey] = {}
    
    def _load_or_generate_keys(self) -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
        """Load existing keys or generate new ones."""
        try:
            # Try to load existing keys
            with open("node_private.pem", "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )
            
            with open("node_public.pem", "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
            
            return private_key, public_key
            
        except FileNotFoundError:
            # Generate new keys
            private_key = ec.generate_private_key(ec.SECP384R1())
            public_key = private_key.public_key()
            
            # Save keys
            with open("node_private.pem", "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            with open("node_public.pem", "wb") as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            
            return private_key, public_key
    
    def get_public_key_bytes(self) -> bytes:
        """Get the node's public key in bytes."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def establish_session(self, peer_id: str, peer_public_key_bytes: bytes) -> bool:
        """Establish a secure session with a peer."""
        try:
            # Load peer's public key
            peer_public_key = serialization.load_pem_public_key(peer_public_key_bytes)
            self.peer_keys[peer_id] = peer_public_key
            
            # Generate shared key using ECDH
            shared_key = self.private_key.exchange(ec.ECDH(), peer_public_key)
            
            # Derive session key using HKDF
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b"session_key"
            )
            session_key = hkdf.derive(shared_key)
            
            self.session_keys[peer_id] = session_key
            return True
            
        except Exception as e:
            self.logger.error("Failed to establish session", peer_id=peer_id, error=str(e))
            return False
    
    def end_session(self, peer_id: str) -> None:
        """End a secure session with a peer."""
        self.session_keys.pop(peer_id, None)
        self.peer_keys.pop(peer_id, None)
    
    def encrypt_message(self, peer_id: str, message: bytes) -> Optional[bytes]:
        """Encrypt a message for a peer."""
        try:
            if peer_id not in self.session_keys:
                raise ValueError(f"No session key for peer {peer_id}")
            
            # Generate random IV
            iv = os.urandom(16)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.session_keys[peer_id]),
                modes.CBC(iv)
            )
            encryptor = cipher.encryptor()
            
            # Add padding
            padded_message = self._add_padding(message)
            
            # Encrypt message
            ciphertext = encryptor.update(padded_message) + encryptor.finalize()
            
            # Combine IV and ciphertext
            return iv + ciphertext
            
        except Exception as e:
            self.logger.error("Failed to encrypt message", peer_id=peer_id, error=str(e))
            return None
    
    def decrypt_message(self, peer_id: str, encrypted_message: bytes) -> Optional[bytes]:
        """Decrypt a message from a peer."""
        try:
            if peer_id not in self.session_keys:
                raise ValueError(f"No session key for peer {peer_id}")
            
            # Extract IV and ciphertext
            iv = encrypted_message[:16]
            ciphertext = encrypted_message[16:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.session_keys[peer_id]),
                modes.CBC(iv)
            )
            decryptor = cipher.decryptor()
            
            # Decrypt message
            padded_message = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remove padding
            return self._remove_padding(padded_message)
            
        except Exception as e:
            self.logger.error("Failed to decrypt message", peer_id=peer_id, error=str(e))
            return None
    
    def sign_message(self, message: bytes) -> Optional[bytes]:
        """Sign a message with the node's private key."""
        try:
            signature = self.private_key.sign(
                message,
                ec.ECDSA(hashes.SHA256())
            )
            return signature
            
        except Exception as e:
            self.logger.error("Failed to sign message", error=str(e))
            return None
    
    def verify_signature(self, peer_id: str, message: bytes, signature: bytes) -> bool:
        """Verify a message signature from a peer."""
        try:
            if peer_id not in self.peer_keys:
                raise ValueError(f"No public key for peer {peer_id}")
            
            self.peer_keys[peer_id].verify(
                signature,
                message,
                ec.ECDSA(hashes.SHA256())
            )
            return True
            
        except (InvalidSignature, Exception) as e:
            self.logger.error("Failed to verify signature", peer_id=peer_id, error=str(e))
            return False
    
    def _add_padding(self, message: bytes) -> bytes:
        """Add PKCS7 padding to a message."""
        padding_length = 16 - (len(message) % 16)
        padding = bytes([padding_length] * padding_length)
        return message + padding
    
    def _remove_padding(self, padded_message: bytes) -> bytes:
        """Remove PKCS7 padding from a message."""
        padding_length = padded_message[-1]
        return padded_message[:-padding_length]
    
    def rotate_session_key(self, peer_id: str) -> bool:
        """Rotate the session key for a peer."""
        try:
            if peer_id not in self.peer_keys:
                raise ValueError(f"No public key for peer {peer_id}")
            
            # Generate new shared key
            shared_key = self.private_key.exchange(
                ec.ECDH(),
                self.peer_keys[peer_id]
            )
            
            # Derive new session key
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b"session_key"
            )
            new_session_key = hkdf.derive(shared_key)
            
            self.session_keys[peer_id] = new_session_key
            return True
            
        except Exception as e:
            self.logger.error("Failed to rotate session key", peer_id=peer_id, error=str(e))
            return False 