import ast
import typing
import copy
import os
import subprocess
import json
import networkx
import matplotlib.pyplot as plt
import mimetypes
import internal_cfg
import ast_visitors

import pydeps

class ControlFlowGraph:
    def __init__(self, function_to_locate: str = None):
        self._graph = internal_cfg.InternalGraphRepesentation()
        self._root_tree: typing.Optional[ast.AST] = None
        self._function_to_locate = function_to_locate
        self._detected = False
        self._imports = {}  # Data structure from pydeps

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
        output = subprocess.run(['pydeps', file_path, '--show-deps', '--pylib', '--no-show', '--max-bacon', '0', '--no-dot'], capture_output=True)

        json_import_tree = json.loads(output.stdout.decode("utf-8"))
        self._imports = copy.deepcopy(json_import_tree)

    def _parse_and_resolve(self, ast_chunk: ast.AST,
                           context: typing.List[str],
                           current_file_location: str):
        if isinstance(ast_chunk, ast.Call):
            func_name: typing.Optional[str] = None
            if isinstance(ast_chunk.func, ast.Name):
                func_name = ast_chunk.func.id
            elif isinstance(ast_chunk.func, ast.Subscript):
                # TODO Unsure how to handle this yet...
                pass
            elif isinstance(ast_chunk.func, ast.Attribute):
                func_name = ast_chunk.func.attr
            else:
                raise ValueError("Unknown Call.func type")

            if func_name:
                if not self.function_exists(func_name):
                    self._graph.add_node_to_graph(context, func_name)

                    call_defs = self._find_function_def_nodes(func_name, self._root_tree, current_file_location, imports_analyzed={})
                    for call_def in call_defs:
                        self._parse_and_resolve(call_def,
                                                context + ['unknown.' + func_name], current_file_location)

                        if (call_def and call_def.name == self._function_to_locate):
                            print('Found {} in code'.format(self._function_to_locate))
                            self._detected = True
                            return

                if self._function_to_locate == func_name:
                    print('Found {} in code'.format(self._function_to_locate))
                    self._detected = True
                    return

        if isinstance(ast_chunk, ast.BinOp):
            # Need to recursively check left and right sides
            self._parse_and_resolve(ast_chunk.left, context, current_file_location)
            self._parse_and_resolve(ast_chunk.right, context, current_file_location)
        elif isinstance(ast_chunk, ast.If):
            # Need to check orelse in addition to generic body
            self._parse_and_resolve(ast_chunk.test, context, current_file_location)
            for child in ast_chunk.orelse:
                self._parse_and_resolve(child, context, current_file_location)

        # More work?
        if hasattr(ast_chunk, 'body'):
            for child in ast_chunk.body:
                # Check for FunctionDefs because we don't want to walk these
                # until we find a function call to them.
                if not isinstance(child, ast.FunctionDef):
                    self._parse_and_resolve(child, context, current_file_location)
        if hasattr(ast_chunk, 'args'):
            if isinstance(ast_chunk.args, list):
                for child in ast_chunk.args:
                    self._parse_and_resolve(child, context, current_file_location)
        elif hasattr(ast_chunk, 'value'):
            self._parse_and_resolve(ast_chunk.value, context, current_file_location)

    # Find all possible matching Function Definition nodes and return them,
    # if possible
    # This may include a Class' __init__ if it exists.
    def _find_function_def_nodes(self, func_name: str, starting_ast: ast.AST,
                                 current_file_location: str,
                                 class_type: str = 'unknown',
                                 imports_analyzed: dict = {}):
        result: typing.List[ast.AST] = []
        func_visitor = ast_visitors.FunctionDefVisitor()
        func_visitor.visit(starting_ast)

        funcs = func_visitor.get_functions()
        for func in funcs:
            if func_name == func["name"]:
                result.append(func["node"])

        # Check for class definitions
        class_visitor = ast_visitors.ClassDefVisitor()
        class_visitor.visit(starting_ast)
        init_funcs = class_visitor.get_initalizer()

        for init_func in init_funcs:
            if func_name == init_func["class"]:
                result.append(init_func["node"])

        # Not in current file, check imported files
        import_visitor = ast_visitors.ImportVisitor()
        import_visitor.visit(starting_ast)

        imports = import_visitor.get_imports()

        for import_name, import_details in imports.items():
            if import_name not in imports_analyzed:
                imports_analyzed[import_name] = True

                import_path = self._find_entry_for_import(import_details['name'],
                                                          current_file_location,
                                                          import_details['module'])
                if import_path and mimetypes.guess_type(import_path)[0] == 'text/x-python':
                    with open(import_path, mode='r') as source_content:
                        syntax_tree: ast.Module = ast.parse(source_content.read(),
                                                            import_path)
                        other_tree = copy.deepcopy(syntax_tree)

                        definitions = self._find_function_def_nodes(func_name,
                                                                    other_tree,
                                                                    import_path,
                                                                    class_type,
                                                                    imports_analyzed)
                        for definition in definitions:
                            print("Found def")
                            result.append(definition)

        return result

    # Returns the file on disk corresponding to the import if it can be found
    # Otherwise returns None
    def _find_entry_for_import(self, import_name: str,
                               current_file_location: str,
                               module: str = ''):
        # Try using pydeps
        import_loc = None
        if (module != '' and module + '.' + import_name in self._imports):
            import_loc = module + '.' + import_name
        elif (module == '' and import_name in self._imports):
            import_loc = import_name

        if import_loc:
            print("Found import: " + import_loc)
            if self._imports[import_loc]['path']:
                print("  --> " + self._imports[import_loc]['path'])
            return self._imports[import_loc]['path']

        return None

    def function_exists(self, func_name: str):
        return self._graph.has_function(func_name)
