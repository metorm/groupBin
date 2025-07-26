import os
import uuid
import time
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from app import db
from app.models import File, FileVersion
from flask import current_app


def handle_file_upload(
    group_id,
    file,
    upload_folder,
    description="",
    uploader="anonymous",
    comment="",
    file_id=None,
):
    # 创建小组目录
    group_folder = os.path.join(upload_folder, group_id)
    os.makedirs(group_folder, exist_ok=True)

    # 生成安全的文件名
    original_filename = file.filename  # 保留原始文件名（含中文）
    # 仅对存储文件名使用安全处理
    safe_extension = secure_filename(os.path.splitext(file.filename)[1])
    stored_filename = str(uuid.uuid4()) + safe_extension
    file_path = os.path.join(group_folder, stored_filename)

    # 保存文件
    file.save(file_path)

    # 等待文件完全写入磁盘
    max_wait_time = (
        current_app.config.get("FILE_MOVE_OPERATION_MAX_WAIT_MS", 3000) / 1000.0
    )  # 转换为秒
    wait_interval = 0.25
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        if os.path.exists(file_path):
            try:
                # 尝试获取文件大小，确保文件完全可用
                file_size = os.path.getsize(file_path)
                break
            except OSError:
                # 文件存在但无法访问，继续等待
                pass

        # 记录INFO级别日志
        current_app.logger.info(
            f"等待文件完全写入磁盘: {file_path}, 已等待 {elapsed_time:.2f} 秒"
        )

        # 等待150毫秒
        time.sleep(wait_interval)
        elapsed_time += wait_interval
    else:
        # 超时仍未找到文件或无法访问文件
        current_app.logger.error(
            f"文件操作超时，无法访问文件: {file_path}，已等待 {max_wait_time} 秒"
        )
        raise FileNotFoundError(f"文件操作超时，无法访问文件: {file_path}")

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
            uploaded_at=datetime.now(timezone.utc),
            uploader=uploader,
            comment=comment,
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
            uploaded_at=datetime.now(timezone.utc),
            description=description,
        )
        db.session.add(new_file)
        db.session.flush()  # 获取新文件的ID，但不提交事务

        # 创建初始版本
        initial_version = FileVersion(
            file_id=new_file.id,
            stored_filename=stored_filename,
            size=file_size,
            uploaded_at=datetime.now(timezone.utc),
            uploader=uploader,
            comment=comment,
        )
        db.session.add(initial_version)
        return new_file
