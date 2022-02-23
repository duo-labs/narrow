import ast
import copy


class FunctionDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self._funcs = {}

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name not in self._funcs:
            self._funcs[node.name] = copy.deepcopy(node)

    def get_functions(self):
        return self._funcs


class ClassDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self.initalizer = None

    def visit_ClassDef(self, node: ast.ClassDef):
        func_visitor = FunctionDefVisitor()
        func_visitor.visit(node)

        funcs = func_visitor.get_functions()

        if '__init__' in funcs:
            self.initalizer = copy.deepcopy(funcs['__init__'])

    def get_initalizer(self):
        return self.initalizer


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self._imports = {}

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name not in self._imports:
                self._imports[alias.name] = copy.deepcopy(alias)

    def get_imports(self):
        return self._imports
