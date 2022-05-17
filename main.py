import argparse
import cfg
import patch_extractor

parser = argparse.ArgumentParser(
    description='Generates Control Flow Graph for given code')
parser.add_argument('file', help='the starting file')
parser.add_argument('--cve', help='cve ID to use to find targets',
                    required=False)
parser.add_argument('--target', help='the function to locate',
                    required=False)
parser.add_argument(
    '--print-cfg',
    help='indicate whether you want to display a CFG after running.',
    default=False, required=False)

args = parser.parse_args()
targets = []

if args.target:
    targets.append(args.target)

if args.cve:
    extractor = patch_extractor.PatchExtractor()
    targets += extractor.find_targets_in_ndv_entry(args.cve)

if len(targets) > 1:
    print("Multiple targets detected. We will try only the first one: " +
          targets[0])

graph = cfg.ControlFlowGraph(targets[0])
graph.construct_from_file(args.file, True)

if args.print_cfg:
    graph.print_graph_matplotlib()

detect_status = graph.did_detect()
if detect_status is False:
    exit(1)
