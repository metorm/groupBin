import os
from dotenv import load_dotenv
from datetime import timedelta


class Config:
    # 基础配置
    SECRET_KEY = os.getenv("SECRET_KEY")

    # 数据库URI配置 - 如果使用默认的sqlite数据库，将其放在数据目录中
    DATA_DIR = os.getenv("DATA_DIR", ".")
    # 处理DATA_DIR相对路径，转换为绝对路径
    if not os.path.isabs(DATA_DIR):
        DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), DATA_DIR))

    DATABASE_PATH = os.path.join(DATA_DIR, "groupbin.db")
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("SQLALCHEMY_DATABASE_URI") or f"sqlite:///{DATABASE_PATH}"
    )

    # 上传目录配置 - 默认放在数据目录下的data子目录中
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(DATA_DIR, "data"))

    # 处理相对路径，转换为绝对路径
    if not os.path.isabs(UPLOAD_FOLDER):
        UPLOAD_FOLDER = os.path.abspath(os.path.join(os.getcwd(), UPLOAD_FOLDER))
    MAX_CONTENT_LENGTH = (
        int(os.getenv("MAX_UPLOAD_SIZE_MB")) * 1024 * 1024
    )  # 从MB转换为字节
    # 分片大小配置
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE_MB", 5)) * 1024 * 1024  # 从MB转换为字节
    # 文件操作最大等待时间（毫秒）
    FILE_MOVE_OPERATION_MAX_WAIT_MS = int(
        os.getenv("FILE_MOVE_OPERATION_MAX_WAIT_MS", 3000)
    )

    # 小组配置
    MAX_RECENT_GROUPS = int(os.getenv("MAX_RECENT_GROUPS"))
    DEFAULT_GROUP_DURATION = int(os.getenv("DEFAULT_GROUP_DURATION_HOURS"))
    MAX_GROUP_DURATION = int(os.getenv("MAX_GROUP_DURATION_HOURS"))

    # 前端配置
    SITE_NAME = os.getenv("SITE_NAME")
    SITE_DESCRIPTION = os.getenv("SITE_DESCRIPTION")
    FOOTER_TEXT = os.getenv("FOOTER_TEXT")

    # 系统配置
    AUTH_DELAY_SECONDS = int(os.getenv("AUTH_DELAY_SECONDS"))
    EXPIRED_FILE_CLEANUP_DAYS = int(os.getenv("EXPIRED_FILE_CLEANUP_DAYS"))
    UNIFIED_PUBLIC_PASSWORD = os.getenv("UNIFIED_PUBLIC_PASSWORD")
    CREATE_GROUP_PUBLIC_PASSWORD = os.getenv("CREATE_GROUP_PUBLIC_PASSWORD")

    # Session配置
    SESSION_TYPE = "filesystem"  # 使用文件系统存储session
    SESSION_FILE_DIR = os.path.join(DATA_DIR, "sessions")  # Session文件存储在DATA_DIR下
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = "groupbin:"
    SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", "168"))  # 从环境变量获取过期时间，默认168小时
    PERMANENT_SESSION_LIFETIME = timedelta(hours=SESSION_LIFETIME_HOURS)  # 会话有效期

    # 日志配置
    LOG_FILE = os.path.join(DATA_DIR, "groupbin.log")  # 日志文件路径
    LOG_FILE_MAX_SIZE = int(os.getenv("LOG_FILE_MAX_SIZE_MB", "10")) * 1024 * 1024  # 日志文件最大大小，默认10MB
    LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))  # 日志文件备份数量，默认5个

    def __init__(self):
        """在配置对象构造完成后，输出自身的所有属性和值，便于调试"""
        if os.getenv("FLASK_ENV") == "development":
            print("=" * 50)
            print("Configuration Properties:")
            print("=" * 50)
            for attr in dir(self):
                # 只打印公共属性（不以下划线开头的）
                if not attr.startswith("_") and not callable(getattr(self, attr)):
                    print(f"{attr}: {getattr(self, attr)}")
            print("=" * 50)


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = "INFO"
    LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = "WARNING"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}