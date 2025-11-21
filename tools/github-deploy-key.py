#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import requests
import getpass

def err(msg):
    print(f"❌ {msg}", file=sys.stderr)

def info(msg):
    print(f"ℹ️  {msg}")

def ok(msg):
    print(f"✅ {msg}")

def parse_args():
    parser = argparse.ArgumentParser(description="Ensure GitHub deploy key is added")
    parser.add_argument("--repo", required=True, help="GitHub repo in 'org/repo' format")
    parser.add_argument("--user", required=True, help="Local system user owning the key")
    parser.add_argument("--key-path", required=True, help="Path to the public key file")
    return parser.parse_args()

def read_key(pubkey_path):
    if not os.path.exists(pubkey_path):
        err(f"Public key {pubkey_path} does not exist")
        sys.exit(1)
    with open(pubkey_path) as f:
        return f.read().strip()

def prompt_for_token():
    print("\nA GitHub Personal Access Token is required.")
    print("Scopes required:  ✨  **repo (full access to repos)**")
    print("Create one at:    https://github.com/settings/tokens\n")
    print("Your input will be hidden for security.\n")

    token = getpass.getpass("Paste GitHub token: ").strip()

    if not token:
        err("No token provided. Aborting.")
        sys.exit(1)

    return token

def get_github_token():
    token = os.environ.get("GITHUB_TOKEN")

    if token:
        # Validate the token safely (without revealing it)
        if validate_token(token):
            return token
        else:
            warn("Existing GITHUB_TOKEN appears invalid; prompting for a new token.")

    token = prompt_for_token()

    # Validate before using
    if not validate_token(token):
        err("Token appears invalid or has insufficient permissions.")
        sys.exit(1)

    # Store in env for the lifetime of the script (not shown to user)
    os.environ["GITHUB_TOKEN"] = token
    return token

def validate_token(token):
    """Validate token without printing it or exposing it."""
    try:
        r = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
            timeout=6
        )
        return r.status_code == 200
    except Exception:
        return False

def list_deploy_keys(repo, token):
    url = f"https://api.github.com/repos/{repo}/keys"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 404:
        err(f"Repository {repo} not found or insufficient permissions")
        sys.exit(1)
    r.raise_for_status()
    return r.json()

def main():
    args = parse_args()
    pubkey = read_key(args.key_path)
    token = get_github_token()

    keys = list_deploy_keys(args.repo, token)
    key_short = pubkey.split()[1]

    if any(key_short in k["key"] for k in keys):
        ok(f"Deploy key already exists for {args.repo}")
        return

    info(f"Deploy key not found for {args.repo}")
    print("\n=== Public Key to add to GitHub deploy keys ===")
    print(pubkey)
    print(f"\nAdd the key at:")
    print(f"  👉  https://github.com/{args.repo}/settings/keys\n")

    input("Once added, press ENTER to continue...")

    ok("User confirmed deploy key added.")
    print("You may now retry the clone step.\n")

if __name__ == "__main__":
    main()
