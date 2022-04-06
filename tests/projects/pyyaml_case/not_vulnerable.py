# Example program based on yaml 3.12 which is NOT vulnerable to RCE
# when calling full_load on arbitrary data.
#
# This calls safe_load which is supposedly not affected by the vuln

import yaml
import pathlib


with open((pathlib.Path(__file__).parent.resolve() / "arbitrary_data.yml").as_posix(), 'r') as arb:
    result = yaml.safe_load(arb)
    print(result)
