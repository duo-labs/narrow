source ../../env/bin/activate

cd ../projects/pyyaml_case

./install.sh

cd ../../integration_tests

if python3 ../../main.py ../projects/pyyaml_case/vulnerable.py --target set_python_instance_state; then
	echo "Found set_python_instance_state succesfully"
else
	echo "Should've detected set_python_instance_state"
	exit 1
fi

if python3 ../../main.py ../projects/pyyaml_case/not_vulnerable.py --target set_python_instance_state; then
	echo "Found set_python_instance_state incorrectly"
	exit 1
else
	echo "Should've detected tail"
	exit 0
fi

echo "PASS"
exit 0
