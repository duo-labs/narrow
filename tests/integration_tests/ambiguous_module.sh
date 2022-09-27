source ../../env/bin/activate

if python3 ../../main.py ../projects/ambiguous_module/src/main.py --target print; then
	echo "Found print succesfully"
else
	echo "Should've detected print"
	exit 1
fi


echo "PASS"
exit 0
