from flask import Blueprint, request, jsonify, send_from_directory, redirect, url_for, flash, current_app, render_template, make_response
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

file = Blueprint('file', __name__, url_prefix='/file')

def handle_upload_common(group, file=None, redirect_endpoint=None, redirect_params=None):
    # 检查小组是否只读
    if group.is_readonly:
        return jsonify({
            'error': 'permission_denied',
            'message': '该小组为只读，无法上传文件',
            'group_id': group.id,
            'is_readonly': True
        }), 403
    
    if 'file' not in request.files:
        return jsonify({
            'error': 'no_file',
            'message': '未找到文件',
            'group_id': group.id
        }), 400
    
    file_upload = request.files['file']
    if file_upload.filename == '':
        return jsonify({
            'error': 'empty_filename',
            'message': '未选择文件',
            'group_id': group.id
        }), 400
    
    if file_upload:
        # 准备handle_file_upload参数
        upload_kwargs = {
            'group_id': group.id,
            'file': file_upload,
            'upload_folder': current_app.config['UPLOAD_FOLDER'],
            'uploader': request.form.get('uploader', 'anonymous')
        }
        
        # 根据是否为新文件设置不同参数
        if file:
            # 版本上传
            upload_kwargs['file_id'] = file.id
            upload_kwargs['description'] = file.description
            upload_kwargs['comment'] = request.form.get('comment', '版本更新')
        else:
            # 新文件上传
            upload_kwargs['description'] = request.form.get('description', '')
            upload_kwargs['comment'] = request.form.get('comment', '常规上传')
        
        # 处理文件上传
        new_file = handle_file_upload(**upload_kwargs)  # Capture the returned file object
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'file_id': new_file.id if not file else file.id,
            'group_id': group.id
        }), 200 if file else 201
    
    return jsonify({
        'error': 'upload_failed',
        'message': '文件上传失败',
        'group_id': group.id
    }), 500


@file.route('/upload/<group_id>', methods=['GET', 'POST'])
def upload(group_id):
    # 检查是否是Resumable.js的分块上传请求
    resumable_identifier = request.form.get('resumableIdentifier', '')
    resumable_filename = request.form.get('resumableFilename', '')
    resumable_chunk_number = request.form.get('resumableChunkNumber', '')
    
    # 也检查URL参数中的Resumable.js标识
    if not resumable_identifier:
        resumable_identifier = request.args.get('resumableIdentifier', '')
        resumable_filename = request.args.get('resumableFilename', '')
        resumable_chunk_number = request.args.get('resumableChunkNumber', '')
    
    if resumable_identifier:
        # 处理Resumable.js上传
        if request.method == 'GET':
            # 检查分块是否已经上传
            return check_chunk(group_id, resumable_identifier, resumable_chunk_number)
        elif request.method == 'POST':
            # 处理分块上传
            return handle_resumable_upload(group_id, resumable_identifier, resumable_filename, resumable_chunk_number)
    
    # 处理普通的表单上传
    if request.method == 'POST':
        group = Group.query.get_or_404(group_id)
        return handle_upload_common(
            group=group,
            redirect_endpoint='group.view',
            redirect_params={'group_id': group_id}
        )
    
    # 如果是GET请求但不是Resumable.js的检查请求，则返回405
    return jsonify({'error': 'Method not allowed'}), 405

def check_chunk(group_id, resumable_identifier, resumable_chunk_number):
    """检查分块是否已存在"""
    # 构建分块文件路径
    chunk_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tmp', resumable_identifier)
    chunk_file = os.path.join(chunk_dir, str(resumable_chunk_number))
    
    # 检查分块是否已存在
    if os.path.exists(chunk_file):
        return 'found', 200
    else:
        return 'not_found', 204  # 204表示分块不存在，需要上传

def handle_resumable_upload(group_id, resumable_identifier, resumable_filename, resumable_chunk_number, file_id=None):
    """处理Resumable.js上传请求"""
    group = Group.query.get_or_404(group_id)
    
    # 检查小组是否只读
    if group.is_readonly:
        return jsonify({
            'error': 'permission_denied',
            'message': '该小组为只读，无法上传文件',
            'group_id': group.id,
            'is_readonly': True
        }), 403
    
    # 创建临时目录存储分块
    chunk_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tmp', resumable_identifier)
    os.makedirs(chunk_dir, exist_ok=True)
    
    # 保存上传的分块
    chunk_file = os.path.join(chunk_dir, str(resumable_chunk_number))
    uploaded_file = request.files['file']
    uploaded_file.save(chunk_file)
    
    # 检查是否所有分块都已上传完成
    resumable_total_chunks = int(request.args.get('resumableTotalChunks', 0) or request.form.get('resumableTotalChunks', 0))
    if all_chunks_uploaded(chunk_dir, resumable_total_chunks):
        # 合并所有分块
        final_file_path = merge_chunks(chunk_dir, resumable_filename, resumable_total_chunks)
        
        # 创建一个类文件对象供handle_file_upload使用
        class UploadedFile:
            def __init__(self, path, filename):
                self.path = path
                self.filename = filename
                self.content_type = 'application/octet-stream'  # 默认内容类型
            
            def save(self, target_path):
                os.rename(self.path, target_path)
        
        file_upload = UploadedFile(final_file_path, resumable_filename)
        
        # 准备handle_file_upload参数
        upload_kwargs = {
            'group_id': group.id,
            'file': file_upload,
            'upload_folder': current_app.config['UPLOAD_FOLDER'],
            'uploader': request.args.get('uploader', '') or request.form.get('uploader', 'anonymous'),
            'description': request.args.get('description', '') or request.form.get('description', ''),
            'comment': request.args.get('comment', '') or request.form.get('comment', '常规上传')
        }
        
        # 根据是否为新文件设置不同参数
        if file_id:
            # 版本上传
            upload_kwargs['file_id'] = file_id
            upload_kwargs['description'] = request.args.get('description', '') or request.form.get('description', '')
            upload_kwargs['comment'] = request.args.get('comment', '') or request.form.get('comment', '版本更新')
        
        # 处理文件上传
        new_file = handle_file_upload(**upload_kwargs)
        db.session.commit()
        
        # 清理临时分块文件
        cleanup_chunks(chunk_dir)
        
        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'file_id': new_file.id,
            'group_id': group.id
        }), 200
    else:
        return 'chunk_uploaded', 200

def all_chunks_uploaded(chunk_dir, total_chunks):
    """检查是否所有分块都已上传"""
    for i in range(1, total_chunks + 1):
        if not os.path.exists(os.path.join(chunk_dir, str(i))):
            return False
    return True

def merge_chunks(chunk_dir, filename, total_chunks):
    """合并所有分块文件"""
    final_file_path = os.path.join(chunk_dir, filename)
    with open(final_file_path, 'wb') as final_file:
        for i in range(1, total_chunks + 1):
            chunk_file = os.path.join(chunk_dir, str(i))
            with open(chunk_file, 'rb') as cf:
                final_file.write(cf.read())
    return final_file_path

def cleanup_chunks(chunk_dir):
    """清理临时分块文件"""
    import shutil
    shutil.rmtree(chunk_dir, ignore_errors=True)

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

@file.route('/upload_version/<group_id>/<file_id>', methods=['GET', 'POST'])
def upload_version(group_id, file_id):
    # 检查是否是Resumable.js的分块上传请求
    resumable_identifier = request.form.get('resumableIdentifier', '')
    resumable_filename = request.form.get('resumableFilename', '')
    resumable_chunk_number = request.form.get('resumableChunkNumber', '')
    
    # 也检查URL参数中的Resumable.js标识
    if not resumable_identifier:
        resumable_identifier = request.args.get('resumableIdentifier', '')
        resumable_filename = request.args.get('resumableFilename', '')
        resumable_chunk_number = request.args.get('resumableChunkNumber', '')
    
    if resumable_identifier:
        # 处理Resumable.js上传
        if request.method == 'GET':
            # 检查分块是否已经上传
            return check_chunk(group_id, resumable_identifier, resumable_chunk_number)
        elif request.method == 'POST':
            # 处理分块上传
            return handle_resumable_upload(group_id, resumable_identifier, resumable_filename, resumable_chunk_number, file_id)
    
    group = Group.query.get_or_404(group_id)
    file = File.query.get_or_404(file_id)
    return handle_upload_common(
        group=group,
        file=file,
        redirect_endpoint='file.version_history',
        redirect_params={'group_id': group_id, 'file_id': file_id}
    )
