#!/usr/bin/env python3
import json
import subprocess
import sys
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

# Force a wide console width and ensure standard Unicode handling for dark mode terminals
console = Console(width=160, legacy_windows=False)

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

def get_styled_target(target):
    """Styling with fixed-width emoji presentation for perfect alignment."""
    if "ACCEPT" in target:
        return Text("✅ ACCEPT", style="bold green")
    if "DROP" in target or "REJECT" in target:
        return Text("❌ DROP  ", style="bold red")
    return Text(f"↪️  {target}", style="yellow")

def get_styled_iface(iface):
    """Styling for network interfaces with context emojis."""
    if not iface or iface == "-": 
        return Text("-")
    if "tailscale" in iface:
        return Text(f"🕵️  {iface}", style="cyan")
    if "lo" in iface:
        return Text(f"🔄 {iface}", style="blue")
    if "br-" in iface or "docker" in iface:
        return Text(f"🐳 {iface}", style="bold yellow")
    return Text(iface, style="bold")

# Fetch nftables ruleset JSON
try:
    raw = subprocess.check_output(["nft", "-j", "list", "ruleset"], text=True)
    ruleset = json.loads(raw)
except Exception as e:
    console.print(f"[bold red]Error fetching nftables ruleset:[/bold red] {e}")
    sys.exit(1)

# Initialize Table with heavy simplified lines for dark mode readability
table = Table(
    title="🔥 Firewall Rules (nftables)", 
    header_style="bold magenta", 
    box=box.SIMPLE_HEAVY, 
    show_lines=False,
    expand=False,
    pad_edge=False
)

columns = ["Num", "Pkts", "Bytes", "Target", "Prot", "Opt", "In", "Out", 
           "Source", "Destination", "Chain", "Table", "Family"]

for col in columns:
    table.add_column(col, justify="left", no_wrap=False)

# Process each rule
for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule:
        continue

    # Data extraction
    num = str(rule.get("handle", "-"))
    pkts = str(0); bytes_ = str(0); target = "-"; prot = "-"; opt = "-"
    in_if = "-"; out_if = "-"; src = []; dst = []

    for expr in rule.get("expr", []):
        if "counter" in expr:
            pkts = f"{expr['counter'].get('packets', 0):,}"
            bytes_ = f"{expr['counter'].get('bytes', 0):,}"
        if "jump" in expr: target = str(expr["jump"].get("target", "-"))
        if "accept" in expr: target = "ACCEPT"
        if "reject" in expr: target = "REJECT"
        if "drop" in expr: target = "DROP"
        
        match = expr.get("match")
        if match and "left" in match:
            left, right = match["left"], match.get("right", "-")
            fld = left.get("payload", {}).get("field") or left.get("meta", {}).get("key")
            if fld == "saddr": src.extend(extract_address(right))
            elif fld == "daddr": dst.extend(extract_address(right))
            elif fld == "iifname": in_if = str(right)
            elif fld == "oifname": out_if = str(right)

    # Styling and Rendering with Rich
    row_data = [
        Text(num, style="yellow"),
        pkts,
        bytes_,
        get_styled_target(target),
        prot,
        opt,
        get_styled_iface(in_if),
        get_styled_iface(out_if),
        "\n".join(src) if src else "-",
        "\n".join(dst) if dst else "-",
        rule.get("chain", "-"),
        rule.get("table", "-"),
        rule.get("family", "-")
    ]
    
    table.add_row(*row_data)

console.print(table)