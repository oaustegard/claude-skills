#!/usr/bin/env python3
"""
Setup script for webctl with authenticated proxy support.

Run: python3 /mnt/skills/user/using-webctl/scripts/setup_webctl.py
"""

import subprocess
import sys
from pathlib import Path


def run(cmd, check=True):
    """Run shell command."""
    print(f"  → {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"    ERROR: {result.stderr}")
        return False
    return True


def main():
    print("Setting up webctl with proxy auth support...\n")
    
    # 1. Install webctl
    print("[1/4] Installing webctl...")
    if not run("pip install webctl --break-system-packages"):
        return 1
    
    # 2. Setup browser
    print("\n[2/4] Setting up browser...")
    if not run("webctl setup"):
        return 1
    
    # 3. Copy auth_proxy.py
    print("\n[3/4] Deploying auth proxy module...")
    skill_dir = Path(__file__).parent.parent
    auth_proxy_src = skill_dir / "scripts" / "auth_proxy.py"
    dest_dir = Path("/usr/local/lib/python3.12/dist-packages/webctl/daemon")
    
    if not dest_dir.exists():
        print(f"    ERROR: webctl daemon directory not found: {dest_dir}")
        return 1
    
    import shutil
    shutil.copy(auth_proxy_src, dest_dir / "auth_proxy.py")
    print(f"    Copied auth_proxy.py to {dest_dir}")
    
    # 4. Patch session_manager.py
    print("\n[4/4] Patching session manager...")
    session_mgr = dest_dir / "session_manager.py"
    
    content = session_mgr.read_text()
    
    old_block = '''        # Create context
        context = await browser.new_context(
            storage_state=storage_state, viewport={"width": 1280, "height": 720}
        )'''
    
    new_block = '''        # Create context with proxy from env (with auth handling)
        from .auth_proxy import get_local_proxy_url
        proxy_url = get_local_proxy_url()
        proxy_config = {"server": proxy_url} if proxy_url else None
        
        context = await browser.new_context(
            storage_state=storage_state, 
            viewport={"width": 1280, "height": 720},
            proxy=proxy_config
        )'''
    
    if old_block in content:
        content = content.replace(old_block, new_block)
        session_mgr.write_text(content)
        print("    Patched session_manager.py")
    elif "get_local_proxy_url" in content:
        print("    Already patched")
    else:
        print("    WARNING: Could not find expected code block to patch")
        print("    Manual patching may be required - see SKILL.md")
    
    print("\n✓ Setup complete!")
    print("\nTest with:")
    print("  webctl start --mode unattended")
    print('  webctl --quiet navigate "https://github.com"')
    print("  webctl snapshot --interactive-only --limit 10")
    print("  webctl stop --daemon")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
