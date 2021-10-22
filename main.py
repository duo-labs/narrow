import sys

import cfg

starting_file = sys.argv[1]
function_to_locate = sys.argv[2]

graph = cfg.ControlFlowGraph()
graph.construct_from_file(starting_file, True)
