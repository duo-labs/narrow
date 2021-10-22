import ast
import typing
import copy

class ControlFlowGraph:
    def __init__(self):
        self._graph = {}

    # Function responsible for constructing a CFG given an entry file.
    #   only_file: If True, only builds a CFG contained in a single file.
    #              External references are noted as such but not resolved.
    def construct_from_file(self, file_path: str, only_file=False):
        with open(file_path, mode='r') as source_content:
            syntax_tree: ast.Module = ast.parse(source_content.read(), file_path)

            self._parse_and_resolve(syntax_tree, [])

            print(self._graph)

    def _parse_and_resolve(self, ast_chunk: ast.AST,
                           context: typing.List[str]):
        if isinstance(ast_chunk, ast.Call):
            if not self._in_graph(ast_chunk.func.attr, context):
                self._add_node_to_graph(ast_chunk.func.attr, context)
                # TODO recurse

        # More work?
        if hasattr(ast_chunk, 'body'):
            for child in ast_chunk.body:
                self._parse_and_resolve(child, context)
        elif hasattr(ast_chunk, 'value'):
            self._parse_and_resolve(ast_chunk.value, context)



    # Check if we're already reached next_node_name
    def _in_graph(self, next_node_name: str, context: typing.List[str]):
        current = copy.deepcopy(self._graph)
        for node in context:
            current = current[node]

        if next_node_name in current:
            return True

        return False

    def _add_node_to_graph(self, next_node_name: str,
                           context: typing.List[str]):
        current = self._graph  # Get a reference
        for node in context:
            current = current[node]

        current[next_node_name] = {}
