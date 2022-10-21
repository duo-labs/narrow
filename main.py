import argparse
import json
import cfg
from narrower import Narrower
import patch_extractor

parser = argparse.ArgumentParser(
    description='Generates Control Flow Graph for given code')
parser.add_argument('file', help='the starting file')

parser.add_argument('--osv-id', help='Vulnerability ID from OSV to use to find targets',
                    required=False)

parser.add_argument('--target', help='the function to locate',
                    required=False)
parser.add_argument(
    '--print-cfg',
    help='indicate whether you want to display a CFG after running.',
    default=False, required=False)

parser.add_argument(
    '--max-print-depth',
    help='indicate how many levels of the CFG you want to print.',
    default=None, required=False)

parser.add_argument(
    '--print-all-paths',
    help='If set to true, shows all paths from the entrypoint, not only paths to the target.',
    default=False, required=False)

parser.add_argument(
    '--module-backtracking',
    help='indicates far back in the filesystem you want to support searching for modules.',
    default=2, required=False)

parser.add_argument(
    '--input-file',
    help='path to the output of an SCA scanner that we want to narrow',
    default=None, required=False)

args = parser.parse_args()
targets = []

if args.target:
    targets.append(args.target)

if args.osv_id:
    extractor = patch_extractor.PatchExtractor()
    targets += extractor.find_targets_in_osv_entry(args.osv_id)

input_file = args.input_file

if input_file:
    with open(input_file, 'r') as fp:
        narrower_ctrlr = Narrower(fp, args.module_backtracking, args.file)
        new_output = narrower_ctrlr.generate_output()
        with open('narrow_output.json', 'w') as narrow_fp:
            narrow_fp.write(json.dumps(new_output))
else:
    if len(targets) > 1:
        print("Multiple targets detected. We will try only the first one: " +
            targets[0])

    if len(targets) == 0:
        print("No targets detected. Exiting.")
        exit(1)

    graph = cfg.ControlFlowGraph(targets[0], args.module_backtracking)
    graph.construct_from_file(args.file, False)

    if args.print_cfg:
        depth = None
        if args.max_print_depth:
            depth = int(args.max_print_depth)
        graph.print_graph_matplotlib(depth, args.print_all_paths)

    detect_status = graph.did_detect()
    if detect_status is False:
        exit(1)

