# Utility script which takes the output of pip-audit (as JSON) and extracts the PySec IDs and passes them to narrow
# for relevancy prediction.

import os
import sys
import json
import subprocess
audit_file = sys.argv[1]

command = ["python3", "main.py"]

with open(audit_file, 'r') as fd:
    audit_data = fd.read()
    audit_json = json.loads(audit_data)

    for dependency in audit_json['dependencies']:
        for vuln in dependency['vulns']:
            vuln_id = vuln['id']
            command.append("--osv-id")
            command.append(vuln_id)

# Now run narrow against narrow

command.append("main.py")

subprocess.call(command)