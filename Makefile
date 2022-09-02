run:
	uvicorn app.api:app --reload --port 8080

format:
	isort app tests
	black app tests

test:
	pytest -sv tests
