import typing
import networkx


class InternalGraphRepesentation:
    def __init__(self):
        self._graph = {
            '__narrow_entry__': {
                'next': set()
            }
        }

    def _get_subgraph_for(self, key):
        subgraph = {}
        for val in self._graph[key]['next']:
            subgraph[val] = self._get_subgraph_for(val)

        return subgraph

    def get_expanded_graph(self):
        resolved_graph = self._get_subgraph_for('__narrow_entry__')

        return resolved_graph

    def get_networkx_digraph(self):
        graph = networkx.DiGraph()

        for key in self._graph.keys():
            graph.add_node(key, label=key)

        for key in self._graph.keys():
            for child in self._graph[key]['next']:
                graph.add_edge(key, child)

        return graph

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
    def add_node_to_graph(self, context: typing.List[str], next_node: str,
                          type: str = 'unknown'):
        if len(context) == 0:
            raise ValueError("context should never be empty. \
            Use __narrow_entry__ for the root node")

        caller = context[-1]

        if caller not in self._graph:
            raise ValueError("The caller should already exist in the graph")

        resolved_node = type + '.' + next_node

        self._graph[caller]['next'].add(resolved_node)

        if resolved_node not in self._graph:
            self._graph[resolved_node] = {
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

    def remove_class(function_name: str):
        if len(function_name.split('.')) == 2:
            return function_name.split('.')[1]

        return function_name

    # Checks whether a function exists. If strict is False,
    # ignores the Class.
    def has_function(self, function_name: str, strict: bool = False):
        if strict and function_name in self._graph:
            return True

        if not strict:
            keys = self._graph.keys()
            keys = map(lambda key: InternalGraphRepesentation.remove_class(key), keys)

            if function_name in keys:
                return True

        return False
