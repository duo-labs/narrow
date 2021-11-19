import ast
import typing
import copy
import os

class FunctionDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self._funcs = {}

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name not in self._funcs:
            self._funcs[node.name] = copy.deepcopy(node)

    def get_functions(self):
        return self._funcs


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self._imports = {}

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name not in self._imports:
                self._imports[alias.name] = copy.deepcopy(alias)

    def get_imports(self):
        return self._imports


class InternalGraphRepesentation:
    def __init__(self):
        self._graph = {
            '__narrow_entry__': {
                'next': set()
            }
        }

    def __str__(self):
        return self._graph.__repr__()

    # Adds a new node to the graph. context is used to find the path so far
    # and next_node represents the name of the next node.
    #
    # Since right now the implementation only works on flat function calls,
    # most of context is unused. Only the last element is used to find the
    # caller.
    #
    # Duplicates are automatically prevneted, so you can call this without
    # checking is_in_graph()
    def add_node_to_graph(self, context: typing.List[str], next_node: str):
        if len(context) == 0:
            raise ValueError("context should never be empty. \
            Use __narrow_entry__ for the root node")

        caller = context[-1]

        if caller not in self._graph:
            raise ValueError("The caller should already exist in the graph")

        self._graph[caller]['next'].add(next_node)

        if next_node not in self._graph:
            self._graph[next_node] = {
                'next': set()
            }

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

    def has_function(self, function_name: str):
        if function_name in self._graph:
            return True

        return False


class ControlFlowGraph:
    def __init__(self, function_to_locate: str = None):
        self._graph = InternalGraphRepesentation()
        self._root_tree = None
        self._function_to_locate = function_to_locate
        self._detected = False

    # Function responsible for constructing a CFG given an entry file.
    #   only_file: If True, only builds a CFG contained in a single file.
    #              External references are noted as such but not resolved.
    def construct_from_file(self, file_path: str, only_file=False):
        with open(file_path, mode='r') as source_content:
            syntax_tree: ast.Module = ast.parse(source_content.read(), file_path)
            self._root_tree = copy.deepcopy(syntax_tree)

            self._parse_and_resolve(syntax_tree, ['__narrow_entry__'], file_path)
            
            if self._detected == False:
                print('Did not find {} in code'.format(self._function_to_locate))
                print(self._graph)


    def did_detect(self):
        return self._detected


    def _parse_and_resolve(self, ast_chunk: ast.AST,
                           context: typing.List[str],
                           current_file_location: str):
        if isinstance(ast_chunk, ast.Call):
            func_name = None
            if isinstance(ast_chunk.func, ast.Name):
                func_name = ast_chunk.func.id
            else:
                func_name = ast_chunk.func.attr

            self._graph.add_node_to_graph(context, func_name)

            if self._function_to_locate == func_name:
                print('Found {} in code'.format(self._function_to_locate))
                self._detected = True
                print(self._graph)
                return

            
            call_def = self._find_function_def_node(func_name, self._root_tree, current_file_location)
            if call_def:
                self._parse_and_resolve(call_def,
                                        context + [func_name], current_file_location)
        # More work?
        if hasattr(ast_chunk, 'body'):
            for child in ast_chunk.body:
                # Check for FunctionDefs because we don't want to walk these
                # until we find a function call to them.
                if not isinstance(child, ast.FunctionDef):
                    self._parse_and_resolve(child, context, current_file_location)
        elif hasattr(ast_chunk, 'value'):
            self._parse_and_resolve(ast_chunk.value, context, current_file_location)

    # Find a Function Definition node and return it, if possible
    def _find_function_def_node(self, func_name: str, starting_ast: ast.AST, current_file_location: str):
        func_visitor = FunctionDefVisitor()
        func_visitor.visit(starting_ast)

        funcs = func_visitor.get_functions()
        if func_name in funcs:
            return funcs[func_name]

        # Not in current file, check imported files
        import_visitor = ImportVisitor()
        import_visitor.visit(starting_ast)

        imports = import_visitor.get_imports()

        for import_name, node in imports.items():
            import_path = self._find_entry_for_import(import_name, current_file_location)
            if import_path:
                with open(import_path, mode='r') as source_content:
                    syntax_tree: ast.Module = ast.parse(source_content.read(), import_path)
                    other_tree = copy.deepcopy(syntax_tree)

                    res = self._find_function_def_node(func_name, other_tree, import_path)
                    if res:
                        return res

        return None

    # Returns the file on disk corresponding to the import if it can be found
    # Otherwise returns None
    def _find_entry_for_import(self, import_name: str, current_file_location: str):
        # If there's a file name matching import_name in the same location as
        # the calling file this is probably what will get imported
        caller_abs_path = os.path.abspath(current_file_location)
        caller_directory = os.path.dirname(caller_abs_path)

        target_path = os.path.join(caller_directory, import_name + ".py")
        if os.path.exists(target_path):
            return target_path

        return None

    def function_exists(self, func_name: str):
        return self._graph.has_function(func_name)
