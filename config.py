import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE = os.path.join(BASE_DIR, "database", "game.db")

SECRET_KEY = "CHANGE_THIS_SECRET_KEY"