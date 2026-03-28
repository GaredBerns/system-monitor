#!/usr/bin/env python3
"""Completely fix notebook structure - move registration to main block."""

import json
from pathlib import Path

def fix_notebook_structure():
    """Fix notebook structure - ensure registration is in main block."""
    nb_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    
    with open(nb_path) as f:
        notebook = json.load(f)
    
    source = notebook["cells"][0]["source"]
    lines = source.split('\n')
    
    # Find and extract the registration block
    registration_block = None
    registration_start = None
    registration_end = None
    
    for i, line in enumerate(lines):
        if '# Register' in line and 'agent.register()' in lines[i+1] if i+1 < len(lines) else False:
            registration_start = i
            # Find end of registration block
            for j in range(i, min(i+20, len(lines))):
                if lines[j].strip().startswith('# Start beacon') or lines[j].strip().startswith('threading.Thread'):
                    registration_end = j
                    break
            
            if registration_start and registration_end:
                registration_block = lines[registration_start:registration_end]
                break
    
    if not registration_block:
        print("✗ Could not find registration block")
        return False
    
    # Remove registration from inside functions
    new_lines = []
    skip_until = -1
    
    for i, line in enumerate(lines):
        # Skip lines that are inside function definitions
        if i >= registration_start and i < registration_end:
            continue
        
        new_lines.append(line)
    
    # Find where to insert registration (after agent creation, before monitoring loop)
    insert_idx = None
    for i, line in enumerate(new_lines):
        if 'agent = C2Agent(tg_c2)' in line:
            # Find next good insertion point
            for j in range(i+1, min(i+30, len(new_lines))):
                if new_lines[j].strip().startswith('print(') and 'ANALYZER' in new_lines[j]:
                    insert_idx = j
                    break
            break
    
    if insert_idx:
        # Insert registration block at correct location with correct indentation
        # First, ensure correct indentation (0 spaces for top-level)
        fixed_registration = []
        for line in registration_block:
            # Remove any leading whitespace and add correct indent
            fixed_registration.append(line.lstrip())
        
        new_lines = new_lines[:insert_idx] + fixed_registration + new_lines[insert_idx:]
        new_source = '\n'.join(new_lines)
        
        notebook["cells"][0]["source"] = new_source
        
        with open(nb_path, 'w') as f:
            json.dump(notebook, f, indent=2)
        
        print(f"✓ Fixed notebook structure")
        print(f"  Registration moved to main block")
        print(f"  Source length: {len(new_source)} chars")
        return True
    
    print("✗ Could not find insertion point")
    return False

if __name__ == "__main__":
    fix_notebook_structure()
