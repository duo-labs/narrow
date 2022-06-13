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

        for line in lines:
            if line.strip(' ').startswith('-'):
                pre_lines.append({
                    'line': line[1:],
                    'real': True
                })

            if line.strip(' ').startswith("@@ "):
                pre_lines.append({
                    'line': line.split("@@", 3)[2].strip(" "),
                    'real': False
                })

        tentative_def = None
        for line_data in pre_lines:
            line = str(line_data['line'])
            # Initially see if we can get by using searches rather than
            # python parsing
            if line_data['real']:
                if ' def ' in line or line.startswith('def '):
                    function_def_name = line.split('def', 1)[1] \
                                        .split('(', 1)[0]
                    discovered_functions.append(function_def_name.strip(' '))
                elif tentative_def is not None:
                    discovered_functions.append(tentative_def)
                    tentative_def = None
            else:
                if ' def ' in line or line.startswith('def '):
                    function_def_name = line.split('def', 1)[1] \
                                        .split('(', 1)[0]
                    tentative_def = function_def_name.strip(" ")

        return discovered_functions

    def find_targets_in_file(self, path_to_file: str, language: LanguageName):
        with open(path_to_file, 'r') as fd:
            return self.find_targets_in_string(fd.read(), language)

    def find_targets_in_github_pull_request(self, url: str):
        diff_url = url
        if not url.endswith('.diff'):
            diff_url = url + '.diff'

        resp = requests.get(diff_url)
        patch_contents = resp.text

        language = self.infer_language()

        return self.find_targets_in_string(patch_contents, language)

    def find_targets_in_ndv_entry(self, cve_id: str):
        resp = requests.get(
            'https://www.cve.org/api/?action=getCveById&cveId=' + cve_id)

        json_data = resp.json()

        references = json_data['references']

        ref_data = references['reference_data']

        for ref in ref_data:
            if ref['url'].startswith('https://github.com') \
               and '/pull/' in ref['url']:
                return self.find_targets_in_github_pull_request(ref['url'])

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


