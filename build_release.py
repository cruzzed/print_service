#!/usr/bin/env python3
"""
Build script for creating QR Print Client releases
"""

import os
import shutil
import zipfile
from pathlib import Path

def create_release():
    """Create a release package"""
    
    # Define paths
    current_dir = Path(__file__).parent
    release_dir = current_dir / "release"
    
    # Clean and create release directory
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir()
    
    # Files to include in release
    files_to_include = [
        "gui_qr_print_service.py",
        "install.bat",
        "install.sh",
        "README.md",
        "requirements.txt"
    ]
    
    # Copy files to release directory
    for file_name in files_to_include:
        src = current_dir / file_name
        if src.exists():
            shutil.copy2(src, release_dir / file_name)
            print(f"✓ Copied {file_name}")
        else:
            print(f"⚠ Warning: {file_name} not found")
    
    # Create ZIP file
    zip_path = current_dir / "qr-print-client.zip"
    if zip_path.exists():
        zip_path.unlink()
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in release_dir.rglob("*"):
            if file_path.is_file():
                # Store files with relative path from release directory
                arcname = file_path.relative_to(release_dir)
                zipf.write(file_path, arcname)
                print(f"✓ Added {arcname} to ZIP")
    
    print(f"\n🎉 Release created: {zip_path}")
    print(f"📁 Release files also available in: {release_dir}")
    
    return zip_path

if __name__ == "__main__":
    create_release()