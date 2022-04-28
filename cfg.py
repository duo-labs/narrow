import ast
import typing
import copy
import subprocess
import json
import mimetypes
import internal_cfg
import ast_visitors
import cache
import networkx
from matplotlib import pyplot as plt


class ControlFlowGraph:
    def __init__(self, function_to_locate: str = None):
        self._graph = internal_cfg.InternalGraphRepesentation()
        self._root_tree: typing.Optional[ast.AST] = None
        self._function_to_locate = function_to_locate
        self._detected = False
        # Data structure from pydeps
        self._imports: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
        self._cache = cache.Cache()

    # Function responsible for constructing a CFG given an entry file.
    #   only_file: If True, only builds a CFG contained in a single file.
    #              External references are noted as such but not resolved.
    def construct_from_file(self, file_path: str, only_file=False):
        with open(file_path, mode='r') as source_content:
            syntax_tree: ast.Module = ast.parse(source_content.read(),
                                                file_path)
            self._root_tree = copy.deepcopy(syntax_tree)

            self._resolve_module_imports(file_path)

            self._parse_and_resolve(syntax_tree, ['__narrow_entry__'],
                                    file_path)

            if self._detected is False:
                print('Did not find {} in code'.format(
                    self._function_to_locate))

    def did_detect(self):
        return self._detected

    def print_graph_to_stdout(self):
        print(self._graph.get_expanded_graph())

    def print_graph_matplotlib(self):
        networkx_data = self._graph.get_networkx_digraph()

        networkx.draw_spring(networkx_data, with_labels=True)

        plt.show()

    def _resolve_module_imports(self, file_path: str):
        output = subprocess.run(['pydeps', file_path, '--show-deps', '--pylib',
                                '--no-show', '--max-bacon', '0', '--no-dot'],
                                capture_output=True)

        json_import_tree = json.loads(output.stdout.decode("utf-8"))
        self._imports = copy.deepcopy(json_import_tree)

    def _parse_and_resolve(self, ast_chunk: ast.AST,
                           context: typing.List[str],
                           current_file_location: str):
        assert(self._root_tree is not None)

        if isinstance(ast_chunk, ast.Call):
            func_name: typing.Optional[str] = None
            if isinstance(ast_chunk.func, ast.Name):
                func_name = ast_chunk.func.id
            elif isinstance(ast_chunk.func, ast.Subscript):
                # TODO Unsure how to handle this yet...
                print("Skipped something I probably shouldn't")
                pass
            elif isinstance(ast_chunk.func, ast.Attribute):
                func_name = ast_chunk.func.attr
            elif isinstance(ast_chunk.func, ast.Call):
                self._parse_and_resolve(ast_chunk.func, context, current_file_location)
            elif isinstance(ast_chunk.func, ast.BoolOp):
                left = ast_chunk.func.values[0]
                right = ast_chunk.func.values[1]
                self._parse_and_resolve(left, context, current_file_location)
                self._parse_and_resolve(right, context, current_file_location)
            else:
                raise ValueError("Unknown Call.func type:" + str(ast_chunk.func))

            if func_name:
                if not self.function_exists(func_name):
                    self._graph.add_node_to_graph(context, func_name)

                    call_defs = self._find_function_def_nodes_matching_name(
                        func_name, self._root_tree, current_file_location)
                    for call_def in call_defs:
                        self._parse_and_resolve(call_def,
                                                context +
                                                ['unknown.' + func_name],
                                                current_file_location)

                        if (call_def and
                                call_def.name == self._function_to_locate):
                            print('Found {} in code'.format(
                                self._function_to_locate))
                            self._detected = True
                            return

                if self._function_to_locate == func_name:
                    print('Found {} in code'.format(self._function_to_locate))
                    self._detected = True
                    return

        if isinstance(ast_chunk, ast.BinOp):
            # Need to recursively check left and right sides
            self._parse_and_resolve(
                ast_chunk.left, context, current_file_location)
            self._parse_and_resolve(
                ast_chunk.right, context, current_file_location)
        elif isinstance(ast_chunk, ast.If):
            # Need to check orelse in addition to generic body
            self._parse_and_resolve(
                ast_chunk.test, context, current_file_location)
            for child in ast_chunk.orelse:
                self._parse_and_resolve(child, context, current_file_location)

        # More work?
        if hasattr(ast_chunk, 'body'):
            if isinstance(typing.cast(typing.Any, ast_chunk).body, list):
                for child in typing.cast(typing.Any, ast_chunk).body:
                    # Check for FunctionDefs because we don't want to walk these
                    # until we find a function call to them.
                    if not isinstance(child, ast.FunctionDef):
                        self._parse_and_resolve(
                            child, context, current_file_location)
        if hasattr(ast_chunk, 'args'):
            if isinstance(typing.cast(typing.Any, ast_chunk).args, list):
                for child in typing.cast(typing.Any, ast_chunk).args:
                    self._parse_and_resolve(
                        child, context, current_file_location)
        elif hasattr(ast_chunk, 'value'):
            self._parse_and_resolve(
                typing.cast(typing.Any, ast_chunk).value, context,
                current_file_location)

    def _find_function_def_nodes_matching_name(self, func_name: str,
                                               starting_ast: ast.AST,
                                               current_file_location: str,
                                               class_type: str = 'unknown'):
        (nodes, names) = self._find_function_def_nodes(starting_ast,
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
    def _find_function_def_nodes(self, starting_ast: ast.AST,
                                 current_file_location: str,
                                 class_type: str = 'unknown',
                                 imports_analyzed: dict = {}):

        result: typing.List[ast.AST] = []
        result_names: typing.List[str] = []

        (cache_nodes, cache_names) = self._cache.get_function_defs(
            current_file_location, starting_ast)
        if cache_nodes is not None:
            return (cache_nodes, cache_names)

        func_visitor = ast_visitors.FunctionDefVisitor()
        func_visitor.visit(starting_ast)

        funcs = func_visitor.get_functions()
        for func in funcs:
            result_names.append(func['name'])
            result.append(func["node"])

        # Check for class definitions
        class_visitor = ast_visitors.ClassDefVisitor()
        class_visitor.visit(starting_ast)
        init_funcs = class_visitor.get_initalizer()

        for init_func in init_funcs:
            result_names.append(init_func['class'])
            result.append(init_func["node"])

        # Not in current file, check imported files
        import_visitor = ast_visitors.ImportVisitor()
        import_visitor.visit(starting_ast)

        imports = import_visitor.get_imports()

        for import_name, import_details in imports.items():
            if import_name not in imports_analyzed:
                imports_analyzed[import_name] = True

                import_path = self._find_entry_for_import(
                                import_details['name'],
                                current_file_location,
                                import_details['module'],
                                import_details['level'])
                if import_path and \
                   mimetypes.guess_type(import_path)[0] == 'text/x-python':

                    with open(import_path, mode='r') as source_content:
                        syntax_tree: ast.Module = ast.parse(
                                                    source_content.read(),
                                                    import_path)
                        other_tree = copy.deepcopy(syntax_tree)

                        (definitions, names) = self._find_function_def_nodes(
                                        other_tree,
                                        import_path,
                                        class_type,
                                        imports_analyzed)
                        for idx, definition in enumerate(definitions):
                            result.append(definition)
                            result_names.append(names[idx])

        self._cache.store_function_defs(
            current_file_location, starting_ast, (result, result_names))
        return (result, result_names)

    # Returns the file on disk corresponding to the import if it can be found
    # Otherwise returns None
    def _find_entry_for_import(self, import_name: str,
                               current_file_location: str,
                               module: str = '',
                               level: int = 0):
        # Try using pydeps
        import_loc = None
        if level == 1:
            # Try to find a matching import
            for import_data in self._imports.values():
                if import_data['path'] == current_file_location:
                    for imported_name in import_data['imports']:
                        if imported_name.endswith(module):
                            return self._imports[imported_name]['path']

        if (module != '' and module + '.' + import_name in self._imports):
            import_loc = module + '.' + import_name
        elif (module == '' and import_name in self._imports):
            import_loc = import_name

        if import_loc:
            return self._imports[import_loc]['path']

        return None

    def function_exists(self, func_name: str):
        return self._graph.has_function(func_name)
