import os
import logging
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import Config

logger = logging.getLogger(__name__)

_mongo_client = None
_db_instance = None

LOCAL_DB_FILE = os.path.join(os.path.dirname(__file__), 'local_db.json')

def is_mock_db():
    """Returns True if database is using in-memory mongomock fallback."""
    global _mongo_client
    if _mongo_client is None:
        return False
    mod = getattr(type(_mongo_client), '__module__', '')
    return 'mongomock' in mod or 'mongomock' in str(type(_mongo_client))

def save_mock_db():
    """Saves all collections from mongomock to a persistent JSON file."""
    global _db_instance
    if _db_instance is None or not is_mock_db():
        return
    try:
        import bson.json_util as json_util
        data = {}
        for col_name in _db_instance.list_collection_names():
            docs = list(_db_instance[col_name].find({}))
            data[col_name] = docs
        with open(LOCAL_DB_FILE, 'w', encoding='utf-8') as f:
            f.write(json_util.dumps(data, indent=2))
        logger.info(f"Saved local database state ({len(data)} collections) to disk.")
    except Exception as e:
        logger.warning(f"Could not persist local database: {e}")

def load_mock_db(db):
    """Loads all collections from the persistent JSON file into the mongomock instance."""
    if not os.path.exists(LOCAL_DB_FILE):
        return False
    try:
        import bson.json_util as json_util
        with open(LOCAL_DB_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if not content:
            return False
        data = json_util.loads(content)
        if not data or not isinstance(data, dict):
            return False
        for col_name, docs in data.items():
            if docs:
                db[col_name].insert_many(docs)
        logger.info(f"Loaded {len(data)} collections from persistent local database.")
        return True
    except Exception as e:
        logger.warning(f"Could not load persistent local database: {e}")
        return False

def init_db(app=None):
    """
    Initializes and returns the MongoDB connection.
    Connects to MongoDB Atlas if reachable; otherwise falls back
    to a persistent mongomock database.
    """
    global _mongo_client, _db_instance
    
    if _db_instance is not None:
        return _db_instance

    uri = Config.MONGO_URI
    db_name = Config.DATABASE_NAME
    
    try:
        try:
            import certifi
            client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2500)
        except Exception:
            client = MongoClient(uri, serverSelectionTimeoutMS=2500)

        # Verify connection is alive
        client.admin.command('ping')
        _mongo_client = client
        _db_instance = client[db_name]
        logger.info(f"Connected to live MongoDB Atlas database: {db_name}")
        # Create indexes
        _create_indexes(_db_instance)
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
        logger.warning(f"MongoDB Atlas connection unavailable: {e}. Check Atlas Network Access IP Whitelist.")
        try:
            import mongomock
            logger.info("Initializing mongomock database fallback with local persistence...")
            mock_client = mongomock.MongoClient()
            _mongo_client = mock_client
            _db_instance = mock_client[db_name]
            _create_indexes(_db_instance)
            if not load_mock_db(_db_instance):
                from seed import seed_database
                seed_database(_db_instance)
                save_mock_db()
            logger.info("mongomock database initialized and persisted successfully.")
        except Exception as mock_err:
            logger.error(f"Failed to initialize fallback database: {mock_err}")
            _mongo_client = None
            _db_instance = None
            if app is None:
                raise e

    return _db_instance

def get_db():
    """Returns the current database instance."""
    global _db_instance
    if _db_instance is None:
        return init_db()
    return _db_instance

def _create_indexes(db):
    """Creates required indexes for collections."""
    try:
        # users indexes
        db.users.create_index([("email", ASCENDING)], unique=True, sparse=True)
        db.users.create_index([("user_id", ASCENDING)], unique=True, sparse=True)
        db.users.create_index([("role", ASCENDING)])
        db.users.create_index([("member_id", ASCENDING)])
        db.users.create_index([("trainer_id", ASCENDING)])

        # members indexes
        db.members.create_index([("member_id", ASCENDING)], unique=True)
        db.members.create_index([("phone", ASCENDING)])
        db.members.create_index([("email", ASCENDING)])
        db.members.create_index([("status", ASCENDING)])
        db.members.create_index([("trainer_id", ASCENDING)])
        
        # trainers indexes
        db.trainers.create_index([("trainer_id", ASCENDING)], unique=True)
        db.trainers.create_index([("email", ASCENDING)])
        
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

        # workout plans & schedules
        db.workout_plans.create_index([("member_id", ASCENDING)])
        db.workout_plans.create_index([("trainer_id", ASCENDING)])
        db.schedules.create_index([("trainer_id", ASCENDING)])
        db.schedules.create_index([("member_id", ASCENDING)])
        db.schedules.create_index([("session_date", ASCENDING)])
        
        logger.info("Database indexes ensured successfully.")
    except Exception as e:
        logger.warning(f"Note on index creation: {e}")
