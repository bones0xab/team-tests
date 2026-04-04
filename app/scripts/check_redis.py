#!/usr/bin/env python3
"""
check_redis.py — Vérification complète de Redis et du système d'alertes
Usage :
    python scripts/check_redis.py
    python scripts/check_redis.py --host redis --port 6379
    python scripts/check_redis.py --watch          # mode surveillance (toutes les 30s)
    python scripts/check_redis.py --watch --interval 10
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ── couleurs terminal ──────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg: str)   -> str: return f"{GREEN}✅ {msg}{RESET}"
def warn(msg: str) -> str: return f"{YELLOW}⚠️  {msg}{RESET}"
def err(msg: str)  -> str: return f"{RED}❌ {msg}{RESET}"
def info(msg: str) -> str: return f"{CYAN}ℹ️  {msg}{RESET}"
def hdr(msg: str)  -> str: return f"\n{BOLD}{CYAN}{'─'*60}{RESET}\n{BOLD}{msg}{RESET}\n{'─'*60}"


# ── client Redis ───────────────────────────────────────────────────────────────
def get_client(host: str, port: int, password: Optional[str] = None):
    """Retourne un client Redis ou None si unavailable."""
    try:
        import redis as redis_lib  # type: ignore
        r = redis_lib.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        r.ping()
        return r
    except ImportError:
        print(err("redis-py non installé — pip install redis"))
        return None
    except Exception as e:
        print(err(f"Impossible de se connecter à Redis ({host}:{port}) — {e}"))
        return None


# ── sections de vérification ───────────────────────────────────────────────────
def check_connectivity(r) -> bool:
    """Section 1 — Connectivité de base."""
    print(hdr("1. Connectivité Redis"))
    try:
        latency_ms = _measure_latency(r)
        print(ok(f"PING → PONG  (latence {latency_ms:.1f} ms)"))
        return True
    except Exception as e:
        print(err(f"PING échoué : {e}"))
        return False


def check_memory(r) -> None:
    """Section 2 — Mémoire."""
    print(hdr("2. Mémoire"))
    try:
        mem: Dict[str, Any] = r.info("memory")
        used     = mem.get("used_memory_human", "?")
        rss      = mem.get("used_memory_rss_human", "?")
        peak     = mem.get("used_memory_peak_human", "?")
        maxmem   = mem.get("maxmemory_human", "0B")
        frag     = mem.get("mem_fragmentation_ratio", 0.0)

        print(f"  Utilisée   : {BOLD}{used}{RESET}")
        print(f"  RSS        : {rss}")
        print(f"  Pic        : {peak}")
        print(f"  Max config : {maxmem if maxmem != '0B' else 'illimitée'}")

        # Fragmentation > 1.5 = suspect
        frag_val = float(frag) if frag else 0.0
        if frag_val > 1.5:
            print(warn(f"Fragmentation élevée : {frag_val:.2f}  (> 1.5 = suspect)"))
        else:
            print(ok(f"Fragmentation normale : {frag_val:.2f}"))
    except Exception as e:
        print(warn(f"Impossible de lire la mémoire : {e}"))


def check_clients(r) -> None:
    """Section 3 — Clients connectés."""
    print(hdr("3. Clients connectés"))
    try:
        clients: Dict[str, Any] = r.info("clients")
        connected = clients.get("connected_clients", "?")
        blocked   = clients.get("blocked_clients", 0)
        print(f"  Connectés  : {BOLD}{connected}{RESET}")
        if int(blocked) > 0:
            print(warn(f"Clients bloqués : {blocked}  (attente BLPOP/BRPOP ?)"))
        else:
            print(ok("Aucun client bloqué"))
    except Exception as e:
        print(warn(f"Impossible de lire les clients : {e}"))


def check_persistence(r) -> None:
    """Section 4 — Persistance (AOF / RDB)."""
    print(hdr("4. Persistance"))
    try:
        pers: Dict[str, Any] = r.info("persistence")
        aof_enabled = pers.get("aof_enabled", 0)
        rdb_last    = pers.get("rdb_last_bgsave_status", "?")
        aof_last    = pers.get("aof_last_write_status", "?")

        if int(aof_enabled):
            status = ok("AOF activé") if aof_last == "ok" else warn(f"AOF — dernier statut : {aof_last}")
            print(status)
        else:
            print(warn("AOF désactivé (données non persistées entre redémarrages)"))

        rdb_status = ok(f"RDB dernier save : {rdb_last}") if rdb_last == "ok" else warn(f"RDB : {rdb_last}")
        print(rdb_status)
    except Exception as e:
        print(warn(f"Impossible de lire la persistance : {e}"))


def check_alert_keys(r) -> None:
    """Section 5 — Clés d'alertes (locks, dedup)."""
    print(hdr("5. Clés d'alertes"))
    lock_keys:  List[str] = r.keys("alert_lock:*")
    dedup_keys: List[str] = r.keys("alert_dedup:*")

    if not lock_keys:
        print(info("Aucun verrou d'alerte actif (normal entre cycles)"))
    else:
        for k in lock_keys:
            ttl = r.ttl(k)
            val = r.get(k)
            print(ok(f"LOCK  {k}  →  TTL {ttl}s  val={val}"))

    if not dedup_keys:
        print(info("Aucune clé de déduplication active"))
    else:
        for k in dedup_keys:
            ttl = r.ttl(k)
            print(ok(f"DEDUP {k}  →  TTL {ttl}s"))


def check_throttle_keys(r) -> None:
    """Section 6 — Clés de throttling."""
    print(hdr("6. Clés de throttling"))
    throttle_keys: List[str] = r.keys("throttle:*")

    if not throttle_keys:
        print(info("Aucune clé throttle active"))
        return

    # Grouper par scope
    groups: Dict[str, List[Tuple[str, int, Optional[str]]]] = {}
    for k in sorted(throttle_keys):
        parts = k.split(":")
        scope = parts[1] if len(parts) > 1 else "unknown"
        ttl   = r.ttl(k)
        val   = r.get(k)
        groups.setdefault(scope, []).append((k, ttl, val))

    for scope, items in groups.items():
        print(f"\n  [{scope}]")
        for (k, ttl, val) in items:
            print(f"    {k}  TTL={ttl}s  val={val}")


def check_escalation_keys(r) -> None:
    """Section 7 — Clés d'escalade."""
    print(hdr("7. Clés d'escalade"))
    esc_keys: List[str] = r.keys("escalation:*")

    if not esc_keys:
        print(info("Aucune clé d'escalade active"))
        return

    for k in sorted(esc_keys):
        ttl = r.ttl(k)
        val = r.get(k)
        print(f"  {k}  TTL={ttl}s  val={val}")


def check_keyspace_stats(r) -> None:
    """Section 8 — Statistiques globales."""
    print(hdr("8. Statistiques globales"))
    try:
        stats: Dict[str, Any] = r.info("stats")
        ops       = stats.get("total_commands_processed", 0)
        hits      = stats.get("keyspace_hits", 0)
        misses    = stats.get("keyspace_misses", 0)
        expired   = stats.get("expired_keys", 0)
        evicted   = stats.get("evicted_keys", 0)
        total     = int(hits) + int(misses)
        hit_rate  = (int(hits) / total * 100) if total > 0 else 0

        print(f"  Commandes traitées : {ops}")
        print(f"  Hit rate cache     : {hit_rate:.1f}%  ({hits} hits / {misses} misses)")
        print(f"  Clés expirées      : {expired}")
        if int(evicted) > 0:
            print(warn(f"Clés évincées (mémoire pleine ?) : {evicted}"))
        else:
            print(ok("Aucune clé évincée"))
    except Exception as e:
        print(warn(f"Impossible de lire les stats : {e}"))


# ── utilitaires ────────────────────────────────────────────────────────────────
def _measure_latency(r, n: int = 5) -> float:
    """Mesure la latence moyenne sur n pings."""
    total = 0.0
    for _ in range(n):
        t0 = time.perf_counter()
        r.ping()
        total += (time.perf_counter() - t0) * 1000
    return total / n


def print_summary(r) -> None:
    """Affiche un résumé JSON compact — utile pour les scripts CI."""
    lock_keys  = r.keys("alert_lock:*")
    dedup_keys = r.keys("alert_dedup:*")
    thr_keys   = r.keys("throttle:*")
    esc_keys   = r.keys("escalation:*")
    mem        = r.info("memory")
    clients    = r.info("clients")

    summary = {
        "timestamp"         : datetime.utcnow().isoformat() + "Z",
        "redis_ok"          : True,
        "used_memory"       : mem.get("used_memory_human"),
        "connected_clients" : clients.get("connected_clients"),
        "active_locks"      : [{"key": k, "ttl": r.ttl(k)} for k in lock_keys],
        "dedup_keys_count"  : len(dedup_keys),
        "throttle_keys_count": len(thr_keys),
        "escalation_keys_count": len(esc_keys),
    }
    print("\n" + hdr("Résumé JSON (pour CI/équipe)"))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


# ── point d'entrée ─────────────────────────────────────────────────────────────
def run_checks(host: str, port: int, password: Optional[str] = None) -> bool:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{BOLD}═══ CHECK REDIS  —  {ts}  ═══{RESET}")

    r = get_client(host, port, password)
    if r is None:
        return False

    if not check_connectivity(r):
        return False

    check_memory(r)
    check_clients(r)
    check_persistence(r)
    check_alert_keys(r)
    check_throttle_keys(r)
    check_escalation_keys(r)
    check_keyspace_stats(r)
    print_summary(r)

    print(f"\n{GREEN}{BOLD}═══ Vérification terminée ✅ ═══{RESET}\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Vérification Redis — système d'alertes")
    parser.add_argument("--host",     default=os.getenv("REDIS_HOST", "localhost"), help="Hôte Redis")
    parser.add_argument("--port",     type=int, default=int(os.getenv("REDIS_PORT", "6379")), help="Port Redis")
    parser.add_argument("--password", default=os.getenv("REDIS_PASSWORD"), help="Mot de passe Redis")
    parser.add_argument("--watch",    action="store_true", help="Mode surveillance (boucle continue)")
    parser.add_argument("--interval", type=int, default=30, help="Intervalle en secondes (--watch)")
    parser.add_argument("--json",     action="store_true", help="Sortie JSON uniquement (CI)")
    args = parser.parse_args()

    if args.watch:
        print(info(f"Mode surveillance activé — intervalle {args.interval}s (Ctrl+C pour arrêter)"))
        try:
            while True:
                run_checks(args.host, args.port, args.password)
                print(info(f"Prochain check dans {args.interval}s…"))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n" + info("Surveillance arrêtée."))
    else:
        success = run_checks(args.host, args.port, args.password)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()