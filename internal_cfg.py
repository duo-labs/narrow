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

import math
import typing
import networkx


class InternalGraphRepesentation:
    def __init__(self):
        self._graph = {
            '__narrow_entry__': {
                'next': set()
            }
        }

        self._file_context = {
             '__narrow_entry__': '<ignore>'
        }

        self._alternate_keys = {

        }

    def _get_subgraph_for(self, key):
        subgraph = {}
        for val in self._graph[key]['next']:
            subgraph[val] = self._get_subgraph_for(val)

        return subgraph

    def get_expanded_graph(self):
        resolved_graph = self._get_subgraph_for('__narrow_entry__')

        return resolved_graph

    def get_networkx_digraph(self):
        graph = networkx.DiGraph()

        for key in self._graph.keys():
            file_context = self._file_context[key]
            graph.add_node(key, file=file_context)

        for key in self._graph.keys():
            for child in self._graph[key]['next']:
                graph.add_edge(key, child)

        return graph

    def __str__(self):
        return self._graph.__repr__()

    def note_alternate_names(self, type, name, arg_count):
        resolved_node = type + '.' + name + '.' + str(arg_count)

        type_and_name = type + '.' + name
        name_and_arg_count = name + '.' + str(arg_count)
        
        if name not in self._alternate_keys:
            self._alternate_keys[name] = []
        
        if type_and_name not in self._alternate_keys:
            self._alternate_keys[type_and_name] = []

        if name_and_arg_count not in self._alternate_keys:
            self._alternate_keys[name_and_arg_count] = []

        self._alternate_keys[name].append(resolved_node)
        self._alternate_keys[type_and_name].append(resolved_node)
        self._alternate_keys[name_and_arg_count].append(resolved_node)



    # Adds a new node to the graph. context is used to find the path so far
    # and next_node represents the name of the next node.
    #
    # Since right now the implementation only works on flat function calls,
    # most of context is unused. Only the last element is used to find the
    # caller.
    #
    # Duplicates are automatically prevneted, so you can call this without
    # checking is_in_graph()
    def add_node_to_graph(self, context: typing.List[str], next_node: str,
                          arg_count: int,
                          type: str = 'unknown', file: str = 'unknown'):
        if len(context) == 0:
            raise ValueError("context should never be empty. \
            Use __narrow_entry__ for the root node")

        caller = context[-1]

        if caller not in self._graph:
            raise ValueError("The caller should already exist in the graph")

        resolved_node = type + '.' + next_node + '.' + str(arg_count)

        self._graph[caller]['next'].add(resolved_node)

        if resolved_node not in self._graph:
            self._graph[resolved_node] = {
                'next': set()
            }

            self._file_context[resolved_node] = file
            self.note_alternate_names(type, next_node, arg_count)

    # Decides if context -> next_node already exists
    # Since right now we only work on flat function calls, most of context is
    # ignored.
    def is_in_graph(self, context: typing.List[str], next_node: str):
        if len(context) == 0:
            raise ValueError("context should never be empty. \
            Use __narrow_entry__ for the root node")

        caller = context[-1]

        if caller not in self._graph:
            return False

        if next_node in self._graph[caller]:
            return True

        return False

    @staticmethod
    def remove_class(function_name: str):
        parts = function_name.split('.')
        sans_type = parts[1:len(parts)]
        return '.'.join(sans_type)

    @staticmethod
    def remove_arg_count(function_name: str):
        parts = function_name.split('.')
        sans_count = parts[0:len(parts) - 1]
        return '.'.join(sans_count)

    # Checks whether a function exists. If strict is False,
    # ignores the Class.
    def has_function(self, function_name: str, arg_count: typing.Optional[int], strict: bool = False):
        if strict and function_name + '.' + str(arg_count) in self._alternate_keys:
            return True

        if not strict:
            if arg_count is None:
                if function_name in self._alternate_keys:
                    return True
            elif function_name + '.' + str(arg_count) in self._alternate_keys:
                return True

        return False

    def find_functions_matching_name(self, function_name: str) -> typing.List[str]:
        return self._alternate_keys[function_name]
