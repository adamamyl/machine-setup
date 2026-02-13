#!/usr/bin/env python3
import json
import subprocess
import sys
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

# Force a standard width and disable background highlights for better legibility
console = Console(width=160, legacy_windows=False)

def extract_address(val):
    if isinstance(val, str): return [val]
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
    # High contrast labels with consistent spacing
    if "ACCEPT" in target:
        return Text("✅ ACCEPT", style="bold green")
    if "DROP" in target or "REJECT" in target:
        return Text("❌ DROP  ", style="bold red")
    return Text(f"↪️  {target}", style="bold yellow")

def get_styled_iface(iface):
    if not iface or iface == "-": return Text("-")
    if "tailscale" in iface:
        return Text(f"🕵️  {iface}", style="bold cyan")
    if "lo" in iface:
        return Text(f"🔄 {iface}", style="bold blue")
    if "br-" in iface or "docker" in iface:
        return Text(f"🐳 {iface}", style="bold yellow")
    return Text(iface, style="bold white")

# Fetch nftables ruleset JSON
try:
    raw = subprocess.check_output(["nft", "-j", "list", "ruleset"], text=True)
    ruleset = json.loads(raw)
except Exception as e:
    console.print(f"[bold red]Error:[/bold red] {e}")
    sys.exit(1)

# Using box.MINIMAL to remove distracting vertical bars and background shading
table = Table(
    title="\n🔥 Firewall Rules (nftables)\n", 
    header_style="bold underline magenta", 
    box=box.MINIMAL, 
    show_lines=False,
    expand=False,
    pad_edge=False,
    # This prevents the 'alternating row' shading that affects dyslexia/astigmatism
    row_styles=["none"] 
)

columns = ["Num", "Pkts", "Bytes", "Target", "Prot", "In", "Out", "Source", "Destination"]

for col in columns:
    table.add_column(col, justify="left", no_wrap=True)

for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule: continue

    num = str(rule.get("handle", "-"))
    pkts = bytes_ = 0
    target = prot = in_if = out_if = "-"
    src = dst = []

    for expr in rule.get("expr", []):
        if "counter" in expr:
            pkts, bytes_ = expr['counter'].get('packets', 0), expr['counter'].get('bytes', 0)
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

    table.add_row(
        Text(num, style="bold yellow"),
        f"{pkts:,}",
        f"{bytes_:,}",
        get_styled_target(target),
        Text(prot, style="white"),
        get_styled_iface(in_if),
        get_styled_iface(out_if),
        "\n".join(src) if src else "-",
        "\n".join(dst) if dst else "-"
    )

console.print(table)