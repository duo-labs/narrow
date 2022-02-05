source ../../env/bin/activate


if python3 ../../main.py ../projects/multi_file/main.py bar; then
	echo "Found bar succesfully"
else
	echo "Should've detected bar"
	exit 1
fi

if python3 ../../main.py ../projects/multi_file/main.py foobar; then
	echo "Found foobar succesfully"
else
	echo "Should've detected foobar"
	exit 1
fi

if python3 ../../main.py ../projects/multi_file/main.py acos; then
	echo "Found acos succesfully"
else
	echo "Should've detected acos"
	exit 1
fi

if python3 ../../main.py ../projects/multi_file/main.py nothere; then
	echo "Found nothere, but should not have."
	exit 1
else
	echo "Did not detect nothere"
fi

echo "PASS"
exit 0
