import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEFAULT_SOURCE_LANGUAGE = 'zh-CN'
    DEFAULT_TARGET_LANGUAGE = 'en-US'
    AI_NAME = os.getenv('AI_NAME')
    # 数据库连接信息，需要判断不能为空
    SQLALCHEMY_DATABASE_URL: str = os.getenv('DATABASE_URL')

    # 文件上传路径
    TEMP_SAVE_FILE_PATH = os.getenv('TEMP_SAVE_FILE_PATH')

    # 微软语音
    AZURE_KEY = os.getenv('AZURE_KEY')

    # AI
    AI_SERVER = os.getenv('AI_SERVER')
    # ChatGPT Key
    CHAT_GPT_PROXY = os.getenv('CHAT_GPT_PROXY')
    CHAT_GPT_KEY = os.getenv('CHAT_GPT_KEY')
    CHAT_GPT_MODEL = os.getenv('CHAT_GPT_MODEL')
    # 智谱AI配置
    ZHIPU_AI_API_KEY = os.getenv('ZHIPU_AI_API_KEY')
    ZHIPU_AI_MODEL = os.getenv('ZHIPU_AI_MODEL')

    # WeChat
    WECHAT_APP_ID = os.getenv('WECHAT_APP_ID')
    WECHAT_APP_SECRET = os.getenv('WECHAT_APP_SECRET')
    WE_CHAT_SERVER_URL = os.getenv('WE_CHAT_SERVER_URL')
  
    # 是否开启SQL语句打印
    SQL_ECHO: bool = os.getenv('SQL_ECHO').lower() == 'true'

    # JWT配置
    TOKEN_SECRET = os.getenv('TOKEN_SECRET')
    ALGORITHM = 'HS256'
    DECODED_TOKEN_USER_KEY = "sub"
    DECODED_TOKEN_IAT_KEY = "iat"
    TOKEN_EXPIRE_TIME = int(os.getenv("TOKEN_EXPIRE_TIME"))

    # API前缀
    API_PREFIX = os.getenv('API_PREFIX', '/api')
    
    # MAS服务配置
    MAS_MMA_URL = os.getenv('MAS_MMA_URL', 'http://localhost:8001')
    MAS_SOA_URL = os.getenv('MAS_SOA_URL', 'http://localhost:8002')
    MAS_GRA_URL = os.getenv('MAS_GRA_URL', 'http://localhost:8003')
    MAS_SCA_URL = os.getenv('MAS_SCA_URL', 'http://localhost:8004')
    MAS_SSA_URL = os.getenv('MAS_SSA_URL', 'http://localhost:8005')
    MAS_OA_URL = os.getenv('MAS_OA_URL', 'http://localhost:8006')
    # OA 定时调度：talkieai-server 是否定时调用 OA（若 OA 内部 loop 已运行，可设为 false 避免重复）
    MAS_OA_SCHEDULER_ENABLED = os.getenv('MAS_OA_SCHEDULER_ENABLED', 'true').lower() == 'true'
    # MAS 代理（SOA/GRA/SCA）调用大模型可能超过 30s，读超时过短会出现 httpx.ReadTimeout
    MAS_HTTP_READ_TIMEOUT = float(os.getenv('MAS_HTTP_READ_TIMEOUT', '120'))
    MAS_HTTP_CONNECT_TIMEOUT = float(os.getenv('MAS_HTTP_CONNECT_TIMEOUT', '10'))