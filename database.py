"""
Simple in-memory database for user management
For production, use a proper database like PostgreSQL
"""

from typing import Dict, Optional
from auth import UserInDB, get_password_hash

# In-memory user database
users_db: Dict[str, UserInDB] = {}
user_id_counter = 1


def get_user(username: str) -> Optional[UserInDB]:
    """Get user by username"""
    return users_db.get(username)


def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get user by email"""
    for user in users_db.values():
        if user.email == email:
            return user
    return None


def create_user(username: str, email: str, password: str) -> UserInDB:
    """Create a new user"""
    global user_id_counter

    if username in users_db:
        raise ValueError("Username already exists")

    if get_user_by_email(email):
        raise ValueError("Email already registered")

    hashed_password = get_password_hash(password)

    user = UserInDB(
        id=user_id_counter,
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_active=True
    )

    users_db[username] = user
    user_id_counter += 1

    return user


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate a user"""
    from auth import verify_password

    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# Create a default test user
try:
    create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )
    print("Test user created: testuser / testpass123")
except ValueError as e:
    print(f"Test user creation skipped: {e}")
except Exception as e:
    print(f"Error creating test user: {e}")
