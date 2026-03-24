import os
import time

BASE = os.path.expanduser("~/.openclaw/agents")

AGENTS = ["manager", "dev", "reviewer", "tester"]

def get_sessions(agent):
    path = os.path.join(BASE, agent, "sessions")
    if not os.path.exists(path):
        return []
    return os.listdir(path)

def snapshot():
    data = {}
    for agent in AGENTS:
        data[agent] = get_sessions(agent)
    return data

def compare(before, after):
    results = {}

    for agent in AGENTS:
        before_set = set(before.get(agent, []))
        after_set = set(after.get(agent, []))

        new_sessions = after_set - before_set
        results[agent] = len(new_sessions)

    return results

print("📸 Snapshot AVANT...")
before = snapshot()

print("👉 Lance maintenant une action dans OpenClaw (manager)")
input("Appuie sur ENTER quand c'est fait...")

print("⏳ Attente...")
time.sleep(5)

print("📸 Snapshot APRÈS...")
after = snapshot()

results = compare(before, after)

print("\n===== RÉSULTATS =====\n")

for agent, count in results.items():
    status = "✅ ACTIF" if count > 0 else "❌ INACTIF"
    print(f"{agent.upper():10} → {status} ({count} nouvelles sessions)")

print("\n===== DIAGNOSTIC =====\n")

if results["dev"] == 0:
    print("❌ DEV NON UTILISÉ")
if results["reviewer"] == 0:
    print("❌ REVIEWER NON UTILISÉ")
if results["tester"] == 0:
    print("❌ TESTER NON UTILISÉ")

if all(results[a] > 0 for a in ["dev", "reviewer", "tester"]):
    print("🔥 MULTI-AGENT OK")
else:
    print("⚠️ MULTI-AGENT PARTIEL OU HS")