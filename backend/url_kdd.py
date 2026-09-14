from scapy.all import sniff, IP, TCP, UDP
from datetime import datetime, timedelta
import webbrowser
import pandas as pd
import numpy as np
import ipaddress
import socket

from dataclasses import dataclass, field

LIVE_FEATURE_COLUMNS = [
    "duration",
    "source_port",
    "destination_port",
    "forward_packets",
    "backward_packets",
    "forward_bytes",
    "backward_bytes",
    "total_packets",
    "total_bytes",
    "packets_per_second",
    "bytes_per_second",
    "mean_packet_size",
    "min_packet_size",
    "max_packet_size",
    "packet_size_std",
    "syn_count",
    "ack_count",
    "fin_count",
    "rst_count",
    "psh_count",
    "forward_packet_ratio",
    "backward_packet_ratio",
    "forward_byte_ratio",
    "backward_byte_ratio",
    "syn_ratio",
    "rst_ratio",
    "protocol"
]

@dataclass
class NetworkFlow:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str

    start_time: float
    end_time: float

    forward_packets: int = 0
    backward_packets: int = 0

    forward_bytes: int = 0
    backward_bytes: int = 0

    syn_count: int = 0
    ack_count: int = 0
    fin_count: int = 0
    rst_count: int = 0
    psh_count: int = 0
    
    packet_sizes: list = field(default_factory=list)

def get_flow_key(src_ip, dst_ip, src_port, dst_port, protocol):
    """
    Create a bidirectional flow key.

    The same key is returned whether traffic travels:
        A → B
    or:
        B → A
    """

    endpoint1 = (src_ip, src_port)
    endpoint2 = (dst_ip, dst_port)

    if endpoint1 <= endpoint2:
        return endpoint1, endpoint2, protocol

    return endpoint2, endpoint1, protocol

def flow_is_expired(flow, current_time, timeout=5.0):
    """
    Determine whether a flow has been inactive for longer
    than the allowed flow timeout.
    """

    return (current_time - flow.end_time) > timeout
def is_multicast_or_broadcast(ip_address):
    """
    Check whether an IPv4 destination is multicast or broadcast.
    """

    try:
        ip = ipaddress.ip_address(ip_address)

        # IPv4 multicast
        if ip.is_multicast:
            return True

        # Global IPv4 broadcast
        if str(ip) == "255.255.255.255":
            return True

        # Common private-network directed broadcasts.
        # We identify them from the captured local addresses.
        local_addresses = []

        try:
            import socket

            hostname = socket.gethostname()
            local_addresses = socket.gethostbyname_ex(hostname)[2]

        except Exception:
            pass

        for local_ip in local_addresses:
            try:
                local = ipaddress.ip_address(local_ip)

                # Handle common /24 private networks.
                network = ipaddress.ip_network(
                    f"{local}/24",
                    strict=False
                )

                if ip == network.broadcast_address:
                    return True

            except ValueError:
                continue

        return False

    except ValueError:
        return False

def capture_flows(capture_time=8, flow_timeout=5.0):
    """
    Capture network packets and aggregate them into bidirectional flows.

    A flow is considered inactive when no packet belonging to it
    has been observed for flow_timeout seconds.
    """

    from scapy.all import sniff, IP, TCP, UDP

    flows = {}
    completed_flows = []

    def process_packet(packet):
        if IP not in packet:
            return

        # Determine protocol and ports
        if TCP in packet:
            protocol = "tcp"
            src_port = int(packet[TCP].sport)
            dst_port = int(packet[TCP].dport)

        elif UDP in packet:
            protocol = "udp"
            src_port = int(packet[UDP].sport)
            dst_port = int(packet[UDP].dport)

        else:
            return

        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        if is_multicast_or_broadcast(dst_ip):
            return
        
        flow_key = get_flow_key(
            src_ip,
            dst_ip,
            src_port,
            dst_port,
            protocol
        )

        timestamp = float(packet.time)
        packet_length = len(packet)

        # Remove flows that have been inactive for too long
        expired_keys = []

        for key, existing_flow in flows.items():
            if flow_is_expired(
                existing_flow,
                timestamp,
                flow_timeout
            ):
                completed_flows.append(existing_flow)
                expired_keys.append(key)

        for key in expired_keys:
            del flows[key]

        # Create a new flow if necessary
        if flow_key not in flows:
            flows[flow_key] = NetworkFlow(
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                protocol=protocol,
                start_time=timestamp,
                end_time=timestamp
            )

        flow = flows[flow_key]

        # Update flow timing
        flow.end_time = timestamp

        # Store packet size
        flow.packet_sizes.append(packet_length)

        # Determine direction
        if (
            src_ip == flow.src_ip
            and src_port == flow.src_port
            and dst_ip == flow.dst_ip
            and dst_port == flow.dst_port
        ):
            forward = True
        else:
            forward = False

        # Update packet and byte statistics
        if forward:
            flow.forward_packets += 1
            flow.forward_bytes += packet_length
        else:
            flow.backward_packets += 1
            flow.backward_bytes += packet_length

        # TCP flags
        if TCP in packet:
            flags = packet[TCP].flags

            if flags & 0x02 and not (flags & 0x10):
                flow.syn_count += 1

            if flags & 0x10:
                flow.ack_count += 1

            if flags & 0x01:
                flow.fin_count += 1

            if flags & 0x04:
                flow.rst_count += 1

            if flags & 0x08:
                flow.psh_count += 1

    sniff(
        iface=r"\Device\NPF_Loopback",
        timeout=capture_time,
        prn=process_packet,
        store=False
    )

    # Finalize flows that are still active when capture ends
    completed_flows.extend(flows.values())

    return completed_flows
def generate_local_probe_traffic(
    target_ip="127.0.0.1",
    start_port=8000,
    number_of_ports=50
):
    """
    Generate controlled local port-probing traffic.

    The traffic targets the local machine only.

    A small delay is introduced between probes so that
    the resulting flows are not all generated at exactly
    the same speed.

    Returns the set of destination ports that were probed.
    """

    import socket
    import time

    print("\n==============================================")
    print("        GENERATING LOCAL PROBE TRAFFIC")
    print("==============================================")

    print(f"🎯 Target: {target_ip}")

    print(
        f"🔢 Ports: {start_port} - "
        f"{start_port + number_of_ports - 1}"
    )

    probed_ports = set()

    for port in range(
        start_port,
        start_port + number_of_ports
    ):

        probed_ports.add(port)

        try:
            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            sock.settimeout(0.2)

            sock.connect_ex(
                (target_ip, port)
            )

            sock.close()

        except Exception:
            pass

        # Small interval between probes.
        time.sleep(0.05)

    print("✅ Local probe traffic generated.")

    print(
        f"📊 Ports probed: {len(probed_ports)}"
    )

    return probed_ports
    """
    Generate controlled local port-probing traffic.

    Returns the set of destination ports that were probed.
    """

    import socket
    import time

    print("\n==============================================")
    print("        GENERATING LOCAL PROBE TRAFFIC")
    print("==============================================")

    print(f"🎯 Target: {target_ip}")
    print(
        f"🔢 Ports: {start_port} - "
        f"{start_port + number_of_ports - 1}"
    )

    probed_ports = set()

    for port in range(
        start_port,
        start_port + number_of_ports
    ):
        probed_ports.add(port)

        try:
            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            sock.settimeout(0.1)

            sock.connect_ex(
                (target_ip, port)
            )

            sock.close()

        except Exception:
            pass

        time.sleep(0.02)

    print("✅ Local probe traffic generated.")

    return probed_ports

def print_flow_summary(flows):
    """
    Print a human-readable summary of captured flows.
    """

    print("\n========== FLOW SUMMARY ==========")
    print(f"Completed flows: {len(flows)}")

    for index, flow in enumerate(flows[:10], start=1):

        duration = max(
            flow.end_time - flow.start_time,
            0.0
        )

        total_packets = (
            flow.forward_packets +
            flow.backward_packets
        )

        total_bytes = (
            flow.forward_bytes +
            flow.backward_bytes
        )

        print(f"\nFlow #{index}")
        print(
            f"  {flow.src_ip}:{flow.src_port}"
            f" <-> "
            f"{flow.dst_ip}:{flow.dst_port}"
        )
        print(f"  Protocol:          {flow.protocol}")
        print(f"  Duration:          {duration:.3f} sec")
        print(f"  Forward packets:   {flow.forward_packets}")
        print(f"  Backward packets:  {flow.backward_packets}")
        print(f"  Total packets:     {total_packets}")
        print(f"  Forward bytes:     {flow.forward_bytes}")
        print(f"  Backward bytes:    {flow.backward_bytes}")
        print(f"  Total bytes:       {total_bytes}")
        print(f"  SYN:               {flow.syn_count}")
        print(f"  ACK:               {flow.ack_count}")
        print(f"  FIN:               {flow.fin_count}")
        print(f"  RST:               {flow.rst_count}")
        print(f"  PSH:               {flow.psh_count}")

def basic_protocol(protocol):
    """
    Normalize the network protocol name.
    """

    protocol = str(protocol).lower()

    if protocol == "tcp":
        return "tcp"

    if protocol == "udp":
        return "udp"

    return "other"

def flow_to_features(flow):
    """
    Convert a NetworkFlow into real measurable network features.
    """

    duration = max(flow.end_time - flow.start_time, 0.0)

    total_packets = (
        flow.forward_packets +
        flow.backward_packets
    )

    total_bytes = (
        flow.forward_bytes +
        flow.backward_bytes
    )

    if duration > 0:
        packets_per_second = total_packets / duration
        bytes_per_second = total_bytes / duration
    else:
        packets_per_second = 0.0
        bytes_per_second = 0.0

    mean_packet_size = (
        total_bytes / total_packets
        if total_packets > 0
        else 0.0
    )
    min_packet_size = (
        min(flow.packet_sizes)
        if flow.packet_sizes
        else 0.0
    )

    max_packet_size = (
        max(flow.packet_sizes)
        if flow.packet_sizes
        else 0.0
    )

    packet_size_std = (
        float(np.std(flow.packet_sizes))
        if len(flow.packet_sizes) > 1
        else 0.0
    )

    return {
        "duration": duration,
        "protocol": basic_protocol(flow.protocol),

        "source_port": flow.src_port,
        "destination_port": flow.dst_port,

        "forward_packets": flow.forward_packets,
        "backward_packets": flow.backward_packets,

        "forward_bytes": flow.forward_bytes,
        "backward_bytes": flow.backward_bytes,

        "total_packets": total_packets,
        "total_bytes": total_bytes,

        "packets_per_second": packets_per_second,
        "bytes_per_second": bytes_per_second,

        "mean_packet_size": mean_packet_size,
        "min_packet_size": min_packet_size,
        "max_packet_size": max_packet_size,
        "packet_size_std": packet_size_std,

        "syn_count": flow.syn_count,
        "ack_count": flow.ack_count,
        "fin_count": flow.fin_count,
        "rst_count": flow.rst_count,
        "psh_count": flow.psh_count,

        "src_ip": flow.src_ip,
        "dst_ip": flow.dst_ip
    }

def calculate_flow_statistics(flow):
    """
    Calculate additional behavioral statistics for a network flow.
    """

    duration = max(flow.end_time - flow.start_time, 0.0)

    total_packets = (
        flow.forward_packets +
        flow.backward_packets
    )

    total_bytes = (
        flow.forward_bytes +
        flow.backward_bytes
    )

    forward_packet_ratio = (
        flow.forward_packets / total_packets
        if total_packets > 0
        else 0.0
    )

    backward_packet_ratio = (
        flow.backward_packets / total_packets
        if total_packets > 0
        else 0.0
    )

    forward_byte_ratio = (
        flow.forward_bytes / total_bytes
        if total_bytes > 0
        else 0.0
    )

    backward_byte_ratio = (
        flow.backward_bytes / total_bytes
        if total_bytes > 0
        else 0.0
    )

    syn_ratio = (
        flow.syn_count / total_packets
        if total_packets > 0
        else 0.0
    )

    rst_ratio = (
        flow.rst_count / total_packets
        if total_packets > 0
        else 0.0
    )

    return {
        "forward_packet_ratio": forward_packet_ratio,
        "backward_packet_ratio": backward_packet_ratio,

        "forward_byte_ratio": forward_byte_ratio,
        "backward_byte_ratio": backward_byte_ratio,

        "syn_ratio": syn_ratio,
        "rst_ratio": rst_ratio,

        "packets_per_second": (
        total_packets / duration
        if duration > 0
        else 0.0
    ),

    "bytes_per_second": (
        total_bytes / duration
        if duration > 0
        else 0.0
    ),
    }

def build_feature_vector(flow):
    """
    Build the canonical feature vector used by the IDS model.
    Every value is derived from the observed network flow.
    """

    basic = flow_to_features(flow)
    stats = calculate_flow_statistics(flow)

    features = {
        # Basic flow information
        "duration": basic["duration"],
        "source_port": basic["source_port"],
        "destination_port": basic["destination_port"],

        # Packet and byte statistics
        "forward_packets": basic["forward_packets"],
        "backward_packets": basic["backward_packets"],
        "forward_bytes": basic["forward_bytes"],
        "backward_bytes": basic["backward_bytes"],
        "total_packets": basic["total_packets"],
        "total_bytes": basic["total_bytes"],

        # Traffic rates
        "packets_per_second": stats["packets_per_second"],
        "bytes_per_second": stats["bytes_per_second"],

        # Packet-size information
        "mean_packet_size": basic["mean_packet_size"],
        "min_packet_size": basic["min_packet_size"],
        "max_packet_size": basic["max_packet_size"],
        "packet_size_std": basic["packet_size_std"],
        
        # TCP behavior
        "syn_count": basic["syn_count"],
        "ack_count": basic["ack_count"],
        "fin_count": basic["fin_count"],
        "rst_count": basic["rst_count"],
        "psh_count": basic["psh_count"],

        # Directional behavior
        "forward_packet_ratio": stats["forward_packet_ratio"],
        "backward_packet_ratio": stats["backward_packet_ratio"],
        "forward_byte_ratio": stats["forward_byte_ratio"],
        "backward_byte_ratio": stats["backward_byte_ratio"],

        # TCP behavior ratios
        "syn_ratio": stats["syn_ratio"],
        "rst_ratio": stats["rst_ratio"],

        # Categorical feature
        "protocol": basic["protocol"]
    }

    return {
        column: features[column]
        for column in LIVE_FEATURE_COLUMNS
    }
def save_flows_to_csv(
    flows,
    output_path="data/live_flows.csv",
    label=None
):
    """
    Save captured network flows and their feature vectors
    to a CSV dataset.

    label:
        Ground-truth label for the captured traffic.
        Example: "normal", "DoS", "Probe".

        If label is None, the samples remain unlabeled.
    """

    import os
    import pandas as pd

    rows = []

    for flow in flows:
        features = build_feature_vector(flow)

        row = {
            column: features[column]
            for column in LIVE_FEATURE_COLUMNS
        }

        row["label"] = label if label is not None else ""

        rows.append(row)

    if not rows:
        print("\n⚠️ No flows to save.")
        return

    df = pd.DataFrame(
        rows,
        columns=LIVE_FEATURE_COLUMNS + ["label"]
    )

    parent_directory = os.path.dirname(output_path)

    if parent_directory:
        os.makedirs(
            parent_directory,
            exist_ok=True
        )

    file_exists = (
        os.path.exists(output_path)
        and os.path.getsize(output_path) > 0
    )

    df.to_csv(
        output_path,
        mode="a",
        header=not file_exists,
        index=False
    )

    print("\n==============================================")
    print("             DATASET SAVED")
    print("==============================================")

    print(f"📁 File: {output_path}")
    print(f"📊 Flows added: {len(df)}")
    print(f"🏷️ Label: {label if label is not None else 'UNLABELED'}")

def print_feature_vector(flow):
    """
    Print the canonical ML feature vector for one flow.
    """

    features = build_feature_vector(flow)

    print("\n========== FEATURE VECTOR ==========")

    for index, (name, value) in enumerate(features.items(), start=1):
        print(f"{index:02d}. {name:<25} = {value}")

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

def show_capture_interfaces():
    """
    Display network interfaces available to Scapy.
    """

    from scapy.all import get_if_list

    print("\n==============================================")
    print("          AVAILABLE CAPTURE INTERFACES")
    print("==============================================")

    interfaces = get_if_list()

    for index, interface in enumerate(interfaces, start=1):
        print(f"{index:02d}. {interface}")

    print(
        f"\nTotal interfaces detected: {len(interfaces)}"
    )

if __name__ == "__main__":
    print("\n==============================================")
    print("       CAPTURING NORMAL TEST TRAFFIC")
    print("==============================================")

    flows = capture_flows(
        capture_time=10
    )

    print_flow_summary(flows)

    if flows:
        save_flows_to_csv(
            flows,
            output_path="data/test_flows.csv",
            label="normal"
        )
    else:
        print("\n⚠️ No normal flows captured.")