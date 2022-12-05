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

from enum import Enum
import requests


class LanguageName(Enum):
    PYTHON = 1
    TYPESCRIPT = 2


class PatchExtractor:
    def __init__(self):
        pass

    # TODO: Actually infer
    def infer_language(self):
        return LanguageName.PYTHON

    # Targets are currently defined as:
    #   - Function definition names
    #       - That were changed in the "before" part of a diff
    def find_targets_in_string(self, patch_contents: str,
                               language: LanguageName):
        discovered_functions = []
        lines = patch_contents.splitlines()
        pre_lines = []
        functionDefStrings = ['def', 'cdef']

        current_function_context = None

        for line in lines:
            if line.strip(' ').startswith('-'):
                pre_lines.append({
                    'line': line[1:],
                    'real': True,
                    'context': current_function_context
                })
            elif line.strip(' ').startswith("@@ "):
                pre_lines.append({
                    'line': line.split("@@", 3)[2].strip(" "),
                    'real': False,
                    'context': current_function_context
                })
            elif line.startswith(' '):
                # This is context
                if ' def ' or ' cedef ' in line:
                    current_function_context = line
                else:
                    current_function_context = None
            

        tentative_def = None
        for line_data in pre_lines:
            line = str(line_data['line'])
            # Initially see if we can get by using searches rather than
            # python parsing
            if line_data['real']:
                if ' cdef ' in line or line.startswith('cdef '):
                    function_def_name = line.split('cdef', 1)[1] \
                                        .split('(', 1)[0]
                    discovered_functions.append(function_def_name.strip(' '))
                elif ' def ' in line or line.startswith('def '):
                    function_def_name = line.split('def', 1)[1] \
                                        .split('(', 1)[0]
                    discovered_functions.append(function_def_name.strip(' '))
                elif tentative_def is not None:
                    discovered_functions.append(tentative_def)
                    tentative_def = None
                # Now check to see if we edited a line inside a function
                elif line_data['context'] is not None:
                    tentative_def = self._get_function_name_from_diff_line(line_data['context'])
                    if tentative_def:
                        discovered_functions.append(tentative_def)
            else:
                if ' cdef ' in line or line.startswith('cdef '):
                    function_def_name = line.split('cdef', 1)[1] \
                                        .split('(', 1)[0]
                    tentative_def = function_def_name.strip(" ")
                elif ' def ' in line or line.startswith('def '):
                    function_def_name = line.split('def', 1)[1] \
                                        .split('(', 1)[0]
                    tentative_def = function_def_name.strip(" ")

        # __init__ is not a helpful target
        while "__init__" in discovered_functions:
            discovered_functions.remove("__init__")
        return discovered_functions

    def find_targets_in_file(self, path_to_file: str, language: LanguageName):
        with open(path_to_file, 'r') as fd:
            return self.find_targets_in_string(fd.read(), language)

    def find_targets_in_github_pull_request_or_commit(self, url: str):
        diff_url = url
        if not url.endswith('.diff'):
            diff_url = url + '.diff'

        try:
            resp = requests.get(diff_url)
            patch_contents = resp.text

            language = self.infer_language()

            return self.find_targets_in_string(patch_contents, language)
        except TimeoutError:
            # Timed out. Just assume no targets could be found
            return []


    def find_targets_in_ndv_entry(self, cve_id: str):
        #resp = requests.get(
        #    'https://www.cve.org/api/?action=getCveById&cveId=' + cve_id)

        resp = requests.get('https://services.nvd.nist.gov/rest/json/cve/1.0/' + cve_id + '?addOns=dictionaryCpes')

        json_data = resp.json()['result']['CVE_Items'][0]['cve']

        references = json_data['references']

        ref_data = references['reference_data']

        for ref in ref_data:
            if ref['url'].startswith('https://github.com'):
                if '/pull/' in ref['url'] or '/commit/' in ref['url']:
                    return self.find_targets_in_github_pull_request_or_commit(ref['url'])              

        return []

    def find_targets_in_osv_entry(self, osv_id: str):
        if osv_id.startswith('CVE-'):
            return self.find_targets_in_ndv_entry(osv_id)

        resp = requests.get('https://api.osv.dev/v1/vulns/' + osv_id)

        json_data = resp.json()
        if 'aliases' in json_data:
            for alias in json_data['aliases']:
                if alias.startswith('CVE-'):
                    return self.find_targets_in_ndv_entry(alias)

        return []

    def _get_function_name_from_diff_line(self, line):
        tentative_def = None
        if ' cdef ' in line or line.startswith('cdef '):
            function_def_name = line.split('cdef', 1)[1] \
                                .split('(', 1)[0]
            tentative_def = function_def_name.strip(" ")
        elif ' def ' in line or line.startswith('def '):
            function_def_name = line.split('def', 1)[1] \
                                .split('(', 1)[0]
            tentative_def = function_def_name.strip(" ")

        return tentative_def

