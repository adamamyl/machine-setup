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
    Calculates the actual space a string takes in the terminal.
    1. Removes ANSI escape sequences (0 width).
    2. Counts emojis/special chars as 2 spaces if they are multi-byte.
    """
    # Remove ANSI codes
    plain_text = re.sub(r'\033\[[0-9;]*m', '', text)
    width = 0
    for char in plain_text:
        # Check if character is an emoji/wide char (Basic heuristic)
        if ord(char) > 0x1F000 or char in "✅❌🕵️🔄🐳↪️":
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

# Process each rule
for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule:
        continue

    num = str(rule.get("handle", "-"))
    pkts = bytes_ = "0"
    target = prot = opt = in_if = out_if = "-"
    src = dst = []

    exprs = rule.get("expr", [])
    for expr in exprs:
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

    src = src if src else ["-"]
    dst = dst if dst else ["-"]

    rows.append([
        num, pkts, bytes_, target, prot, opt, in_if, out_if,
        "\n".join(src), "\n".join(dst),
        rule.get("chain", "-"), rule.get("table", "-"), rule.get("family", "-")
    ])

# Calculate column widths using the visual width helper
widths = []
for i, col in enumerate(columns):
    max_w = len(col)
    for row in rows:
        lines = str(row[i]).split("\n")
        # For each cell, we calculate the visual width of its longest line
        for line in lines:
            # Important: apply_color logic affects width, so we test the result
            visual_w = get_visual_width(line)
            # Add +3 for emoji/icon padding leeway
            if line in ["tailscale0", "lo", "ACCEPT", "DROP", "REJECT"]:
                visual_w += 1 
            max_w = max(max_w, visual_w)
    widths.append(max_w)

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
    return s_val

# Print table
print(hline("=", "+"))
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
            raw_val = lines[idx] if idx < len(lines) else ""
            colored_val = apply_color(raw_val, columns[i])
            
            # Manual padding calculation using visual width
            vis_w = get_visual_width(colored_val)
            padding = " " * (widths[i] - vis_w)
            line_parts.append(f" {colored_val}{padding} ")
        print(f"|{'|'.join(line_parts)}|")

print(hline("=", "+"))