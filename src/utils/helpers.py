import hashlib
import uuid

def unique_generator(*, length: int = 8) -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:length]