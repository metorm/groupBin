import os
from dotenv import load_dotenv
from datetime import timedelta

# 加载.env文件
load_dotenv()

class Config:
    # 基础配置
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER')
    
    # 处理相对路径，转换为绝对路径
    if not os.path.isabs(UPLOAD_FOLDER):
        UPLOAD_FOLDER = os.path.abspath(os.path.join(os.getcwd(), UPLOAD_FOLDER))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_UPLOAD_SIZE_MB')) * 1024 * 1024  # 从MB转换为字节

    # 小组配置
    MAX_RECENT_GROUPS = int(os.getenv('MAX_RECENT_GROUPS'))
    DEFAULT_GROUP_DURATION = int(os.getenv('DEFAULT_GROUP_DURATION_HOURS'))
    MAX_GROUP_DURATION = int(os.getenv('MAX_GROUP_DURATION_HOURS'))
   
    # 前端配置
    SITE_NAME = os.getenv('SITE_NAME')
    SITE_DESCRIPTION = os.getenv('SITE_DESCRIPTION')
    FOOTER_TEXT = os.getenv('FOOTER_TEXT')
    
    # 新增配置项
    AUTH_DELAY_SECONDS = int(os.getenv('AUTH_DELAY_SECONDS'))
    EXPIRED_FILE_CLEANUP_DAYS = int(os.getenv('EXPIRED_FILE_CLEANUP_DAYS'))
    UNIFIED_PASSWORD = os.getenv('UNIFIED_PASSWORD')

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'INFO'
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # 生产环境密钥直接从.env读取
    SECRET_KEY = os.getenv('SECRET_KEY')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}