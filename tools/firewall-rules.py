#!/usr/bin/env python3
import json
import subprocess
import sys
from rich.console import Console
from rich.text import Text

# Configure console for high contrast
console = Console(width=160, legacy_windows=False)

def extract_address(val):
    """Extract readable IP/CIDR from nftables."""
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

def get_row_icons(target, in_if):
    """Returns a 5-character string containing relevant status icons."""
    icons = ""
    # Target Icon
    if "ACCEPT" in target: icons += "✅"
    elif "DROP" in target or "REJECT" in target: icons += "❌"
    else: icons += "↪️ "
    
    # Interface Icon
    if "tailscale" in in_if: icons += "🕵️ "
    elif "lo" in in_if: icons += "🔄"
    elif "br-" in in_if or "docker" in in_if: icons += "🐳"
    
    return icons.ljust(5)

# Fetch nftables ruleset JSON
try:
    raw = subprocess.check_output(["nft", "-j", "list", "ruleset"], text=True)
    ruleset = json.loads(raw)
except Exception as e:
    console.print(f"[bold red]Error:[/bold red] {e}"); sys.exit(1)

# Unified Column Definition (Fixed Widths)
# Icons | Num | Pkts | Bytes | Target | In | Source | Destination | Chain | Table | Family
FMT = "| {:<5} | {:<4} | {:<10} | {:<12} | {:<10} | {:<10} | {:<22} | {:<22} | {:<12} | {:<8} | {:<6} |"
SEP = "+-------+------+------------+--------------+------------+------------+------------------------+------------------------+--------------+----------+--------+"

# Print Header
console.print(SEP)
console.print(FMT.format("STAT", "NUM", "PKTS", "BYTES", "TARGET", "IN", "SOURCE", "DESTINATION", "CHAIN", "TABLE", "FAM"))
console.print(SEP.replace("-", "="))

rows = []
for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule: continue

    num = str(rule.get("handle", "-"))
    pkts = bytes_ = 0
    target = in_if = "-"
    src_list, dst_list = [], []

    for expr in rule.get("expr", []):
        if "counter" in expr:
            pkts, bytes_ = expr['counter'].get('packets', 0), expr['counter'].get('bytes', 0)
        if "accept" in expr: target = "ACCEPT"
        elif "reject" in expr: target = "REJECT"
        elif "drop" in expr: target = "DROP"
        elif "jump" in expr: target = expr["jump"].get("target", "JUMP")
        
        match = expr.get("match")
        if match and "left" in match:
            left, right = match["left"], match.get("right", "-")
            f = left.get("payload", {}).get("field") or left.get("meta", {}).get("key")
            if f == "saddr": src_list.extend(extract_address(right))
            elif f == "daddr": dst_list.extend(extract_address(right))
            elif f == "iifname": in_if = str(right)

    rows.append({
        "icons": get_row_icons(target, in_if),
        "num": num, "pkts": pkts, "bytes": bytes_, "target": target, "in_if": in_if,
        "src": src_list if src_list else ["-"], 
        "dst": dst_list if dst_list else ["-"],
        "chain": rule.get("chain", "-"), "table": rule.get("table", "-"), "family": rule.get("family", "-")
    })

last_section = None
for r in rows:
    # Logic for Section Breaks: Check (Chain, Table, Family) tuple
    current_section = (r["chain"], r["table"], r["family"])
    if last_section and current_section != last_section:
        console.print(SEP)
    last_section = current_section

    # Multi-line Source/Destination handling
    max_lines = max(len(r["src"]), len(r["dst"]))
    for i in range(max_lines):
        s = r["src"][i] if i < len(r["src"]) else ""
        d = r["dst"][i] if i < len(r["dst"]) else ""
        
        if i == 0:
            # Color coding for readability
            t_color = "green" if "ACCEPT" in r["target"] else "red" if r["target"] in ["DROP", "REJECT"] else "yellow"
            console.print(FMT.format(
                r["icons"],
                f"[yellow]{r['num']}[/]",
                f"{r['pkts']:,}",
                f"{r['bytes']:,}",
                f"[bold {t_color}]{r['target']}[/]",
                f"[cyan]{r['in_if']}[/]",
                s, d,
                f"[dim]{r['chain']}[/]", r["table"], r["family"]
            ))
        else:
            console.print(FMT.format("", "", "", "", "", "", s, d, "", "", ""))

console.print(SEP)