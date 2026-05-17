import hashlib
import os
import shutil
import string
import time
from datetime import datetime, timedelta
from uuid import UUID
import random

import jwt
from fastapi import UploadFile

from app.config import Config


def short_uuid() -> str:
    """64-bit characters reduced to 8-bit characters.
    link https://blog.csdn.net/dqchouyang/article/details/70230863
    """
    uuidChars = ("a", "b", "c", "d", "e", "f",
                 "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s",
                 "t", "u", "v", "w", "x", "y", "z", "0", "1", "2", "3", "4", "5",
                 "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "I",
                 "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V",
                 "W", "X", "Y", "Z")
    uuid = str(uuid4()).replace('-', '')
    result = ''
    for i in range(0, 8):
        sub = uuid[i * 4: i * 4 + 4]
        x = int(sub, 16)
        result += uuidChars[x % 0x3E]
    return result


def uuid4():
    """Generate a random UUID."""
    return UUID(bytes=os.urandom(16), version=4)


def digest_password(password: str):
    """Sha256 digest password"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def generate_code():
    """Generate a 4 random letter verification code"""
    code = ''.join(random.sample(string.digits, 6))
    return code


# 日期转换成 年-月-日 时:分:秒
def date_to_str(date):
    return date.strftime("%Y-%m-%d %H:%M:%S")


def day_to_str(date):
    return date.strftime("%Y-%m-%d 00:00:00")


def friendly_time(dt):
  
    now = datetime.now()
    then = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    diff = now - then

    if diff < timedelta(seconds=60):
        return 'just now'
    elif diff < timedelta(minutes=1):
        s = diff.seconds
        return f'{s} second ago' if s == 1 else f'{s} seconds ago'
    elif diff < timedelta(hours=1):
        m = diff.seconds // 60
        return f'{m} minute ago' if m == 1 else f'{m} minutes ago'
    elif diff < timedelta(days=1):
        h = diff.seconds // 3600
        return f'{h} hour ago' if h == 1 else f'{h} hours ago'
    elif diff < timedelta(days=30):
        d = diff.days
        return f'{d} day ago' if d == 1 else f'{d} days ago'
    elif diff < timedelta(days=365):
        mo = diff.days // 30
        return f'{mo} month ago' if mo == 1 else f'{mo} months ago'
    else:
        y = diff.days // 365
        return f'{y} year ago' if y == 1 else f'{y} years ago'


def save_file(upload_file: UploadFile) -> str:
    # 获取upload_file文件后缀名
    file_ext = get_file_ext(upload_file.filename)

    filename = f'{short_uuid()}{file_ext}'
    file_path = f'{Config.TEMP_SAVE_FILE_PATH}/{filename}'
    if not os.path.exists(Config.TEMP_SAVE_FILE_PATH):
        os.makedirs(Config.TEMP_SAVE_FILE_PATH)
    with open(file_path, 'wb') as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return filename

# def save_voice_file(upload_file: UploadFile) -> str:
#     # 获取upload_file文件后缀名
#     file_ext = get_file_ext(upload_file.filename)

#     filename = f'{short_uuid()}{file_ext}'
#     file_path = voice_file_get_path(filename)
#     if not os.path.exists(Config.TEMP_SAVE_FILE_PATH):
#         os.makedirs(Config.TEMP_SAVE_FILE_PATH)
#     with open(file_path, 'wb') as buffer:
#         shutil.copyfileobj(upload_file.file, buffer)
#     return filename


def file_get_path(filename: str) -> str:
    return f'{Config.TEMP_SAVE_FILE_PATH}/{filename}'

# 获取文件的后缀名
def get_file_ext(filename: str) -> str:
    return os.path.splitext(filename)[1]    

# 获取年月日 yyyymmdd格式
def get_date_str():
    return time.strftime("%Y%m%d", time.localtime())


def save_image_file(upload_file: UploadFile) -> str:
    # 获取upload_file文件后缀名 
    file_ext = get_file_ext(upload_file.filename)
    filename = f'{short_uuid()}{file_ext}'

    file_full_path = image_file_get_path(filename)

    # 检查文件的目录是否存在，如果不存在就创建
    if not os.path.exists(os.path.dirname(file_full_path)):
        os.makedirs(os.path.dirname(file_full_path))

    with open(file_full_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return filename


def save_voice_file(upload_file: UploadFile, prefix='') -> str:
    """保存上传的语音文件，重置文件指针确保完整保存"""
    import logging
    # 获取upload_file文件后缀名 
    file_ext = get_file_ext(upload_file.filename)
    filename = f'{prefix}_{short_uuid()}{file_ext}'

    file_full_path = voice_file_get_path(filename)

    # 检查文件的目录是否存在，如果不存在就创建
    if not os.path.exists(os.path.dirname(file_full_path)):
        os.makedirs(os.path.dirname(file_full_path))

    # 重置文件指针到开头，确保完整读取（FastAPI UploadFile 可能已被读取过）
    upload_file.file.seek(0)
    
    # 保存文件并记录大小
    with open(file_full_path, "wb") as buffer:
        bytes_written = shutil.copyfileobj(upload_file.file, buffer)
        file_size = os.path.getsize(file_full_path)
        logging.info(f"语音文件已保存: {filename}, 大小: {file_size} bytes")
        if file_size == 0:
            logging.error(f"警告：保存的语音文件大小为 0，可能上传失败: {filename}")
    
    # 再次重置文件指针，以防后续代码需要读取
    upload_file.file.seek(0)
    
    return filename

def voice_file_get_path(filename: str) -> str:
    result = f"{Config.TEMP_SAVE_FILE_PATH}/voices/{filename}"
    # 检查full_file_name文件的所属目录是否存在，不存在则创建新的目录
    if not os.path.exists(os.path.dirname(result)):
        os.makedirs(os.path.dirname(result))    
    return result    


def image_file_get_path(filename: str) -> str:
    return f"{Config.TEMP_SAVE_FILE_PATH}/images/{filename}"


# 获取文件的后缀名
def get_file_ext(filename: str) -> str:
    return os.path.splitext(filename)[1]