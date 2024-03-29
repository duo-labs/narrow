source ../../env/bin/activate

cd ../projects/requests_case

./install.sh

cd ../../integration_tests

if python3 ../../main.py ../projects/requests_case/not_vulnerable.py --osv-id CVE-2018-18074; then
	echo "Found rebuild_auth incorrectly"
	exit 1
else
	echo "Succesfully did not find rebuild_auth"
	exit 0
fi

echo "PASS"
exit 0
