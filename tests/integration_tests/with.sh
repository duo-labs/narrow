source ../../env/bin/activate

if python3 ../../main.py ../projects/with/main.py other; then
	echo "Found other succesfully"
else
	echo "Should've detected other"
	exit 1
fi


echo "PASS"
exit 0
