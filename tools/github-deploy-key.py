#!/usr/bin/env python3
"""
GitHub Deploy Key Helper Script

Generates an SSH key for a user and waits for it to appear as a deploy key in a GitHub repository.
Supports both personal and organization repositories.

Usage:
    python3 github-deploy-key.py --repo owner/repo --user USERNAME --key-path /path/to/key.pub [--timeout 600]

GitHub Token:
-------------
For private repositories, especially those owned by an organization, you need a
Personal Access Token (PAT) with access to the repository.

1. Go to GitHub token creation page:
   https://github.com/settings/tokens

2. Click "Generate new token" (classic) or "Generate new token (fine-grained)"

3. Recommended scopes:
   - Classic token:
       * repo (Full control of private repositories)
   - Fine-grained token:
       * Resource owner: select the Organization
       * Repository access: select the repository
       * Permissions: "Read & Write" for Deploy keys

4. Copy the token and export it in your environment:
       export GITHUB_TOKEN=ghp_xxxxxxxxxxxxx

Notes:
------
- Without proper token scopes, the API may return 404 even if the key exists in the UI.
- The script will print the public key and the URL to add it manually if needed.
- For organization repos, if API returns 404, confirm manually in the UI.
"""
import argparse, os, sys, time, subprocess
try:
    import requests
except Exception:
    print("Missing 'requests' module. Install via pip: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

GITHUB_API = "https://api.github.com"

def run(cmd):
    return subprocess.run(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def ensure_key(user, key_path):
    priv = key_path.replace('.pub','')
    if not os.path.exists(key_path):
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        cmd = ['ssh-keygen','-t','ed25519','-f',priv,'-N','','-C',f"{user}@{os.uname().nodename}"]
        print(f"Generating SSH key for {user}: {' '.join(cmd)}")
        r = run(cmd)
        if r.returncode != 0:
            print('ssh-keygen failed', r.stderr.decode(), file=sys.stderr)
            sys.exit(1)
    with open(key_path,'r') as f:
        pub = f.read().strip()
    return pub

def check_deploy_key_present(repo, pubkey, token=None):
    owner,name = repo.split('/')
    url = f"{GITHUB_API}/repos/{owner}/{name}/keys"
    headers = {'Accept':'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    r = requests.get(url, headers=headers)
    if r.status_code == 404:
        # Could be an org repo where token cannot see repo
        return False, 404
    if r.status_code != 200:
        print(f"GitHub API returned {r.status_code}: {r.text}", file=sys.stderr)
        return False, r.status_code
    for k in r.json():
        if k.get('key') == pubkey:
            return True, 200
    return False, 200

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, help="GitHub repository in owner/name format")
    parser.add_argument('--user', required=True, help="Local user for SSH key")
    parser.add_argument('--key-path', required=True, help="Path to public key (.pub)")
    parser.add_argument('--token', default=os.environ.get('GITHUB_TOKEN'))
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()

    pub = ensure_key(args.user, args.key_path)
    print('\n=== Public Key to add to GitHub deploy-keys ===')
    print(pub)
    owner,name = args.repo.split('/')
    print(f'Add the key to: https://github.com/{owner}/{name}/settings/keys')

    start = time.time()
    while True:
        found, status = check_deploy_key_present(args.repo, pub, args.token)
        if found:
            print('✅ Key detected on GitHub. Proceeding...')
            sys.exit(0)
        elif status == 404:
            print("⚠️ API cannot access this repo (organization or permission issue).")
            input("Please confirm the deploy key is added in the GitHub UI, then press Enter to continue...")
            found = True
            continue
        elapsed = time.time() - start
        if elapsed > args.timeout:
            print(f"⏱ Timeout ({args.timeout}s) waiting for key. Exiting.", file=sys.stderr)
            sys.exit(3)
        print("Key not found yet. Waiting 5s and retrying...")
        time.sleep(5)

if __name__=='__main__':
    main()
