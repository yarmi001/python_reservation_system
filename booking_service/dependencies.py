from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from booking_service.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login")

class CurrentUser:
    def __init__(self, user_id: str, role: str):
        self.id = user_id
        self.role = role

async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """
    Retrieve the current user based on the provided JWT token.

    Args:
        token (str): JWT access token extracted from the request.

    Returns:
        CurrentUser: An instance containing the user's ID and role.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY.get_secret_value(), 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        role = payload.get("role")
        if user_id is None or role is None:
            raise ValueError()
        return CurrentUser(user_id=user_id, role=role)
    except (jwt.DecodeError, jwt.ExpiredSignatureError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )