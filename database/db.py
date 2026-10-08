import logging
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import Config

logger = logging.getLogger(__name__)

_mongo_client = None
_db_instance = None


def is_mock_db():
    """
    Kept for compatibility with existing application code.
    FITCORE uses MongoDB Atlas only.
    """
    return False


def init_db(app=None):
    """
    Initialize and return the MongoDB Atlas database connection.

    FITCORE uses MongoDB Atlas as the only database.
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
        try:
            import certifi

            client = MongoClient(
                uri,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=10000
            )
        except ImportError:
            client = MongoClient(
                uri,
                serverSelectionTimeoutMS=10000
            )

        # Verify MongoDB Atlas connection
        client.admin.command("ping")

        _mongo_client = client
        _db_instance = client[db_name]

        logger.info(
            f"Connected to MongoDB Atlas database: {db_name}"
        )

        _create_indexes(_db_instance)

        return _db_instance

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(
            f"MongoDB Atlas connection failed: {e}"
        )

        _mongo_client = None
        _db_instance = None

        raise RuntimeError(
            "MongoDB Atlas connection failed. "
            "Check MONGO_URI, Atlas Network Access, "
            "database credentials, and environment variables."
        ) from e

    except Exception as e:
        logger.error(
            f"Unexpected MongoDB initialization error: {e}"
        )

        _mongo_client = None
        _db_instance = None

        raise


def get_db():
    """Return the current MongoDB database instance."""
    global _db_instance

    if _db_instance is None:
        return init_db()

    return _db_instance


def _create_indexes(db):
    """Create required indexes for all FITCORE collections."""
    try:
        # Users
        db.users.create_index(
            [("email", ASCENDING)],
            unique=True,
            sparse=True
        )
        db.users.create_index(
            [("user_id", ASCENDING)],
            unique=True,
            sparse=True
        )
        db.users.create_index(
            [("role", ASCENDING)]
        )
        db.users.create_index(
            [("member_id", ASCENDING)]
        )
        db.users.create_index(
            [("trainer_id", ASCENDING)]
        )

        # Members
        db.members.create_index(
            [("member_id", ASCENDING)],
            unique=True
        )
        db.members.create_index(
            [("phone", ASCENDING)]
        )
        db.members.create_index(
            [("email", ASCENDING)]
        )
        db.members.create_index(
            [("status", ASCENDING)]
        )
        db.members.create_index(
            [("trainer_id", ASCENDING)]
        )

        # Trainers
        db.trainers.create_index(
            [("trainer_id", ASCENDING)],
            unique=True
        )
        db.trainers.create_index(
            [("email", ASCENDING)]
        )

        # Membership plans
        db.membership_plans.create_index(
            [("name", ASCENDING)]
        )

        # Attendance
        db.attendance.create_index(
            [("member_id", ASCENDING)]
        )
        db.attendance.create_index(
            [("status", ASCENDING)]
        )
        db.attendance.create_index(
            [("check_in", ASCENDING)]
        )

        # Payments
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

        # Workout plans
        db.workout_plans.create_index(
            [("member_id", ASCENDING)]
        )
        db.workout_plans.create_index(
            [("trainer_id", ASCENDING)]
        )

        # Schedules
        db.schedules.create_index(
            [("trainer_id", ASCENDING)]
        )
        db.schedules.create_index(
            [("member_id", ASCENDING)]
        )
        db.schedules.create_index(
            [("session_date", ASCENDING)]
        )

        logger.info(
            "Database indexes ensured successfully."
        )

    except Exception as e:
        logger.warning(
            f"Note on index creation: {e}"
        )
