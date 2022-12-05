
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

# This class is responsible for taking an input file and reducing the priority of
# vulns that can't be found by narrow.
# For now the following formats are supported:
#   1. https://wiki.duosec.org/display/Security/Creating+and+Using+SEP+Plugins#CreatingandUsingSEPPlugins-sca-with-vuln-findings:SoftwareCompositionAnalysisResults
import copy
import json
from typing import List
import jsonschema

from patch_extractor import PatchExtractor
import cfg
import cvsslib

STANDARD_SCA_SCHEMA = {
                "$schema": "https://json-schema.org/draft/2019-09/schema",
                "$id": "http://example.com/example.json",
                "type": "array",
                "default": [],
                "title": "Root Schema",
                "items": {
                    "type": "object",
                    "default": {},
                    "title": "A Schema",
                    "required": [
                        "package",
                        "vulns"
                    ],
                    "properties": {
                        "commit": {
                            "type": "string",
                            "default": "",
                            "title": "The commit Schema",
                            "examples": [
                                "string"
                            ]
                        },
                        "version": {
                            "type": "string",
                            "default": "",
                            "title": "The version Schema",
                            "examples": [
                                "string"
                            ]
                        },
                        "package": {
                            "type": "object",
                            "default": {},
                            "title": "The package Schema",
                            "required": [
                                "name",
                                "ecosystem"
                            ],
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "default": "",
                                    "title": "The name Schema",
                                    "examples": [
                                        "string"
                                    ]
                                },
                                "ecosystem": {
                                    "type": "string",
                                    "default": "",
                                    "title": "The ecosystem Schema",
                                    "examples": [
                                        "string"
                                    ]
                                },
                                "purl": {
                                    "type": "string",
                                    "default": "",
                                    "title": "The purl Schema",
                                    "examples": [
                                        "string"
                                    ]
                                }
                            },
                            "examples": [{
                                "name": "string",
                                "ecosystem": "string",
                                "purl": "string"
                            }]
                        },
                        "vulns": {
                            "type": "array",
                            "default": [],
                            "title": "The vulns Schema",
                            "items": {
                                "$ref": "https://raw.githubusercontent.com/ossf/osv-schema/050d98092a994662cbf9daa19c7e99a5c7dcccec/validation/schema.json"
                            },
                            "examples": [
                                []
                            ]
                        }
                    },
                    "examples": [{
                        "commit": "string",
                        "version": "string",
                        "package": {
                            "name": "string",
                            "ecosystem": "string",
                            "purl": "string"
                        },
                        "vulns": []
                    }]
                },
                "examples": [
                    [{
                        "commit": "string",
                        "version": "string",
                        "package": {
                            "name": "string",
                            "ecosystem": "string",
                            "purl": "string"
                        },
                        "vulns": []
                    }]
                ]
            }

KREFST_OUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$id": "http://example.com/example.json",
    "title": "Root Schema",
    "type": "array",
    "default": [],
    "items": {
        "title": "A Schema",
        "type": "object",
        "properties": {
            "name": {
                "title": "The name Schema",
                "type": "string"
            },
            "version": {
                "title": "The version Schema",
                "type": "string"
            },
            "description": {
                "title": "The description Schema",
                "type": ["string", "null"]
            },
            "vulnerabilities": {
                "title": "The vulnerabilities Schema",
                "type": "array",
                "items": {
                    "title": "A Schema",
                    "type": "object",
                    "properties": {
                        "title": {
                            "title": "The title Schema",
                            "type": "string"
                        },
                        "overview": {
                            "title": "The overview Schema",
                            "type": "string"
                        },
                        "cve": {
                            "title": "The cve Schema",
                            "type": "string"
                        },
                        "cvssScore": {
                            "title": "The cvssScore Schema",
                            "type": [
                                "number"
                            ]
                        },
                        "updateToVersion": {
                            "title": "The updateToVersion Schema",
                            "type": ["string", "null"]
                        }
                    }
                }
            },
            "metadata": {
                "title": "The metadata Schema",
                "type": "object",
                "properties": {}
            }
        }
    }
}


class Narrower:
    def __init__(self, input_file_fd, module_backtracking: int, target_file_path):
        self.input_file_fd = input_file_fd
        self.module_backtracking = module_backtracking
        self.target_file_path = target_file_path

    # Raises an exception if we should not continue. Otherwise, returns true
    # is the file was in krefst format and false otherwise.
    def validate_input_data_and_is_krefst(self, contents_as_json):
        try:
            jsonschema.validate(contents_as_json, STANDARD_SCA_SCHEMA )
        except:
            # Might be a krefst format
            jsonschema.validate(contents_as_json, KREFST_OUT_SCHEMA )
            return True

        return False
        
    # Returns an object containing a "narrowed" JSON representation of the input file.
    def generate_output(self):
        contents = self.input_file_fd.read()
        contents_as_json = json.loads(contents)
        krefst_format = self.validate_input_data_and_is_krefst(contents_as_json)

        if krefst_format:
            return self.generate_output_krefst(contents_as_json)
        else:
            return self.generate_output_standard(contents_as_json)


    def generate_output_krefst(self, contents_as_json):
        test_results = {}

        for idx, component in enumerate(contents_as_json):
            name = component['name']
            version = component['version']
            for vuln_idx, vuln in enumerate(component['vulnerabilities']):
                vuln_id = vuln['cve']
                cvssScore = vuln['cvssScore']

                if vuln_id not in test_results:
                    print("Looking for: " + vuln_id)
                    targets = []
                    extractor = PatchExtractor()
                    targets += extractor.find_targets_in_osv_entry(vuln_id)

                    if len(targets) > 0:
                        target = targets[0]

                        print("Multiple targets detected. We will try only the first one: " +
                            target)

                        graph = cfg.ControlFlowGraph(targets[0], self.module_backtracking)
                        graph.construct_from_file(self.target_file_path, False)
                        detect_status = graph.did_detect()
                        if detect_status == False:
                            test_results[vuln_id] = max(cvssScore - 2.5, 0)
                
                # We may have a vuln_id now. Decide whether to reduce priority
                if vuln_id in test_results:
                    contents_as_json[idx]['vulnerabilities'][vuln_idx]['cvssScore'] = test_results[vuln_id]

        return contents_as_json

    def generate_output_standard(self, contents_as_json):
        vulns_to_verify = set()
        vulns_with_no_path = set()
        # Validation okay. Continue
        for package in contents_as_json:
            for vuln in package['vulns']:
                vuln_id = vuln['id']
                vulns_to_verify.add(vuln_id)

        for vuln_id in vulns_to_verify:
            targets = []
            extractor = PatchExtractor()
            targets += extractor.find_targets_in_osv_entry(vuln_id)

            if len(targets) > 0:
                target = targets[0]

                print("Multiple targets detected. We will try only the first one: " +
                    target)

                graph = cfg.ControlFlowGraph(targets[0], self.module_backtracking)
                graph.construct_from_file(self.target_file_path, False)
                detect_status = graph.did_detect()
                if detect_status == False:
                    vulns_with_no_path.add(vuln_id)

        print("No paths available for: ")
        print(vulns_with_no_path)
        # Create output object
        result = copy.deepcopy(contents_as_json)
        for idx, package in enumerate(contents_as_json):
            for vuln_idx, vuln in enumerate(package['vulns']):
                if vuln['id'] in vulns_with_no_path:
                    # Reduce CVSS3
                    if 'severity' in result[idx]['vulns'][vuln_idx]:
                        result[idx]['vulns'][vuln_idx]['severity'] = self.reduce_severities(result[idx]['vulns'][vuln_idx]['severity'])
        
        return result

    # Drops the severity by forcing Exploit Code Maturity to unproven and
    # Report Confidence to Unknown
    def drop_severity(self, cvss: str):
        val = cvsslib.CVSS31State()
        val.from_vector(cvss)

        val.report_confidence = cvsslib.cvss3.ReportConfidence.UNKNOWN
        val.exploit_code_maturity = cvsslib.cvss3.ExploitCodeMaturity.UNPROVEN

        return val.to_vector()


    def reduce_severities(self, severities: List[any]):
        for idx, severity in enumerate(severities):
            if severity['type'] == 'CVSS_V3':
                severities[idx]['score'] = self.drop_severity(severities[idx]['score'])

        return severities