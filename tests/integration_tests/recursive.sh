source ../../env/bin/activate


if python3 ../../main.py ../projects/recursive/main.py --target recurse; then
	echo "Found recurse succesfully"
else
	echo "Should've detected recurse"
	exit 1
fi

if python3 ../../main.py ../projects/recursive/main.py --target tail; then
	echo "Found tail succesfully"
else
	echo "Should've detected tail"
	exit 1
fi

echo "PASS"
exit 0
