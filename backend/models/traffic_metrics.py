from pymongo import MongoClient
import os

# Load MongoDB URI from environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/vanet_db")

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client.get_database()

# Define collection for traffic metrics
traffic_metrics_collection = db["traffic_metrics"]

# Example function to insert traffic metrics
def insert_traffic_metrics(data):
    """Insert traffic metrics into the database."""
    traffic_metrics_collection.insert_one(data)

# Example function to fetch traffic metrics
def get_traffic_metrics():
    """Fetch all traffic metrics from the database."""
    return list(traffic_metrics_collection.find())