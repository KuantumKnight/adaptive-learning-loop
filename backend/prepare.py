"""Explicit database preparation command for deployment and local setup."""

from app.db import init_db


if __name__ == "__main__":
    init_db()
    print("Database schema, lessons, and personalization history are ready")
