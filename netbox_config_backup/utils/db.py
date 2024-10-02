from django import db


def close_db():
    db.connections.close_all()
