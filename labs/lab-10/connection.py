import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def get_client():
    uri = os.getenv("MONGO_URI", "mongodb://host.docker.internal:27017/?directConnection=true")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        hello = client.admin.command("hello")
        if "setName" in hello:
            rs_uri = os.getenv("MONGO_RS_URI")
            if rs_uri:
                client.close()
                client = MongoClient(rs_uri, serverSelectionTimeoutMS=5000)
    except PyMongoError:
        pass
    return client

def get_db(client=None):
    if client is None:
        client = get_client()
    db_name = os.getenv("DB_NAME", "nosql_lab10_transactions")
    return client[db_name]