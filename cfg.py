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

import ast
import queue
import typing
import subprocess
import json
import mimetypes
import internal_cfg
import ast_visitors
import networkx
import threading
from matplotlib import pyplot as plt
from tree_sitter import Language, Parser
import os
import sys
import pathlib
import func_import_graph

# Args should be:
# [0] -> ControlFlowGraph Object
# [1:4] -> Args to _find_function_def_nodes_tree_sitter


class FunctionDefNodesFinder(threading.Thread):
    def __init__(self, find_args):
        threading.Thread.__init__(self)
        # set a default value
        self.result = None
        self.find_args = find_args

    def run(self):
        args = self.find_args
        self.result = args[0]._find_function_def_nodes_tree_sitter(
            args[1], args[2], args[3], args[4])


class ControlFlowGraph:
    class ResolveTask:
        def __init__(self, ast_chunk, context: typing.List[str], current_file_location: str):
            self.ast_chunk = ast_chunk
            self.context = context
            self.current_file_location = current_file_location

    def __init__(self, functions_to_locate: typing.Union[typing.List[str], str] = None, module_backtrace_max=2):
        self._graph = internal_cfg.InternalGraphRepesentation()
        self._root_tree: typing.Optional[ast.AST] = None

        self.reset_targets(functions_to_locate)
        
        self._files_entirely_analyzed = set()
        self.module_backtrace_max = module_backtrace_max

        self._detected = False
        # Data structure from pydeps
        self._imports: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
        # Used to find all function defs in files given some file
        self._func_import_graph = func_import_graph.FuncImportGraph()
        self.parser = None
        self.symlinked_entrypoint = None
        self.thread_import_resolver_lock = threading.Lock()

    def __del__(self):
        if self.symlinked_entrypoint:
            # A symlink was created, delete it
            os.unlink(self.symlinked_entrypoint)

    def reset_targets(self, functions_to_locate: typing.Union[typing.List[str], str] = None):
        if type(functions_to_locate) == str:
            self._functions_to_locate = [functions_to_locate]
        elif functions_to_locate is None:
            self._functions_to_locate = []
        else:
            self._functions_to_locate = functions_to_locate

    # Function responsible for constructing a CFG given an entry file.
    #   only_file: If True, only builds a CFG contained in a single file.
    #              External references are noted as such but not resolved.
    def construct_from_file(self, file_path: str, only_file=False):
        # We may need to recursively scan thousands of modules. Python itself does
        # provide native support for tail-end recursion which means that the default recursionlimit (1000)
        # is sometimes inadequate. For example, it's not sufficient to run narrow on narrow
        # For now we set a larger recursionlimit but really we need to re-write this algorithm to
        # be an iterative algorithm.
        sys.setrecursionlimit(3000)

    
        new_file_path = self.mitigate_extensionless_file(file_path)

        self._resolve_module_imports(new_file_path)

        with open(file_path, mode='r') as source_content:
            self._files_entirely_analyzed.add(file_path)
            dir_path = os.path.dirname(os.path.realpath(__file__))

            Language.build_library(
                # Store the library in the `build` directory
                dir_path + '/build/my-languages.so',

                # Include one or more languages
                [
                    dir_path + '/tree-sitter-python'
                ]
            )

            PY_LANGUAGE = Language(
                dir_path + '/build/my-languages.so', 'python')
            self.parser = Parser()
            self.parser.set_language(PY_LANGUAGE)
            syntax_tree = self.parser.parse(
                source_content.read().encode('utf-8'))
            self._root_tree = syntax_tree.root_node

            self._parse_and_resolve_tree_sitter(
                syntax_tree.root_node, ['__narrow_entry__'], file_path)



    # Returns the new target location
    def mitigate_extensionless_file(self, file_path: str) -> str:
        path = pathlib.Path(file_path)
        if path.suffix == '':
            # Create symlink so ModuleFinder works. As of Sep 2022 it fails on extensionless files
            os.symlink(file_path, file_path + '.py')
            self.symlinked_entrypoint = file_path + '.py'
            return file_path + ".py"

        return file_path
        

    def did_detect(self):
        return self._detected

    def print_graph_to_stdout(self):
        print(self._graph.get_expanded_graph())

    def print_graph_matplotlib(self, max_depth=None, show_all_paths=False):
        networkx_data = self._graph.get_networkx_digraph()

        graphs_to_display: typing.List[networkx.DiGraph] = []

        if show_all_paths:
            networkx_data = networkx.dfs_tree(
            networkx_data, source='__narrow_entry__', depth_limit=max_depth)
            graphs_to_display.append(networkx_data)
        else:
            if self.did_detect():
                # By default we want to show only the path(s) to the target, not all paths
                for target in self._functions_to_locate:
                    for func_to_display in self._graph.find_functions_matching_name(target):

                        inverted_data = networkx_data.reverse()
                        inverted_data = networkx.dfs_tree(inverted_data, source=func_to_display, depth_limit=max_depth)
                        target_data = inverted_data.reverse()
                        graphs_to_display.append(target_data)


        for graph in graphs_to_display:

            networkx.draw_spring(graph, with_labels=True)

            # Show file locations in shell
            for node in list(graph.nodes()):
                print(node + ": " + networkx_data.nodes[node]['file'])
            plt.show()

    def _resolve_module_imports(self, file_path: str):
        output = subprocess.run(['pydeps', file_path, '--show-deps', '--pylib',
                                '--no-show', '--max-bacon', '0', '--no-dot', '--include-missing'],
                                capture_output=True)

        json_import_tree = json.loads(output.stdout.decode("utf-8"))
        self._imports = json_import_tree


    # A helper function for _parse_and_resolve_tree_sitter
    # Responsible for resolving an import statement and trying to recursively analysis the root contents of that file
    def _resolve_import_into_callgraph(self, import_type_node, context: typing.List[str], current_file_location: str, tasks: queue.SimpleQueue):
        import_visitor = ast_visitors.TreeSitterImportVisitor()
        import_visitor.visit(import_type_node)

        imports = import_visitor.get_imports()

        for import_name, import_details in imports.items():
            import_paths = self._find_entries_for_import(
                import_details['name'],
                current_file_location,
                import_details['module'],
                import_details['level'])

            for import_path in import_paths:
                if import_path and \
                mimetypes.guess_type(import_path)[0] == 'text/x-python':
                    if not self.function_exists(import_name, 0) and import_path not in self._files_entirely_analyzed:
                        self._files_entirely_analyzed.add(import_path)
                        with open(import_path, mode='r') as source_content:
                            tree = self.parser.parse(
                                source_content.read().encode('utf-8'))
                            sub_syntax_tree = tree.root_node
                            # Treat import as function call
                            self._graph.add_node_to_graph(context, import_name, 0, file=current_file_location)
                            tasks.put(ControlFlowGraph.ResolveTask(sub_syntax_tree, context +
                                                            ['unknown.' +
                                                                import_name + '.0'], import_path))


    def _parse_and_resolve_tree_sitter(self, init_ast_chunk, init_context: typing.List[str], init_current_file_location: str):



        tasks = queue.SimpleQueue()
        assert(self._root_tree is not None)
        tasks.put(ControlFlowGraph.ResolveTask(init_ast_chunk, init_context, init_current_file_location))


        while not tasks.empty():
            task = tasks.get()
            ast_chunk = task.ast_chunk
            context = task.context
            current_file_location = task.current_file_location

            if self._detected:
                # We're done early. Stop parsing
                return
            if not ast_chunk.is_named:
                # Annomymous nodes are for complete syntax trees which we don't care about
                pass

            if ast_chunk.type == 'module':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))

            elif ast_chunk.type == 'import_statement':
                self._resolve_import_into_callgraph(ast_chunk, context, current_file_location, tasks)
            elif ast_chunk.type == 'expression_statement':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))
            elif ast_chunk.type == 'if_statement':
                condition = ast_chunk.child_by_field_name('condition')
                consequence = ast_chunk.child_by_field_name('consequence')
                alternative = ast_chunk.child_by_field_name('alternative')

                tasks.put(ControlFlowGraph.ResolveTask(condition, context, current_file_location))
                tasks.put(ControlFlowGraph.ResolveTask(consequence, context, current_file_location))

                if alternative:
                    tasks.put(ControlFlowGraph.ResolveTask(alternative, context, current_file_location))

            elif ast_chunk.type == 'else_clause':
                tasks.put(ControlFlowGraph.ResolveTask(ast_chunk.child_by_field_name('body'), context, current_file_location))

            elif ast_chunk.type == 'elif_clause':
                condition = ast_chunk.child_by_field_name('condition')
                consequence = ast_chunk.child_by_field_name('consequence')
                alternative = ast_chunk.child_by_field_name('alternative')

                tasks.put(ControlFlowGraph.ResolveTask(condition, context, current_file_location))
                tasks.put(ControlFlowGraph.ResolveTask(consequence, context, current_file_location))

                if alternative:
                    tasks.put(ControlFlowGraph.ResolveTask(alternative, context, current_file_location))

            elif ast_chunk.type == 'assignment':
                left_node = ast_chunk.child_by_field_name('left')
                right_node = ast_chunk.child_by_field_name('right')
                # Every now and then there are assignments with no "right" node.
                # Very unclear in what situations this occurs
                if right_node:
                    tasks.put(ControlFlowGraph.ResolveTask(right_node, context, current_file_location))

            elif ast_chunk.type == 'call':
                function = ast_chunk.child_by_field_name('function')

                if function.type == 'identifier':
                    func_name = function.text.decode('utf-8')
                elif function.type == 'subscript':
                    #print("Subscript")
                    #print(function.sexp())
                    #print(function.child_by_field_name(
                    #    'value').text.decode('utf-8'))
                    #print(function.child_by_field_name(
                    #    'subscript').text.decode('utf-8'))
                    # Don't handle this for now
                    func_name = None
                else:
                    #function_caller_obj = function.child_by_field_name('object').text.decode('utf-8')
                    if function.child_by_field_name('attribute'):
                        func_name = function.child_by_field_name(
                            'attribute').text.decode('utf-8')
                    else:
                        func_name = None
                args = ast_chunk.child_by_field_name('arguments')
                arg_count = 0
                for arg in args.children:
                    if arg.is_named:
                        arg_count += 1
                
                if func_name:
                    if not self.function_exists(func_name, arg_count):
                        self._graph.add_node_to_graph(context, func_name, arg_count, file=current_file_location)

                        call_defs = self._find_function_def_nodes_matching_name_tree_sitter(
                            func_name, self._root_tree, current_file_location, arg_count)

                        for (call_def, call_file) in call_defs:
                            tasks.put(ControlFlowGraph.ResolveTask(call_def.child_by_field_name('body'), context +
                                                                ['unknown.' +
                                                                    func_name + '.' + str(arg_count)], call_file))


                            if (call_def and
                                    call_def.child_by_field_name('name').text.decode('utf-8') in self._functions_to_locate):
                                self._detected = True
                                return

                    if func_name in self._functions_to_locate:
                        self._detected = True
                        return

                if args:
                    for child in args.children:
                        tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))

            elif ast_chunk.type == 'list':
                pass  # Don't care?

            elif ast_chunk.type == 'block':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))


            elif ast_chunk.type == 'augmented_assignment':
                left_node = ast_chunk.child_by_field_name('left')
                right_node = ast_chunk.child_by_field_name('right')
                tasks.put(ControlFlowGraph.ResolveTask(right_node, context, current_file_location))

            elif ast_chunk.type == 'comment':
                pass  # Don't care
            elif ast_chunk.type == 'import_from_statement':
                self._resolve_import_into_callgraph(ast_chunk, context, current_file_location, tasks)
            elif ast_chunk.type == 'class_definition':
                pass  # Don't care
            elif ast_chunk.type == 'integer':
                pass  # Don't care
            elif ast_chunk.type == 'string':
                pass  # Don't care
            elif ast_chunk.type == 'false':
                pass  # Don't care
            elif ast_chunk.type == 'float':
                pass  # Don't care
            elif ast_chunk.type == 'none':
                pass  # Don't care
            elif ast_chunk.type == 'true':
                pass  # Don't care
            elif ast_chunk.type == 'tuple':
                pass  # Don't care
            elif ast_chunk.type == 'subscript':
                pass  # Don't care
            elif ast_chunk.type == 'list_splat':
                pass  # Don't care

            elif ast_chunk.type == 'keyword_argument':
                pass  # Don't care
            elif ast_chunk.type == 'not_operator':
                argument = ast_chunk.child_by_field_name('argument')
                tasks.put(ControlFlowGraph.ResolveTask(argument, context, current_file_location))

    
            elif ast_chunk.type == 'conditional_expression':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))

            elif ast_chunk.type == 'for_statement':
                left_node = ast_chunk.child_by_field_name('left')
                right_node = ast_chunk.child_by_field_name('right')
                body_node = ast_chunk.child_by_field_name('body')

                tasks.put(ControlFlowGraph.ResolveTask(left_node, context, current_file_location))
                tasks.put(ControlFlowGraph.ResolveTask(right_node, context, current_file_location))
                tasks.put(ControlFlowGraph.ResolveTask(body_node, context, current_file_location))

            elif ast_chunk.type == 'raise_statement':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))
            elif ast_chunk.type == 'parenthesized_expression':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))
            elif ast_chunk.type == 'while_statement':
                condition = ast_chunk.child_by_field_name('condition')
                body = ast_chunk.child_by_field_name('body')
                tasks.put(ControlFlowGraph.ResolveTask(condition, context, current_file_location))
                tasks.put(ControlFlowGraph.ResolveTask(body, context, current_file_location))


            elif ast_chunk.type == 'function_definition':
                pass  # Don't care

            elif ast_chunk.type == 'return_statement':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))

            elif ast_chunk.type == 'binary_operator':
                left_node = ast_chunk.child_by_field_name('left')
                right_node = ast_chunk.child_by_field_name('right')

                tasks.put(ControlFlowGraph.ResolveTask(left_node, context, current_file_location))
                tasks.put(ControlFlowGraph.ResolveTask(right_node, context, current_file_location))
            elif ast_chunk.type == 'boolean_operator':
                left_node = ast_chunk.child_by_field_name('left')
                right_node = ast_chunk.child_by_field_name('right')

                tasks.put(ControlFlowGraph.ResolveTask(left_node, context, current_file_location))
                tasks.put(ControlFlowGraph.ResolveTask(right_node, context, current_file_location))

            elif ast_chunk.type == 'try_statement':
                tasks.put(ControlFlowGraph.ResolveTask(ast_chunk.child_by_field_name('body'), context, current_file_location))


            elif ast_chunk.type == 'identifier':
                pass  # Don't care
            elif ast_chunk.type == 'with_statement':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))

            elif ast_chunk.type == 'with_clause':
                for child in ast_chunk.children:
                    tasks.put(ControlFlowGraph.ResolveTask(child, context, current_file_location))

            elif ast_chunk.type == 'dictionary':
                for child in ast_chunk.children:
                    value = child.child_by_field_name('value')
                    if value is not None:
                        tasks.put(ControlFlowGraph.ResolveTask(child.child_by_field_name('value'), context, current_file_location))

            else:
                # Unknown, unhandled node
                #print(ast_chunk.sexp())
                pass




    # Returns a List of tuples where the first element is the function def node and the
    # second arg is the file where this was found
    def _find_function_def_nodes_matching_name_tree_sitter(self, func_name: str,
                                                           starting_ast,
                                                           current_file_location: str,
                                                           arg_count: int,
                                                           class_type: str = 'unknown') -> typing.List[typing.Tuple[any, str]]:
        (nodes, names, files) = self._find_function_def_nodes_tree_sitter(starting_ast,
                                                                   current_file_location,
                                                                   class_type,
                                                                   imports_analyzed={})

        result = []

        for idx, name in enumerate(names):
            if name == func_name:
                function_def_params = nodes[idx].child_by_field_name('parameters')
                param_count = 0
                default_count = 0
                for param in function_def_params.children:
                    if param.is_named:
                        # Ignore self
                        if not param.text.decode('utf-8') == 'self':
                            if param.type == 'identifier':
                                param_count += 1
                            elif  param.type in ['default', 'dictionary_splat_pattern', 'default_parameter']:
                                default_count += 1

                        
                if param_count == arg_count or (param_count < arg_count and (arg_count - param_count <= default_count)):
                    result.append((nodes[idx], files[idx]))

        return result

    # Find all possible matching Function Definition nodes and return them,
    # if possible
    # This may include a Class' __init__ if it exists.

    def _find_function_def_nodes_tree_sitter(self, init_starting_ast,
                                             init_current_file_location: str,
                                             init_class_type: str = 'unknown',
                                             imports_analyzed: dict = {}) -> typing.Tuple[typing.List[any], typing.List[str], typing.List[str]]:

        class JobQueue:
            def __init__(self, cfg_obj, syntax_tree, import_path, class_type):
                self.cfg_obj = cfg_obj
                self.syntax_tree = syntax_tree
                self.import_path = import_path
                self.class_type = class_type


        search_queue = queue.SimpleQueue()

        result: typing.List[any] = []
        result_names: typing.List[any] = []
        result_files: typing.List[str] = []

        import_paths_examined = {}

        if self._func_import_graph.is_ready() and self._func_import_graph.knows_about_file(init_current_file_location):
            result, result_names, result_files = self._func_import_graph.get_all_data_starting_at(init_current_file_location)
        else:
            search_queue.put(JobQueue(self, init_starting_ast, init_current_file_location, init_class_type))

        while not search_queue.empty():
            search_task = search_queue.get()
            starting_ast = search_task.syntax_tree
            current_file_location = search_task.import_path
            class_type = search_task.class_type

            # Find functions defined in this file

            func_visitor = ast_visitors.TreeSitterFunctionDefVisitor()
            func_visitor.visit(starting_ast)

            funcs = func_visitor.get_functions()

            for func in funcs:
                self._func_import_graph.add_func_def(current_file_location, func["node"], func['name'])

                result_names.append(func['name'])
                result.append(func["node"])
                result_files.append(current_file_location)

            # Find functions defined in classes in this file
            class_visitor = ast_visitors.TreeSitterClassDefVisitor()
            class_visitor.visit(starting_ast)
            init_funcs = class_visitor.get_initalizer()

            for init_func in init_funcs:
                self._func_import_graph.add_func_def(current_file_location, init_func["node"], init_func['class'])

                result_names.append(init_func['class'])
                result.append(init_func["node"])
                result_files.append(current_file_location)

            # Find imports and recursively check those files
            import_visitor = ast_visitors.TreeSitterImportVisitor()
            import_visitor.visit(starting_ast)

            imports = import_visitor.get_imports()

            for import_name, import_details in imports.items():
                self.thread_import_resolver_lock.acquire(True)
                if import_name not in imports_analyzed:
                    self.thread_import_resolver_lock.release()

                    import_paths = self._find_entries_for_import(
                        import_details['name'],
                        current_file_location,
                        import_details['module'],
                        import_details['level'])

                    imports_analyzed[import_name] = import_paths

                    for import_path in import_paths:
                        self._func_import_graph.add_relationship(current_file_location, import_path)

                        if import_path not in import_paths_examined and import_path and \
                        mimetypes.guess_type(import_path)[0] == 'text/x-python':
                            import_paths_examined[import_path] = True

                            with open(import_path, mode='r') as source_content:
                                tree = self.parser.parse(
                                    source_content.read().encode('utf-8'))
                                syntax_tree = tree.root_node

                                search_queue.put(JobQueue(self, syntax_tree, import_path, class_type))

                else:
                    for import_path in import_paths:
                        self._func_import_graph.add_relationship(current_file_location, import_path)
                    self.thread_import_resolver_lock.release()


        self._func_import_graph.set_ready()
        return (result, result_names, result_files)

    # Returns the files on disk possibly corresponding to the import if they can be found

    def _find_entries_for_import(self, import_name: str,
                               current_file_location: str,
                               module: str = '',
                               level: int = 0) -> typing.List[str]:
        results = set()

        # Try using pydeps
        import_loc = None
        if level == 1:
            # Try to find a matching import
            for import_data in self._imports.values():
                if import_data['path'] == current_file_location:
                    for imported_name in import_data['imports']:
                        if imported_name.endswith(module):
                            import_path = self._imports[imported_name]['path']
                            if import_path != None:
                                results = set([self._imports[imported_name]['path']])

        if (module != '' and module + '.' + import_name in self._imports and self._imports[module + '.' + import_name]['path']):
            import_loc = module + '.' + import_name
        elif (module == '' and import_name in self._imports and self._imports[import_name]['path']):
            import_loc = import_name
        elif (module in self._imports and self._imports[module]['path']):
            import_loc = module

        if import_loc:
            results = set([self._imports[import_loc]['path']])

        if module != '' and len(results) == 0:
            # Try to find a folder that looks like a matching module
            for root, dirs, _ in os.walk(self.get_folder_back_n_dirs(pathlib.Path(current_file_location), self.module_backtrace_max)):
                for dir in dirs:
                    if dir == module:
                        matching_file = self.get_file_in_folder(import_name, os.path.join(root, dir))
                        if matching_file is not None:
                            results.add(matching_file)
                        elif os.path.exists(os.path.join(os.path.join(root, dir), '__init__.py')):
                            # There might be an __init__.py file
                            results.add(os.path.join(os.path.join(root, dir), '__init__.py'))
                            
        return results

    def get_folder_back_n_dirs(self, path: pathlib.Path, n: int):
        res = path

        for i in range(n):
            res = res.parent

        return res


    def get_file_in_folder(self, name, root):
        for root, _, files in os.walk(pathlib.Path(root)):
            for file in files:
                new_file = pathlib.Path(file)

                if new_file.name.split(new_file.suffix)[0]  == name:
                    fullpath = os.path.join(root, new_file)
                    return fullpath

            break
        
        return None


    def function_exists(self, func_name: str, arg_count: typing.Optional[int] = None):
        return self._graph.has_function(func_name, arg_count)
