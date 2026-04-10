from scapy.all import sniff, IP, TCP, UDP
from datetime import datetime
import webbrowser


def generate_kdd_features_from_url(url, capture_time=8, window_size=2):
    """Capture traffic from URL and generate EXACT 41 NSL-KDD features."""

    webbrowser.open(url)

    connections_map = {}

    def process_packet(packet):
        if IP not in packet:
            return

        proto = "tcp" if TCP in packet else ("udp" if UDP in packet else "other")
        src = packet[IP].src
        dst = packet[IP].dst
        sport = packet[TCP].sport if TCP in packet else (packet[UDP].sport if UDP in packet else 0)
        dport = packet[TCP].dport if TCP in packet else (packet[UDP].dport if UDP in packet else 0)

        key = (src, dst, sport, dport, proto)
        now = datetime.now()
        pkt_len = len(packet)

        if key not in connections_map:
            connections_map[key] = {
                "start": now,
                "last": now,
                "src": src,
                "dst": dst,
                "protocol_type": proto,
                "service": "http" if dport in [80, 8080] else ("https" if dport == 443 else "other"),
                "src_bytes": 0,
                "dst_bytes": 0,
            }

        conn = connections_map[key]
        conn["last"] = now
        conn["src_bytes"] += pkt_len

    sniff(timeout=capture_time, prn=process_packet)

    # If no packets captured → return safe vector
    if not connections_map:
        return [0.0] * 41

    conn = list(connections_map.values())[-1]

    # ---------------- Core Features ----------------
    duration = int((conn["last"] - conn["start"]).total_seconds())

    protocol = 1 if conn["protocol_type"] == "tcp" else (0 if conn["protocol_type"] == "udp" else 2)
    service = 1 if conn["service"] == "http" else (2 if conn["service"] == "https" else 0)
    flag = 1  # approximated as SF

    src_bytes = int(conn["src_bytes"])
    dst_bytes = int(conn["dst_bytes"])

    # ---------------- Window Stats ----------------
    now = datetime.now()
    recent = [
        c for c in connections_map.values()
        if (now - c["last"]).total_seconds() <= window_size
    ]

    same_host = [c for c in recent if c["dst"] == conn["dst"]]
    same_service = [c for c in same_host if c["service"] == conn["service"]]

    count = len(recent)
    srv_count = len(same_service)

    same_srv_rate = srv_count / count if count else 0
    diff_srv_rate = 1 - same_srv_rate if count else 0

    dst_host_count = len([c for c in connections_map.values() if c["dst"] == conn["dst"]])
    dst_host_srv_count = len([
        c for c in connections_map.values()
        if c["dst"] == conn["dst"] and c["service"] == conn["service"]
    ])

    # ---------------- Build EXACT 41 Features ----------------
    features = [0.0] * 41

    # Basic features
    features[0] = duration
    features[1] = protocol
    features[2] = service
    features[3] = flag
    features[4] = src_bytes
    features[5] = dst_bytes

    # (6–20 remain 0: host-based / login features not available)

    # Traffic stats
    features[22] = count
    features[23] = srv_count

    features[28] = round(same_srv_rate, 2)
    features[29] = round(diff_srv_rate, 2)

    # Host-based stats
    features[31] = dst_host_count
    features[32] = dst_host_srv_count

    # Optional debug (remove later)
    # print("Feature length:", len(features))

    return features