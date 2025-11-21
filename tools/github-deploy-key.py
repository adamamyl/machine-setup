#!/usr/bin/env python3
"""
GitHub Deploy Key Helper Script (interactive)

- Generates SSH key for a user
- Prints the public key and the GitHub URL to add it manually
- Prompts for GitHub token if missing/invalid
- Prompts for confirmation once deploy key is added (no polling)
"""

import os, sys, subprocess

try:
    import requests
except ImportError:
    print("Missing 'requests' module. Install via pip: pip install requests", file=sys.stderr)
    sys.exit(1)


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print(f"Command failed: {cmd}\n{r.stderr.decode()}", file=sys.stderr)
        sys.exit(1)
    return r.stdout.decode().strip()


def ensure_ssh_key(user, key_path):
    priv = key_path.replace('.pub','')
    if not os.path.exists(key_path):
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        run(['ssh-keygen','-t','ed25519','-f',priv,'-N','','-C',f"{user}@{os.uname().nodename}"])
    with open(key_path,'r') as f:
        return f.read().strip()


def verify_token(repo, token):
    import requests
    owner, name = repo.split('/')
    url = f"https://api.github.com/repos/{owner}/{name}"
    headers = {'Authorization': f'token {token}', 'Accept':'application/vnd.github.v3+json'}
    r = requests.get(url, headers=headers)
    return r.status_code == 200


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Add deploy key to GitHub repo interactively")
    parser.add_argument('--repo', required=True, help="GitHub repo in owner/name format")
    parser.add_argument('--user', required=True, help="Local user for SSH key")
    parser.add_argument('--key-path', required=True, help="Path to public key (.pub)")
    args = parser.parse_args()

    pub = ensure_ssh_key(args.user, args.key_path)

    print("\n=== Public Key to add to GitHub deploy-keys ===")
    print(pub)
    owner, name = args.repo.split('/')
    print(f"Add the key to: https://github.com/{owner}/{name}/settings/keys")

    # Ensure we have a valid token
    token = os.environ.get('GITHUB_TOKEN')
    while True:
        if token and verify_token(args.repo, token):
            break
        print("⚠️ GitHub token not set or invalid.")
        token = input("Paste a valid GitHub Personal Access Token (or leave blank to continue manually): ").strip()
        if not token:
            print("Proceeding without API verification. You must confirm manually.")
            break

    input("✅ Once the key is added in the GitHub UI, press Enter to continue...")

    print("All done.")
    sys.exit(0)


if __name__ == '__main__':
    main()
