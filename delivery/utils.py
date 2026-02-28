import uuid

def generate_delivery_id():
    return f"DEL{uuid.uuid4().hex[:8].upper()}"

def generate_transaction_id():
    return f"TXN{uuid.uuid4().hex[:8].upper()}"
