import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from app.models import File, FileVersion


def handle_file_upload(group_id, file, upload_folder, description='', uploader='anonymous', comment='', file_id=None):
    # 创建小组目录
    group_folder = os.path.join(upload_folder, group_id)
    os.makedirs(group_folder, exist_ok=True)
    
    # 生成安全的文件名
    original_filename = secure_filename(file.filename)
    stored_filename = str(uuid.uuid4()) + os.path.splitext(original_filename)[1]
    file_path = os.path.join(group_folder, stored_filename)
    
    # 保存文件
    file.save(file_path)
    
    # 获取文件大小
    file_size = os.path.getsize(file_path)
    
    # 如果提供了file_id，表示是版本更新
    if file_id:
        existing_file = File.query.get_or_404(file_id)
        # 创建新版本
        new_version = FileVersion(
            file_id=existing_file.id,
            stored_filename=stored_filename,
            size=file_size,
            uploaded_at=datetime.utcnow(),
            uploader=uploader,
            comment=comment
        )
        db.session.add(new_version)
        return new_version
    else:
        # 创建新文件
        new_file = File(
            id=str(uuid.uuid4()),
            group_id=group_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            size=file_size,
            content_type=file.content_type,
            uploaded_at=datetime.utcnow(),
            description=description
        )
        db.session.add(new_file)
        db.session.flush()  # 获取新文件的ID，但不提交事务
        
        # 创建初始版本
        initial_version = FileVersion(
            file_id=new_file.id,
            stored_filename=stored_filename,
            size=file_size,
            uploaded_at=datetime.utcnow(),
            uploader=uploader,
            comment=comment
        )
        db.session.add(initial_version)
        return new_file