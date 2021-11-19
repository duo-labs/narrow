import ast
import typing
import copy


class FunctionDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self._funcs = {}

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name not in self._funcs:
            self._funcs[node.name] = copy.deepcopy(node)

    def get_functions(self):
        return self._funcs


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


class ControlFlowGraph:
    def __init__(self):
        self._graph = InternalGraphRepesentation()
        self._root_tree = None

    # Function responsible for constructing a CFG given an entry file.
    #   only_file: If True, only builds a CFG contained in a single file.
    #              External references are noted as such but not resolved.
    def construct_from_file(self, file_path: str, only_file=False):
        with open(file_path, mode='r') as source_content:
            syntax_tree: ast.Module = ast.parse(source_content.read(), file_path)
            self._root_tree = copy.deepcopy(syntax_tree)

            self._parse_and_resolve(syntax_tree, ['__narrow_entry__'])

            print(self._graph)

    def _parse_and_resolve(self, ast_chunk: ast.AST,
                           context: typing.List[str]):
        if isinstance(ast_chunk, ast.Call):
            func_name = None
            if isinstance(ast_chunk.func, ast.Name):
                func_name = ast_chunk.func.id
            else:
                func_name = ast_chunk.func.attr

            self._graph.add_node_to_graph(context, func_name)
            call_def = self._find_function_def_node(func_name)
            if call_def:
                self._parse_and_resolve(call_def,
                                        context + [func_name])

        # More work?
        if hasattr(ast_chunk, 'body'):
            for child in ast_chunk.body:
                self._parse_and_resolve(child, context)
        elif hasattr(ast_chunk, 'value'):
            self._parse_and_resolve(ast_chunk.value, context)

    # Find a Function Definition node and return it, if possible
    def _find_function_def_node(self, func_name: str):
        starting_ast = self._root_tree

        func_visitor = FunctionDefVisitor()
        func_visitor.visit(starting_ast)

        funcs = func_visitor.get_functions()
        if func_name in funcs:
            return funcs[func_name]

        return None
