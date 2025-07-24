from datetime import datetime, timedelta, timezone
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import uuid

class Group(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc) + timedelta(hours=72))  # Default 3 days
    password_hash = db.Column(db.String(128), nullable=True)
    is_readonly = db.Column(db.Boolean, default=False)
    created_duration_hours = db.Column(db.Integer, default=72)  # 创建时设置的有效期（小时）
    
    files = db.relationship('File', backref='group', lazy=True, cascade="all, delete-orphan")
    
    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None
    
    def check_password(self, password):
        if not self.password_hash:
            return True  # 无密码保护
        return check_password_hash(self.password_hash, password)

    def is_expired(self):
        # 确保expires_at是时区感知的UTC时间
        if self.expires_at.tzinfo is None:
            # 为旧记录添加时区信息
            self.expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > self.expires_at

    def refresh_expiration(self):
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=self.created_duration_hours)

class File(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = db.Column(db.String(36), db.ForeignKey('group.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    size = db.Column(db.Integer, nullable=False)  # 文件大小（字节）
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    content_type = db.Column(db.String(100), nullable=False)
    
    versions = db.relationship('FileVersion', backref='file', lazy=True, cascade="all, delete-orphan")

class FileVersion(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = db.Column(db.String(36), db.ForeignKey('file.id'), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader = db.Column(db.String(100), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    size = db.Column(db.Integer, nullable=False)  # 文件大小（字节）

# 用户模拟类（实际项目中可能不需要，因为小组链接和密码就是访问凭证）
class User(UserMixin):
    def __init__(self, group_id):
        self.id = group_id

@login_manager.user_loader
def load_user(group_id):
    return User(group_id)