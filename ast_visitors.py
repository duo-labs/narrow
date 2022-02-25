import ast
import copy


class FunctionDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self._funcs = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name not in self._funcs:
            self._funcs.append({
                "node": copy.deepcopy(node),
                "name": node.name
            })

    def get_functions(self):
        return self._funcs


class ClassDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self.initalizers = []

    def visit_ClassDef(self, node: ast.ClassDef):
        func_visitor = FunctionDefVisitor()
        func_visitor.visit(node)

        funcs = func_visitor.get_functions()

        for func in funcs:
            if '__init__' == func["name"]:
                self.initalizers.append({
                    "node": copy.deepcopy(func['node']),
                    "class": node.name
                })

    def get_initalizer(self):
        return self.initalizers


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self._imports = {}

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name not in self._imports:
                self._imports[alias.name] = copy.deepcopy(alias)

    def get_imports(self):
        return self._imports
