from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path

# Load .env from backend/ directory if present
_here = Path(__file__).parent.parent
_env_path = _here / '.env'
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)

import json
import logging
from urllib.parse import quote_plus

import redis
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# PostgresSQL 配置
DB_USER = "postgres"
DB_PASSWORD = "kb121296"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "agent_db"
encoded_password = quote_plus(DB_PASSWORD)
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?client_encoding=utf8"
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, connect_args={"options": "-c client_encoding=utf8"})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Redis 配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
redis_pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True,
                                  max_connections=20, retry_on_timeout=True, socket_connect_timeout=5, socket_timeout=5,
                                  health_check_interval=30)


def get_redis():
    # Return a Redis client if available; if Redis is unreachable, yield None so callers can degrade gracefully.
    try:
        redis_client = redis.Redis(connection_pool=redis_pool)
        try:
            # quick health check
            redis_client.ping()
        except Exception as e:
            # DO NOT raise here; yield None to let endpoints handle lack of Redis gracefully
            logging.getLogger(__name__).warning(f"Redis ping failed during get_redis: {e}")
            yield None
            return
        yield redis_client
    except Exception as e:
        # Catch any connection pool creation errors and yield None
        logging.getLogger(__name__).warning(f"get_redis: failed to create redis client: {e}")
        yield None
    finally:
        pass


def publish_event(session_id: int, event: dict, redis_client: redis.Redis | None = None) -> None:
    """Publish a JSON event to the session Redis channel: session:{id}:events.

    Notes:
    - `get_redis()` is a FastAPI dependency generator intended to be used with `Depends(get_redis)`
      inside endpoint functions so FastAPI can manage the dependency lifecycle.
    - `publish_event` is a general helper that can be called from background tasks or
      other non-request code where FastAPI's dependency injection isn't available.
      Therefore it defaults to creating/using a Redis client from the shared connection pool.
    - By accepting an optional `redis_client`, callers (including unit tests) can inject
      a client (for example the one from `get_redis()` in an endpoint) for better control.
    """
    try:
        r = redis_client if redis_client is not None else redis.Redis(connection_pool=redis_pool)
        channel = f"session:{session_id}:events"
        payload = json.dumps(event, ensure_ascii=False, default=str)
        r.publish(channel, payload)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"publish_event failed for session {session_id}: {e}")


# JWT 和密码哈希配置
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login/")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", )
logger = logging.getLogger(__name__)
