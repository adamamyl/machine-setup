#!/usr/bin/env python3
import os
import subprocess
import argparse
import datetime
import difflib

DEFAULT_ENV_FILE = ".env"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
MASK_NEW = f"{RED}🔒 [new]{RESET}"
MASK_EXISTING = f"{GREEN}🔒 [existing]{RESET}"

def diceware_password():
    return subprocess.check_output(["diceware", "-n", "5"], text=True).strip().replace(" ", "-")

def load_env_file(filename):
    """Return dict of key=value from a .env-style file."""
    data = {}
    if not os.path.exists(filename):
        return data
    with open(filename) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            data[key.strip()] = val.strip()
    return data

def mask_value(line, is_new):
    """Mask a line depending on whether the value is new or existing."""
    if "=" not in line:
        return line
    key, sep, val = line.partition("=")
    mask = MASK_NEW if is_new else MASK_EXISTING
    return f"{key}={mask}"

def backup_file(filename):
    """Backup file with timestamp if it exists."""
    if os.path.exists(filename):
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup_name = f"{filename}.bak.{timestamp}"
        os.rename(filename, backup_name)
        print(f"{YELLOW}💾 Backed up existing {filename} → {backup_name}{RESET}")

def ensure_ignore_file(ignore_file, patterns):
    """Add patterns to ignore file if not present."""
    if os.path.exists(ignore_file):
        with open(ignore_file, "r") as f:
            existing = f.read().splitlines()
    else:
        existing = []
    updated = False
    with open(ignore_file, "a") as f:
        for pattern in patterns:
            if pattern not in existing:
                f.write(pattern + "\n")
                updated = True
    if updated:
        print(f"{BLUE}📝 Updated {ignore_file} with {', '.join(patterns)}{RESET}")

def main():
    parser = argparse.ArgumentParser(description="Sync .env from template with Diceware passwords")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--sort", action="store_true", help="Sort keys alphabetically in output (keep comments)")
    parser.add_argument("--env", default=None, help="Environment name, e.g. dev, staging")
    parser.add_argument("--template", default=None, help="Specify a custom template file")
    args = parser.parse_args()

    # --- Determine template file ---
    if args.template:
        template_file = args.template
        if not os.path.exists(template_file):
            print(f"{RED}❌ Specified template file {template_file} not found. Aborting.{RESET}")
            return
    elif args.env:
        template_file = f".env-template.{args.env}"
        if not os.path.exists(template_file):
            print(f"{YELLOW}⚠️  Template {template_file} not found, falling back to .env-template{RESET}")
            template_file = ".env-template"
    else:
        template_file = ".env-template"

    if not os.path.exists(template_file):
        print(f"{RED}❌ Template file {template_file} not found. Aborting.{RESET}")
        return

    # --- Determine output file ---
    if args.env:
        output_file = f".env-{args.env}"
    else:
        output_file = DEFAULT_ENV_FILE

    existing = load_env_file(output_file)
    added_keys = []
    reused_keys = []
    skipped_lines = 0

    # --- Read template and group comments ---
    blocks = []
    comment_block = []
    key_status = {}
    for line in open(template_file):
        stripped = line.rstrip("\n")
        if not stripped:
            if comment_block:
                blocks.append({"lines": comment_block, "key": None})
                comment_block = []
            blocks.append({"lines": [""], "key": None})
            skipped_lines += 1
            continue
        if stripped.startswith("#"):
            comment_block.append(stripped)
            continue

        key, sep, value = stripped.partition("=")
        key = key.strip()
        if key in existing:
            val = existing[key]
            reused_keys.append(key)
            key_status[key] = False  # existing
        else:
            val = f'"{diceware_password()}"'
            added_keys.append(key)
            key_status[key] = True  # new

        block_lines = comment_block + [f"{key}={val}"]
        blocks.append({"lines": block_lines, "key": key})
        comment_block = []

    # Include extra keys from existing output file
    for key, val in existing.items():
        if key not in [b["key"] for b in blocks if b["key"]]:
            blocks.append({"lines": [f"{key}={val}"], "key": key})
            reused_keys.append(key)
            key_status[key] = False

    # Optional sorting
    if args.sort:
        key_blocks = [b for b in blocks if b["key"]]
        other_blocks = [b for b in blocks if not b["key"]]
        key_blocks_sorted = sorted(key_blocks, key=lambda b: b["key"].lower())
        blocks = other_blocks[:] + key_blocks_sorted

    # Flatten blocks
    output_lines = []
    for b in blocks:
        output_lines.extend(b["lines"])

    # --- Summary ---
    print(f"\n✨ Synced {output_file} with {template_file}\n")
    if reused_keys:
        print(f"{GREEN}💚 Reused existing:{RESET} {', '.join(reused_keys)}")
    if added_keys:
        print(f"{YELLOW}💛 Added new:{RESET} {', '.join(added_keys)}")
    print(f"{RED}❤️ Skipped comments/blank lines: {skipped_lines}{RESET}")

    # --- Prepare masked lines for diff / dry-run ---
    display_lines = []
    for line in output_lines:
        if "=" in line and not line.startswith("#"):
            key = line.split("=")[0].strip()
            is_new = key_status.get(key, True)
            display_lines.append(mask_value(line, is_new))
        else:
            display_lines.append(line)

    if args.dry_run:
        # Mask old file lines as well
        old_lines = []
        if os.path.exists(output_file):
            for line in open(output_file):
                line = line.rstrip("\n")
                if "=" in line and not line.startswith("#"):
                    old_lines.append(mask_value(line, False))
                else:
                    old_lines.append(line)

        if old_lines:
            diff = difflib.unified_diff(old_lines, display_lines,
                                        fromfile=output_file,
                                        tofile="proposed .env",
                                        lineterm="")
            print(f"\n{BLUE}🔍 Dry run mode — no changes written.{RESET}\n")
            print("Proposed .env content diff (passwords masked):\n")
            for line in diff:
                if line.startswith("+"):
                    print(f"{GREEN}{line}{RESET}")
                elif line.startswith("-"):
                    print(f"{RED}{line}{RESET}")
                elif line.startswith("@"):
                    print(f"{BLUE}{line}{RESET}")
                else:
                    print(line)
            print()
        else:
            print(f"\n{BLUE}🔍 Dry run mode — .env does not exist yet. Proposed content:\n{RESET}")
            print("\n".join(display_lines))
    else:
        backup_file(output_file)
        with open(output_file, "w") as f:
            f.write("\n".join(output_lines) + "\n")
        os.chmod(output_file, 0o600)
        print(f"\n✅ Updated {output_file} (permissions set to 600)\n")

    # --- Ensure gitignore and dockerignore ---
    ensure_ignore_file(".gitignore", [output_file, ".env-template*"])
    ensure_ignore_file(".dockerignore", [output_file, ".env-template*"])

if __name__ == "__main__":
    main()
