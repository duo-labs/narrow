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
