import sys

import cfg

starting_file = sys.argv[1]
function_to_locate = sys.argv[2]

graph = cfg.ControlFlowGraph(function_to_locate)
graph.construct_from_file(starting_file, True)

some_variable = graph.did_detect()
if some_variable == False:
    exit(1)

