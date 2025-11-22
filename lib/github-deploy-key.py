#!/usr/bin/env python3
import os
import sys
import subprocess

token = os.getenv("GITHUB_TOKEN")
if not token:
    import getpass
    token = getpass.getpass("Enter GitHub token (input hidden): ")

repo = sys.argv[1]
key_path = sys.argv[2]

# Provide instructions
print(f"Add the public key {key_path}.pub to the repository: {repo}")
input("Press Enter once added...")

subprocess.run([
    "ssh", "-i", key_path, "git@github.com"
])
