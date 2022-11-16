source ../../env/bin/activate

if python3 ../../main.py ../projects/arg_count/main.py --target print; then
	echo "Found print incorrectly"
    exit 1
else
	echo "Did not find print correctly"
fi

if python3 ../../main.py ../projects/arg_count/main.py --target target_call; then
	echo "Found target_function succesfully"
else
	echo "Should've detected target_call"
	exit 1
fi

if python3 ../../main.py ../projects/arg_count/main.py --target another_target; then
	echo "Found another_target succesfully"
else
	echo "Should've detected another_target"
	exit 1
fi

echo "PASS"
exit 0
