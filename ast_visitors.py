class TreeSitterFunctionDefVisitor():
    def __init__(self):
        self._funcs = []

    def visit(self, node):
        current_node = node

        if current_node.type == 'function_definition':
            func_name = current_node.child_by_field_name(
                'name').text.decode('utf-8')
            if func_name not in self._funcs:
                self._funcs.append({
                    "node": node,
                    "name": func_name
                })
        else:
            if current_node.children:
                for child in current_node.children:
                    self.visit(child)

    def get_functions(self):
        return self._funcs


class TreeSitterClassDefVisitor():
    def __init__(self):
        self.initalizers = []

    def visit(self, node):
        current_node = node

        if current_node.type == 'class_definition':
            func_visitor = TreeSitterFunctionDefVisitor()
            func_visitor.visit(current_node)
            funcs = func_visitor.get_functions()
            for func in funcs:
                if '__init__' == func["name"]:
                    self.initalizers.append({
                        "node": func['node'],
                        "class": current_node.child_by_field_name('name').text.decode('utf-8')
                    })
        else:
            if current_node.children:
                for child in current_node.children:
                    self.visit(child)

    def get_initalizer(self):
        return self.initalizers


class TreeSitterImportVisitor():
    def __init__(self):
        self._imports = {}

    def visit(self, node, allow_recursion=True):
        current_node = node

        if current_node.type == 'import_from_statement':
            module_name = current_node.child_by_field_name(
                'module_name').text.decode('utf-8')
            alias_name = current_node.child_by_field_name('name')
            level = 0
            if module_name.startswith('.'):
                module_name = module_name[1:]
                level = 1
            if alias_name:
                alias_name = alias_name.text.decode('utf-8')
                full_key = module_name + '.' + alias_name
                if full_key not in self._imports:
                    self._imports[full_key] = {
                        'module': module_name,
                        'name': alias_name,
                        'node': current_node.child_by_field_name('name'),
                        'level': level
                    }

        elif current_node.type == 'import_statement':
            alias_name = current_node.child_by_field_name(
                'name').text.decode('utf-8')
            if alias_name not in self._imports:
                self._imports[alias_name] = {
                    'module': '',
                    'name': alias_name,
                    'node': current_node,
                    'level': None
                }
        elif allow_recursion:
            if current_node.children:
                for child in current_node.children:
                    self.visit(child)

    def get_imports(self):
        return self._imports
