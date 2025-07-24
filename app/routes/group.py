from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
import logging 
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, current_app
from app import db
from app.models import Group, BrowserSession, File, FileVersion  # 添加FileVersion模型导入
from datetime import datetime, timedelta
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
        is_readonly = request.form.get('is_readonly') == 'on'
        
        # 创建新小组
        new_group = Group(
            name=group_name,
            created_duration_hours=duration_hours,
            expires_at=datetime.utcnow() + timedelta(hours=duration_hours),
            is_readonly=is_readonly
        )
        
        # 设置密码
        new_group.set_password(password)
        
        # 保存到数据库
        db.session.add(new_group)
        db.session.commit()
        
        # 处理浏览器会话
        browser_id = request.cookies.get('browser_id')
        if not browser_id:
            browser_id = str(uuid.uuid4())
        
        # 添加到浏览器会话
        new_session = BrowserSession(browser_id=browser_id, group_id=new_group.id)
        db.session.add(new_session)
        db.session.commit()
        
        # 创建小组文件夹
        group_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], new_group.id)
        os.makedirs(group_folder, exist_ok=True)

        # 处理上传的初始文件
        for file in request.files.getlist('file'):
            if file.filename:
                # 使用公共函数处理文件上传
                handle_file_upload(
                    group_id=new_group.id,
                    file=file,
                    upload_folder=current_app.config['UPLOAD_FOLDER'],
                    uploader='初始上传',
                    comment='小组创建时上传'
                )
        
        # 提交文件记录到数据库
        db.session.commit()

        # 创建响应并设置cookie
        response = make_response(redirect(url_for('group.view', group_id=new_group.id)))
        response.set_cookie('browser_id', browser_id, max_age=30*24*3600)  # 30天有效期
        
        return response
    
    # GET请求显示创建表单
    return render_template('create_group.html')

@group.route('/<group_id>')
def view(group_id):
    # 添加详细日志
    current_app.logger.info(f"访问小组页面 - group_id: {group_id}")
    current_app.logger.info(f"请求来源: {request.referrer}")
    current_app.logger.info(f"当前时间: {datetime.utcnow()}")
    
    group = Group.query.get_or_404(group_id)
    current_app.logger.info(f"找到小组: {group.id}, 名称: {group.name}, 创建时间: {group.created_at}, 过期时间: {group.expires_at}")
    
    # 检查是否过期
    is_expired = group.is_expired()
    current_app.logger.info(f"小组是否过期: {is_expired}")
    
    if is_expired:
        current_app.logger.warning(f"小组已过期，重定向到过期页面: {group_id}")
        return render_template('group_expired.html', group=group)
    
    # 更新最近访问时间
    browser_id = request.cookies.get('browser_id')
    current_app.logger.info(f"浏览器ID: {browser_id}")
    response = make_response(render_template('group.html', group=group, files=group.files, datetime=datetime))
    
    if browser_id:
        session = BrowserSession.query.filter_by(browser_id=browser_id, group_id=group_id).first()
        current_app.logger.info(f"找到会话: {session.id if session else 'None'}")
        if session:
            session.last_accessed = datetime.utcnow()
            db.session.commit()
            current_app.logger.info(f"更新会话访问时间: {session.id}")
    else:
        browser_id = str(uuid.uuid4())
        response.set_cookie('browser_id', browser_id, max_age=30*24*3600)
        new_session = BrowserSession(browser_id=browser_id, group_id=group_id)
        db.session.add(new_session)
        db.session.commit()
        current_app.logger.info(f"创建新会话: {browser_id}")
    
    current_app.logger.info(f"准备渲染小组页面: {group_id}")
    return response

@group.route('/<group_id>/refresh')
def refresh(group_id):
    group = Group.query.get_or_404(group_id)
    group.refresh_expiration()
    db.session.commit()
    flash('小组有效期已刷新', 'success')
    return redirect(url_for('group.view', group_id=group_id))