set -e

./multi_file.sh
./single_file.sh
./complex.sh
./recursive.sh
./simple.sh
# ./requests_case.sh  TODO: Re-enable one day
# ./pyyaml_case.sh  TODO: Re-enable one day
./with.sh
./ambiguous_module.sh
./function_in_object.sh
./import_code.sh
