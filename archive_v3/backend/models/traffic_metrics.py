from pymongo import MongoClient
import os

# Load MongoDB URI from environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/vanet_db")

# Initialize MongoDB client (optional - will fail gracefully if not available)
client = None
db = None
traffic_metrics_collection = None

try:
    # Try to connect to MongoDB
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)  # 5 second timeout
    # Test the connection
    client.admin.command('ping')
    db = client.get_database()
    traffic_metrics_collection = db["traffic_metrics"]
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"⚠️  MongoDB not available: {e}")
    print("   Backend will run without database storage")
    client = None
    db = None
    traffic_metrics_collection = None

# In-memory storage as fallback
_in_memory_metrics = []

# Example function to insert traffic metrics
def insert_traffic_metrics(data):
    """Insert traffic metrics into the database or in-memory storage."""
    if traffic_metrics_collection:
        try:
            traffic_metrics_collection.insert_one(data)
            return True
        except Exception as e:
            print(f"❌ MongoDB insert failed: {e}")
            # Fall back to in-memory storage
            _in_memory_metrics.append(data)
            return False
    else:
        # Store in memory if MongoDB not available
        _in_memory_metrics.append(data)
        return False

# Example function to fetch traffic metrics
def get_traffic_metrics():
    """Fetch all traffic metrics from the database or in-memory storage."""
    if traffic_metrics_collection:
        try:
            return list(traffic_metrics_collection.find())
        except Exception as e:
            print(f"❌ MongoDB fetch failed: {e}")
            return _in_memory_metrics
    else:
        # Return in-memory metrics if MongoDB not available
        return _in_memory_metrics

def is_mongodb_available():
    """Check if MongoDB is available and connected."""
    return traffic_metrics_collection is not None