import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 檢測是否在 Vercel 環境
IS_VERCEL = os.environ.get('VERCEL') == '1'

class Config:
    SECRET_KEY = "mysecret"
    # Vercel 使用 /tmp 目錄（唯一可寫入的位置）
    if IS_VERCEL:
        SQLALCHEMY_DATABASE_URI = "sqlite:////tmp/data.db"
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "data.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
