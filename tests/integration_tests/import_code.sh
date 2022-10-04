source ../../env/bin/activate

if python3 ../../main.py ../projects/import_code/main.py --target print; then
	echo "Found print succesfully"
else
	echo "Should've detected print"
	exit 1
fi

if python3 ../../main.py ../projects/import_code/main.py --target very_unique_function; then
	echo "Found very_unique_function succesfully"
else
	echo "Should've detected very_unique_function"
	exit 1
fi

if python3 ../../main.py ../projects/import_code/main.py --target implict_and_unique; then
	echo "Found implict_and_unique succesfully"
else
	echo "Should've detected implict_and_unique"
	exit 1
fi


echo "PASS"
exit 0
