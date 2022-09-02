PHONY: run
run:
	uvicorn app.api:app --reload

PHONY: format
format:
	isort app tests
	black app tests

PHONY: lint
lint:
	flake8 app tests
	mypy app tests

PHONY: test
test:
	pytest -sv tests
