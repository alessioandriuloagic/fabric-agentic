#!/usr/bin/env python3

import sys
import traceback

try:
    from scripts.fabric_crm_preflight import FabricClient
    print("✓ FabricClient imported successfully")
    
    # Try to check the method signature
    import inspect
    sig = inspect.signature(FabricClient.ensure_item)
    print(f"✓ ensure_item signature: {sig}")
    print(f"✓ ensure_item return annotation: {sig.return_annotation}")
    
    # Try to create an instance (will fail without token, but that's ok)
    try:
        client = FabricClient("dummy-token")
        print("✓ FabricClient instance created successfully")
    except Exception as e:
        print(f"✗ Error creating instance: {e}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All checks passed!")
