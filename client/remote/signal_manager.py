import time
import uuid


SIGNAL_TTL_SECONDS = 180


def create_signal(sender, receiver, signal_type, payload):
    now = int(time.time())
    return {
        "messageId": uuid.uuid4().hex,
        "from": sender,
        "to": receiver,
        "type": signal_type,
        "payload": payload,
        "createdAt": now,
        "expiresAt": now + SIGNAL_TTL_SECONDS
    }


def get_pending_signals(device, local_key):
    now = int(time.time())
    signals = device.get("signals") or []
    if not isinstance(signals, list):
        return []

    pending = []
    for signal in signals:
        if not isinstance(signal, dict) or signal.get("to") != local_key:
            continue
        try:
            expires_at = int(signal.get("expiresAt", 0) or 0)
        except (TypeError, ValueError):
            continue
        if expires_at >= now:
            pending.append(signal)

    return pending
