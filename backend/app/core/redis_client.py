from redis import Redis
from app import config

if config.REDIS_URL:
    redis_client = Redis.from_url(config.REDIS_URL, db=1, decode_responses=True)
else:
    redis_client = Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        password=config.REDIS_PASSWORD or None,
        db=1,
        decode_responses=True,
    )
