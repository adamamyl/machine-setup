#!/usr/bin/env python3
import json, subprocess, re

# ANSI Color Codes for Dark Mode Terminals
C_RESET = "\033[0m"
C_BOLD  = "\033[1m"
C_GREEN = "\033[32m"
C_RED   = "\033[31m"
C_CYAN  = "\033[36m"
C_BLUE  = "\033[34m"
C_YELL  = "\033[33m"

def get_visual_width(text):
    """
    Calculates actual terminal space taken by a string.
    1. Removes ANSI escape sequences (0 width).
    2. Counts known emojis/icons as 2 spaces.
    """
    # Remove ANSI codes first
    plain_text = re.sub(r'\033\[[0-9;]*m', '', text)
    width = 0
    # List of emojis used in apply_color that take double width
    emojis = "✅❌🕵️🔄🐳↪️"
    for char in plain_text:
        if char in emojis:
            width += 2
        else:
            width += 1
    return width

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

for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule: continue

    num = str(rule.get("handle", "-"))
    pkts = bytes_ = "0"
    target = prot = opt = in_if = out_if = "-"
    src = dst = []

    for expr in rule.get("expr", []):
        if "counter" in expr:
            pkts = str(expr["counter"].get("packets", 0))
            bytes_ = str(expr["counter"].get("bytes", 0))
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

    rows.append([
        num, pkts, bytes_, target, prot, opt, in_if, out_if,
        "\n".join(src or ["-"]), "\n".join(dst or ["-"]),
        rule.get("chain", "-"), rule.get("table", "-"), rule.get("family", "-")
    ])

def apply_color(val, col_name):
    """Apply ANSI colors and emojis."""
    s_val = str(val)
    if col_name == "Target":
        if "ACCEPT" in s_val: return f"{C_BOLD}{C_GREEN}✅ {s_val}{C_RESET}"
        if "DROP" in s_val or "REJECT" in s_val: return f"{C_BOLD}{C_RED}❌ {s_val}{C_RESET}"
        return f"{C_YELL}↪️ {s_val}{C_RESET}"
    if col_name in ["In", "Out"]:
        if "tailscale" in s_val: return f"{C_CYAN}🕵️  {s_val}{C_RESET}"
        if "lo" in s_val: return f"{C_BLUE}🔄 {s_val}{C_RESET}"
        if "br-" in s_val or "docker" in s_val: return f"{C_YELL}🐳 {s_val}{C_RESET}"
    return s_val

# Calculate dynamic widths based on visual (terminal) size
widths = []
for i, col in enumerate(columns):
    max_w = len(col)
    for row in rows:
        lines = str(row[i]).split("\n")
        for line in lines:
            # We calculate width AFTER applying color/emoji logic
            visual_w = get_visual_width(apply_color(line, columns[i]))
            max_w = max(max_w, visual_w)
    widths.append(max_w)

def hline(char="-", cross="+"):
    return cross + cross.join([char * (w + 2) for w in widths]) + cross

# Render Table
print(hline("=", "+"))
# Header row (standard length works for header text)
print("| " + " | ".join(columns[i].ljust(widths[i]) for i in range(len(columns))) + " |")
print(hline("=", "+"))

last_group = None
for row in rows:
    current_group = (row[10], row[11], row[12])
    if last_group and current_group != last_group:
        print(hline("-", "+"))
    last_group = current_group

    num_lines = max(len(str(cell).split("\n")) for cell in row)
    for idx in range(num_lines):
        line_parts = []
        for i, cell in enumerate(row):
            lines = str(cell).split("\n")
            raw_content = lines[idx] if idx < len(lines) else ""
            colored_content = apply_color(raw_content, columns[i])
            
            # Use visual width to calculate exact padding needed
            v_width = get_visual_width(colored_content)
            padding = " " * (widths[i] - v_width)
            line_parts.append(f" {colored_content}{padding} ")
        print(f"|{'|'.join(line_parts)}|")

print(hline("=", "+"))