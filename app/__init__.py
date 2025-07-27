from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request
from flask_session import Session

# 从环境变量获取.env文件路径，优先级高于默认位置
env_file = os.getenv("ENV_FILE")
if env_file and os.path.exists(env_file):
    load_dotenv(env_file)
else:
    # 默认加载项目根目录下的.env文件
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from config import config

# 初始化数据库
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def log_configuration(app):
    """将配置信息输出到日志中"""
    if app.config.get("DEBUG", False):
        app.logger.info("=" * 50)
        app.logger.info("Configuration Properties:")
        app.logger.info("=" * 50)
        for key in app.config.keys():
            app.logger.info(f"{key}: {app.config[key]}")
        app.logger.info("=" * 50)


# 添加日志配置
def setup_logging(app):
    # 设置日志级别
    # 从配置中获取日志级别，默认为INFO
    log_level = getattr(
        logging, app.config.get("LOG_LEVEL", "WARNING").upper(), logging.INFO
    )
    app.logger.setLevel(log_level)

    # 调整现有处理器的日志级别，而不是添加新的处理器
    for handler in app.logger.handlers:
        handler.setLevel(log_level)
        # 设置日志格式（控制台格式）
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(name)s : %(message)s"
        )
        handler.setFormatter(formatter)

    # 创建RotatingFileHandler
    if app.config.get("LOG_FILE"):
        # 确保日志目录存在
        log_dir = os.path.dirname(app.config["LOG_FILE"])
        os.makedirs(log_dir, exist_ok=True)

        # 创建RotatingFileHandler
        file_handler = RotatingFileHandler(
            app.config["LOG_FILE"],
            maxBytes=app.config.get("LOG_FILE_MAX_SIZE", 10 * 1024 * 1024),  # 默认10MB
            backupCount=app.config.get("LOG_FILE_BACKUP_COUNT", 5),  # 默认保留5个备份
        )

        # 设置纯文本日志格式
        file_formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.setLevel(log_level)

        app.logger.info(
            "RotatingFileHandler configured for: %s", app.config["LOG_FILE"]
        )


def create_app(config_name=None):
    if not config_name:
        config_name = os.environ.get("FLASK_CONFIG", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])  # 从配置对象加载配置

    # 初始化日志
    setup_logging(app)
    app.logger.info("Application initialized with config: %s", config_name)

    # 输出配置信息到日志
    log_configuration(app)

    # 确保session目录存在
    if app.config.get("SESSION_FILE_DIR"):
        os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
        app.logger.info(
            "Session folder configured at: %s", app.config["SESSION_FILE_DIR"]
        )

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    CORS(app)
    CSRFProtect(app)  # 初始化CSRF保护

    # 初始化Session
    Session(app)

    # 添加方法覆盖处理
    @app.before_request
    def handle_method_override():
        # 添加详细调试日志
        original_method = request.method
        override_method = request.form.get("_method", "").upper()

        if override_method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            request.method = override_method
            app.logger.info(f"原始方法: {original_method} 已覆盖为: {request.method}")
        elif override_method:
            app.logger.warning(f"无效的方法覆盖参数: {override_method}")

    # 确保上传文件夹存在
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        app.logger.info("Upload folder configured at: %s", app.config["UPLOAD_FOLDER"])
    except Exception as e:
        app.logger.error("Failed to create upload folder: %s", str(e))
        raise

    # 注册全局404错误处理器
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    # 注册蓝图
    from app.routes.main import main as main_bp

    app.register_blueprint(main_bp)

    from app.routes.group import group as group_bp

    app.register_blueprint(group_bp, url_prefix="/group")

    from app.routes.file import file as file_bp

    app.register_blueprint(file_bp, url_prefix="/file")
    app.logger.info("Blueprints registered successfully")

    # 创建数据库表
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully")
        except Exception as e:
            app.logger.error("Failed to create database tables: %s", str(e))
            raise

    # 验证关键配置
    required_configs = ["SECRET_KEY", "UPLOAD_FOLDER", "SQLALCHEMY_DATABASE_URI"]
    for config_key in required_configs:
        if not app.config.get(config_key):
            app.logger.error(f"Missing required configuration: {config_key}")
            raise ValueError(f"Missing required configuration: {config_key}")

    app.logger.info("Application instance created successfully")
    return app
