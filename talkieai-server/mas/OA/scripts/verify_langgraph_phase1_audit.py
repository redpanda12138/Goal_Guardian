import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
found = []
for dependency in payload["dependencies"]:
    for vuln in dependency.get("vulns", []):
        found.append((dependency["name"], dependency["version"], vuln["id"], vuln.get("aliases", [])))
if found:
    raise SystemExit(f"known vulnerabilities are not allowed: {found}")
print("OA_PHASE1_AUDIT_GATE=PASS")
