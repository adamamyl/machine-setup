#!/usr/bin/env python3
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