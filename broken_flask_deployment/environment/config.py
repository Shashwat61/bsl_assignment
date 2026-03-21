import os


class Config:
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "flaskapp")
    DB_USER = os.environ.get("DB_USER", "flaskuser")
    DB_PASS = os.environ.get("DB_PASS", "flaskpass")

    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

    @property
    def DATABASE_URL(self):
        return f"host={self.DB_HOST} port={self.DB_PORT} dbname={self.DB_NAME} user={self.DB_USER} password={self.DB_PASS}"
