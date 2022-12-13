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

class FuncImportGraph:
    def __init__(self):
        self._files = {}
        self._ready = False

    def knows_about_file(self, file_path):
        return file_path in self._files
            

    def add_func_def(self, file_path, func_def, func_name):
        if file_path not in self._files:
            self._files[file_path] = {
                'defs': list(),
                'names': list(),
                'next': set()
            } 

        self._files[file_path]['defs'].append(func_def)
        self._files[file_path]['names'].append(func_name)

    def add_relationship(self, start_file, end_file):
        if start_file not in self._files:
            self._files[start_file] = {
                'defs': list(),
                'names': list(),
                'next': set()
            } 

        if end_file not in self._files:
            self._files[end_file] = {
                'defs': list(),
                'names': list(),
                'next': set()
            } 

        self._files[start_file]['next'].add(end_file)

    def set_ready(self):
        self._ready = True
    
    def is_ready(self):
        return self._ready

    # Needs to ignore cycles!
    def get_all_data_starting_at(self, file_path, scanned_nodes = None):
        if not scanned_nodes:
            scanned_nodes = {}

        if file_path not in self._files:
            return ([], [], [])

        result_nodes = []
        result_names = []
        result_paths = []

        for node in self._files[file_path]['defs']:
            result_nodes.append(node)

        for name in self._files[file_path]['names']:
            result_names.append(name)
            result_paths.append(file_path)


        for child in self._files[file_path]['next']:
            if child != file_path and child not in scanned_nodes:
                scanned_nodes[file_path] = True
                (nodes, names, paths) = self.get_all_data_starting_at(child, scanned_nodes)

                result_nodes.extend(nodes)
                result_names.extend(names)
                result_paths.extend(paths)

        return (result_nodes, result_names, result_paths)

