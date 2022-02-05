import argparse
import cfg

parser = argparse.ArgumentParser(description='Generates Control Flow Graph for given code')
parser.add_argument('file', help ='the starting file')
parser.add_argument('function', help = 'the function to locate')
parser.add_argument('--print_cfg', help = 'indicate whether you want to display a CFG after running.', default=False, required=False)

args = parser.parse_args()

graph = cfg.ControlFlowGraph(args.function)
graph.construct_from_file(args.file, True)

if args.print_cfg:
    graph.print_graph_matplotlib()

detect_status = graph.did_detect()
if detect_status == False:
    exit(1)
