source ../../env/bin/activate

cd ../projects/requests_case

./install.sh

cd ../../integration_tests


if python3 ../../main.py ../projects/requests_case/vulnerable.py --input-file ../projects/requests_case/krefst_output.json; then
	echo "Run okay"
else
	echo "Threw non-zero exit code but should not"
	exit 1
fi

if grep -q "7.2" narrow_output.json; then
	echo "Resulting file contained correct CVSS"
else
	echo "Resulting file contained incorrect CVSS."
	exit 1
fi

if grep -q "4.1" narrow_output.json; then
	echo "Resulting file contained incorrect CVSS. Should have been reduced"
	exit 1
else
	echo "Resulting file contained correct CVSS"

fi


echo "PASS"
exit 0
