from redis import Redis
from app import config

redis_client = Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=1, decode_responses=True)
