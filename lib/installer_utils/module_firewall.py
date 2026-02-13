import os
from ..executor import Executor
from ..logger import log
from ..constants import FIREWALL_SCRIPT_DEST, FIREWALL_SERVICE_NAME, FIREWALL_PACKAGES
from .apt_tools import apt_install

# ==============================================================================
# FIREWALL RULES HELPER SCRIPT (Diagnostic Tool)
# ==============================================================================
# Note: This string uses 'r' prefix to treat backslashes literally and 
# starts the content at the very first column to prevent IndentationErrors.
FIREWALL_RULES_HELPER_CONTENT = r"""#!/usr/bin/env python3
import json, subprocess

# ANSI Color Codes for Dark Mode Terminals
C_RESET = "\033[0m"
C_BOLD  = "\033[1m"
C_GREEN = "\033[32m"
C_RED   = "\033[31m"
C_CYAN  = "\033[36m"
C_BLUE  = "\033[34m"
C_YELL  = "\033[33m"

def extract_address(val):
    """Extract readable IP/CIDR from nftables expr right field."""
    if isinstance(val, str):
        return [val]
    if isinstance(val, dict):
        if "prefix" in val:
            p = val["prefix"]
            return [f"{p['addr']}/{p['len']}"]
        if "set" in val:
            result = []
            for entry in val["set"]:
                result.extend(extract_address(entry))
            return result
    return ["-"]

# Fetch nftables ruleset JSON
try:
    raw = subprocess.check_output(["nft", "-j", "list", "ruleset"], text=True)
    ruleset = json.loads(raw)
except Exception as e:
    print("Error fetching nftables ruleset:", e)
    exit(1)

columns = ["Num", "Pkts", "Bytes", "Target", "Prot", "Opt", "In", "Out",
           "Source", "Destination", "Chain", "Table", "Family"]
rows = []

# Process each rule
for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule:
        continue

    num = str(rule.get("handle", "-"))
    pkts = bytes_ = "0"
    target = "-"
    prot = opt = "-"
    in_if = out_if = "-"
    src = dst = []

    exprs = rule.get("expr", [])
    for expr in exprs:
        if "counter" in expr:
            pkts = str(expr["counter"].get("packets", 0))
            bytes_ = str(expr["counter"].get("bytes", 0))
        if "jump" in expr:
            target = str(expr["jump"].get("target", "-"))
        if "accept" in expr:
            target = "ACCEPT"
        if "reject" in expr:
            target = "REJECT"
        if "drop" in expr:
            target = "DROP"

        meta = expr.get("meta")
        if meta:
            key = meta.get("key")
            if key == "iifname":
                in_if = str(meta.get("iifname", "-"))
            elif key == "oifname":
                out_if = str(meta.get("oifname", "-"))
            elif key == "l4proto":
                prot = str(meta.get("l4proto", "-"))

        match = expr.get("match")
        if match and "left" in match:
            left = match["left"]
            right = match.get("right", "-")
            if "payload" in left:
                fld = left["payload"].get("field")
                if fld == "saddr":
                    src.extend(extract_address(right))
                elif fld == "daddr":
                    dst.extend(extract_address(right))
            elif "meta" in left:
                key = left["meta"].get("key")
                if key == "iifname":
                    in_if = str(right)
                elif key == "oifname":
                    out_if = str(right)

    src = src if src else ["-"]
    dst = dst if dst else ["-"]

    rows.append([
        num, pkts, bytes_, target, prot, opt, in_if, out_if,
        "\n".join(src),
        "\n".join(dst),
        rule.get("chain", "-"),
        rule.get("table", "-"),
        rule.get("family", "-")
    ])

# Compute column widths (ignoring color codes)
widths = [max(len(col), *(max(len(line) for line in str(row[i]).split("\n")) for row in rows))
          for i, col in enumerate(columns)]

def hline(char="-", cross="+"):
    return cross + cross.join([char * (width + 2) for width in widths]) + cross

def apply_color(val, col_name):
    """Apply ANSI colors and emojis based on content."""
    s_val = str(val)
    if col_name == "Target":
        if "ACCEPT" in s_val: return f"{C_BOLD}{C_GREEN}✅ {s_val}{C_RESET}"
        if "DROP" in s_val or "REJECT" in s_val: return f"{C_BOLD}{C_RED}❌ {s_val}{C_RESET}"
        return f"{C_YELL}↪️ {s_val}{C_RESET}"
    if col_name in ["In", "Out"]:
        if "tailscale" in s_val: return f"{C_CYAN}🕵️  {s_val}{C_RESET}"
        if "lo" in s_val: return f"{C_BLUE}🔄 {s_val}{C_RESET}"
        if "br-" in s_val or "docker" in s_val: return f"{C_YELL}🐳 {s_val}{C_RESET}"
        if s_val == "-": return s_val
        return f"{C_BOLD}{s_val}{C_RESET}"
    if col_name == "Num": return f"{C_YELL}{s_val}{C_RESET}"
    return s_val

# Print table
print(hline("=", "+"))
print("| " + " | ".join(columns[i].ljust(widths[i]) for i in range(len(columns))) + " |")
print(hline("=", "+"))

last_chain_table_family = ("", "", "")
for row in rows:
    chain_table_family = (row[10], row[11], row[12])
    if chain_table_family != last_chain_table_family and last_chain_table_family != ("", "", ""):
        print(hline("-", "+"))
    last_chain_table_family = chain_table_family

    num_lines = max(len(str(row[i]).split("\n")) for i in range(len(row)))
    for line_idx in range(num_lines):
        line_parts = []
        for i in range(len(row)):
            cell_lines = str(row[i]).split("\n")
            raw_val = cell_lines[line_idx] if line_idx < len(cell_lines) else ""
            colored_val = apply_color(raw_val, columns[i])
            padding = " " * (widths[i] - len(raw_val))
            line_parts.append(f" {colored_val}{padding} ")
        print("|" + "|".join(line_parts) + "|")

print(hline("=", "+"))
"""

# ==============================================================================
# MAIN FIREWALL SCRIPT (iptables logic)
# ==============================================================================
FIREWALL_SCRIPT_CONTENT = """#!/bin/bash
# ============================================
# CONFIGURATION - NETWORK DEFINITIONS
# ============================================

# Check for verbose flag to toggle output
VERBOSE=false
if [[ "$1" == "--verbose" ]]; then
    VERBOSE=true
fi

# Helper function for conditional echoing
v_echo() {
    if [ "$VERBOSE" = true ]; then
        echo "$1"
    fi
}

# Network Definitions
TAILSCALE_V4="100.64.0.0/10"
TAILSCALE_V6="fd7a:115c:a1e0::/48"

# Specific Home/Office IPv4 Addresses
WOODSIDE_V4="90.210.184.112"

TRUSTED_V4=("$TAILSCALE_V4" "$WOODSIDE_V4")
TRUSTED_V6=("$TAILSCALE_V6")

# Docker Subnets (Extracted from your compose/network setup)
DOCKER_V4_SUBNET="172.16.0.0/12" # Broad range covering standard Docker pools
GHOST_NET_V4="172.18.0.0/16"    # Specific subnet seen in your nftables logs

TCP_ALLOWED=(80 443)
UDP_ALLOWED=()
SMTP_PORTS=(25 465 587)

# Idempotent directory creation for rule persistence
mkdir -p /etc/iptables

# ============================================
# APPLY RULES - IPv4
# ============================================
v_echo ">>> Initializing IPv4 Firewall Rules..."

# FORWARD Chain - The critical fix for Caddy/Docker
v_echo "    Configuring FORWARD chain (Least Privilege)..."
iptables -P FORWARD DROP
iptables -F FORWARD

# Allow established traffic back into containers
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow Docker containers to initiate outbound connections (DNS/ACME)
iptables -A FORWARD -s "$GHOST_NET_V4" -j ACCEPT
iptables -A FORWARD -s "$DOCKER_V4_SUBNET" -j ACCEPT

# DOCKER-USER Chain
v_echo "    Configuring DOCKER-USER chain..."
iptables -F DOCKER-USER

# Trust the tailscale interface
v_echo "    # Trust the tailscale interface"
iptables -A DOCKER-USER -i tailscale0 -j ACCEPT  

# trusted addresses (range)           
v_echo "    # trusted addresses (range)"
for ip in "${TRUSTED_V4[@]}"; do
    iptables -A DOCKER-USER -s "$ip" -j ACCEPT
done

# default stuff
v_echo "    # default stuff (established, related, public services)"
iptables -A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
for port in "${TCP_ALLOWED[@]}"; do
    iptables -A DOCKER-USER -p tcp --dport "$port" -j ACCEPT
done

iptables -A DOCKER-USER -j RETURN

# INPUT Chain (Host Protection)
v_echo "    Configuring INPUT chain (Host)..."
iptables -P INPUT DROP
iptables -F INPUT

# allow interfaces:
v_echo "    # allow interfaces: lo and tailscale0"
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -i tailscale0 -j ACCEPT

# allow states, and icmp
v_echo "    # allow states, and icmp"
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p icmp -j ACCEPT

# Trusted Access (SSH, Mosh, etc.)
v_echo "    # Trusted Access (SSH, Mosh, etc.)"
for ip in "${TRUSTED_V4[@]}"; do
    iptables -A INPUT -s "$ip" -j ACCEPT
done

# Public Services
v_echo "    # Public Services"
for port in "${TCP_ALLOWED[@]}"; do
    iptables -A INPUT -p tcp --dport "$port" -j ACCEPT
done

# Toggleable UDP Rule
v_echo "    # Toggleable UDP Rule"
for port in "${UDP_ALLOWED[@]}"; do
    iptables -A INPUT -p udp --dport "$port" -j ACCEPT
done

# reject everything else
v_echo "    # reject everything else"
iptables -A INPUT -j REJECT

# OUTPUT Chain
v_echo "    Configuring OUTPUT chain..."
# Block direct outbound SMTP 
v_echo "    # Block direct outbound SMTP to enforce smarthost usage"
for port in "${SMTP_PORTS[@]}"; do
    iptables -A OUTPUT -p tcp --dport "$port" -j REJECT --reject-with tcp-reset
done

# ============================================
# APPLY RULES - IPv6
# ============================================
v_echo ">>> Initializing IPv6 Firewall Rules..."

ip6tables -P INPUT DROP
ip6tables -F INPUT
ip6tables -P FORWARD DROP
ip6tables -F FORWARD

# accept v6 from these interfaces
v_echo "    # accept v6 from these interfaces: lo and tailscale0"
ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -A INPUT -i tailscale0 -j ACCEPT

# state
v_echo "    # state: established, related, and icmpv6"
ip6tables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
ip6tables -A INPUT -p ipv6-icmp -j ACCEPT

# allow-listing
v_echo "    # allow-listing trusted v6 addresses"
for ip6 in "${TRUSTED_V6[@]}"; do
    ip6tables -A INPUT -s "$ip6" -j ACCEPT
done

# Allow tcp traffic
v_echo "    # Allow tcp traffic (IPv6)"
for port in "${TCP_ALLOWED[@]}"; do
    ip6tables -A INPUT -p tcp --dport "$port" -j ACCEPT
done

# reject everything else
v_echo "    # reject everything else (IPv6)"
ip6tables -A INPUT -j REJECT

# ============================================
# PERSISTENCE
# ============================================
v_echo ">>> Saving rules..."
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6
v_echo "Firewall applied with Docker Forwarding restricted to local subnets."
"""

SERVICE_CONTENT = f"""[Unit]
Description=Custom Iptables Firewall with Docker and Tailscale Support
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={FIREWALL_SCRIPT_DEST}
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

def setup_firewall(exec_obj: Executor) -> None:
    """Installs required packages, scripts, and service. Prompts for application."""
    log.info("Starting **Firewall** setup...")

    # 1. Install Required Packages
    log.info("Ensuring firewall dependencies are installed...")
    apt_install(exec_obj, FIREWALL_PACKAGES)

    # 2. Install the Management Script
    log.info(f"Writing firewall management script to {FIREWALL_SCRIPT_DEST}")
    tmp_path = "/tmp/firewall_setup.sh"
    with open(tmp_path, "w") as f:
        f.write(FIREWALL_SCRIPT_CONTENT)
    
    exec_obj.run(f"mv {tmp_path} {FIREWALL_SCRIPT_DEST}", force_sudo=True)
    exec_obj.run(f"chmod +x {FIREWALL_SCRIPT_DEST}", force_sudo=True)
    exec_obj.run(f"chown root:root {FIREWALL_SCRIPT_DEST}", force_sudo=True)

    # 3. Install the firewall-rules helper tool
    helper_dest = "/usr/local/bin/firewall-rules"
    log.info(f"Installing firewall-rules diagnostic tool to {helper_dest}")
    
    tmp_helper = "/tmp/firewall-rules"
    with open(tmp_helper, "w") as f:
        f.write(FIREWALL_RULES_HELPER_CONTENT)
        
    exec_obj.run(f"mv {tmp_helper} {helper_dest}", force_sudo=True)
    exec_obj.run(f"chmod +x {helper_dest}", force_sudo=True)
    exec_obj.run(f"chown root:root {helper_dest}", force_sudo=True)

    # 4. Install the Systemd Service
    service_path = f"/etc/systemd/system/{FIREWALL_SERVICE_NAME}"
    log.info(f"Installing systemd service at {service_path}")
    
    tmp_service = "/tmp/firewall.service"
    with open(tmp_service, "w") as f:
        f.write(SERVICE_CONTENT)
        
    exec_obj.run(f"mv {tmp_service} {service_path}", force_sudo=True)
    exec_obj.run("systemctl daemon-reload", force_sudo=True)
    exec_obj.run(f"systemctl enable {FIREWALL_SERVICE_NAME}", force_sudo=True)

    # 5. Interactive Confirmation to Apply
    if exec_obj.dry_run:
        log.info("[DRY-RUN] Skipping interactive firewall application.")
        return

    print("\n" + "!"*70)
    log.warning("FIREWALL INSTALLATION COMPLETE.")
    log.warning("Applying these rules now may affect active network connections.")
    print("!"*70 + "\n")

    confirm = input("Would you like to apply the firewall rules immediately? (y/N): ").lower()
    if confirm == 'y':
        log.info("Applying firewall rules via systemd...")
        exec_obj.run(f"systemctl start {FIREWALL_SERVICE_NAME}", force_sudo=True)
        log.success("Firewall rules applied and service is active.")
    else:
        log.info("Firewall rules not applied. You can apply them later with:")
        log.info(f"  sudo systemctl start {FIREWALL_SERVICE_NAME}")

    log.success("Firewall module configuration finished.")