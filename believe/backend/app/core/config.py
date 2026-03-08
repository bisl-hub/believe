import os

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
# Set to 10 years (60 minutes * 24 hours * 365 days * 10 years) to make the session effectively persistent
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 365 * 10
