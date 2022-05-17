build:
	python3 -m venv env
	. env/bin/activate && python3 -m pip install -r requirements.txt

integrationTests:
	. env/bin/activate && cd tests/integration_tests && ./run_all.sh

unitTests:
	. env/bin/activate && python3 -m pytest tests/unit/*.py

lint:
	. env/bin/activate && python3 -m pip install -r requirements-dev.txt
	. env/bin/activate && flake8 *.py
	. env/bin/activate && mypy *.py

clean:
	rm -rf env


.PHONY: clean integrationTests unitTests lint build
