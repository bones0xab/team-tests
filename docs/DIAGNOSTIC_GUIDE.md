# Guide de diagnostic — Redis & Système d'alertes
> Généré le 2026-04-13 — Équipe NTT Data / Jira Health Dashboard

---

## 1. Architecture du système de throttling

```
┌─────────────────────────────────────────────────────────────┐
│                     JIRA SCHEDULER                          │
│  (thread périodique — toutes les N minutes)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ collecte le rapport complet
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   ALERT SERVICE                             │
│  1. Vérifie le LOCK Redis  ──► alert_lock:jira_report       │
│  2. Vérifie la DÉDUP       ──► alert_dedup:<type>:<hash>    │
│  3. Envoie Teams si OK                                      │
│  4. Pose la clé DÉDUP (TTL 600s)                            │
└──────────────────────────┬──────────────────────────────────┘
                           │ appel HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                THROTTLE / ESCALATION SERVICE                │
│  ThrottleService  ──► throttle:<scope>:<event>  (TTL)       │
│  EscalationService ──► escalation:<project>:<level>         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        REDIS                                │
│  Container: ai-dashboard-redis  Port: 6379                  │
│  Persistance: appendonly yes (volume redis_data)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Vérifier Redis à tout moment

### 2.1 Commande de base (30 secondes)

```bash
# ① Ping — Redis répond-il ?
docker exec ai-dashboard-redis redis-cli PING
# Attendu : PONG

# ② Mémoire utilisée
docker exec ai-dashboard-redis redis-cli INFO memory | grep used_memory_human
# Attendu : < 100M en fonctionnement normal

# ③ Clients connectés
docker exec ai-dashboard-redis redis-cli INFO clients | grep connected_clients
# Attendu : 2–5 (backend + scheduler)

# ④ Clés actives liées aux alertes
docker exec ai-dashboard-redis redis-cli KEYS "alert_*"
docker exec ai-dashboard-redis redis-cli KEYS "throttle:*"
docker exec ai-dashboard-redis redis-cli KEYS "escalation:*"
```

### 2.2 Vérifier une clé spécifique

```bash
# Valeur d'une clé
docker exec ai-dashboard-redis redis-cli GET "throttle:portfolio:digest"

# TTL restant en secondes (-1 = pas d'expiration, -2 = n'existe pas)
docker exec ai-dashboard-redis redis-cli TTL "throttle:portfolio:digest"

# Type de la clé (string, hash, list…)
docker exec ai-dashboard-redis redis-cli TYPE "throttle:portfolio:digest"
```

### 2.3 Observer en temps réel (MONITOR)

```bash
# ⚠️  MONITOR est très verbeux — limiter à 30 secondes en production
docker exec ai-dashboard-redis redis-cli MONITOR
# Chercher des patterns anormaux :
#   OK  → GET espacés de 10s+ sur la même clé
#   NOK → GET en rafale sur la même clé (boucle non throttlée)

# Filtrer uniquement les clés d'alerte
docker exec ai-dashboard-redis redis-cli MONITOR | grep -E "(alert|throttle|escalation)"
```

### 2.4 Vider un verrou bloqué (urgence)

```bash
# Supprimer un verrou bloqué manuellement
docker exec ai-dashboard-redis redis-cli DEL "alert_lock:jira_report"

# Supprimer toutes les clés d'alerte (reset complet — ⚠️  relance les alertes)
docker exec ai-dashboard-redis redis-cli --eval - 0 <<'EOF'
local keys = redis.call('KEYS', 'alert_*')
for _, k in ipairs(keys) do redis.call('DEL', k) end
return #keys
EOF
```

---

## 3. Vérifier que le processus d'alertes fonctionne

### 3.1 Logs backend (lecture rapide)

```bash
# Dernières 30 lignes
docker logs ai-dashboard-backend --tail=30

# Suivi en direct (Ctrl+C pour arrêter)
docker logs -f ai-dashboard-backend

# Filtrer uniquement les messages d'alerte
docker logs ai-dashboard-backend --tail=100 | grep -E "(ALERT|THROTTLE|LOCK|SKIP|Teams|⏭️|🔒|✅|❌)"
```

**Messages clés à reconnaître :**

| Message dans les logs | Signification |
|----------------------|---------------|
| `[THROTTLE] Using Redis for throttling` | Redis correctement connecté au démarrage |
| `🔒 Lock acquis — envoi de l'alerte` | Une alerte est en cours d'envoi (normal) |
| `⏭️  SKIP — alerte déjà envoyée (dedup)` | Doublon évité grâce à Redis |
| `⏭️  SKIP — throttle actif (Xs restants)` | Throttle en place, pas de spam |
| `✅ Alerte Teams envoyée` | Alerte envoyée avec succès |
| `❌ Échec envoi Teams` | Erreur réseau ou webhook invalide |
| `[ESCALATION] is_pending` | Vérification d'escalade en cours |

### 3.2 Endpoint de debug Redis (API)

```bash
# Status complet Redis via l'API
curl -s http://localhost:8000/api/debug/redis | python -m json.tool

# Réponse attendue :
# {
#   "redis_available": true,
#   "connected": true,
#   "memory_used": "1.12M",
#   "active_locks": [
#     {"key": "alert_lock:jira_report", "ttl": 243}
#   ],
#   "dedup_keys": [...],
#   "throttle_keys": [...]
# }
```

```bash
# Vider tous les verrous via l'API (reset doux)
curl -X DELETE http://localhost:8000/api/debug/redis/locks
```

### 3.3 Vérifier la santé générale

```bash
# Health check global
curl -s http://localhost:8000/api/health | python -m json.tool

# Métriques Prometheus
curl -s http://localhost:8000/api/metrics | grep -E "(alert|redis|throttle)"
```

---

## 4. Expliquer le processus à l'équipe

### 4.1 Pourquoi plusieurs cartes Teams apparaissaient-elles ?

**Avant le correctif :**
```
Thread 1 ──► fetch Jira batch A ──► envoie Teams ──┐
Thread 2 ──► fetch Jira batch B ──► envoie Teams ──┼─► 4-5 cartes identiques
Thread 3 ──► fetch Jira batch C ──► envoie Teams ──┘
Thread 4 ──► fetch Jira batch D ──► envoie Teams
```
Aucun verrou ne protégeait l'envoi → chaque thread pensait être le seul.

**Après le correctif :**
```
Thread 1 ──► acquiert le LOCK Redis ──► envoie Teams ──► pose clé DÉDUP ──► libère LOCK
Thread 2 ──► essaie le LOCK ──► occupé ──► SKIP
Thread 3 ──► vérifie clé DÉDUP ──► existe ──► SKIP
Thread 4 ──► vérifie clé DÉDUP ──► existe ──► SKIP
```
Résultat : **1 seule carte Teams** pour N threads concurrents.

### 4.2 Pourquoi `GET escalation:PROJECT` apparaissait en boucle ?

**Avant le correctif :**
- Le scheduler appelait `is_pending(project)` sans délai entre deux checks
- Avec 10 projets × 50 vérifications/seconde → 500 GET/s sur Redis
- Redis répondait correctement mais c'était du gaspillage CPU/réseau

**Après le correctif :**
- Un cache local de 10 secondes évite les appels Redis redondants
- Résultat : 1 GET toutes les 10 secondes par projet (×50 amélioration)

### 4.3 Pourquoi les erreurs Pyright `Awaitable[Unknown]` ?

```python
# Le problème
r: redis.Redis = redis.Redis(...)  # type non résolu → Redis[ResponseT=Unknown]
val = r.get("key")                 # Pyright voit : Awaitable[Unknown]
if val:                            # Erreur : Awaitable n'est pas itérable

# La solution
from app.services.redis_typing import RedisStrClient
r: RedisStrClient = cast(RedisStrClient, redis.Redis(..., decode_responses=True))
val = r.get("key")                 # Pyright voit : Optional[str]  ✅
```

---

## 5. Routine de surveillance hebdomadaire (pour l'équipe)

### Lundi matin — vérification rapide (5 min)

```bash
# 1. Tous les containers UP ?
docker compose ps

# 2. Redis répond ?
docker exec ai-dashboard-redis redis-cli PING

# 3. Mémoire Redis OK ?
docker exec ai-dashboard-redis redis-cli INFO memory | grep used_memory_human

# 4. Pas d'erreur dans les logs backend ?
docker logs ai-dashboard-backend --tail=50 | grep -iE "(error|exception|❌)"

# 5. API saine ?
curl -s http://localhost:8000/api/health
```

### En cas d'incident Teams (cartes en doublon)

```bash
# Étape 1 — Vérifier les clés Redis
docker exec ai-dashboard-redis redis-cli KEYS "alert_*"

# Étape 2 — Regarder les logs
docker logs ai-dashboard-backend --tail=100 | grep -E "(ALERT|SKIP|LOCK)"

# Étape 3 — Si verrou bloqué (TTL élevé sans activité)
docker exec ai-dashboard-redis redis-cli DEL "alert_lock:jira_report"

# Étape 4 — Redémarrer le backend si nécessaire
docker compose restart backend

# Étape 5 — Confirmer via l'API
curl http://localhost:8000/api/debug/redis
```

### En cas de flood Redis (GET en boucle)

```bash
# Observer 10 secondes de MONITOR
timeout 10 docker exec ai-dashboard-redis redis-cli MONITOR | sort | uniq -c | sort -rn | head -20

# Si une clé est appelée > 10 fois / seconde → throttle local cassé
# Redémarrer le scheduler :
docker compose restart backend
```

---

## 6. Tableau de bord Grafana

URL : **http://localhost:3001**  
Identifiants : `nour` / `123456`

Métriques à surveiller :
- `redis_connected_clients` — nombre de connexions actives
- `alert_sent_total` — compteur d'alertes envoyées
- `alert_skipped_total` — compteur d'alertes ignorées (throttle/dedup)
- `throttle_hits_total` — nombre de blocages throttle

---

## 7. Checklist de mise en production

- [ ] `REDIS_HOST=redis` dans `.env` (pas `localhost`)
- [ ] Volume `redis_data` monté (persistance des clés entre redémarrages)
- [ ] `redis-server --appendonly yes` dans docker-compose.yml
- [ ] Endpoint `/api/debug/redis` accessible uniquement en interne
- [ ] TTL alertes configurés : `ALERT_LOCK_TTL=300`, `ALERT_DEDUP_TTL=600`
- [ ] Logs backend surveillés par Prometheus/Grafana
- [ ] Test de bout-en-bout réalisé après chaque déploiement

---

*Guide maintenu par l'équipe NTT Data — mise à jour à chaque changement majeur du système d'alertes.*