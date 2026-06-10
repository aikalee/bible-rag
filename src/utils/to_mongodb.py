from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import json
import os


def launch_collection():

    load_dotenv()

    mongo_user = os.getenv("MONGO_USER")
    mongo_pass = os.getenv("MONGO_PASS")

    db_name = "bible"
    collection_name = "commentary"

    uri = f"mongodb+srv://{mongo_user}:{mongo_pass}@bible-rag-prod.w3pskcn.mongodb.net/?retryWrites=true&w=majority&appName=bible-rag-prod"

    client = MongoClient(uri, server_api=ServerApi('1'))

    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

    db = client[db_name]
    collection = db[collection_name]

    return collection


def add_one(collection, doc):

    try:
        collection.insert_one(doc)
        print("Inserted 1 document.")

    except Exception as e:
        print(f"Insert error: {e}")


def add_many(collection, docs):
    if not docs:
        print("No documents to insert.")
        return
    
    try:
        collection.insert_many(docs)
        print(f"Inserted {len(docs)} documents.")

    except Exception as e:
        print(f"Insert error: {e}")


def add_documents(collection, data):

    if isinstance(data, list):

        add_many(collection, data)

    elif isinstance(data, dict):

        add_one(collection, data)

    else:
        print("Unsupported data type.")

def create_index(collection):

    collection.create_index([("metadata.doc_id", 1)], unique=True)

def main():

    with open("../../data/commentary.json", encoding="utf-8") as f:
        commentary = json.load(f)
    
    collection = launch_collection()
    create_index(collection)

    # add_documents(collection, commentary)

if __name__ == "__main__":
    main()

