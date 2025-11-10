from scapy.all import sniff, IP, TCP, UDP
from datetime import datetime, timedelta
import webbrowser
import pandas as pd

def generate_kdd_features_from_url(url, capture_time=8, window_size=2):
    """Open URL, capture packets, and return exactly 41 numeric features."""
    import webbrowser, pandas as pd
    from scapy.all import sniff, IP, TCP, UDP
    from datetime import datetime, timedelta

    webbrowser.open(url)
    connections = []

    def process_packet(packet):
        if IP not in packet:
            return
        proto = "tcp" if TCP in packet else ("udp" if UDP in packet else "other")
        src = packet[IP].src
        dst = packet[IP].dst
        sport = packet[TCP].sport if TCP in packet else (packet[UDP].sport if UDP in packet else 0)
        dport = packet[TCP].dport if TCP in packet else (packet[UDP].dport if UDP in packet else 0)
        timestamp = datetime.now()
        pkt_len = len(packet)
        service = "http" if dport in [80, 8080] else "https" if dport == 443 else "other"
        connections.append({
            "time": timestamp,
            "src": src,
            "dst": dst,
            "sport": sport,
            "dport": dport,
            "protocol_type": proto,
            "service": service,
            "src_bytes": pkt_len,
            "dst_bytes": 0,
            "flag": "SF",
            "duration": 0
        })

    sniff(timeout=capture_time, prn=process_packet)
    df = pd.DataFrame(connections)

    if df.empty:
        # No packets captured → return zeros
        return [0.0] * 41

    row = df.iloc[-1]
    start_time = row["time"] - timedelta(seconds=window_size)
    recent = df[(df["time"] >= start_time) & (df["time"] <= row["time"])]

    same_host = recent[recent["dst"] == row["dst"]]
    same_service = same_host[same_host["service"] == row["service"]]

    count = len(recent)
    srv_count = len(same_service)
    same_srv_rate = srv_count / count if count > 0 else 0
    diff_srv_rate = (count - srv_count) / count if count > 0 else 0
    dst_host_count = len(df[df["dst"] == row["dst"]])
    dst_host_srv_count = len(df[(df["dst"] == row["dst"]) & (df["service"] == row["service"])])

    # --- Build 41 features ---
    features = [
        int(row["duration"]),                  # duration
        1 if row["protocol_type"]=="tcp" else (0 if row["protocol_type"]=="udp" else 2), # protocol_type
        1 if row["service"]=="http" else (2 if row["service"]=="https" else 0),          # service
        1,                                     # flag SF
        int(row["src_bytes"]),
        int(row["dst_bytes"]),
        # 14 placeholders for unused features
    ] + [0]*14 + [
        count, srv_count,                      # statistical features
        round(same_srv_rate,2), round(diff_srv_rate,2),
        0.0,0.0,1.0,0.0,0.0,                   # more host/stat features
        dst_host_count, dst_host_srv_count,
        0.17,0.03,0.17,0.0,0.0,0.0,0.05,0.0   # final features
    ]

    # Ensure exactly 41 features
    if len(features) < 41:
        features += [0]*(41-len(features))
    elif len(features) > 41:
        features = features[:41]

    return features
