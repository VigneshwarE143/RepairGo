import os

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is required")

client = MongoClient(MONGO_URI)

# Create / Use database
db = client["repairgo"]

# Collections
users_collection = db["users"]
technicians_collection = db["technicians"]
services_collection = db["services"]
feedback_collection = db["feedback"]
notifications_collection = db["notifications"]
categories_collection = db["categories"]
fraud_flags_collection = db["fraud_flags"]
ml_models_collection = db["ml_models"]  # ML model versioning and metrics
payments_collection = db["payments"]  # Payment transactions

# Create unique indexes
try:
    users_collection.create_index("email", unique=True)
    technicians_collection.create_index("email", unique=True)
    services_collection.create_index("service_id", unique=True, sparse=True)
    fraud_flags_collection.create_index("entity_id", unique=True, sparse=True)
except Exception as e:
    print(f"Index creation warning: {e}")

print("MongoDB Connected Successfully ✅")
