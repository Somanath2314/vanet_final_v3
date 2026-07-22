#!/usr/bin/env python3
"""
Security assessment runner for VANET cryptographic schemes.

Evaluates:
- no_security: plaintext baseline
- rsa_signature_only: integrity/authentication baseline
- hybrid_rsa_aes: proposed hybrid encryption + signature

Reports:
- Computational overhead (tx/rx/e2e latency)
- Effective throughput (msg/s)
- Message size expansion
- Attack resilience (spoofing, replay, tamper/injection, flood)

Usage:
  python run_security_assessment.py --messages 300 --attack-trials 100
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import random
import statistics
import time
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from v2v_communication.security import (
    DigitalSignature,
    RSAKeyPair,
    SecureMessage,
    SecureMessageHandler,
)


def b64(n: int = 16) -> str:
    return base64.b64encode(os.urandom(n)).decode("utf-8")


def now() -> float:
    return time.time()


@dataclass
class SchemeResult:
    name: str
    tx_ms_mean: float
    rx_ms_mean: float
    e2e_ms_mean: float
    e2e_ms_p95: float
    throughput_msg_s: float
    payload_bytes_mean: float
    wire_bytes_mean: float
    expansion_ratio: float
    attack_detection: Dict[str, float]


class NoSecurityEndpoint:
    def __init__(self, entity_id: str):
        self.entity_id = entity_id

    def send(self, recipient_id: str, payload: Dict[str, Any], message_type: str = "data") -> Dict[str, Any]:
        return {
            "sender_id": self.entity_id,
            "recipient_id": recipient_id,
            "timestamp": now(),
            "nonce": b64(12),
            "message_type": message_type,
            "payload": payload,
        }

    def receive(self, packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # No authentication / no replay checks.
        return packet.get("payload")


class SignatureOnlyEndpoint:
    """RSA signature-based scheme without payload encryption."""

    def __init__(self, entity_id: str, key_size: int = 2048):
        self.entity_id = entity_id
        self.key_pair = RSAKeyPair(entity_id, key_size=key_size)
        self.peer_public_keys: Dict[str, Any] = {}
        self.nonce_history: Dict[str, float] = {}

    def get_public_key_pem(self) -> bytes:
        return self.key_pair.get_public_key_pem()

    def register_peer_public_key(self, peer_id: str, public_key_pem: bytes) -> None:
        self.peer_public_keys[peer_id] = RSAKeyPair.load_public_key_from_pem(public_key_pem)

    def send(self, recipient_id: str, payload: Dict[str, Any], message_type: str = "data") -> Dict[str, Any]:
        payload_text = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        nonce = b64(16)
        timestamp = now()

        sign_blob = payload_text.encode("utf-8") + nonce.encode("utf-8") + str(timestamp).encode("utf-8")
        signature = DigitalSignature.sign_message(sign_blob, self.key_pair.private_key)

        return {
            "sender_id": self.entity_id,
            "recipient_id": recipient_id,
            "timestamp": timestamp,
            "nonce": nonce,
            "message_type": message_type,
            "payload": payload_text,
            "signature": base64.b64encode(signature).decode("utf-8"),
        }

    def receive(self, packet: Dict[str, Any], max_age_seconds: float = 30.0) -> Optional[Dict[str, Any]]:
        timestamp = float(packet.get("timestamp", 0.0))
        if now() - timestamp > max_age_seconds:
            return None

        nonce = packet.get("nonce")
        if not nonce:
            return None
        if nonce in self.nonce_history:
            return None

        sender_id = packet.get("sender_id")
        if sender_id not in self.peer_public_keys:
            return None

        payload_text = packet.get("payload")
        sig_text = packet.get("signature")
        if not isinstance(payload_text, str) or not isinstance(sig_text, str):
            return None

        try:
            signature = base64.b64decode(sig_text)
        except Exception:
            return None

        verify_blob = payload_text.encode("utf-8") + nonce.encode("utf-8") + str(timestamp).encode("utf-8")
        if not DigitalSignature.verify_signature(verify_blob, signature, self.peer_public_keys[sender_id]):
            return None

        try:
            payload = json.loads(payload_text)
        except Exception:
            return None

        self.nonce_history[nonce] = timestamp
        cutoff = now() - max_age_seconds
        self.nonce_history = {k: v for k, v in self.nonce_history.items() if v >= cutoff}
        return payload


def make_payload(i: int, pad_bytes: int) -> Dict[str, Any]:
    # Fixed-format payload so per-message size is comparable.
    return {
        "type": "emergency_request",
        "vehicle_id": f"Vehicle_{i % 25}",
        "location": {"x": round((i * 7.31) % 3500, 2), "y": round((i * 5.17) % 2400, 2)},
        "speed": round(12.0 + (i % 15) * 1.3, 2),
        "priority": "HIGH",
        "msg": "X" * max(0, pad_bytes),
    }


def packet_wire_size(packet: Dict[str, Any]) -> int:
    return len(json.dumps(packet, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((p / 100.0) * (len(ordered) - 1)))
    return ordered[idx]


def setup_scheme(name: str):
    if name == "no_security":
        sender = NoSecurityEndpoint("Vehicle_A")
        receiver = NoSecurityEndpoint("RSU_1")
        attacker = NoSecurityEndpoint("Attacker_1")
    elif name == "rsa_signature_only":
        sender = SignatureOnlyEndpoint("Vehicle_A")
        receiver = SignatureOnlyEndpoint("RSU_1")
        attacker = SignatureOnlyEndpoint("Attacker_1")

        receiver.register_peer_public_key("Vehicle_A", sender.get_public_key_pem())
        sender.register_peer_public_key("RSU_1", receiver.get_public_key_pem())
    elif name == "hybrid_rsa_aes":
        sender = SecureMessageHandler("Vehicle_A")
        receiver = SecureMessageHandler("RSU_1")
        attacker = SecureMessageHandler("Attacker_1")

        receiver.register_peer_public_key("Vehicle_A", sender.get_public_key_pem())
        sender.register_peer_public_key("RSU_1", receiver.get_public_key_pem())

        receiver.register_peer_public_key("Attacker_1", attacker.get_public_key_pem())
        attacker.register_peer_public_key("RSU_1", receiver.get_public_key_pem())
    else:
        raise ValueError(f"Unknown scheme: {name}")

    return sender, receiver, attacker


def scheme_send(scheme: str, sender: Any, recipient_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if scheme == "hybrid_rsa_aes":
        msg = sender.encrypt_message(recipient_id, payload, "emergency")
        if msg is None:
            raise RuntimeError("encrypt_message returned None")
        return msg.to_dict()
    return sender.send(recipient_id, payload, "emergency")


def scheme_receive(scheme: str, receiver: Any, packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if scheme == "hybrid_rsa_aes":
        try:
            msg = SecureMessage.from_dict(packet)
        except Exception:
            return None
        with redirect_stdout(io.StringIO()):
            return receiver.decrypt_message(msg)
    with redirect_stdout(io.StringIO()):
        return receiver.receive(packet)


def benchmark_overhead(scheme: str, messages: int, payload_pad_bytes: int) -> Dict[str, float]:
    sender, receiver, _ = setup_scheme(scheme)

    tx_times: list[float] = []
    rx_times: list[float] = []
    e2e_times: list[float] = []
    payload_sizes: list[int] = []
    wire_sizes: list[int] = []

    t_global_start = time.perf_counter()

    for i in range(messages):
        payload = make_payload(i, payload_pad_bytes)
        payload_sizes.append(len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")))

        t0 = time.perf_counter()
        t_tx0 = time.perf_counter()
        packet = scheme_send(scheme, sender, "RSU_1", payload)
        t_tx1 = time.perf_counter()

        t_rx0 = time.perf_counter()
        decoded = scheme_receive(scheme, receiver, packet)
        t_rx1 = time.perf_counter()
        t1 = time.perf_counter()

        if decoded is None:
            raise RuntimeError(f"{scheme}: valid message could not be decoded")

        tx_times.append((t_tx1 - t_tx0) * 1000.0)
        rx_times.append((t_rx1 - t_rx0) * 1000.0)
        e2e_times.append((t1 - t0) * 1000.0)
        wire_sizes.append(packet_wire_size(packet))

    total_s = time.perf_counter() - t_global_start

    return {
        "tx_ms_mean": statistics.mean(tx_times),
        "rx_ms_mean": statistics.mean(rx_times),
        "e2e_ms_mean": statistics.mean(e2e_times),
        "e2e_ms_p95": percentile(e2e_times, 95.0),
        "throughput_msg_s": float(messages) / max(total_s, 1e-9),
        "payload_bytes_mean": statistics.mean(payload_sizes),
        "wire_bytes_mean": statistics.mean(wire_sizes),
        "expansion_ratio": statistics.mean(wire_sizes) / max(statistics.mean(payload_sizes), 1.0),
    }


def run_attack_trials(scheme: str, attack_trials: int, payload_pad_bytes: int) -> Dict[str, float]:
    sender, receiver, attacker = setup_scheme(scheme)

    def accepted(pkt: Dict[str, Any]) -> bool:
        return scheme_receive(scheme, receiver, pkt) is not None

    spoof_blocked = 0
    replay_blocked = 0
    tamper_blocked = 0

    for i in range(attack_trials):
        payload = make_payload(i, payload_pad_bytes)

        # 1) Spoofing attack
        if scheme == "no_security":
            spoof_packet = attacker.send("RSU_1", payload, "emergency")
            spoof_packet["sender_id"] = "Vehicle_A"
        elif scheme == "rsa_signature_only":
            spoof_packet = attacker.send("RSU_1", payload, "emergency")
            spoof_packet["sender_id"] = "Vehicle_A"
        else:
            # Create attacker message, then forge sender_id to trusted node.
            forged = attacker.encrypt_message("RSU_1", payload, "emergency")
            spoof_packet = forged.to_dict() if forged else {}
            spoof_packet["sender_id"] = "Vehicle_A"

        if not accepted(spoof_packet):
            spoof_blocked += 1

        # 2) Replay attack
        valid = scheme_send(scheme, sender, "RSU_1", payload)
        first_ok = accepted(valid)
        second_ok = accepted(valid)
        # Replay considered blocked only if first is accepted and duplicate rejected.
        if first_ok and not second_ok:
            replay_blocked += 1

        # 3) Data tamper / injection attack
        tampered = json.loads(json.dumps(valid))
        if scheme == "no_security":
            if isinstance(tampered.get("payload"), dict):
                tampered["payload"]["priority"] = "LOW"
                tampered["payload"]["speed"] = 1.0
        elif scheme == "rsa_signature_only":
            # Change signed payload without recomputing signature.
            if isinstance(tampered.get("payload"), str):
                tampered["payload"] = tampered["payload"].replace("HIGH", "LOW", 1)
        else:
            enc = tampered.get("encrypted_data", "")
            if isinstance(enc, str) and len(enc) > 10:
                # Flip one base64 character in ciphertext text.
                pos = random.randint(5, len(enc) - 2)
                tampered["encrypted_data"] = enc[:pos] + ("A" if enc[pos] != "A" else "B") + enc[pos + 1 :]

        if not accepted(tampered):
            tamper_blocked += 1

    # 4) Flood stress: invalid packets processed per second and drop ratio.
    flood_packets = []
    for i in range(attack_trials):
        payload = make_payload(10_000 + i, payload_pad_bytes)
        if scheme == "no_security":
            pkt = attacker.send("RSU_1", payload, "emergency")
            pkt["sender_id"] = "Vehicle_A"
        elif scheme == "rsa_signature_only":
            pkt = attacker.send("RSU_1", payload, "emergency")
            pkt["sender_id"] = "Vehicle_A"
        else:
            forged = attacker.encrypt_message("RSU_1", payload, "emergency")
            pkt = forged.to_dict() if forged else {}
            pkt["sender_id"] = "Vehicle_A"
        flood_packets.append(pkt)

    t0 = time.perf_counter()
    accepted_count = 0
    for pkt in flood_packets:
        if accepted(pkt):
            accepted_count += 1
    flood_s = time.perf_counter() - t0

    flood_drop_rate = (1.0 - (accepted_count / max(len(flood_packets), 1))) * 100.0
    flood_process_rate = float(len(flood_packets)) / max(flood_s, 1e-9)

    return {
        "spoof_block_rate": (spoof_blocked / max(attack_trials, 1)) * 100.0,
        "replay_block_rate": (replay_blocked / max(attack_trials, 1)) * 100.0,
        "tamper_block_rate": (tamper_blocked / max(attack_trials, 1)) * 100.0,
        "flood_drop_rate": flood_drop_rate,
        "flood_process_rate_msg_s": flood_process_rate,
    }


def run_assessment(messages: int, attack_trials: int, payload_pad_bytes: int) -> Dict[str, Any]:
    schemes = ["no_security", "rsa_signature_only", "hybrid_rsa_aes"]
    results: Dict[str, Any] = {}

    for scheme in schemes:
        overhead = benchmark_overhead(scheme, messages, payload_pad_bytes)
        attacks = run_attack_trials(scheme, attack_trials, payload_pad_bytes)
        results[scheme] = {**overhead, **attacks}

    return {
        "messages": messages,
        "attack_trials": attack_trials,
        "payload_pad_bytes": payload_pad_bytes,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }


def to_markdown_table(report: Dict[str, Any]) -> str:
    rows = []
    rows.append("| Scheme | E2E Mean (ms) | E2E P95 (ms) | Throughput (msg/s) | Expansion (x) | Spoof Block (%) | Replay Block (%) | Tamper Block (%) | Flood Drop (%) |")
    rows.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    pretty = {
        "no_security": "No Security",
        "rsa_signature_only": "RSA Signature Only",
        "hybrid_rsa_aes": "Hybrid RSA-AES (Proposed)",
    }

    for key in ["no_security", "rsa_signature_only", "hybrid_rsa_aes"]:
        r = report["results"][key]
        rows.append(
            "| {name} | {e2e:.3f} | {p95:.3f} | {thr:.2f} | {exp:.2f} | {spoof:.1f} | {replay:.1f} | {tamper:.1f} | {flood:.1f} |".format(
                name=pretty[key],
                e2e=r["e2e_ms_mean"],
                p95=r["e2e_ms_p95"],
                thr=r["throughput_msg_s"],
                exp=r["expansion_ratio"],
                spoof=r["spoof_block_rate"],
                replay=r["replay_block_rate"],
                tamper=r["tamper_block_rate"],
                flood=r["flood_drop_rate"],
            )
        )

    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run VANET security overhead and attack assessment")
    parser.add_argument("--messages", type=int, default=300, help="Valid message samples per scheme")
    parser.add_argument("--attack-trials", type=int, default=100, help="Attack attempts per attack type")
    parser.add_argument("--payload-pad-bytes", type=int, default=64, help="Additional payload bytes in each message")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join("benchmark_results", "security_assessment"),
        help="Directory to write JSON and markdown summary",
    )
    args = parser.parse_args()

    if args.messages <= 0 or args.attack_trials <= 0:
        raise ValueError("--messages and --attack-trials must be positive")

    os.makedirs(args.output_dir, exist_ok=True)

    report = run_assessment(
        messages=args.messages,
        attack_trials=args.attack_trials,
        payload_pad_bytes=args.payload_pad_bytes,
    )

    json_path = os.path.join(args.output_dir, "security_assessment.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    md_table = to_markdown_table(report)
    md_path = os.path.join(args.output_dir, "security_assessment_table.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Security Assessment Summary\n\n")
        f.write(md_table)
        f.write("\n")

    print("=" * 78)
    print("SECURITY ASSESSMENT COMPLETE")
    print("=" * 78)
    print(f"Messages per scheme : {args.messages}")
    print(f"Attack trials       : {args.attack_trials}")
    print(f"Payload pad bytes   : {args.payload_pad_bytes}")
    print(f"JSON report         : {json_path}")
    print(f"Markdown table      : {md_path}")
    print()
    print(md_table)


if __name__ == "__main__":
    main()
