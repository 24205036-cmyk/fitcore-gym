import logging
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import Config

logger = logging.getLogger(__name__)

_mongo_client = None
_db_instance = None


def init_db(app=None):
    """
    Initialize and return the MongoDB Atlas database connection.
    No local MongoDB or mongomock fallback is used.
    """
    global _mongo_client, _db_instance

    if _db_instance is not None:
        return _db_instance

    uri = Config.MONGO_URI
    db_name = Config.DATABASE_NAME

    if not uri:
        raise RuntimeError(
            "MONGO_URI is not configured. "
            "Set MONGO_URI in the environment variables."
        )

    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=10000
        )

        client.admin.command("ping")

        _mongo_client = client
        _db_instance = client[db_name]

        logger.info(
            "Connected to MongoDB Atlas successfully. "
            f"Database: {db_name}"
        )

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Could not connect to MongoDB Atlas: {e}")
        raise RuntimeError(
            "MongoDB Atlas connection failed. "
            "Check MONGO_URI, Atlas Network Access, "
            "database credentials, and environment variables."
        ) from e

    _create_indexes(_db_instance)

    return _db_instance


def get_db():
    """Return the current MongoDB database instance."""
    global _db_instance

    if _db_instance is None:
        return init_db()

    return _db_instance


def is_mock_db():
    """
    Kept for compatibility with existing application code.
    FITCORE no longer uses mongomock.
    """
    return False


def _create_indexes(db):
    """Create required MongoDB indexes."""
    try:
        db.members.create_index(
            [("member_id", ASCENDING)],
            unique=True
        )
        db.members.create_index([("phone", ASCENDING)])
        db.members.create_index([("email", ASCENDING)])
        db.members.create_index([("status", ASCENDING)])

        db.trainers.create_index(
            [("trainer_id", ASCENDING)],
            unique=True
        )

        db.membership_plans.create_index(
            [("name", ASCENDING)]
        )

        db.attendance.create_index(
            [("member_id", ASCENDING)]
        )
        db.attendance.create_index(
            [("status", ASCENDING)]
        )
        db.attendance.create_index(
            [("check_in", ASCENDING)]
        )

        db.payments.create_index(
            [("payment_id", ASCENDING)],
            unique=True
        )
        db.payments.create_index(
            [("member_id", ASCENDING)]
        )
        db.payments.create_index(
            [("payment_date", ASCENDING)]
        )

        logger.info("Database indexes ensured successfully.")

    except Exception as e:
        logger.warning(f"Note on index creation: {e}")
