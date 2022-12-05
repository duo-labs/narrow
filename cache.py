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

import typing


class Cache:
    def __init__(self):
        self.function_defs = {}

    def store_function_defs(self, start_file: str,
                            start_ast_node: any,
                            result: typing.Any):
        unique_key = str(start_ast_node.start_point) + str(start_ast_node.end_point)

        self.function_defs[start_file] = {}
        self.function_defs[start_file][unique_key] = result

    def get_function_defs(self, start_file: str,
                          start_ast_node:  any) -> \
            typing.Tuple[typing.Any, typing.Any]:
        unique_key = str(start_ast_node.start_point) + str(start_ast_node.end_point)

        if start_file not in self.function_defs:
            return (None, None)

        if unique_key not in \
           self.function_defs[start_file]:
            return (None, None)

        return self.function_defs[start_file][unique_key]
