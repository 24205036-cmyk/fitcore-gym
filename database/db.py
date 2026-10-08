import os
import logging
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import Config

logger = logging.getLogger(__name__)

_mongo_client = None
_db_instance = None
_using_mock = False

def init_db(app=None):
    """
    Initializes and returns the MongoDB database connection.
    Gracefully falls back to mongomock if no live MongoDB daemon is running,
    ensuring 100% crash-free execution in academic or demo environments.
    """
    global _mongo_client, _db_instance, _using_mock
    
    if _db_instance is not None:
        return _db_instance

    uri = Config.MONGO_URI
    db_name = Config.DATABASE_NAME
    
    try:
        # Attempt connection with a short timeout to check availability
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        # Force a call to verify the connection is alive
        client.admin.command('ping')
        _mongo_client = client
        _db_instance = client[db_name]
        _using_mock = False
        logger.info(f"Connected to live MongoDB at {uri} -> database: {db_name}")
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
        logger.warning(
            f"Could not connect to live MongoDB server ({e}). "
            "Falling back to mongomock for safe local development/demo mode."
        )
        try:
            import mongomock
            mock_client = mongomock.MongoClient()
            _mongo_client = mock_client
            _db_instance = mock_client[db_name]
            _using_mock = True
            logger.info("Using mongomock in-memory database successfully.")
        except Exception as mock_err:
            logger.error(f"Failed to initialize mongomock: {mock_err}")
            raise e

    # Create indexes
    _create_indexes(_db_instance)
    return _db_instance

def get_db():
    """Returns the current database instance."""
    global _db_instance
    if _db_instance is None:
        return init_db()
    return _db_instance

def is_mock_db():
    """Returns True if the database is running via mongomock."""
    return _using_mock

def _create_indexes(db):
    """Creates required indexes for collections."""
    try:
        # members indexes
        db.members.create_index([("member_id", ASCENDING)], unique=True)
        db.members.create_index([("phone", ASCENDING)])
        db.members.create_index([("email", ASCENDING)])
        db.members.create_index([("status", ASCENDING)])
        
        # trainers indexes
        db.trainers.create_index([("trainer_id", ASCENDING)], unique=True)
        
        # membership_plans indexes
        db.membership_plans.create_index([("name", ASCENDING)])
        
        # attendance indexes
        db.attendance.create_index([("member_id", ASCENDING)])
        db.attendance.create_index([("status", ASCENDING)])
        db.attendance.create_index([("check_in", ASCENDING)])
        
        # payments indexes
        db.payments.create_index([("payment_id", ASCENDING)], unique=True)
        db.payments.create_index([("member_id", ASCENDING)])
        db.payments.create_index([("payment_date", ASCENDING)])
        
        logger.info("Database indexes ensured successfully.")
    except Exception as e:
        logger.warning(f"Note on index creation: {e}")
