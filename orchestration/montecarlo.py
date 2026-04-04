import sys
import os
import json
import concurrent.futures
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import time
import redis
import pandas as pd
import numpy as np

# Ensure we can import from our services
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.Fetch import get_projects, search_issues, get_issue_count
import dateutil.parser

# ── Redis / File Cache Configuration ─────────────────────────────────────────
CACHE_FILE_PATH = os.path.join(os.path.dirname(__file__), "montecarlo_cache.json")
CACHE_TTL = 86400  # 24 hours in seconds (stops Jira 429 rate limit errors)

# ── Redis Cache Setup ────────────────────────────────────────────────────────
# Connect to your existing Redis. Fallback to localhost if config is missing.
try:
    from app.core.config import REDIS_HOST, REDIS_PORT
    sync_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
except ImportError:
    sync_redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def _load_file_cache() -> dict:
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_file_cache(cache_data: dict):
    try:
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)
    except Exception:
        pass

def get_project_stats_from_jira(project_key: str) -> Tuple[List[int], int]:
    """
    Performs the heavy Jira API calls for exactly ONE project.
    Returns: (list_of_weekly_throughput, current_backlog_count)
    """
    # 1. Fetch Historical Completed Dates (Resolution Date) PARALLELIZED
    jql_closed = f'project = "{project_key}" AND statusCategory = Done AND resolved >= "-365d"'
    resolution_dates = []
    
    try:
        # Utilize the hyper-fast batched thread-pool fetcher
        for issue in search_issues(jql_closed, ["resolutiondate"], batch=200):
            fields = issue.get("fields", {})
            if fields and fields.get("resolutiondate"):
                resolution_dates.append(fields["resolutiondate"])
    except Exception as e:
        print(f"Error fetching historical data for {project_key}: {e}")
            
    # Process "bag of marbles" natively (microsecond fast, avoids heavy Pandas imports)
    # Also provides mathematically superior strict 7-day rolling buckets
    throughput = []
    if resolution_dates:
        try:
            dates = [dateutil.parser.isoparse(d) for d in resolution_dates]
            min_date = min(dates)
            max_date = max(dates)
            total_weeks = (max_date - min_date).days // 7 + 1
            throughput = [0] * total_weeks
            for d in dates:
                throughput[(d - min_date).days // 7] += 1
        except Exception as e:
            print(f"Error calculating throughput with pure python for {project_key}: {e}")
            
    # 2. Fetch Backlog Count (All incomplete tickets) safely via Fetch.py
    jql_open = f'project = "{project_key}" AND statusCategory != Done'
    backlog_count = get_issue_count(jql_open)
        
    return throughput, backlog_count

def fetch_and_cache_project(project_key: str) -> Dict:
    """
    Checks Redis FIRST, then JSON File Cache. If MISSING, hits Jira heavily and CACHES it globally.
    Returns standard dictionary for the specific project.
    """
    cache_key = f"montecarlo:project:{project_key}"
    
    # ✅ STEP 1: CHECK REDIS OR FILE CACHE INSTANTLY
    try:
        cached = sync_redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            historical = data.get("throughput", data.get("cycle_times", []))
            return {"project_key": project_key, "throughput": historical, "N": data["N"], "from_cache": True}
    except Exception:
        # Fallback to local file cache if Redis is down
        file_db = _load_file_cache()
        if cache_key in file_db:
            data = file_db[cache_key]
            if time.time() - data.get("timestamp", 0) < CACHE_TTL:
                historical = data.get("throughput", data.get("cycle_times", []))
                return {"project_key": project_key, "throughput": historical, "N": data["N"], "from_cache": True}
        
    # 🚨 STEP 2: FETCH FROM JIRA (Heavy/Slow)
    throughput, backlog_count = get_project_stats_from_jira(project_key)
    
    # 💾 STEP 3: SAVE TO REDIS OR FILE CACHE
    payload = {"throughput": throughput, "N": backlog_count, "timestamp": time.time()}
    try:
        sync_redis.setex(cache_key, CACHE_TTL, json.dumps(payload))
    except Exception:
        # Graceful File save fallback
        file_db = _load_file_cache()
        file_db[cache_key] = payload
        _save_file_cache(file_db)
        
    return {"project_key": project_key, "throughput": throughput, "N": backlog_count, "from_cache": False}

def run_project_simulation(project_data: Dict, num_simulations: int = 10_000) -> Dict:
    """Runs a Monte Carlo simulation isolated to a single project's capacity using Throughput."""
    throughput = project_data.get("throughput", [])
    N = project_data.get("N", 0)
    
    if not throughput or N <= 0:
        return {"p50": 0, "p75": 0, "p85": 0, "p95": 0}
        
    throughput_array = np.array(throughput)
    
    # Safeguard to prevent infinite loops if throughput is completely zero but items exist
    if np.sum(throughput_array) == 0:
         return {"p50": 0, "p75": 0, "p85": 0, "p95": 0}
         
    # Vectorized Simulation for Throughput
    results = np.zeros(num_simulations, dtype=int)
    remaining = np.full(num_simulations, N)
    active_mask = remaining > 0
    
    # Draw randomly from the "bag of marbles" each week until backlog reaches 0
    while np.any(active_mask):
        draws = np.random.choice(throughput_array, size=np.sum(active_mask))
        remaining[active_mask] -= draws
        results[active_mask] += 1
        active_mask = remaining > 0

    return {
        "p50": int(np.percentile(results, 50)),
        "p75": int(np.percentile(results, 75)),
        "p85": int(np.percentile(results, 85)),
        "p95": int(np.percentile(results, 95)),
    }

def get_cached_project_keys() -> List[str]:
    """Retrieves the master list of projects from Cache first to prevent 429 limits."""
    cache_key = "montecarlo:master_project_keys"
    
    # 1. Check Redis
    try:
        cached = sync_redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        file_db = _load_file_cache()
        if cache_key in file_db:
            data = file_db[cache_key]
            if time.time() - data.get("timestamp", 0) < CACHE_TTL:
                return data["keys"]
                
    # 2. Heavy Fetch from Jira
    try:
        projects = get_projects()
        keys = list(set([p.get("key") for p in projects if p.get("key")]))
    except Exception as e:
        print(f"\n⚠️ Jira API 429 Rate Limit hit fetching master projects: {e}")
        return []
        
    # 3. Save to Cache
    try:
        sync_redis.setex(cache_key, CACHE_TTL, json.dumps(keys))
    except Exception:
        file_db = _load_file_cache()
        file_db[cache_key] = {"keys": keys, "timestamp": time.time()}
        _save_file_cache(file_db)
        
    return keys

def process_all_projects_parallel() -> List[Dict]:
    """Main function that orchestrates the per-project extraction and forecasting."""
    print("--- 🚀 Initializing Production Per-Project Analytics (Throughput Model) ---")
    keys = get_cached_project_keys()
    
    if not keys:
        print("No projects found.")
        return []
        
    print(f"📊 Processing exactly {len(keys)} projects using Redis & Jira...\n")
    
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        future_map = {pool.submit(fetch_and_cache_project, key): key for key in keys}
        for future in concurrent.futures.as_completed(future_map):
            data = future.result()
            pkey = data["project_key"]
            source = "⚡ (Redis Cache)" if data.get("from_cache") else "☁️ (Jira API)"
            
            historical_data = data.get("throughput", [])
            # Skip inactive projects cleanly
            if data["N"] == 0 and not historical_data:
                continue
                
            sim = run_project_simulation(data)
            
            payload = {
                "project_key": pkey,
                "source": "Redis Cache" if data.get("from_cache") else "Jira API",
                "backlog_issues": data["N"],
                "historical_base": len(historical_data),
                "p85_weeks": sim.get("p85", 0),
                "p95_weeks": sim.get("p95", 0),
                "skipped": data["N"] == 0 or not historical_data
            }
            results.append(payload)
            
            print(f"📌 Project: {pkey} {source}")
            print(f"   Backlog Issues: {data['N']}")
            print(f"   Historical Base: {len(historical_data)} weeks of throughput data")
            if not payload["skipped"]:
                print(f"   => 85% Confidence to finish backlog: {sim.get('p85')} weeks")
                print(f"   => 95% Confidence to finish backlog: {sim.get('p95')} weeks\n")
            else:
                print("   => Simulation Skipped (No backlog or no history)\n")

    return results
