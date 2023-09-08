#!/bin/bash

mysql < schema.sql
mysql < room_schema.sql
pytest tests/test_user.py -v
pytest tests/test_room.py -v