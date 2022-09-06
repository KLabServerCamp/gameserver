run:
	uvicorn app.api:app --reload

format:
	isort app tests
	black app tests

test:
	pytest -sv tests

show_db:
	mysql webapp \
		" \
		select * from user; \
		select * from room; \
		select * from room_member; \
		"
