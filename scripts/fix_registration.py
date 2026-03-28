#!/usr/bin/env python3
"""Fix registration - move out of if setup_mining() block."""

import json
from pathlib import Path

def fix_registration():
    """Move agent.register() out of if setup_mining() block."""
    nb_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    
    with open(nb_path) as f:
        notebook = json.load(f)
    
    source = notebook["cells"][0]["source"]
    lines = source.split('\n')
    
    # Find and fix the registration block
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Find the problematic block
        if 'if setup_mining():' in line and i < len(lines) - 10:
            # Check if agent.register() is inside this block
            indent_level = len(line) - len(line.lstrip())
            
            # Add the if block
            new_lines.append(line)
            i += 1
            
            # Collect lines inside if block
            if_block = []
            while i < len(lines):
                current = lines[i]
                current_indent = len(current) - len(current.lstrip()) if current.strip() else indent_level + 4
                
                # If line is less indented or is agent.register(), handle specially
                if current_indent <= indent_level and current.strip():
                    # End of if block
                    break
                
                if_block.append(current)
                i += 1
            
            # Process if_block - move agent.register() out
            for if_line in if_block:
                if 'agent.register()' in if_line:
                    # Move this line out of if block (reduce indentation)
                    fixed_line = if_line.lstrip()  # Remove extra indent
                    new_lines.append(fixed_line)
                else:
                    new_lines.append(if_line)
            
            continue
        
        new_lines.append(line)
        i += 1
    
    new_source = '\n'.join(new_lines)
    
    notebook["cells"][0]["source"] = new_source
    
    with open(nb_path, 'w') as f:
        json.dump(notebook, f, indent=2)
    
    print(f"✓ Fixed registration - moved out of if setup_mining() block")
    print(f"  Source length: {len(new_source)} chars")
    return True

if __name__ == "__main__":
    fix_registration()
