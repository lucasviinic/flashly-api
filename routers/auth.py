from datetime import datetime, timedelta, timezone
import secrets
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
import requests
from starlette import status

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from database import db_dependency
from models.user_model import Users
from usecases.auth import authenticate_user_usecase, create_access_token_usecase, bcrypt_context


router = APIRouter(prefix='/auth', tags=['auth'])
load_dotenv()

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class GoogleSignInRequest(BaseModel):
    access_token: str

class CreateUserRequest(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str
    password: str

@router.post("/signin", response_model=Token)
async def signin(google_signin_request: GoogleSignInRequest, db: db_dependency):
    token = google_signin_request.access_token

    response = requests.get(
        'https://www.googleapis.com/oauth2/v1/userinfo',
        headers={'Authorization': f'Bearer {token}'}
    )

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid Google access token.')

    user_info = response.json()

    google_id = user_info.get('id')
    email = user_info.get('email')
    name = user_info.get('name', '')
    picture = user_info.get('picture', '')

    user = db.query(Users).filter(Users.google_id == google_id).first()

    if not user:
        user = Users(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
            is_active=True
        )
        db.add(user)
    else:
        user.last_login = datetime.now(timezone.utc)

    access_token = create_access_token_usecase(user.name, str(user.id), timedelta(days=90))
    refresh_token = secrets.token_hex(32)

    user.refresh_token = refresh_token
    db.commit()

    return {'access_token': access_token, 'token_type': 'bearer', 'refresh_token': refresh_token}

@router.post("/refresh-token", response_model=Token)
async def refresh_access_token(refresh_token: str, db: db_dependency):
    user = db.query(Users).filter(Users.refresh_token == refresh_token).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token.')

    access_token = create_access_token_usecase(user.name, user.id, timedelta(days=90))
    new_refresh_token = secrets.token_hex(32)

    user.refresh_token = new_refresh_token
    db.commit()

    return {'access_token': access_token, 'token_type': 'bearer', 'refresh_token': new_refresh_token}
