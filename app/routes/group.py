from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
import logging 
import datetime
from datetime import timedelta, timezone
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, current_app
from app import db
from app.models import Group, File, FileVersion  # 添加FileVersion模型导入
import string
import random
import os
import uuid 
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app.utils.file_handling import handle_file_upload 

group = Blueprint('group', __name__)

@group.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        # 处理表单数据
        group_name = request.form.get('group_name', '')
        duration_hours = int(request.form.get('duration', 72))
        password = request.form.get('password', '')
        allow_convert_to_readonly = request.form.get('allow_convert_to_readonly') == 'on'
        
        # 创建新小组
        new_group = Group(
            name=group_name,
            created_duration_hours=duration_hours,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(hours=duration_hours),
            is_readonly=False,  # 初始为可写
            allow_convert_to_readonly=allow_convert_to_readonly,
            creator=request.form.get('creator', '')
        )
        
        # 设置密码
        new_group.set_password(password)
        
        # 保存到数据库
        db.session.add(new_group)
        db.session.commit()
       
        # 创建小组文件夹
        group_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], new_group.id)
        os.makedirs(group_folder, exist_ok=True)

        return redirect(url_for('group.view', group_id=new_group.id))
    
    # GET请求显示创建表单
    return render_template('create_group.html')

@group.route('/<group_id>')
def view(group_id):
    # 添加详细日志
    #current_app.logger.info(f"访问小组页面 - group_id: {group_id}")
    #current_app.logger.info(f"请求来源: {request.referrer}")
    #current_app.logger.info(f"当前时间: {datetime.datetime.now(timezone.utc)}")
    
    group = Group.query.get_or_404(group_id)
    #current_app.logger.info(f"找到小组: {group.id}, 名称: {group.name}, 创建时间: {group.created_at}, 过期时间: {group.expires_at}")
    
    # 检查是否过期
    is_expired = group.is_expired()
    #current_app.logger.info(f"小组是否过期: {is_expired}")
    
    if is_expired:
        current_app.logger.warning(f"小组已过期，重定向到过期页面: {group_id}")
        return render_template('group_expired.html', group=group)

    #current_app.logger.info(f"准备渲染小组页面: {group_id}")
    return render_template('group.html', group=group, files=group.files, datetime=datetime)

@group.route('/<group_id>/refresh')
def refresh(group_id):
    group = Group.query.get_or_404(group_id)
    group.refresh_expiration()
    db.session.commit()
    flash('小组有效期已刷新', 'success')
    return redirect(url_for('group.view', group_id=group_id))

@group.route('/<group_id>/convert-to-readonly', methods=['POST'])
def convert_to_readonly(group_id):
    group = Group.query.get_or_404(group_id)
    
    # 检查是否允许转换且当前不是只读
    if not group.allow_convert_to_readonly or group.is_readonly:
        return jsonify({
            'success': False,
            'message': '无法转换为只读小组'
        }), 400
    
    # 执行转换
    group.is_readonly = True
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '小组已成功转换为只读状态'
    })