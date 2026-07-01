import sys
content = open("scripts/build_frontend.py").read()
if "npm install" not in content:
    content = content.replace('subprocess.run(["npm", "run", "build"], cwd=web_dir, check=True)', 'subprocess.run(["npm", "install"], cwd=web_dir, check=True)\n        subprocess.run(["npm", "run", "build"], cwd=web_dir, check=True)')
    open("scripts/build_frontend.py", "w").write(content)
