from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from app.models import Group, BrowserSession
from datetime import datetime 
import uuid

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # 获取浏览器ID（从cookie或生成新的）
    browser_id = request.cookies.get('browser_id')
    if not browser_id:
        browser_id = str(uuid.uuid4())
    
    # 获取该浏览器访问过的小组
    recent_groups = []
    if browser_id:
        sessions = BrowserSession.query.filter_by(browser_id=browser_id).order_by(BrowserSession.last_accessed.desc()).all()
        recent_groups = [session.group for session in sessions if not session.group.is_expired()]
    
    # 将datetime模块传递给模板
    return render_template('index.html', recent_groups=recent_groups, browser_id=browser_id, datetime=datetime)


@main.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404