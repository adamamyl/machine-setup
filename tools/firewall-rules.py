#!/usr/bin/env python3
import json
import subprocess
import sys
import re
import ipaddress

# Muted High-Contrast Palette
C_RESET = "\033[0m"
C_BOLD  = "\033[1m"
C_DIM   = "\033[2m"

# Action Background "Pills"
BG_GREEN = "\033[48;5;114;30m"  # Sage (ACCEPT)
BG_RED   = "\033[48;5;167;30m"  # Coral (DROP/REJECT)
BG_YELL  = "\033[48;5;186;30m"  # Sand (JUMP)

# Port Pill Styles
P_SSH   = "\033[48;5;93;38;5;255m"  # Violet background, white text
P_WEB   = "\033[48;5;114;38;5;16m"   # Light Green background, dark text
P_INFRA = "\033[48;5;117;38;5;16m"   # Cyan background, dark text
P_HIGH  = "\033[48;5;238;38;5;250m"  # Dark Grey background, light text
P_DEF   = "\033[48;5;33;38;5;255m"   # Blue background, white text

# Interface/Context Background Pills
BG_CYAN  = "\033[48;5;117;30m"  # Sky Blue (Tailscale)
BG_BLUE  = "\033[48;5;111;30m"  # Cornflower (Loopback)
BG_ORNG  = "\033[48;5;209;30m"  # Peach (Docker)
BG_GRAY  = "\033[48;5;240;37m"  # Gray (Generic)

# Muted Text Colors
C_CYAN  = "\033[38;5;117m"  # Tailscale
C_ORNG  = "\033[38;5;209m"  # Docker
C_BLUE  = "\033[38;5;111m"  # Loopback
C_MAG   = "\033[38;5;170m"  # Sky Magenta (AS5607)
C_LIME  = "\033[38;5;112m"  # Mythic Lime (AS44684)
C_NUM   = "\033[38;5;223m"  # Cream
C_IP    = "\033[38;5;153m"  # Default IP Blue
C_GREEN = "\033[38;5;114m"
C_RED   = "\033[38;5;167m"
C_YELL  = "\033[38;5;186m"

# Network Definitions
try:
    DOCKER_NETS = [ipaddress.ip_network("172.16.0.0/12")]
    TS_NETS = [
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("fd7a:115c:a1e0:ab12::/64")
    ]
    # Sky (AS5607) Aggregate ranges
    SKY_NETS = [
        ipaddress.ip_network("90.192.0.0/11"),
        ipaddress.ip_network("2.24.0.0/13"),
        ipaddress.ip_network("2a02:c78::/29")
    ]
    # Mythic (AS44684) Aggregate ranges
    MYTHIC_NETS = [
        ipaddress.ip_network("46.235.224.0/19"),
        ipaddress.ip_network("93.93.128.0/19"),
        ipaddress.ip_network("2a00:1098::/32")
    ]
except ValueError:
    DOCKER_NETS, TS_NETS, SKY_NETS, MYTHIC_NETS = [], [], [], []

def get_visual_width(text):
    return len(re.sub(r'\033\[[0-9;]*m', '', text))

def format_num(n):
    try: return f"{int(n):,}".replace(",", "'")
    except: return "0"

def extract_address(val):
    if isinstance(val, str): return [val]
    if isinstance(val, dict):
        if "prefix" in val: return [f"{val['prefix']['addr']}/{val['prefix']['len']}"]
        if "set" in val:
            res = []
            for e in val["set"]: res.extend(extract_address(e))
            return res
    return ["-"]

def colorize_address(addr):
    if addr in ["-", "", None]: return addr
    try:
        target = ipaddress.ip_network(addr, strict=False)
        is_net = (target.num_addresses > 1)
        
        if target.is_loopback: return f"{C_BLUE}{addr}{C_RESET}"
        
        # Mythic Check
        for net in MYTHIC_NETS:
            if target.overlaps(net): return f"{C_LIME}{addr}{C_RESET}"
        
        # Sky Check
        for net in SKY_NETS:
            if target.overlaps(net): return f"{C_MAG}{addr}{C_RESET}"
            
        # Docker Check
        for net in DOCKER_NETS:
            if target.overlaps(net): return f"{C_ORNG}{addr}{C_RESET}"
            
        # Tailscale Check
        for net in TS_NETS:
            if target.overlaps(net): return f"{C_CYAN}{addr}{C_RESET}"
    except: pass
    return f"{C_IP}{addr}{C_RESET}"

def colorize_port(port):
    """Formats a port number into a styled pill."""
    if port == "-": return port
    try:
        p = int(port)
        if p == 22: color = P_SSH
        elif p in [80, 443]: color = P_WEB
        elif p in [53, 123]: color = P_INFRA
        elif p >= 1024: color = P_HIGH
        else: color = P_DEF
        return f"{color} {p} {C_RESET}"
    except:
        return port

def get_row_labels(target, in_if):
    if "ACCEPT" in target: t_label = f"{BG_GREEN} OK {C_RESET}" 
    elif "DROP" in target or "REJECT" in target: t_label = f"{BG_RED} !! {C_RESET}"   
    else: t_label = f"{BG_YELL} >> {C_RESET}" 
    
    if "tailscale" in in_if: i_label = f"{BG_CYAN} TS {C_RESET}" 
    elif "lo" in in_if: i_label = f"{BG_BLUE} LO {C_RESET}" 
    elif "br-" in in_if or "docker" in in_if: i_label = f"{BG_ORNG} DK {C_RESET}" 
    else: i_label = f"{BG_GRAY} -- {C_RESET}"
    return f"{t_label} {i_label}"

try:
    raw = subprocess.check_output(["nft", "-j", "list", "ruleset"], text=True)
    ruleset = json.loads(raw)
except Exception as e:
    print(f"Error: {e}"); sys.exit(1)

columns = ["num", "stat", "pkts", "bytes", "target", "in_if", "src", "sport", "dst", "dport", "chain", "table", "family"]
headers = ["NUM", "STAT", "PKTS", "BYTES", "TARGET", "IN", "SOURCE", "S-PORT", "DESTINATION", "D-PORT", "CHAIN", "TABLE", "FAM"]
data_rows = []
col_widths = {k: len(h) for k, h in zip(columns, headers)}

for item in ruleset.get("nftables", []):
    rule = item.get("rule")
    if not rule: continue
    row = {
        "num": f"{C_NUM}{rule.get('handle', '-')}{C_RESET}",
        "stat": get_row_labels("-", "-"), # Placeholder
        "pkts": format_num(0), "bytes": format_num(0),
        "target": "-", "in_if": "-", "src": ["-"], "sport": "-", "dst": ["-"], "dport": "-",
        "chain": rule.get("chain", "-"), "table": rule.get("table", "-"), "family": rule.get("family", "-"),
        "ctx": (rule.get("chain"), rule.get("table"), rule.get("family"))
    }
    
    src_list, dst_list = [], []
    for expr in rule.get("expr", []):
        if "counter" in expr:
            row["pkts"], row["bytes"] = format_num(expr['counter'].get('packets', 0)), format_num(expr['counter'].get('bytes', 0))
        if "accept" in expr: row["target"] = "ACCEPT"
        elif "reject" in expr: row["target"] = "REJECT"
        elif "drop" in expr: row["target"] = "DROP"
        elif "jump" in expr: row["target"] = expr["jump"].get("target", "JUMP")
        match = expr.get("match")
        if match and "left" in match:
            l, r = match["left"], match.get("right", "-")
            f = l.get("payload", {}).get("field") or l.get("meta", {}).get("key")
            if f == "saddr": src_list.extend(extract_address(r))
            elif f == "daddr": dst_list.extend(extract_address(r))
            elif f == "sport": row["sport"] = str(r)
            elif f == "dport": row["dport"] = str(r)
            elif f == "iifname": row["in_if"] = str(r)

    row["stat"] = get_row_labels(row["target"], row["in_if"])
    row["src"], row["dst"] = (src_list if src_list else ["-"]), (dst_list if dst_list else ["-"])
    
    for k in columns:
        if k in ["src", "dst"]:
            for line in row[k]: col_widths[k] = max(col_widths[k], get_visual_width(line))
        elif k in ["sport", "dport"]:
            col_widths[k] = max(col_widths[k], get_visual_width(colorize_port(row[k])))
        else:
            col_widths[k] = max(col_widths[k], get_visual_width(str(row[k])))
    data_rows.append(row)

def get_sep(char="-"):
    parts = [char * (col_widths[k] + 2) for k in columns]
    return f"+{'+'.join(parts)}+"

def print_row(data_dict, is_header=False):
    src_raw = data_dict.get("src", [""]) if not is_header else ["SOURCE"]
    dst_raw = data_dict.get("dst", [""]) if not is_header else ["DESTINATION"]
    max_lines = max(len(src_raw), len(dst_raw))

    for idx in range(max_lines):
        cells = []
        for k in columns:
            if is_header: val = headers[columns.index(k)]
            elif idx == 0:
                val = str(data_dict.get(k, ""))
                if k == "src": val = src_raw[0]
                elif k == "dst": val = dst_raw[0]
                if k == "in_if": 
                    color = BG_CYAN if "tailscale" in val else BG_BLUE if "lo" in val else BG_ORNG if ("br-" in val or "docker" in val) else C_RESET
                    val = f"{color}{val}{C_RESET}" if val != "-" else val
                elif k == "target":
                    color = C_GREEN if "ACCEPT" in val else C_RED if ("DROP" in val or "REJECT" in val) else C_YELL
                    val = f"{C_BOLD}{color}{val}{C_RESET}"
                elif k == "chain": val = f"{C_DIM}{val}{C_RESET}"
                elif k in ["src", "dst"]: val = colorize_address(val)
                elif k in ["sport", "dport"]: val = colorize_port(val)
            else:
                val = (src_raw[idx] if k == "src" and idx < len(src_raw) else dst_raw[idx] if k == "dst" and idx < len(dst_raw) else "")
                if val: val = colorize_address(val)

            padding = " " * (col_widths[k] - get_visual_width(val))
            if k in ["pkts", "bytes"] and not is_header: cells.append(f" {padding}{val} ")
            else: cells.append(f" {val}{padding} ")
        print(f"|{'|'.join(cells)}|")

print(get_sep("="))
print_row({}, is_header=True)
print(get_sep("="))

last_ctx = None
for r in data_rows:
    if last_ctx and r["ctx"] != last_ctx: print(get_sep("-"))
    last_ctx = r["ctx"]
    print_row(r)
print(get_sep("="))