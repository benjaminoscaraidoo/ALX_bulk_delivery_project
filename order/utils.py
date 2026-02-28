import uuid

def generate_package_id():
    return f"PKG{uuid.uuid4().hex[:8].upper()}"

def generate_order_id():
    return f"ORD{uuid.uuid4().hex[:8].upper()}"
