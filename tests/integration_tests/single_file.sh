source ../../env/bin/activate


if python3 ../../main.py ../projects/single_file/main.py bar; then
	echo "Found bar succesfully"
else
	echo "Should've detected bar"
	exit 1
fi

if python3 ../../main.py ../projects/single_file/main.py other; then
	echo "Found other succesfully"
else
	echo "Should've detected other"
	exit 1
fi

if python3 ../../main.py ../projects/single_file/main.py print; then
	echo "Found print succesfully"
else
	echo "Should've detected print"
	exit 1
fi

if python3 ../../main.py ../projects/single_file/main.py notused; then
	echo "Found notused incorrectly"
	exit 1
else
	echo "Correctly did not detect notused"
fi

echo "PASS"
exit 0
