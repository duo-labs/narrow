
# This class is responsible for taking an input file and reducing the priority of
# vulns that can't be found by narrow.
# For now the following formats are supported:
#   1. https://wiki.duosec.org/display/Security/Creating+and+Using+SEP+Plugins#CreatingandUsingSEPPlugins-sca-with-vuln-findings:SoftwareCompositionAnalysisResults
import copy
import enum
import json
from typing import List
import jsonschema

from patch_extractor import PatchExtractor
import cfg
import cvsslib


class Narrower:
    def __init__(self, input_file_fd, module_backtracking: int, target_file_path):
        self.input_file_fd = input_file_fd
        self.module_backtracking = module_backtracking
        self.target_file_path = target_file_path

    # Returns an object containing a "narrowed" JSON representation of the input file.
    def generate_output(self):
        contents = self.input_file_fd.read()
        contents_as_json = json.loads(contents)
        jsonschema.validate(contents_as_json, {
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
        })

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