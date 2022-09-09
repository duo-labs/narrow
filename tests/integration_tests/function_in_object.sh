source ../../env/bin/activate


if python3 ../../main.py ../projects/function_in_object/main.py --target print; then
	echo "Found print succesfully"
else
	echo "Should've detected print"
	exit 1
fi

if python3 ../../main.py ../projects/function_in_object/main.py --target exit; then
	echo "Found exit succesfully"
else
	echo "Should've detected exit"
	exit 1
fi