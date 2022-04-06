# Example program based on yaml 3.12 which is vulnerable to RCE
# when calling full_load on arbitrary data.
#
# set_python_instance_state is one function related to the fix:
#   https://github.com/yaml/pyyaml/commit/5080ba513377b6355a0502104846ee804656f1e0

import yaml
import pathlib


with open((pathlib.Path(__file__).parent.resolve() / "arbitrary_data.yml").as_posix(), 'r') as arb:
    result = yaml.full_load(arb)
    print(result)
