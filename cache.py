import ast
import typing


class Cache:
    def __init__(self):
        self.function_defs = {}

    def store_function_defs(self, start_file: str,
                            start_ast_node: ast.AST,
                            result: typing.Any):
        self.function_defs[start_file] = {}
        self.function_defs[start_file][str(start_ast_node)] = result

    def get_function_defs(self, start_file: str,
                          start_ast_node: ast.AST) -> \
            typing.Tuple[typing.Any, typing.Any]:

        if start_file not in self.function_defs:
            return (None, None)

        if str(start_ast_node) not in \
           self.function_defs[start_file]:
            return (None, None)

        return self.function_defs[start_file][str(start_ast_node)]
