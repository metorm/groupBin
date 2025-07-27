from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    current_app,
)
import datetime
from datetime import timedelta, timezone
from app import db
from app.models import Group  # 添加FileVersion模型导入
import os

group = Blueprint("group", __name__)


@group.before_request
def update_last_activity():
    """更新用户最后活动时间"""
    session["last_activity"] = datetime.datetime.now(timezone.utc).timestamp()


@group.route("/create", methods=["GET", "POST"])
def create():
    # 检查是否需要创建小组密码验证
    create_group_password = current_app.config.get("CREATE_GROUP_PUBLIC_PASSWORD")
    if create_group_password:
        # 检查用户是否已经通过创建小组密码验证
        authenticated = session.get("create_group_authenticated", False)
        if not authenticated:
            if request.method == "POST":
                password = request.form.get("password", "")
                if password == create_group_password:
                    # 密码正确，标记为已验证
                    session["create_group_authenticated"] = True
                    next_url = request.form.get("next", url_for("group.create"))
                    return redirect(next_url)
                else:
                    flash("建组权限密码错误，请重试", "danger")

            # 显示统一密码输入页面
            return render_template(
                "unified_password.html",
                title="建组权限验证",
                message="本站设置了建组权限密码，请输入公用建组密码以创建小组。",
                next_url=request.url,
            )

    if request.method == "POST":
        # 处理表单数据
        group_name = request.form.get("group_name", "")
        duration_hours = int(request.form.get("duration", 72))
        password = request.form.get("password", "")
        allow_convert_to_readonly = (
            request.form.get("allow_convert_to_readonly") == "on"
        )

        # 创建新小组
        new_group = Group(
            name=group_name,
            created_duration_hours=duration_hours,
            expires_at=datetime.datetime.now(timezone.utc)
            + timedelta(hours=duration_hours),
            is_readonly=False,  # 初始为可写
            allow_convert_to_readonly=allow_convert_to_readonly,
            creator=request.form.get("creator", ""),
        )

        # 设置密码
        new_group.set_password(password)

        # 保存到数据库
        db.session.add(new_group)
        db.session.commit()

        # 创建小组文件夹
        group_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], new_group.id)
        os.makedirs(group_folder, exist_ok=True)

        return redirect(url_for("group.view", group_id=new_group.id))

    # GET请求显示创建表单
    create_group_password_enabled = (
        len(current_app.config.get("CREATE_GROUP_PUBLIC_PASSWORD")) > 0
    )
    return render_template(
        "create_group.html", unified_password=create_group_password_enabled
    )


@group.route("/<group_id>", methods=["GET", "POST"])
def view(group_id):
    # 添加详细日志
    # current_app.logger.info(f"访问小组页面 - group_id: {group_id}")
    # current_app.logger.info(f"请求来源: {request.referrer}")
    # current_app.logger.info(f"当前时间: {datetime.datetime.now(timezone.utc)}")

    group = Group.query.get_or_404(group_id)
    # current_app.logger.info(f"找到小组: {group.id}, 名称: {group.name}, 创建时间: {group.created_at}, 过期时间: {group.expires_at}")

    # 检查是否过期
    is_expired = group.is_expired()
    # current_app.logger.info(f"小组是否过期: {is_expired}")

    if is_expired:
        current_app.logger.warning(f"小组已过期，重定向到过期页面: {group_id}")
        return render_template("group_expired.html", group=group)

    # 检查是否需要统一密码验证（针对未设置密码的小组）
    unified_password = current_app.config.get("UNIFIED_PUBLIC_PASSWORD")
    if (
        not group.password_hash and unified_password
    ):  # 小组未设置密码但系统设置了统一密码
        # 检查用户是否已经通过统一密码验证
        authenticated = session.get("unified_password_authenticated", False)
        if not authenticated:
            if request.method == "POST" and request.form.get("password"):
                # 用户提交了密码
                password = request.form.get("password", "")
                if password == unified_password:  # 密码正确
                    # 标记为已验证
                    session["unified_password_authenticated"] = True
                    # 重定向到小组页面，避免表单重新提交
                    return redirect(url_for("group.view", group_id=group_id))
                else:  # 密码错误
                    flash("小组公用密码错误，请重试", "danger")

            # 显示统一密码输入页面
            return render_template(
                "unified_password.html",
                title="小组受公用密码保护",
                message="建组时未设置密码，但本站设置了小组公用密码保护，请输入小组公用密码。",
                group=group,
                next_url=request.url,
            )

    # 检查小组是否有密码保护
    if group.password_hash:  # 小组有密码保护
        # 检查用户是否已经通过密码验证
        authenticated_groups = session.get("authenticated_groups", [])
        if group_id not in authenticated_groups:  # 用户尚未通过验证
            if request.method == "POST":  # 用户提交了密码
                password = request.form.get("password", "")
                if group.check_password(password):  # 密码正确
                    # 将小组ID添加到已验证列表中
                    authenticated_groups.append(group_id)
                    session["authenticated_groups"] = authenticated_groups
                    # 重定向到小组页面，避免表单重新提交
                    return redirect(url_for("group.view", group_id=group_id))
                else:  # 密码错误
                    flash("小组访问密码错误，请重试", "danger")

            # 显示统一密码输入页面（用于小组独立密码）
            return render_template(
                "unified_password.html",
                title="小组受独立密码保护",
                message="此小组受独立密码保护，请输入建组是设置的密码以继续访问。",
                group=group,
                next_url=request.url,
            )

    # current_app.logger.info(f"准备渲染小组页面: {group_id}")
    return render_template(
        "group.html", group=group, files=group.files, datetime=datetime
    )


@group.route("/<group_id>/refresh")
def refresh(group_id):
    group = Group.query.get_or_404(group_id)
    group.refresh_expiration()
    db.session.commit()
    flash("小组有效期已刷新", "success")
    return redirect(url_for("group.view", group_id=group_id))


@group.route("/<group_id>/convert-to-readonly", methods=["POST"])
def convert_to_readonly(group_id):
    group = Group.query.get_or_404(group_id)

    # 检查是否允许转换且当前不是只读
    if not group.allow_convert_to_readonly or group.is_readonly:
        return jsonify({"success": False, "message": "无法转换为只读小组"}), 400

    # 执行转换
    group.is_readonly = True
    db.session.commit()

    return jsonify({"success": True, "message": "小组已成功转换为只读状态"})