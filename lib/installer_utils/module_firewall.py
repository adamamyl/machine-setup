import os
from ..executor import Executor
from ..logger import log
from ..constants import FIREWALL_SCRIPT_DEST, FIREWALL_SERVICE_NAME, FIREWALL_PACKAGES, TOOLS_DIR
from .apt_tools import apt_install

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

# Monitoring
MUNIN_V4="93.93.128.100"
MUNIN_V6=("2a00:1098:0:80:1000::100")
MUNIN_PORT="4949"

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

# Mythic Monitoring
v_echo "    # Mythic's Munin"
for host in "${MUNIN_V4}"; do
    iptables -A INPUT -s "$host" -p tcp --dport "${MUNIN_PORT}" -j ACCEPT
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

# Mythic Monitoring
v_echo "    # Mythic's Munin ipv6"
for host in "${MUNIN_V6[@]}"; do
    ip6tables -A INPUT -s "$host" -p tcp --dport "${MUNIN_PORT}" -j ACCEPT
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
    helper_src = os.path.join(TOOLS_DIR, "firewall-rules.py")
    helper_dest = "/usr/local/bin/firewall-rules"
    
    if os.path.exists(helper_src):
        log.info(f"Installing firewall-rules diagnostic tool from {helper_src} to {helper_dest}")
        exec_obj.run(f"cp {helper_src} {helper_dest}", force_sudo=True)
        exec_obj.run(f"chmod +x {helper_dest}", force_sudo=True)
        exec_obj.run(f"chown root:root {helper_dest}", force_sudo=True)
        log.success("Firewall diagnostic tool installed.")
    else:
        log.warning(f"Diagnostic tool source not found at {helper_src}. Skipping installation.")

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