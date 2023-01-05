from sqlalchemy import create_engine

import app.config as config

engine = create_engine(config.DATABASE_URI, future=True, echo=True)
