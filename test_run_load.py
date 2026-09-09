#!/usr/bin/env python3

import sys
import traceback

# Minimal reproduction of the fabric_crm_load script behavior
try:
    from scripts.fabric_crm_load import run_load, main
    print("OK: fabric_crm_load imported successfully")
    
    # Try calling main with work-item-id
    sys.argv = ["fabric_crm_load", "--work-item-id", "158"]
    print(f"OK: sys.argv set to: {sys.argv}")
    
    exit_code = main()
    print(f"OK: main() returned: {exit_code}")
    
except SystemExit as e:
    print(f"ERROR: SystemExit: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\nOK: Script execution completed!")
