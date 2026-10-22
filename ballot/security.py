from cryptography.fernet import Fernet
from pathlib import Path

KEY_FILE = Path("ballot_key.key")


def load_or_create_key():
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


FERNET_KEY = load_or_create_key()
cipher = Fernet(FERNET_KEY)


def encrypt_ballot(ballot_text: str) -> str:
    encrypted = cipher.encrypt(ballot_text.encode())
    return encrypted.decode()


def decrypt_ballot(encrypted_text: str) -> str:
    decrypted = cipher.decrypt(encrypted_text.encode())
    return decrypted.decode()