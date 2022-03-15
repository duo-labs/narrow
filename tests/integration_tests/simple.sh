source ../../env/bin/activate

cd ../projects/simple

./install.sh

cd ../../integration_tests

if python3 ../../main.py ../projects/simple/main.py _checkRequirements; then
	echo "Found _checkRequirements succesfully"
else
	echo "Should've detected _checkRequirements"
	exit 1
fi

if python3 ../../main.py ../projects/simple/main.py getattr; then
	echo "Found getattr succesfully"
else
	echo "Should've detected getattr"
	exit 1
fi

if python3 ../../main.py ../projects/simple/main.py isLinux; then
	echo "Found isLinux succesfully"
else
	echo "Should've detected isLinux"
	exit 1
fi

echo "PASS"
exit 0
