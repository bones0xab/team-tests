#!/usr/bin/env python3
"""
check_system_full.py — Diagnostic complet : Redis + Backend + Docker
Vérifie en une seule commande :
  1. Redis (ping, clés, mémoire)
  2. Backend FastAPI (/api/health, /api/debug/redis)
  3. Résumé des problèmes détectés + recommandations

Usage (depuis le dossier team-tests) :
    python scripts/check_system_full.py
    python scripts/check_system_full.py --backend http://localhost:8000
    python scripts/check_system_full.py --redis-host redis --backend http://backend:8000
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

from redis import Redis
# ── couleurs ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg: str)   -> str: return f"  {GREEN}✅ {msg}{RESET}"
def warn(msg: str) -> str: return f"  {YELLOW}⚠️  {msg}{RESET}"
def err(msg: str)  -> str: return f"  {RED}❌ {msg}{RESET}"
def info(msg: str) -> str: return f"  {CYAN}ℹ️  {msg}{RESET}"
def sec(title: str)-> str:
    return f"\n{BOLD}{CYAN}{'━'*62}{RESET}\n{BOLD}  {title}{RESET}\n{CYAN}{'━'*62}{RESET}"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Redis
# ══════════════════════════════════════════════════════════════════════════════
def check_redis(host: str, port: int, password: Optional[str]) -> Tuple[bool, List[str]]:
    """
    Retourne (ok: bool, issues: List[str]).
    issues = liste de problèmes détectés.
    """
    issues: List[str] = []
    print(sec("1 / 3  —  Redis"))

    try:
        r: Redis = Redis(
            host=host, port=port, password=password,
            decode_responses=True, socket_connect_timeout=3
        )

        # Ping
        t0  = time.perf_counter()
        r.ping()
        lat = (time.perf_counter() - t0) * 1000
        print(ok(f"PING → PONG  (latence {lat:.1f} ms)"))

        # Mémoire
        mem  = cast(Dict[str, Any], r.info("memory"))
        used = mem.get("used_memory_human", "?")
        frag = float(mem.get("mem_fragmentation_ratio", 1.0))
        used_bytes = float(mem.get("used_memory", 0))
        used_mb = used_bytes / (1024 * 1024)
        print(ok(f"Mémoire utilisée : {used}"))

        # Seuil adaptatif : la fragmentation n'est pas significative
        # en dessous de 10 MB (overhead normal de l'allocateur)
        if used_mb < 10:
            print(ok(f"Fragmentation : {frag:.2f}  (non significatif < 10 MB de données)"))
        elif frag > 3.0:
            print(warn(f"Fragmentation élevée : {frag:.2f}  (recommandé < 3.0)"))
            issues.append(f"Fragmentation Redis élevée ({frag:.2f})")
        else:
            print(ok(f"Fragmentation normale : {frag:.2f}"))

        # Persistance AOF
        pers   = cast(Dict[str, Any], r.info("persistence"))
        aof_on = int(pers.get("aof_enabled", 0))
        if not aof_on:
            print(warn("AOF désactivé — données perdues au redémarrage"))
            issues.append("AOF Redis désactivé")
        else:
            print(ok("AOF activé (persistance assurée)"))

        # Clés actives
        locks:   List[str] = cast(List[str], r.keys("alert_lock:*"))
        dedups:  List[str] = cast(List[str], r.keys("alert_dedup:*"))
        throtts: List[str] = cast(List[str], r.keys("throttle:*"))
        escs:    List[str] = cast(List[str], r.keys("escalation:*"))

        print(info(f"Verrous actifs    : {len(locks)}   {locks}"))
        print(info(f"Clés dedup        : {len(dedups)}"))
        print(info(f"Clés throttle     : {len(throtts)}"))
        print(info(f"Clés escalation   : {len(escs)}"))

        # Détection de verrou bloqué (TTL > 200s → suspect)
        for k in locks:
            ttl = cast(int, r.ttl(k))
            if ttl > 250:
                print(warn(f"Verrou '{k}' TTL={ttl}s — peut-être bloqué ?"))
                issues.append(f"Verrou bloqué potentiel : {k} (TTL={ttl}s)")

        # Détection de boucle GET escalation (clés nombreuses < 5s TTL)
        short_esc = [k for k in escs if 0 < cast(int, r.ttl(k)) < 5]
        if len(short_esc) > 3:
            print(warn(f"{len(short_esc)} clés escalation avec TTL < 5s — boucle possible"))
            issues.append(f"Boucle escalation possible ({len(short_esc)} clés)")

        return True, issues

    except Exception as e:
        print(err(f"Connexion Redis échouée : {e}"))
        issues.append(f"Redis inaccessible : {e}")
        return False, issues


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Backend FastAPI
# ══════════════════════════════════════════════════════════════════════════════
def _http_get(url: str, timeout: int = 5) -> Tuple[int, Optional[Dict[str, Any]]]:
    """GET simple sans dépendance externe."""
    try:
        req  = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, {"raw": body[:200]}
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, {"error": str(e)}


def check_backend(base_url: str) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    print(sec("2 / 3  —  Backend FastAPI"))

    # Health
    code, body = _http_get(f"{base_url}/api/health")
    if code == 200:
        print(ok(f"GET /api/health → {code}  {body}"))
    else:
        print(err(f"GET /api/health → {code}  {body}"))
        issues.append(f"Health check échoué : HTTP {code}")

    # Debug Redis (endpoint optionnel)
    code2, body2 = _http_get(f"{base_url}/api/debug/redis")
    if code2 == 200 and body2:
        # Cherche "connected" sous plusieurs noms de champs possibles
        connected = body2.get("connected") \
                 or body2.get("redis_connected") \
                 or body2.get("redis_available") \
                 or body2.get("status")
        if connected is None:
            connected = "⚠️  champ 'connected' absent de la réponse"

        used_mem  = body2.get("memory_used") \
                 or body2.get("memory", {}).get("used") \
                 or body2.get("used_memory_human", "?")

        active_locks = body2.get("active_locks", [])
        print(ok(f"GET /api/debug/redis → {code2}"))
        print(info(f"  connected      : {connected}"))
        print(info(f"  memory_used    : {used_mem}"))
        print(info(f"  active_locks   : {len(active_locks)}"))
        for lock in active_locks:
            ttl = lock.get("ttl", "?")
            key = lock.get("key", "?")
            print(info(f"    🔒 {key}  TTL={ttl}s"))
    elif code2 == 404:
        print(warn("/api/debug/redis non trouvé — endpoint non enregistré dans main.py"))
        issues.append("Endpoint /api/debug/redis absent")
    else:
        print(warn(f"GET /api/debug/redis → {code2}  {body2}"))

    # Métriques Prometheus
    code3, body3 = _http_get(f"{base_url}/api/metrics", timeout=3)
    if code3 == 200:
        print(ok(f"GET /api/metrics → {code3}  (Prometheus exposé)"))
    else:
        print(warn(f"GET /api/metrics → {code3}  (non critique)"))

    return code == 200, issues


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Résumé & Recommandations
# ══════════════════════════════════════════════════════════════════════════════
def print_summary(redis_ok: bool, backend_ok: bool, all_issues: List[str]) -> None:
    print(sec("3 / 3  —  Résumé & Recommandations"))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status_redis   = f"{GREEN}OK{RESET}" if redis_ok   else f"{RED}ERREUR{RESET}"
    status_backend = f"{GREEN}OK{RESET}" if backend_ok else f"{RED}ERREUR{RESET}"

    print(f"  {BOLD}Horodatage{RESET}  : {now}")
    print(f"  {BOLD}Redis{RESET}       : {status_redis}")
    print(f"  {BOLD}Backend{RESET}     : {status_backend}")

    if not all_issues:
        print(f"\n  {GREEN}{BOLD}Aucun problème détecté ✅{RESET}")
        return

    print(f"\n  {YELLOW}{BOLD}Problèmes détectés ({len(all_issues)}) :{RESET}")
    for i, issue in enumerate(all_issues, 1):
        print(f"  {i}. {YELLOW}{issue}{RESET}")

    print(f"\n  {BOLD}Recommandations :{RESET}")
    if any("Fragmentation" in x for x in all_issues):
        print(warn("Fragmentation Redis élevée → redémarrer Redis ou lancer MEMORY PURGE"))
    if any("AOF" in x for x in all_issues):
        print(warn("Activer AOF → ajouter `--appendonly yes` dans docker-compose.yml redis command"))
    if any("Verrou bloqué" in x for x in all_issues):
        print(warn("Verrou bloqué → docker exec ai-dashboard-redis redis-cli DEL alert_lock:jira_report"))
        print(info("ou appeler : curl -X DELETE http://localhost:8000/api/debug/redis/locks"))
    if any("Boucle" in x for x in all_issues):
        print(warn("Boucle escalation → vérifier ThrottleService._local_cache dans throttle_service.py"))
        print(info("Redémarrer le backend : docker compose restart backend"))
    if any("Health check" in x for x in all_issues):
        print(warn("Backend inaccessible → docker compose up -d backend"))
    if any("debug/redis" in x for x in all_issues):
        print(warn("Ajouter le router debug dans app/main.py :"))
        print(f"  {DIM}from app.routes.debug import router as debug_router{RESET}")
        print(f"  {DIM}app.include_router(debug_router){RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic complet du système d'alertes")
    parser.add_argument("--redis-host", default=os.getenv("REDIS_HOST", "localhost"))
    parser.add_argument("--redis-port", type=int, default=int(os.getenv("REDIS_PORT", "6379")))
    parser.add_argument("--redis-pass", default=os.getenv("REDIS_PASSWORD"))
    parser.add_argument("--backend",    default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    args = parser.parse_args()

    print(f"\n{BOLD}╔══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║          DIAGNOSTIC COMPLET — Alertes & Redis                ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════════════╝{RESET}")

    redis_ok,   redis_issues   = check_redis(args.redis_host, args.redis_port, args.redis_pass)
    backend_ok, backend_issues = check_backend(args.backend)

    all_issues = redis_issues + backend_issues
    print_summary(redis_ok, backend_ok, all_issues)

    print(f"\n{DIM}─── Commandes de référence rapide ──────────────────────────────{RESET}")
    print(f"{DIM}  docker exec ai-dashboard-redis redis-cli KEYS 'alert_*'{RESET}")
    print(f"{DIM}  docker exec ai-dashboard-redis redis-cli MONITOR{RESET}")
    print(f"{DIM}  docker logs ai-dashboard-backend --tail=30 | grep -E '(ALERT|SKIP|LOCK)'{RESET}")
    print(f"{DIM}  curl -s http://localhost:8000/api/debug/redis | python -m json.tool{RESET}")
    print()

    sys.exit(0 if (redis_ok and backend_ok and not all_issues) else 1)


if __name__ == "__main__":
    main()