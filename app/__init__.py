from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request

# 明确指定.env文件路径
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))
from config import config

# 加载环境变量
load_dotenv()

# 初始化数据库
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

# 添加日志配置
def setup_logging(app):
    # 设置日志级别
    # 从配置中获取日志级别，默认为INFO
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'WARNING').upper(), logging.INFO)
    app.logger.setLevel(log_level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # 设置日志格式
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(name)s : %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    app.logger.addHandler(console_handler)


def create_app(config_name=None):
    if not config_name:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])  # 从配置对象加载配置
   
    # 初始化日志
    setup_logging(app)
    app.logger.info('Application initialized with config: %s', config_name)
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    CORS(app)
    CSRFProtect(app)  # 初始化CSRF保护
    
    # 添加方法覆盖处理
    @app.before_request
    def handle_method_override():
        # 添加详细调试日志
        original_method = request.method
        override_method = request.form.get('_method', '').upper()
        app.logger.info(f"方法覆盖检查 - 原始方法: {original_method}, 覆盖参数: {override_method}")
        
        if override_method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            request.method = override_method
            app.logger.info(f"方法已覆盖为: {request.method}")
        elif override_method:
            app.logger.warning(f"无效的方法覆盖参数: {override_method}")
    
    # 确保上传文件夹存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.logger.info('Upload folder configured at: %s', app.config['UPLOAD_FOLDER'])
    
    # 注册蓝图
    from app.routes.main import main as main_bp
    app.register_blueprint(main_bp)

    from app.routes.group import group as group_bp
    app.register_blueprint(group_bp, url_prefix='/group')

    from app.routes.file import file as file_bp
    app.register_blueprint(file_bp, url_prefix='/file')
    app.logger.info('Blueprints registered successfully')

    # 创建数据库表
    with app.app_context():
        db.create_all()
        app.logger.info('Database tables created')
    
    return app


