# narrow
This project investigates ways to automatically determine (in some cases) whether a known vulnerability in some dependency affects a targeted first-party codebase. It does this by combining two things: 1) Patch Extraction and 2) Static Program Analysis.

Specifically, this repo implements a python-based command-line tool that can be used to do one of the following:

1. Determine whether user-provided "target functions" are reachable by some codebase.
1. Determine whether a user-provided vulnerability (CVE or OSV-conformant vulnerability identifier) might be reachable by some codebase.
1. Extend the result of some CycloneDX + VEX scan (e.g. one produced using `pip-audit`) to include additional metadata regarding whether each vulnerability might be reachable by some codebase.

## Usage

### Pre-requisites

Narrow currently is known to work on Python 3.9.

*Note: Python 3.10 is explicitly not supported.*

### Get the source

narrow makes use of git submodules. As such, the proper way to get a copy of the source is to run:

`git clone --recurse-submodules https://github.com/duo-labs/narrow.git`


### Installation
To create a virtual environment and install dependencies for narrow, run: 

```make build```

You can then "activate" that environment by running: `source env/bin/activate`.

### Function Finder Mode
To determine whether a function can be reached by a codebase use:

```
python3 main.py <path/to/some/codebase/entrypoint.py> --target <function_name>
```

Example: `python3 main.py main.py --target construct_from_file`

### Vulnerability Finder Mode
To determine whether vulnerability might be reachable by a codebase use:

```
python3 main.py <path/to/some/codebase/entrypoint.py> --osv-id <some_osv_id>
```

Example: `python3 main.py main.py --osv-id CVE-2018-18074`

### CycloneDX Mode
This mode takes the result of some software composition analysis tool (e.g. `pip-audit`) and
"narrow" it so that it includes predictions of whether the vulnerabilities are reachable.

It does this by outputing CycloneDX JSON data with the following field set to `not_affected`: https://cyclonedx.org/docs/1.4/json/#vulnerabilities_items_analysis_state

use:
```
python3 main.py <path/to/some/codebase/entrypoint.py> --input-file <path/to/cyclonedx.json>
```

Example: 
```
# Run SCA tool in CycloneDX form:
pip-audit -r requirements.lock -s osv -l -f json -o audit.json  || true
python3 main.py main.py --input-file audit.json
# Show result (CycloneDX data now with `analysis.state` populated if not reachable)
cat narrow_output.json
```

## Design

The high-level logic is described below:

**Input**: Some first-party codebase. Some metadata about a vulnerability in a dependency used by the first-party codebase. At minimum this data needs to provide a link to some patch / diff / pull request.

**Output**: A code path that takes you from first party code to some line that will be fixed by applying a patch to the dependency, if possible to find. If found, this gives you high assurance that you are affected by this vulnerability. If a code path is not found, returns "No path"

**Algorithm**:

1. Path Extraction
    1. Automatically follow the link to a patch that fixes the vulnerability
    1. Look at all functions changed by patch and extract these.
        1. Core insight is this: Assuming the patch actually fixes the vulnerability, your first-party code can not be vulnerable unless at least some of the changed code in the dependency can be reached by your first-party code.
1. Static Program Analysis
    1. Now look at the first-code and generate a control flow graph showing all reachable code paths starting at your program's entry point.
    1. Match nodes in the control flow graph to one of the modified functions in the vulnerable dependency. If you can find a matching reachable node, return the code path.
    1. If a code path is not found, return "No Path"

For now this project only tries to support detection on Python-based third-party code.

## Communication
If you have questions or suggestions, please use the GitHub issue tracker.

For security issues, refer to SECURITY.md.