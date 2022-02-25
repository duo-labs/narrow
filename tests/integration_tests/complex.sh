source ../../env/bin/activate


if python3 ../../main.py ../projects/complex/main.py test; then
	echo "Found test succesfully"
else
	echo "Should've detected test"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py other; then
	echo "Found other succesfully"
else
	echo "Should've detected other"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py cos; then
	echo "Found cos succesfully"
else
	echo "Should've detected cos"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py sin; then
	echo "Found sin succesfully (ambiguous)"
else
	echo "Should've detected sin"
	exit 1
fi

if python3 ../../main.py ../projects/complex/main.py __init__; then
	echo "Found __init__ succesfully"
else
	echo "Did not detect __init__"
	exit 1
fi

echo "PASS"
exit 0
