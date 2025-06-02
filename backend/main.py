from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from core.middleware import MaxSizeLimitMiddleware
from api import endpoints

app = FastAPI()
app.add_middleware(MaxSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router)
