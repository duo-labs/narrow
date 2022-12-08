# // Copyright 2022 Cisco Systems, Inc.
# //
# // Licensed under the Apache License, Version 2.0 (the "License");
# // you may not use this file except in compliance with the License.
# // You may obtain a copy of the License at
# //
# // http://www.apache.org/licenses/LICENSE-2.0
# //
# // Unless required by applicable law or agreed to in writing, software
# // distributed under the License is distributed on an "AS IS" BASIS,
# // WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# // See the License for the specific language governing permissions and
# // limitations under the License.

# Utility script which takes the output of pip-audit (as JSON) and extracts the PySec IDs and passes them to narrow
# for relevancy prediction.

import os
import sys
import json
import subprocess

audit_file = sys.argv[1]
entry_file = sys.argv[2]

command = ["python3", "main.py"]
resp = subprocess.run(command + ['--input-file', audit_file, entry_file])
vuln_count = 0

with open("narrow_output.json", 'r') as fd:
    audit_data = fd.read()
    audit_json = json.loads(audit_data)

    vuln_count = len(audit_json['vulnerabilities'])

exit(vuln_count)
