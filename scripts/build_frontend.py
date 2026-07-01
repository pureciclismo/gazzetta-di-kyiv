#!/usr/bin/env python3
import subprocess
import shutil
import os
from pathlib import Path

def build():
    print("[build_frontend] Starting Next.js build...")
    project_root = Path(__file__).resolve().parent.parent
    web_dir = project_root / "web"
    public_dir = project_root / "public"
    data_dir = project_root / "data"
    public_data = public_dir / "data"
    posted_stories = public_data / "posted_stories.jsonl"
    
    # Run npm run build in the web directory
    try:
        subprocess.run(["npm", "install"], cwd=web_dir, check=True)
        subprocess.run(["npm", "run", "build"], cwd=web_dir, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error building Next.js app: {e}")
        raise
        
    # Save posted_stories.jsonl if it exists
    posted_stories_backup = None
    if posted_stories.exists():
        posted_stories_backup = posted_stories.read_text()
        
    # Clear the public directory completely
    if public_dir.exists():
        shutil.rmtree(public_dir)
    public_dir.mkdir(parents=True, exist_ok=True)
            
    # Copy web/out to public/
    out_dir = web_dir / "out"
    if out_dir.exists():
        for item in out_dir.iterdir():
            dest = public_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
                
    # Copy project root /data to public/data so it can be uploaded
    if data_dir.exists():
        shutil.copytree(data_dir, public_data, dirs_exist_ok=True)
        
    # Restore posted_stories.jsonl
    if posted_stories_backup:
        public_data.mkdir(parents=True, exist_ok=True)
        posted_stories.write_text(posted_stories_backup)
            
    print("[build_frontend] Build complete. Output copied to public directory.")

if __name__ == "__main__":
    build()
