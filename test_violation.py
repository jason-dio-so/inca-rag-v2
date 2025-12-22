# This file intentionally violates PR Guardian rules
# to test the CI failure detection

def get_carrier_info():
    """Get carrier information - THIS SHOULD FAIL PR GUARDIAN"""
    carrier = "SAMSUNG"  # VIOLATION: should use 'insurer' not 'carrier'
    return carrier
