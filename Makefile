run:
	uvicorn app.api:app --reload

format:
	isort app tests
	black app tests

test:
	pytest -sv tests

db_init:
	mysql webapp < schema.sql