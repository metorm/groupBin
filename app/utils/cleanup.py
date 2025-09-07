import os
import logging
from datetime import datetime, timedelta, timezone
from threading import Thread, Event
import time
from app import db
from app.models import Group, File, FileVersion
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)

class CleanupTask:
    def __init__(self, app):
        self.app = app
        self.stop_event = Event()
        self.thread = None

    def start(self):
        """启动定时清理任务"""
        if self.thread is not None and self.thread.is_alive():
            logger.warning("清理任务已经在运行中")
            return
            
        # 检查是否启用清理任务（如果间隔设置为0或负数，则不启动）
        interval = max(self.app.config.get('CLEAN_INTERVAL_HOUR', 3), 1/6)
        if interval <= 0:
            logger.info("清理任务间隔设置为0或负数，不启动清理任务")
            return
            
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"定时清理任务已启动，间隔: {interval} 小时")

    def stop(self):
        """停止定时清理任务"""
        if self.thread is None:
            logger.warning("清理任务未启动")
            return
            
        self.stop_event.set()
        self.thread.join()
        logger.info("定时清理任务已停止")

    def _run(self):
        """运行定时清理任务"""
        interval = max(self.app.config.get('CLEAN_INTERVAL_HOUR', 3), 1/6) * 3600  # 转换为秒，最小10分钟
        
        while not self.stop_event.wait(interval):
            try:
                self._perform_cleanup()
            except Exception as e:
                logger.error(f"执行清理任务时出错: {e}")

    def _perform_cleanup(self):
        """执行清理任务"""
        logger.info("开始执行定时清理任务")
        
        with self.app.app_context():
            # 清理过期的小组和相关文件
            self._cleanup_expired_groups()
            
            # 清理数据库中孤立的文件记录
            self._cleanup_orphaned_files()
            
            # 清理文件系统中的孤立文件
            self._cleanup_orphaned_files_on_disk()
            
        logger.info("定时清理任务执行完成")

    def _cleanup_expired_groups(self):
        """清理过期的小组"""
        delete_from_db_hours = max(self.app.config.get('CLEAN_INTERVAL_HOUR_DELETE_FROM_DB', 144), 1/6)
        delete_data_hours = max(self.app.config.get('CLEAN_INTERVAL_HOUR_DELETE_DATA', 72), 1/6)
        
        cutoff_time_db = datetime.now(timezone.utc) - timedelta(hours=delete_from_db_hours)
        cutoff_time_data = datetime.now(timezone.utc) - timedelta(hours=delete_data_hours)
        
        # 删除数据库中过期很久的小组
        old_groups = Group.query.filter(Group.expires_at < cutoff_time_db).all()
        for group in old_groups:
            logger.info(f"删除过期小组: {group.name} (ID: {group.id})")
            db.session.delete(group)
        
        # 删除文件系统中过期的小组文件
        expired_groups = Group.query.filter(
            and_(
                Group.expires_at < cutoff_time_data,
                Group.expires_at >= cutoff_time_db
            )
        ).all()
        
        for group in expired_groups:
            # 删除小组目录中的所有文件
            group_dir = os.path.join(self.app.config['UPLOAD_FOLDER'], group.id)
            if os.path.exists(group_dir):
                try:
                    import shutil
                    shutil.rmtree(group_dir)
                    logger.info(f"删除小组目录: {group_dir}")
                except Exception as e:
                    logger.error(f"删除小组目录失败 {group_dir}: {e}")
        
        if old_groups or expired_groups:
            db.session.commit()
            logger.info(f"清理了 {len(old_groups)} 个过期小组记录和 {len(expired_groups)} 个过期小组文件")

    def _cleanup_orphaned_files_on_disk(self):
        """清理磁盘上的孤立文件"""
        upload_folder = self.app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            return
            
        # 获取所有小组ID
        group_ids = [str(group.id) for group in Group.query.all()]
        
        # 遍历上传目录
        for item in os.listdir(upload_folder):
            item_path = os.path.join(upload_folder, item)
            
            # 如果是目录且不是任何现有小组的目录，则删除
            if os.path.isdir(item_path) and item not in group_ids:
                try:
                    import shutil
                    shutil.rmtree(item_path)
                    logger.info(f"删除孤立目录: {item_path}")
                except Exception as e:
                    logger.error(f"删除孤立目录失败 {item_path}: {e}")
                    
            # 如果是文件且不在任何小组中，则删除（处理遗留文件）
            elif os.path.isfile(item_path):
                # 检查是否有关联的文件记录
                file_exists = File.query.filter_by(stored_filename=item).first() is not None
                version_exists = FileVersion.query.filter_by(stored_filename=item).first() is not None
                
                if not file_exists and not version_exists:
                    try:
                        os.remove(item_path)
                        logger.info(f"删除孤立文件: {item_path}")
                    except Exception as e:
                        logger.error(f"删除孤立文件失败 {item_path}: {e}")

    def _cleanup_orphaned_files(self):
        """清理数据库中孤立的文件记录"""
        # 获取所有存在的小组ID
        group_ids = [str(group.id) for group in Group.query.all()]
        
        # 查找不属于任何现有小组的文件
        orphaned_files = File.query.filter(~File.group_id.in_(group_ids)).all()
        for file in orphaned_files:
            logger.info(f"删除孤立文件记录: {file.original_filename} (ID: {file.id})")
            db.session.delete(file)
            
        # 查找不属于任何现有文件的文件版本
        file_ids = [str(file.id) for file in File.query.all()]
        orphaned_versions = FileVersion.query.filter(~FileVersion.file_id.in_(file_ids)).all()
        for version in orphaned_versions:
            logger.info(f"删除孤立文件版本记录: {version.id}")
            db.session.delete(version)
            
        if orphaned_files or orphaned_versions:
            db.session.commit()
            logger.info(f"清理了 {len(orphaned_files)} 个孤立文件记录和 {len(orphaned_versions)} 个孤立文件版本记录")