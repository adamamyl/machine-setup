#!/usr/bin/env python3
import argparse, os, sys, time, subprocess
try: import requests
except Exception:
    print("Missing 'requests' module. Install via pip: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

GITHUB_API = "https://api.github.com"

def run(cmd): return subprocess.run(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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

def check_deploy_key_present(repo,pubkey,token=None):
    owner,name = repo.split('/')
    url = f"{GITHUB_API}/repos/{owner}/{name}/keys"
    headers = {'Accept':'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    r = requests.get(url, headers=headers)
    if r.status_code != 200: return False, r.status_code
    for k in r.json():
        if k.get('key') == pubkey:
            return True, 200
    return False, 200

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--key-path', required=True)
    parser.add_argument('--token', default=os.environ.get('GITHUB_TOKEN'))
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()

    pub = ensure_key(args.user, args.key_path)
    print('\n=== Public Key to add to GitHub deploy-keys ===')
    print(pub)
    owner,name = args.repo.split('/')
    print(f'Add the key to: https://github.com/{owner}/{name}/settings/keys')

    start=time.time()
    while True:
        found,status=check_deploy_key_present(args.repo,pub,args.token)
        if found:
            print('Key detected on GitHub. Proceeding...')
            sys.exit(0)
        elapsed=time.time()-start
        if elapsed>args.timeout:
            print(f'Timeout ({args.timeout}s) waiting for key. Exiting.', file=sys.stderr)
            sys.exit(3)
        print('Key not found yet. Waiting 5s and retrying...')
        time.sleep(5)

if __name__=='__main__':
    main()
