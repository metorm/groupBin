import threading
from flask import (
    Blueprint,
    request,
    jsonify,
    send_from_directory,
    redirect,
    url_for,
    flash,
    current_app,
    render_template,
    make_response,
)
from app import db
from app.models import Group, File, FileVersion
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
import zipfile
import time
from io import BytesIO
from app.utils.file_handling import handle_file_upload

file = Blueprint("file", __name__, url_prefix="/file")


@file.route("/upload/<group_id>", methods=["GET", "POST"])
def upload(group_id):
    return handle_file_request(group_id)


@file.route("/upload_version/<group_id>/<file_id>", methods=["GET", "POST"])
def upload_version(group_id, file_id):
    return handle_file_request(group_id, file_id)


def handle_file_request(group_id, file_id=None):
    """
    统一处理文件上传请求（包括普通上传和版本上传）

    Args:
        group_id: 小组ID
        file_id: 文件ID（可选，用于版本上传）
    """
    # 检查是否是Resumable.js的分块上传请求
    resumable_identifier = request.form.get("resumableIdentifier", "")
    resumable_filename = request.form.get("resumableFilename", "")
    resumable_chunk_number = request.form.get("resumableChunkNumber", "")
    resumable_total_size = request.form.get("resumableTotalSize", "")

    # 也检查URL参数中的Resumable.js标识
    if not resumable_identifier:
        resumable_identifier = request.args.get("resumableIdentifier", "")
        resumable_filename = request.args.get("resumableFilename", "")
        resumable_chunk_number = request.args.get("resumableChunkNumber", "")
        resumable_total_size = request.args.get("resumableTotalSize", "")

    # 检查文件大小是否超过限制
    if resumable_total_size:
        max_size = current_app.config.get("MAX_UPLOAD_SIZE_MB", 10 * 1024 * 1024)  # 默认10MB
        if int(resumable_total_size) > max_size:
            return (
                jsonify(
                    {
                        "error": "file_too_large",
                        "message": f"文件大小超过限制 ({max_size / 1024 / 1024:.1f} MB)",
                        "max_size": max_size,
                    }
                ),
                413,
            )

    if resumable_identifier:
        # 处理Resumable.js上传
        if request.method == "GET":
            # 检查分块是否已经上传
            return check_chunk(group_id, resumable_identifier, resumable_chunk_number)
        elif request.method == "POST":
            # 处理分块上传
            return handle_resumable_upload(
                group_id,
                resumable_identifier,
                resumable_filename,
                resumable_chunk_number,
                file_id,
            )

    # 如果是GET请求但不是Resumable.js的检查请求，则返回405
    return jsonify({"error": "Method not allowed"}), 405


def check_chunk(group_id, resumable_identifier, resumable_chunk_number):
    """检查分块是否已存在"""
    # 构建分块文件路径
    chunk_dir = os.path.join(
        current_app.config["UPLOAD_FOLDER"], "tmp", resumable_identifier
    )
    chunk_file = os.path.join(chunk_dir, str(resumable_chunk_number))

    # 检查分块是否已存在
    if os.path.exists(chunk_file):
        return "found", 200
    else:
        return "not_found", 204  # 204表示分块不存在，需要上传


def handle_resumable_upload(
    group_id,
    resumable_identifier,
    resumable_filename,
    resumable_chunk_number,
    file_id=None,
):
    """处理Resumable.js上传请求"""
    group = Group.query.get_or_404(group_id)

    # 检查小组是否只读
    if group.is_readonly:
        return (
            jsonify(
                {
                    "error": "permission_denied",
                    "message": "该小组为只读，无法上传文件",
                    "group_id": group.id,
                    "is_readonly": True,
                }
            ),
            403,
        )

    # 创建临时目录存储分块
    chunk_dir = os.path.join(
        current_app.config["UPLOAD_FOLDER"], "tmp", resumable_identifier
    )
    os.makedirs(chunk_dir, exist_ok=True)

    # 保存上传的分块
    chunk_file = os.path.join(chunk_dir, str(resumable_chunk_number))
    uploaded_file = request.files["file"]

    # 检查当前分块是否会导致总大小超过限制
    # 注意：这个检查只在第一个分块时有效，因为其他分块可能已经上传了
    if resumable_chunk_number == "1":
        max_size = current_app.config.get("MAX_UPLOAD_SIZE_MB", 10 * 1024 * 1024)  # 默认10MB
        resumable_total_size = int(request.form.get("resumableTotalSize", 0))
        if resumable_total_size > max_size:
            # 清理已创建的目录
            import shutil
            shutil.rmtree(chunk_dir, ignore_errors=True)
            return (
                jsonify(
                    {
                        "error": "file_too_large",
                        "message": f"文件大小超过限制 ({max_size / 1024 / 1024:.1f} MB)",
                        "max_size": max_size,
                    }
                ),
                413,
            )

    # 使用.un-complete后缀，防止文件写入过程中被其他线程误认为已完成
    chunk_file_temp = chunk_file + ".un-complete"
    uploaded_file.save(chunk_file_temp)

    # 检查分片大小是否与声明的一致，防止恶意攻击者绕过限制
    resumable_current_chunk_size = int(
        request.form.get("resumableCurrentChunkSize", 0)
    )
    actual_chunk_size = os.path.getsize(chunk_file_temp)
    
    if resumable_current_chunk_size != actual_chunk_size:
        # 分片大小不一致，可能是恶意攻击
        os.remove(chunk_file_temp)
        current_app.logger.warning(
            f"分片大小不一致，声明大小: {resumable_current_chunk_size}, 实际大小: {actual_chunk_size}"
        )
        return (
            jsonify(
                {
                    "error": "chunk_size_mismatch",
                    "message": "分片大小与声明不一致",
                }
            ),
            400,
        )

    # 确保文件完全写入磁盘后再重命名
    os.rename(chunk_file_temp, chunk_file)

    # 等待文件重命名完成，最多等待1秒
    max_wait_time = 1.0  # 最长等待1秒
    wait_interval = 0.1  # 每次检查间隔0.1秒
    elapsed_time = 0
    while elapsed_time < max_wait_time:
        if os.path.exists(chunk_file) and not os.path.exists(chunk_file_temp):
            break
        time.sleep(wait_interval)
        elapsed_time += wait_interval
    # 出循环检查
    if os.path.exists(chunk_file_temp) or (not os.path.exists(chunk_file)):
        current_app.logger.warning(f"文件重命名失败，请检查逻辑")

    # 获取请求的唯一标识符
    request_id = getattr(threading.current_thread(), "ident", "unknown")

    current_app.logger.info(f"线程 {request_id} 写入分片 {chunk_file}")

    # 检查是否所有分块都已上传完成
    resumable_total_chunks = int(
        request.args.get("resumableTotalChunks", 0)
        or request.form.get("resumableTotalChunks", 0)
    )

    if not all_chunks_uploaded(chunk_dir, resumable_total_chunks):
        # 最常见的情况：上传了一个分块，没有其他工作要做
        return "chunk_uploaded", 200

    current_app.logger.info(
        f"线程 {request_id} 启动分块合并进程…… {resumable_identifier}"
    )

    # 创建基于客户端IP+resumable_identifier的合并锁文件
    # 使用request.remote_addr和resumable_identifier组合创建锁文件名
    # TODO 反向代理？
    lock_file_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        "tmp",
        f"{request.remote_addr}_{resumable_identifier}.lock",
    )

    # 尝试获取锁
    lock_fd = None
    try:
        # 尝试创建锁文件，如果文件已存在会抛出异常
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        current_app.logger.info(
            f"[Request {request_id}] 成功获取合并锁: {lock_file_path}"
        )
    except FileExistsError:
        # 锁已被其他进程获取
        current_app.logger.info(
            f"[Request {request_id}] 合并锁已被占用，另一个线程正在进行合并: {lock_file_path}"
        )
        # 锁文件存在但无法获得，说明另一个线程已经在合并，当前线程无需等待，直接返回
        return "chunk_uploaded", 200
    except Exception as e:
        # 其他异常
        current_app.logger.error(
            f"[Request {request_id}] 获取合并锁时发生错误: {str(e)}"
        )
        return "chunk_uploaded", 200

    # 获取锁后，再次检查临时目录是否存在（可能其他线程已完成合并并清理了目录）
    if not os.path.exists(chunk_dir):
        current_app.logger.warning(
            f"[Request {request_id}] 临时目录不存在，但本线程已经获得锁，可能需要检查多线程逻辑"
        )
        # 关闭并删除锁文件
        try:
            if lock_fd is not None:
                os.close(lock_fd)
            os.remove(lock_file_path)
            current_app.logger.info(
                f"[Request {request_id}] 合并锁已释放: {lock_file_path}"
            )
        except:
            pass
        return "chunk_uploaded", 200

    # 合并所有分块
    marged_file_in_temp_path = merge_chunks(
        chunk_dir, resumable_filename, resumable_total_chunks
    )

    # 检查合并后的文件是否存在
    if not os.path.exists(marged_file_in_temp_path):
        current_app.logger.error(
            f"[Request {request_id}] 合并出现意外，合并结果文件不存在: {marged_file_in_temp_path}"
        )
        # 关闭并删除锁文件
        try:
            if lock_fd is not None:
                os.close(lock_fd)
            os.remove(lock_file_path)
            current_app.logger.info(
                f"[Request {request_id}] 合并锁已释放: {lock_file_path}"
            )
        except:
            pass
        return (
            jsonify(
                {
                    "error": "merge_failed",
                    "message": "文件合并失败",
                    "group_id": group.id,
                }
            ),
            500,
        )

    # 创建一个类文件对象供handle_file_upload使用
    class UploadedFile:
        def __init__(self, path, filename):
            self.path = path
            self.filename = filename
            self.content_type = "application/octet-stream"  # 默认内容类型

        def save(self, target_path):
            os.rename(self.path, target_path)

    file_upload = UploadedFile(marged_file_in_temp_path, resumable_filename)

    # 这时候就可以关闭并删除锁文件了
    try:
        if lock_fd is not None:
            os.close(lock_fd)
        os.remove(lock_file_path)
        current_app.logger.info(
            f"[Request {request_id}] 合并锁已释放: {lock_file_path}"
        )
    except:
        pass

    # 准备handle_file_upload参数
    upload_kwargs = {
        "group_id": group.id,
        "file": file_upload,
        "upload_folder": current_app.config["UPLOAD_FOLDER"],
        "uploader": request.args.get("uploader", "")
        or request.form.get("uploader", "anonymous"),
        "description": request.args.get("description", "")
        or request.form.get("description", ""),
        "comment": request.args.get("comment", "")
        or request.form.get("comment", "常规上传"),
    }

    # 根据是否为新文件设置不同参数
    if file_id:
        # 版本上传
        upload_kwargs["file_id"] = file_id
        upload_kwargs["description"] = request.args.get(
            "description", ""
        ) or request.form.get("description", "")
        upload_kwargs["comment"] = request.args.get("comment", "") or request.form.get(
            "comment", "版本更新"
        )

    # 处理文件上传
    new_file = handle_file_upload(**upload_kwargs)
    db.session.commit()

    # 清理临时分块文件
    cleanup_chunks(chunk_dir)

    # 最后检查一遍锁还在不在
    if os.path.exists(lock_file_path):
        current_app.logger.warning(
            f"[Request {request_id}] 锁文件仍然存在，请检查合并逻辑: {lock_file_path}"
        )

    return (
        jsonify(
            {
                "success": True,
                "message": "文件上传成功",
                "file_id": new_file.id,
                "group_id": group.id,
            }
        ),
        200,
    )


def all_chunks_uploaded(chunk_dir, total_chunks):
    """检查是否所有分块都已上传"""
    for i in range(1, total_chunks + 1):
        if not os.path.exists(os.path.join(chunk_dir, str(i))):
            return False
    return True


def merge_chunks(chunk_dir, filename, total_chunks):
    """合并所有分块文件"""
    final_file_path = os.path.join(chunk_dir, filename)
    with open(final_file_path, "wb") as final_file:
        for i in range(1, total_chunks + 1):
            chunk_file = os.path.join(chunk_dir, str(i))
            with open(chunk_file, "rb") as cf:
                final_file.write(cf.read())
    return final_file_path


def cleanup_chunks(chunk_dir):
    """清理临时分块文件"""
    import shutil

    shutil.rmtree(chunk_dir, ignore_errors=True)


@file.route("/download/<group_id>/<file_id>")
def download(group_id, file_id):
    file = File.query.get_or_404(file_id)
    return redirect(
        url_for(
            "file.download_version",
            group_id=group_id,
            file_id=file_id,
            version_id=file.versions[-1].id,
        )
    )


@file.route("/<group_id>/<file_id>/version/<version_id>")
def download_version(group_id, file_id, version_id):
    version = FileVersion.query.get_or_404(version_id)
    file = version.file

    # 添加调试日志
    current_app.logger.info(
        f"Download attempt - File ID: {file_id}, Version ID: {version_id}"
    )
    current_app.logger.info(f"File group ID: {file.group_id}, URL group ID: {group_id}")
    current_app.logger.info(f"Stored filename: {version.stored_filename}")

    # 构建并验证文件路径 - 使用统一配置
    file_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"], file.group_id, version.stored_filename
    )
    current_app.logger.info(f"Downloading from absolute path: {file_path}")
    current_app.logger.info(f"File exists: {os.path.exists(file_path)}")

    if not os.path.exists(file_path):
        current_app.logger.error(f"File not found at: {file_path}")
        # 返回500错误但提供明确的错误信息
        return (
            jsonify(
                {
                    "error": "文件不存在",
                    "message": "请联系管理员检查文件系统",
                    "file_path": file_path,
                }
            ),
            500,
        )
        # abort(404, description=f"File not found: {version.stored_filename}")

    # 使用绝对路径调用send_from_directory
    return send_from_directory(
        os.path.dirname(file_path),
        os.path.basename(file_path),
        as_attachment=True,
        download_name=file.original_filename,
    )


# 同时支持POST方法以兼容表单方法覆盖机制，DELETE用于直接API调用，POST用于表单提交
@file.route("/delete/<group_id>/<file_id>", methods=["POST", "DELETE"])
def delete_file(group_id, file_id):
    # 添加详细日志
    current_app.logger.info(
        f"删除请求 - 方法: {request.method}, 组ID: {group_id}, 文件ID: {file_id}"
    )
    current_app.logger.info(f"表单数据: {request.form.to_dict()}")
    current_app.logger.info(f"方法覆盖来源: {request.form.get('_method')}")

    group = Group.query.get_or_404(group_id)

    # 检查小组是否只读
    if group.is_readonly:
        return jsonify({"error": "该小组为只读，无法删除文件"}), 403

    file = File.query.get_or_404(file_id)

    # 删除文件和版本
    for version in file.versions:
        # 删除文件和版本 - 使用统一配置
        file_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], group_id, version.stored_filename
        )
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(file)
    db.session.commit()

    # 将原有的成功响应替换为重定向
    return redirect(url_for("group.view", group_id=group_id))


@file.route("/zip/<group_id>")
def zip_download(group_id):
    group = Group.query.get_or_404(group_id)

    # 创建内存中的ZIP文件
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in group.files:
            for version in file.versions:
                # 生成带版本号的文件名
                timestamp = version.uploaded_at.strftime("%m-%d-%H-%M-%S")
                versioned_filename = f"v-{timestamp}_{file.original_filename}"
                # 使用统一配置构建路径
                file_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    group_id,
                    version.stored_filename,
                )
                zf.write(file_path, versioned_filename)

    memory_file.seek(0)

    # 准备响应
    response = make_response(memory_file.getvalue())
    response.headers["Content-Disposition"] = (
        f"attachment; filename=group_{group_id}_files.zip"
    )
    response.headers["Content-type"] = "application/zip"

    return response


@file.route("/version_history/<group_id>/<file_id>")
def version_history(group_id, file_id):
    file = File.query.get_or_404(file_id)
    group = Group.query.get_or_404(group_id)
    # 按上传时间降序排列版本
    versions = sorted(file.versions, key=lambda v: v.uploaded_at, reverse=True)
    return render_template(
        "version_history.html", group=group, file=file, versions=versions
    )
