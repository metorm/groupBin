import os
from dotenv import load_dotenv
from datetime import timedelta

# 加载.env文件
load_dotenv()

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-development-only'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///groupbin.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 从环境变量获取UPLOAD_FOLDER，如未设置则使用默认值
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    
    # 处理相对路径，转换为绝对路径
    if not os.path.isabs(UPLOAD_FOLDER):
        # 使用当前工作目录(CWD)拼接相对路径
        UPLOAD_FOLDER = os.path.abspath(os.path.join(os.getcwd(), UPLOAD_FOLDER))
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    
    # 小组配置
    MAX_RECENT_GROUPS = 10  # 浏览器缓存的最大小组数量
    DEFAULT_GROUP_DURATION = 72  # 默认小组有效期（小时）
    MAX_GROUP_DURATION = 720  # 最大小组有效期（小时，30天）
    
    # 安全配置
    PASSWORD_HASH_METHOD = 'pbkdf2:sha256'
    PASSWORD_HASH_SALT_LENGTH = 16
    
    # 前端配置
    SITE_NAME = 'groupBin'
    SITE_DESCRIPTION = '小组文件临时共享平台'
    FOOTER_TEXT = '注意：本服务仅用于临时文件共享，请勿上传敏感信息'

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'INFO'
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # 生产环境应使用更安全的密钥
    SECRET_KEY = os.environ.get('SECRET_KEY')  # 生产环境必须设置环境变量

# 配置字典，便于根据环境选择
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}