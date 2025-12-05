from fastapi import FastAPI, Depends, HTTPException, status, Response, Cookie # 補上 Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI()

fake_user_db = {
    "alice": {"username": "alice", "password": "secret123"} 
}

# JWT config
SECRET_KEY = "amalkf+5484aalfasl"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7  # [NEW] Refresh Token 的效期通常比較長

oauth2_schema = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"}) # 建議加入 type 區分
    encode_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encode_jwt

# [NEW] 這是白板上要求的第一點：Refresh Token Def
def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    # 如果沒有指定時間，預設使用 REFRESH_TOKEN_EXPIRE_DAYS
    expire = datetime.utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"}) # 標記這是 refresh token
    encode_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encode_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) # 這裡通常是 list
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return username
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

@app.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    # 這裡要注意 dictionary key 是 user_name 還是 username，你的 DB 是 user_name
    user = fake_user_db.get(form_data.username) 
    
    if not user or user["password"] != form_data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # [MODIFIED] 同時建立 Access Token 和 Refresh Token
    access_token = create_access_token(data={"sub": user["user_name"]})
    refresh_token = create_refresh_token(data={"sub": user["user_name"]})
    
    # 設定 Cookie (修正了 sanesite -> samesite)
    response.set_cookie(
        key="jwt",
        value=access_token,
        httponly=True,
        samesite="lax" # 修正拼字
    )
    
    # 回傳時把兩個 Token 都給前端
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer"
    }

# [NEW] 新增 Refresh 路由：用 Refresh Token 換新的 Access Token
@app.post("/refresh")
def refresh_access_token(refresh_token: str):
    try:
        # 驗證 Refresh Token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 檢查這是不是一個 Refresh Token (避免有人拿 Access Token 來刷)
        if payload.get("type") != "refresh":
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
            
        # 發新的 Access Token
        new_access_token = create_access_token(data={"sub": username})
        return {"access_token": new_access_token, "token_type": "bearer"}
        
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

@app.get("/user/me")
def me(token: Optional[str] = Depends(oauth2_schema), jwt_cookie: Optional[str] = Cookie(None)):
    username = None
    if token:
        username = verify_token(token)
    elif jwt_cookie:
        username = verify_token(jwt_cookie)
    
    if not username:
         raise HTTPException(status_code=401, detail="Missing token or cookie")
    
    # 這裡 f-string 修正
    return {"message": f"Hello, {username}! You are authenticated."}