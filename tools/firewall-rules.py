#!/usr/bin/env python3
import json, subprocess, re

# ANSI Color Codes
C_RESET = "\033[0m"
C_BOLD  = "\033[1m"
C_GREEN = "\033[32m"
C_RED   = "\033[31m"
C_CYAN  = "\033[36m"
C_BLUE  = "\033[34m"
C_YELL  = "\033[33m"

def get_visual_width(text):
    """
    Calculates terminal width by stripping ANSI codes and 
    treating emojis/wide chars as 2 units.
    """
    # 1. Strip ANSI escape sequences
    plain = re.sub(r'\033\[[0-9;]*m', '', text)
    
    width = 0
    for char in plain:
        # Check for emojis and specific symbols used in our apply_color
        # These are technically 2-columns wide in most modern terminals
        if ord(char) > 0x7F: 
            width += 2
        else:
            width += 1
    return width

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

def apply_color(val, col_name):
    s_val = str(val)
    if s_val == "-" or not s_val: return s_val
    
    if col_name == "Target":
        if "ACCEPT" in s_val: return f"{C_BOLD}{C_GREEN}✅ {s_val}{C_RESET}"
        if "DROP" in s_val or "REJECT" in s_val: return f"{C_BOLD}{C_RED}❌ {s_val}{C_RESET}"
        return f"{C_YELL}↪️ {s_val}{C_RESET}"
    if col_name in ["In", "Out"]:
        if "tailscale" in s_val: return f"{C_CYAN}🕵️ {s_val}{C_RESET}"
        if "lo" in s_val: return f"{C_BLUE}🔄 {s_val}{C_RESET}"
        if "br-" in s_val or "docker" in s_val: return f"{C_YELL}🐳 {s_val}{C_RESET}"
        return f"{C_BOLD}{s_val}{C_RESET}"
    if col_name == "Num": return f"{C_YELL}{s_val}{C_RESET}"
    return s_val

# --- Fetch Data ---
try:
    raw = subprocess.check_output(["nft", "-j", "list", "ruleset"], text=True)
    ruleset = json.loads(raw)
except Exception as e:
    print("Error:", e); exit(1)

columns = ["Num", "Pkts", "Bytes", "Target", "Prot", "Opt", "In", "Out", "Source", "Destination", "Chain", "Table", "Family"]
rows = []

for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule: continue
    
    # Process rule content (same logic as before)
    num, pkts, bts, target, prot, opt, in_if, out_if = str(rule.get("handle", "-")), "0", "0", "-", "-", "-", "-", "-"
    src, dst = [], []

    for expr in rule.get("expr", []):
        if "counter" in expr:
            pkts, bts = str(expr["counter"].get("packets", 0)), str(expr["counter"].get("bytes", 0))
        if "jump" in expr: target = str(expr["jump"].get("target", "-"))
        if "accept" in expr: target = "ACCEPT"
        if "reject" in expr: target = "REJECT"
        if "drop" in expr: target = "DROP"
        match = expr.get("match")
        if match and "left" in match:
            l, r = match["left"], match.get("right", "-")
            f = l.get("payload", {}).get("field") or l.get("meta", {}).get("key")
            if f == "saddr": src.extend(extract_address(r))
            elif f == "daddr": dst.extend(extract_address(r))
            elif f == "iifname": in_if = str(r)
            elif f == "oifname": out_if = str(r)

    rows.append([num, pkts, bts, target, prot, opt, in_if, out_if, "\n".join(src or ["-"]), "\n".join(dst or ["-"]), rule.get("chain"), rule.get("table"), rule.get("family")])

# --- Unified Width Calculation ---
widths = []
for i, col in enumerate(columns):
    # Base width is the header width
    max_w = len(col)
    for row in rows:
        lines = str(row[i]).split("\n")
        for line in lines:
            # We must measure the width of the COLORIZED version
            max_w = max(max_w, get_visual_width(apply_color(line, columns[i])))
    widths.append(max_w)

def hline(char="=", cross="+"):
    return cross + cross.join([char * (w + 2) for w in widths]) + cross

def print_row(row_data, is_header=False):
    num_lines = max(len(str(cell).split("\n")) for cell in row_data)
    for idx in range(num_lines):
        line_parts = []
        for i, cell in enumerate(row_data):
            lines = str(cell).split("\n")
            content = lines[idx] if idx < len(lines) else ""
            
            # Apply colors if not the literal header row
            display_text = content if is_header else apply_color(content, columns[i])
            
            # Calculate padding based on visual width
            v_width = get_visual_width(display_text)
            padding = " " * (widths[i] - v_width)
            line_parts.append(f" {display_text}{padding} ")
        print(f"|{'|'.join(line_parts)}|")

# --- Render ---
print(hline("=", "+"))
print_row(columns, is_header=True)
print(hline("=", "+"))

last_grp = None
for row in rows:
    curr_grp = (row[10], row[11], row[12])
    if last_grp and curr_grp != last_grp:
        print(hline("-", "+"))
    last_grp = curr_grp
    print_row(row)

print(hline("=", "+"))