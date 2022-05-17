source ../../env/bin/activate


if python3 ../../main.py ../projects/complex/main.py --target test; then
	echo "Found test succesfully"
else
	echo "Should've detected test"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py --target other; then
	echo "Found other succesfully"
else
	echo "Should've detected other"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py --target cos; then
	echo "Found cos succesfully"
else
	echo "Should've detected cos"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py --target sin; then
	echo "Found sin succesfully (ambiguous)"
else
	echo "Should've detected sin"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py --target __init__; then
	echo "Found __init__ succesfully"
else
	echo "Did not detect __init__"
	exit 1
fi

echo "PASS"
exit 0
