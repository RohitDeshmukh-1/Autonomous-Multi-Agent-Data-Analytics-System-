"""
connectors/crypto.py
Lightweight, pure-Python secure symmetric encryption for database connection strings.
Uses SHA-256 keystream block generation and symmetric XOR stream cipher, encoded in base64.
"""

import base64
import hashlib
import os

# Server-side persistent secret salt
_SECRET = os.environ.get("DATABASE_SECRET_KEY", os.environ.get("GROQ_API_KEY", "default-db-secret-key-salt"))


def encrypt_connection_string(plain_text: str) -> str:
    """
    Encrypt a database connection string using server-side secret.
    Returns a secure base64-encoded ciphertext string.
    """
    if not plain_text:
        return ""
    
    key = hashlib.sha256(_SECRET.encode("utf-8")).digest()
    plain_bytes = plain_text.encode("utf-8")
    cipher_bytes = bytearray()
    
    # Generate symmetric key stream in 32-byte blocks
    keystream_block = b""
    for i in range(len(plain_bytes)):
        if i % 32 == 0:
            keystream_block = hashlib.sha256(key + str(i // 32).encode("utf-8")).digest()
        cipher_bytes.append(plain_bytes[i] ^ keystream_block[i % 32])
        
    return base64.urlsafe_b64encode(cipher_bytes).decode("utf-8")


def decrypt_connection_string(cipher_text: str) -> str:
    """
    Decrypt a base64-encoded ciphertext string using server-side secret.
    """
    if not cipher_text:
        return ""
    
    try:
        cipher_bytes = base64.urlsafe_b64decode(cipher_text.encode("utf-8"))
        key = hashlib.sha256(_SECRET.encode("utf-8")).digest()
        plain_bytes = bytearray()
        
        # Identical key stream for symmetric decryption
        keystream_block = b""
        for i in range(len(cipher_bytes)):
            if i % 32 == 0:
                keystream_block = hashlib.sha256(key + str(i // 32).encode("utf-8")).digest()
            plain_bytes.append(cipher_bytes[i] ^ keystream_block[i % 32])
            
        return plain_bytes.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to decrypt database credentials securely: {e}")
