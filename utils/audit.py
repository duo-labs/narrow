# Utility script which takes the output of pip-audit (as JSON) and extracts the PySec IDs and passes them to narrow
# for relevancy prediction.

import os
import sys
import json
import subprocess
audit_file = sys.argv[1]

command = ["python3", "main.py"]
confirmed_count = 0

with open(audit_file, 'r') as fd:
    audit_data = fd.read()
    audit_json = json.loads(audit_data)

    for dependency in audit_json['dependencies']:
        for vuln in dependency['vulns']:
            vuln_id = vuln['id']
            print("Checking vulnerability ID: {}".format(vuln_id))
            resp = subprocess.run(command + ['--osv-id', vuln_id, 'main.py'], capture_output=True)

            if resp.returncode == 0:
                print("CONFIRMED: Vulnerability ID: {}".format(vuln_id))
                confirmed_count += 1
            print('\n')

exit(confirmed_count)
