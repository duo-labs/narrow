import ast
import typing
import subprocess
import json
import mimetypes
import internal_cfg
import ast_visitors
import cache
import networkx
import threading
from matplotlib import pyplot as plt
from tree_sitter import Language, Parser
import os
import pathlib

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
    def __init__(self, function_to_locate: str = None, module_backtrace_max=2):
        self._graph = internal_cfg.InternalGraphRepesentation()
        self._root_tree: typing.Optional[ast.AST] = None
        self._function_to_locate = function_to_locate
        self.module_backtrace_max = module_backtrace_max

        self._detected = False
        # Data structure from pydeps
        self._imports: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
        self._cache = cache.Cache()
        self.parser = None
        self.symlinked_entrypoint = None

    def __del__(self):
        if self.symlinked_entrypoint:
            # A symlink was created, delete it
            os.unlink(self.symlinked_entrypoint)

    # Function responsible for constructing a CFG given an entry file.
    #   only_file: If True, only builds a CFG contained in a single file.
    #              External references are noted as such but not resolved.
    def construct_from_file(self, file_path: str, only_file=False):
    
        new_file_path = self.mitigate_extensionless_file(file_path)

        self._resolve_module_imports(new_file_path)

        with open(file_path, mode='r') as source_content:
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
            print(syntax_tree)

            self._parse_and_resolve_tree_sitter(
                syntax_tree.root_node, ['__narrow_entry__'], file_path)

            if self._detected is False:
                print('Did not find {} in code'.format(
                    self._function_to_locate))


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

    def print_graph_matplotlib(self, max_depth=None):
        networkx_data = self._graph.get_networkx_digraph()
        networkx_data = networkx.dfs_tree(
            networkx_data, source='__narrow_entry__', depth_limit=max_depth)

        networkx.draw_spring(networkx_data, with_labels=True)

        plt.show()

    def _resolve_module_imports(self, file_path: str):
        output = subprocess.run(['pydeps', file_path, '--show-deps', '--pylib',
                                '--no-show', '--max-bacon', '0', '--no-dot', '--include-missing'],
                                capture_output=True)

        print(output.stdout.decode("utf-8"))
        print(output.stderr.decode("utf-8"))

        json_import_tree = json.loads(output.stdout.decode("utf-8"))
        self._imports = json_import_tree

    def _parse_and_resolve_tree_sitter(self, ast_chunk, context: typing.List[str], current_file_location: str):
        assert(self._root_tree is not None)
        if self._detected:
            # We're done early. Stop parsing
            return
        if not ast_chunk.is_named:
            # Annomymous nodes are for complete syntax trees which we don't care about
            return

        if ast_chunk.type == 'module':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)
        elif ast_chunk.type == 'import_statement':
            pass  # Don't care
        elif ast_chunk.type == 'expression_statement':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)
        elif ast_chunk.type == 'if_statement':
            condition = ast_chunk.child_by_field_name('condition')
            consequence = ast_chunk.child_by_field_name('consequence')
            alternative = ast_chunk.child_by_field_name('alternative')
            self._parse_and_resolve_tree_sitter(
                condition, context, current_file_location)
            self._parse_and_resolve_tree_sitter(
                consequence, context, current_file_location)

            if alternative:
                self._parse_and_resolve_tree_sitter(
                    alternative, context, current_file_location)
        elif ast_chunk.type == 'else_clause':
            self._parse_and_resolve_tree_sitter(
                ast_chunk.child_by_field_name('body'), context, current_file_location)
        elif ast_chunk.type == 'elif_clause':
            condition = ast_chunk.child_by_field_name('condition')
            consequence = ast_chunk.child_by_field_name('consequence')
            alternative = ast_chunk.child_by_field_name('alternative')
            self._parse_and_resolve_tree_sitter(
                condition, context, current_file_location)
            self._parse_and_resolve_tree_sitter(
                consequence, context, current_file_location)

            if alternative:
                self._parse_and_resolve_tree_sitter(
                    alternative, context, current_file_location)

        elif ast_chunk.type == 'assignment':
            left_node = ast_chunk.child_by_field_name('left')
            right_node = ast_chunk.child_by_field_name('right')
            self._parse_and_resolve_tree_sitter(
                right_node, context, current_file_location)
        elif ast_chunk.type == 'call':
            function = ast_chunk.child_by_field_name('function')

            if function.type == 'identifier':
                func_name = function.text.decode('utf-8')
            elif function.type == 'subscript':
                print("Subscript")
                print(function.sexp())
                print(function.child_by_field_name(
                    'value').text.decode('utf-8'))
                print(function.child_by_field_name(
                    'subscript').text.decode('utf-8'))
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

            if func_name:
                if not self.function_exists(func_name):
                    self._graph.add_node_to_graph(context, func_name)

                    call_defs = self._find_function_def_nodes_matching_name_tree_sitter(
                        func_name, self._root_tree, current_file_location)

                    for call_def in call_defs:
                        self._parse_and_resolve_tree_sitter(call_def.child_by_field_name('body'),
                                                            context +
                                                            ['unknown.' +
                                                                func_name],
                                                            current_file_location)

                        if (call_def and
                                call_def.child_by_field_name('name').text.decode('utf-8') == self._function_to_locate):
                            print('Found {} in code'.format(
                                self._function_to_locate))
                            self._detected = True
                            return

                if self._function_to_locate == func_name:
                    print('Found {} in code'.format(self._function_to_locate))
                    self._detected = True
                    return

            if args:
                for child in args.children:
                    self._parse_and_resolve_tree_sitter(
                        child, context, current_file_location)
        elif ast_chunk.type == 'list':
            pass  # Don't care?

        elif ast_chunk.type == 'block':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)

        elif ast_chunk.type == 'augmented_assignment':
            left_node = ast_chunk.child_by_field_name('left')
            right_node = ast_chunk.child_by_field_name('right')
            self._parse_and_resolve_tree_sitter(
                right_node, context, current_file_location)
        elif ast_chunk.type == 'comment':
            pass  # Don't care
        elif ast_chunk.type == 'import_from_statement':
            pass  # Don't care
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
            self._parse_and_resolve_tree_sitter(
                argument, context, current_file_location)
 
        elif ast_chunk.type == 'conditional_expression':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)

        elif ast_chunk.type == 'for_statement':
            left_node = ast_chunk.child_by_field_name('left')
            right_node = ast_chunk.child_by_field_name('right')
            body_node = ast_chunk.child_by_field_name('body')

            self._parse_and_resolve_tree_sitter(
                left_node, context, current_file_location)
            self._parse_and_resolve_tree_sitter(
                right_node, context, current_file_location)
            self._parse_and_resolve_tree_sitter(
                body_node, context, current_file_location)

        elif ast_chunk.type == 'raise_statement':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)
        elif ast_chunk.type == 'parenthesized_expression':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)
        elif ast_chunk.type == 'while_statement':
            condition = ast_chunk.child_by_field_name('condition')
            body = ast_chunk.child_by_field_name('body')
            self._parse_and_resolve_tree_sitter(
                condition, context, current_file_location)
            self._parse_and_resolve_tree_sitter(
                body, context, current_file_location)


        elif ast_chunk.type == 'function_definition':
            pass  # Don't care

        elif ast_chunk.type == 'return_statement':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)
        elif ast_chunk.type == 'binary_operator':
            left_node = ast_chunk.child_by_field_name('left')
            right_node = ast_chunk.child_by_field_name('right')

            self._parse_and_resolve_tree_sitter(
                left_node, context, current_file_location)
            self._parse_and_resolve_tree_sitter(
                right_node, context, current_file_location)
        elif ast_chunk.type == 'boolean_operator':
            left_node = ast_chunk.child_by_field_name('left')
            right_node = ast_chunk.child_by_field_name('right')

            self._parse_and_resolve_tree_sitter(
                left_node, context, current_file_location)
            self._parse_and_resolve_tree_sitter(
                right_node, context, current_file_location)
        elif ast_chunk.type == 'try_statement':
            self._parse_and_resolve_tree_sitter(
                ast_chunk.child_by_field_name('body'), context, current_file_location)

        elif ast_chunk.type == 'identifier':
            pass  # Don't care
        elif ast_chunk.type == 'with_statement':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)
        elif ast_chunk.type == 'with_clause':
            for child in ast_chunk.children:
                self._parse_and_resolve_tree_sitter(
                    child, context, current_file_location)

        else:
            # Unknown, unhandled node
            #print(ast_chunk.sexp())
            pass

    def _find_function_def_nodes_matching_name_tree_sitter(self, func_name: str,
                                                           starting_ast,
                                                           current_file_location: str,
                                                           class_type: str = 'unknown'):
        (nodes, names) = self._find_function_def_nodes_tree_sitter(starting_ast,
                                                                   current_file_location,
                                                                   class_type,
                                                                   imports_analyzed={})

        result = []

        for idx, name in enumerate(names):
            if name == func_name:
                result.append(nodes[idx])

        return result

    # Find all possible matching Function Definition nodes and return them,
    # if possible
    # This may include a Class' __init__ if it exists.

    def _find_function_def_nodes_tree_sitter(self, starting_ast,
                                             current_file_location: str,
                                             class_type: str = 'unknown',
                                             imports_analyzed: dict = {}):

        result: typing.List[any] = []
        result_names: typing.List[any] = []

        (cache_nodes, cache_names) = self._cache.get_function_defs(
            current_file_location, starting_ast)
        if cache_nodes is not None:
            return (cache_nodes, cache_names)

        # Find functions defined in this file

        func_visitor = ast_visitors.TreeSitterFunctionDefVisitor()
        func_visitor.visit(starting_ast)

        funcs = func_visitor.get_functions()
        for func in funcs:
            result_names.append(func['name'])
            result.append(func["node"])

        # Find functions defined in classes in this file
        class_visitor = ast_visitors.TreeSitterClassDefVisitor()
        class_visitor.visit(starting_ast)
        init_funcs = class_visitor.get_initalizer()

        for init_func in init_funcs:
            result_names.append(init_func['class'])
            result.append(init_func["node"])

        # Find imports and recursively check those files
        import_visitor = ast_visitors.TreeSitterImportVisitor()
        import_visitor.visit(starting_ast)

        imports = import_visitor.get_imports()

        started_threads = []

        for import_name, import_details in imports.items():
            if import_name not in imports_analyzed:
                imports_analyzed[import_name] = True

                import_paths = self._find_entries_for_import(
                    import_details['name'],
                    current_file_location,
                    import_details['module'],
                    import_details['level'])
                for import_path in import_paths:
                    if import_path and \
                    mimetypes.guess_type(import_path)[0] == 'text/x-python':

                        with open(import_path, mode='r') as source_content:
                            tree = self.parser.parse(
                                source_content.read().encode('utf-8'))
                            syntax_tree = tree.root_node

                            new_thread = FunctionDefNodesFinder(find_args=(self, syntax_tree, import_path, class_type, imports_analyzed,))
                            new_thread.start()
                            started_threads.append(new_thread)


        for started_thread in started_threads:
            started_thread.join()

            (sub_res, sub_names) = started_thread.result
            for idx, sub_res in enumerate(sub_res):
                result.append(sub_res)
                result_names.append(sub_names[idx])

        self._cache.store_function_defs(
            current_file_location, starting_ast, (result, result_names))

        return (result, result_names)

    # Returns the files on disk possibly corresponding to the import if they can be found

    def _find_entries_for_import(self, import_name: str,
                               current_file_location: str,
                               module: str = '',
                               level: int = 0) -> typing.List[str]:
        results = []

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
                                results = [ self._imports[imported_name]['path'] ]

        if (module != '' and module + '.' + import_name in self._imports):
            import_loc = module + '.' + import_name
        elif (module == '' and import_name in self._imports):
            import_loc = import_name

        if import_loc:
            results = [self._imports[import_loc]['path']]

        if module != '' and len(results) == 0:
            # Try to find a folder that looks like a matching module
            for root, dirs, _ in os.walk(self.get_folder_back_n_dirs(pathlib.Path(current_file_location), self.module_backtrace_max)):
                for dir in dirs:
                    if dir == module:
                        print("Found folder: " + dir)

                        matching_file = self.get_file_in_folder(import_name, os.path.join(root, dir))
                        if matching_file is not None:
                            results.append(matching_file)
                        
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


    def function_exists(self, func_name: str):
        return self._graph.has_function(func_name)
