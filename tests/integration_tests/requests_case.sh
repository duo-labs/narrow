source ../../env/bin/activate

cd ../projects/requests_case

./install.sh

cd ../../integration_tests

if python3 ../../main.py ../projects/requests_case/vulnerable.py --osv-id GHSA-x84v-xcm2-53pg; then
	echo "Found rebuild_auth succesfully"
else
	echo "Should've detected rebuild_auth"
	exit 1
fi

if python3 ../../main.py ../projects/requests_case/vulnerable.py --input-file ../projects/requests_case/sca_output.json; then
	echo "Run okay"
else
	echo "Threw non-zero exit code but should not"
	exit 1
fi

if grep -q "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N" narrow_output.json; then
	echo "Resulting file contained correct CVSS"
else
	echo "Resulting file contained incorrect CVSS"
	exit 1
fi

if grep -q "\"CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N\"" narrow_output.json; then
	echo "Resulting file contained incorrect CVSS in octoprint"
	exit 1
else
	echo "Resulting file contained correct CVSS in octoprint"
fi

echo "PASS"
exit 0
