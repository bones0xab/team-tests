#!/usr/bin/env python3
"""
monitor_alerts.py — Surveillance continue du pipeline d'alertes Teams
Affiche en temps réel :
  • Clés Redis actives (locks, dedup, throttle, escalation)
  • Compteurs d'alertes envoyées / ignorées
  • Dernier timestamp d'activité par projet

Usage :
    python scripts/monitor_alerts.py
    python scripts/monitor_alerts.py --host redis --port 6379 --interval 5
    python scripts/monitor_alerts.py --once   # une seule passe, sortie JSON
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ── terminal ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def _clear() -> None:
    """Efface l'écran (ANSI)."""
    print("\033[2J\033[H", end="")

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _bar(value: int, total: int, width: int = 20) -> str:
    """Barre de progression ASCII."""
    if total == 0:
        return "[" + "░" * width + "]"
    filled = int(round(value / total * width))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


# ── connexion Redis ────────────────────────────────────────────────────────────
def connect(host: str, port: int, password: Optional[str] = None):
    try:
        import redis  # type: ignore
        r = redis.Redis(host=host, port=port, password=password,
                        decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception:
        return None


# ── collecte des données ───────────────────────────────────────────────────────
def collect(r) -> Dict[str, Any]:
    """Récupère toutes les métriques en une passe."""
    data: Dict[str, Any] = {
        "timestamp"   : _ts(),
        "redis_ok"    : False,
        "locks"       : [],
        "dedup"       : [],
        "throttle"    : {},
        "escalation"  : [],
        "counters"    : {"sent": 0, "skipped": 0, "errors": 0},
        "memory"      : {},
        "clients"     : 0,
    }

    try:
        # Locks
        for k in r.keys("alert_lock:*"):
            data["locks"].append({"key": k, "ttl": r.ttl(k), "val": r.get(k)})

        # Dedup
        for k in r.keys("alert_dedup:*"):
            data["dedup"].append({"key": k, "ttl": r.ttl(k)})

        # Throttle (groupés par scope)
        throttle_keys: List[str] = r.keys("throttle:*")
        for k in sorted(throttle_keys):
            parts = k.split(":")
            scope = parts[1] if len(parts) > 1 else "other"
            event = ":".join(parts[2:]) if len(parts) > 2 else k
            ttl   = r.ttl(k)
            data["throttle"].setdefault(scope, []).append({"event": event, "ttl": ttl})

        # Escalation
        for k in r.keys("escalation:*"):
            data["escalation"].append({"key": k, "ttl": r.ttl(k), "val": r.get(k)})

        # Compteurs persistants (stockés par l'application)
        for counter_key, field in [("alert:sent", "sent"), ("alert:skipped", "skipped"), ("alert:errors", "errors")]:
            val = r.get(counter_key)
            if val:
                data["counters"][field] = int(val)

        # Mémoire / clients
        mem     = r.info("memory")
        clients = r.info("clients")
        data["memory"]  = {"used": mem.get("used_memory_human", "?"), "rss": mem.get("used_memory_rss_human", "?")}
        data["clients"] = clients.get("connected_clients", 0)
        data["redis_ok"] = True

    except Exception as e:
        data["error"] = str(e)

    return data


# ── rendu terminal ─────────────────────────────────────────────────────────────
def render(data: Dict[str, Any], prev: Optional[Dict[str, Any]] = None) -> None:
    """Affiche le dashboard dans le terminal."""
    _clear()

    # ── entête ──────────────────────────────────────────────────────────────
    redis_status = f"{GREEN}●  Redis OK{RESET}" if data["redis_ok"] else f"{RED}●  Redis HORS LIGNE{RESET}"
    print(f"{BOLD}╔══════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║  Monitor Alertes — {data['timestamp']}  ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════════╝{RESET}")
    print(f"  {redis_status}   {DIM}Mémoire : {data['memory'].get('used','?')}   Clients : {data['clients']}{RESET}")

    # ── compteurs ───────────────────────────────────────────────────────────
    c = data["counters"]
    sent    = c["sent"]
    skipped = c["skipped"]
    errors  = c["errors"]
    total   = sent + skipped + errors
    print(f"\n{BOLD}── Compteurs d'alertes ──────────────────────────────────────{RESET}")
    print(f"  Envoyées  : {GREEN}{BOLD}{sent:4d}{RESET}  {_bar(sent,    total)}  {_pct(sent,    total)}")
    print(f"  Ignorées  : {YELLOW}      {skipped:4d}{RESET}  {_bar(skipped, total)}  {_pct(skipped, total)}")
    print(f"  Erreurs   : {RED}      {errors:4d}{RESET}  {_bar(errors,  total)}  {_pct(errors,  total)}")

    # Variation depuis la dernière passe
    if prev:
        prev_c = prev.get("counters", {})
        d_sent    = sent    - prev_c.get("sent", sent)
        d_skipped = skipped - prev_c.get("skipped", skipped)
        d_errors  = errors  - prev_c.get("errors", errors)
        parts = []
        if d_sent    > 0: parts.append(f"{GREEN}+{d_sent} envoyée(s){RESET}")
        if d_skipped > 0: parts.append(f"{YELLOW}+{d_skipped} ignorée(s){RESET}")
        if d_errors  > 0: parts.append(f"{RED}+{d_errors} erreur(s){RESET}")
        if parts:
            print(f"  {DIM}△ Depuis le dernier check :{RESET}  {', '.join(parts)}")

    # ── verrous actifs ───────────────────────────────────────────────────────
    print(f"\n{BOLD}── Verrous actifs (alert_lock:*) ────────────────────────────{RESET}")
    if not data["locks"]:
        print(f"  {DIM}Aucun verrou — le scheduler est au repos{RESET}")
    else:
        for lock in data["locks"]:
            ttl_bar = _ttl_indicator(lock["ttl"], 300)
            print(f"  {GREEN}🔒{RESET} {lock['key']}  TTL {lock['ttl']:>4d}s  {ttl_bar}")

    # ── déduplication ────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Déduplication (alert_dedup:*) ────────────────────────────{RESET}")
    if not data["dedup"]:
        print(f"  {DIM}Aucune clé dedup active{RESET}")
    else:
        for d in data["dedup"]:
            ttl_bar = _ttl_indicator(d["ttl"], 600)
            print(f"  {CYAN}🔑{RESET} {d['key']}  TTL {d['ttl']:>4d}s  {ttl_bar}")

    # ── throttling ───────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Throttling actif (throttle:*) ────────────────────────────{RESET}")
    thr = data["throttle"]
    if not thr:
        print(f"  {DIM}Aucune clé throttle active{RESET}")
    else:
        for scope, items in sorted(thr.items()):
            print(f"  {YELLOW}[{scope}]{RESET}")
            for item in items:
                ttl_bar = _ttl_indicator(item["ttl"], 300)
                print(f"    {item['event']:<40s}  TTL {item['ttl']:>4d}s  {ttl_bar}")

    # ── escalades ────────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Escalades en cours (escalation:*) ───────────────────────{RESET}")
    if not data["escalation"]:
        print(f"  {DIM}Aucune escalade en cours{RESET}")
    else:
        for esc in sorted(data["escalation"], key=lambda x: x["key"]):
            ttl_bar = _ttl_indicator(esc["ttl"], 3600)
            status  = f"  val={esc['val']}" if esc.get("val") else ""
            print(f"  {RED}⚠️ {RESET} {esc['key']:<50s}  TTL {esc['ttl']:>5d}s{status}")

    # ── aide ─────────────────────────────────────────────────────────────────
    print(f"\n{DIM}Ctrl+C pour arrêter  |  Commandes utiles :{RESET}")
    print(f"  {DIM}docker exec ai-dashboard-redis redis-cli KEYS 'alert_*'{RESET}")
    print(f"  {DIM}curl http://localhost:8000/api/debug/redis{RESET}")
    print(f"  {DIM}docker logs ai-dashboard-backend --tail=20{RESET}")


def _pct(n: int, total: int) -> str:
    if total == 0:
        return f"{DIM}0.0%{RESET}"
    pct = n / total * 100
    return f"{DIM}{pct:.1f}%{RESET}"


def _ttl_indicator(ttl: int, max_ttl: int) -> str:
    """Mini-barre TTL colorée."""
    if ttl < 0:
        return f"{DIM}(no TTL){RESET}"
    ratio = ttl / max_ttl if max_ttl > 0 else 0
    width = 10
    filled = int(round(ratio * width))
    bar    = "█" * filled + "░" * (width - filled)
    if ratio > 0.5:
        color = GREEN
    elif ratio > 0.2:
        color = YELLOW
    else:
        color = RED
    return f"{color}[{bar}]{RESET}"


# ── point d'entrée ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Surveillance du pipeline d'alertes Teams")
    parser.add_argument("--host",     default=os.getenv("REDIS_HOST", "localhost"))
    parser.add_argument("--port",     type=int, default=int(os.getenv("REDIS_PORT", "6379")))
    parser.add_argument("--password", default=os.getenv("REDIS_PASSWORD"))
    parser.add_argument("--interval", type=int, default=5, help="Intervalle de rafraîchissement (secondes)")
    parser.add_argument("--once",     action="store_true", help="Une seule passe — sortie JSON")
    args = parser.parse_args()

    r = connect(args.host, args.port, args.password)

    if args.once:
        if r is None:
            print(json.dumps({"redis_ok": False, "error": "connection failed"}, indent=2))
            sys.exit(1)
        data = collect(r)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        sys.exit(0)

    if r is None:
        print(f"{RED}Impossible de se connecter à Redis ({args.host}:{args.port}).{RESET}")
        print(f"{YELLOW}Relancez depuis le container : docker exec -it ai-dashboard-backend python scripts/monitor_alerts.py{RESET}")
        sys.exit(1)

    prev: Optional[Dict[str, Any]] = None
    try:
        while True:
            data = collect(r)
            render(data, prev)
            prev = data
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n{CYAN}Surveillance arrêtée.{RESET}")


if __name__ == "__main__":
    main()