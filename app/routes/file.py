from flask import Blueprint, request, jsonify, send_from_directory, redirect, url_for, flash, current_app, render_template
from app import db
from app.models import Group, File, FileVersion
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
import zipfile
from io import BytesIO
from app.utils.file_handling import handle_file_upload

file = Blueprint('file', __name__)

@file.route('/upload/<group_id>', methods=['POST'])
def upload(group_id):
    group = Group.query.get_or_404(group_id)
    
    # 检查小组是否只读
    if group.is_readonly:
        return jsonify({'error': '该小组为只读，无法上传文件'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': '未找到文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    if file:
        # 使用公共函数处理文件上传
        handle_file_upload(
            group_id=group_id,
            file=file,
            upload_folder=current_app.config['UPLOAD_FOLDER'],
            description=request.form.get('description', ''),
            uploader=request.form.get('uploader', 'anonymous'),
            comment=request.form.get('comment', '常规上传')
        )
        db.session.commit()
        return redirect(url_for('group.view', group_id=group_id))
        return jsonify({'success': True}), 201

@file.route('/download/<group_id>/<file_id>')
def download(group_id, file_id):
    file = File.query.get_or_404(file_id)
    return redirect(url_for('file.download_version', group_id=group_id, file_id=file_id, version_id=file.versions[-1].id))

@file.route('/<group_id>/<file_id>/version/<version_id>')
def download_version(group_id, file_id, version_id):
    version = FileVersion.query.get_or_404(version_id)
    file = version.file
    
    # 添加调试日志
    current_app.logger.info(f"Download attempt - File ID: {file_id}, Version ID: {version_id}")
    current_app.logger.info(f"File group ID: {file.group_id}, URL group ID: {group_id}")
    current_app.logger.info(f"Stored filename: {version.stored_filename}")
    
    # 构建并验证文件路径 - 使用统一配置
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.group_id, version.stored_filename)
    current_app.logger.info(f"Downloading from absolute path: {file_path}")
    current_app.logger.info(f"File exists: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        current_app.logger.error(f"File not found at: {file_path}")
        # 返回500错误但提供明确的错误信息
        return jsonify({
            'error': '文件不存在',
            'message': '请联系管理员检查文件系统',
            'file_path': file_path
        }), 500
        abort(404, description=f"File not found: {version.stored_filename}")
    
    # 使用绝对路径调用send_from_directory
    return send_from_directory(
        os.path.dirname(file_path),
        os.path.basename(file_path),
        as_attachment=True,
        download_name=file.original_filename
    )

# 同时支持POST方法以兼容表单方法覆盖机制，DELETE用于直接API调用，POST用于表单提交
@file.route('/delete/<group_id>/<file_id>', methods=['POST','DELETE'])
def delete_file(group_id, file_id):
    # 添加详细日志
    current_app.logger.info(f"删除请求 - 方法: {request.method}, 组ID: {group_id}, 文件ID: {file_id}")
    current_app.logger.info(f"表单数据: {request.form.to_dict()}")
    current_app.logger.info(f"方法覆盖来源: {request.form.get('_method')}")
    
    group = Group.query.get_or_404(group_id)
    
    # 检查小组是否只读
    if group.is_readonly:
        return jsonify({'error': '该小组为只读，无法删除文件'}), 403
    
    file = File.query.get_or_404(file_id)
    
    # 删除文件和版本
    for version in file.versions:
        # 删除文件和版本 - 使用统一配置
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], group_id, version.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.session.delete(file)
    db.session.commit()
    
    # 将原有的成功响应替换为重定向
    return redirect(url_for('group.view', group_id=group_id))

@file.route('/zip/<group_id>')
def zip_download(group_id):
    group = Group.query.get_or_404(group_id)
    
    # 创建内存中的ZIP文件
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in group.files:
            for version in file.versions:
                # 生成带版本号的文件名
                timestamp = version.uploaded_at.strftime('%m-%d-%H-%M-%S')
                versioned_filename = f'v-{timestamp}_{file.original_filename}'
                # 使用统一配置构建路径
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], group_id, version.stored_filename)
                zf.write(file_path, versioned_filename)
    
    memory_file.seek(0)
    
    # 准备响应
    response = make_response(memory_file.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=group_{group_id}_files.zip'
    response.headers['Content-type'] = 'application/zip'
    
    return response

@file.route('/version_history/<group_id>/<file_id>')
def version_history(group_id, file_id):
    file = File.query.get_or_404(file_id)
    group = Group.query.get_or_404(group_id)
    # 按上传时间降序排列版本
    versions = sorted(file.versions, key=lambda v: v.uploaded_at, reverse=True)
    return render_template('version_history.html', group=group, file=file, versions=versions)

@file.route('/upload_version/<group_id>/<file_id>', methods=['POST'])
def upload_version(group_id, file_id):
    group = Group.query.get_or_404(group_id)
    file = File.query.get_or_404(file_id)
    
    # 检查小组是否只读
    if group.is_readonly:
        return jsonify({'error': '该小组为只读，无法上传新版本'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': '未找到文件'}), 400
    
    file_upload = request.files['file']
    if file_upload.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    if file_upload:
        # 使用公共函数处理文件上传，作为新版本
        handle_file_upload(
            group_id=group_id,
            file=file_upload,
            upload_folder=current_app.config['UPLOAD_FOLDER'],
            description=file.description,  # 保持原描述
            uploader=request.form.get('uploader', 'anonymous'),
            comment=request.form.get('comment', '版本更新'),
            file_id=file_id  # 指定现有文件ID，表示版本更新
        )
        db.session.commit()
        return redirect(url_for('file.version_history', group_id=group_id, file_id=file_id))