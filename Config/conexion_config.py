from dotenv import load_dotenv
import os

load_dotenv()

CONFIG_SQL = {
    "user": os.getenv("SQL_USER"),
    "password": os.getenv("SQL_PASS"),
    "server": os.getenv("SQL_SERVER"),
    "database": os.getenv("SQL_DB"),
}

CONFIG_HANA = {
    "host": os.getenv("HANA_HOST"),
    "port": os.getenv("HANA_PORT"),
    "dsn": os.getenv("HANA_DSN"),
    "user": os.getenv("HANA_USER"),
    "password": os.getenv("HANA_PASS"),
    "schema" : os.getenv("HANA_SCHEMA"),
}
