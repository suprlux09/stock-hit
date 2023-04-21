import os
import threading
import psycopg2
from dotenv import load_dotenv


load_dotenv()
host = os.getenv("DB_HOST")
dbname = os.getenv("DB_NAME")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWD")
port = os.getenv("DB_PORT")
db = psycopg2.connect(host=host, dbname=dbname, user=user, password=password, port=port)
lock = threading.Lock()
