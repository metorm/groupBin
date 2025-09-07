import os
import logging
from datetime import datetime, timedelta, timezone
from threading import Thread, Event
import time
from app import db
from app.models import Group, File, FileVersion
from sqlalchemy import and_

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
        interval = self.app.config.get('CLEAN_INTERVAL_HOUR')
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
        interval = self.app.config.get('CLEAN_INTERVAL_HOUR') * 3600  # 转换为秒，最小10分钟
        
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
            
            # 清理过期的session文件
            self._cleanup_expired_sessions()
            
        logger.info("定时清理任务执行完成")

    def _cleanup_expired_groups(self):
        """清理过期的小组"""
        delete_from_db_hours = self.app.config.get('CLEAN_INTERVAL_HOUR_DELETE_FROM_DB', 144)
        delete_data_hours = self.app.config.get('CLEAN_INTERVAL_HOUR_DELETE_DATA', 72)
        
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
                # 检查是否为tmp目录（用于分片上传的临时目录）
                if item == 'tmp':
                    # 清理tmp目录中的过期临时文件
                    self._cleanup_expired_temp_files(item_path)
                    continue
                    
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

    def _cleanup_expired_temp_files(self, tmp_dir):
        """清理tmp目录中过期的临时文件"""
        if not os.path.exists(tmp_dir):
            return
            
        # 设置过期时间（默认24小时）
        expiration_hours = self.app.config.get('TEMP_FILE_EXPIRATION_HOURS', 24)
        cutoff_time = time.time() - (expiration_hours * 3600)
        
        try:
            # 遍历tmp目录下的所有项目
            for item in os.listdir(tmp_dir):
                item_path = os.path.join(tmp_dir, item)
                
                # 检查是否为目录（每个上传任务的临时目录）
                if os.path.isdir(item_path):
                    # 检查目录的修改时间判断是否过期
                    dir_mtime = os.path.getmtime(item_path)
                    if dir_mtime < cutoff_time:
                        # 目录已过期，删除它
                        try:
                            import shutil
                            shutil.rmtree(item_path)
                            logger.info(f"删除过期临时目录: {item_path}")
                        except Exception as e:
                            logger.error(f"删除过期临时目录失败 {item_path}: {e}")
                    # 如果目录未过期，则保留它（可能正在上传中）
                
                # 检查是否为锁文件
                elif os.path.isfile(item_path) and item.endswith('.lock'):
                    # 检查锁文件的修改时间判断是否过期
                    lock_mtime = os.path.getmtime(item_path)
                    if lock_mtime < cutoff_time:
                        # 锁文件已过期，删除它
                        try:
                            os.remove(item_path)
                            logger.info(f"删除过期锁文件: {item_path}")
                        except Exception as e:
                            logger.error(f"删除过期锁文件失败 {item_path}: {e}")
                    # 如果锁文件未过期，则保留它（可能正在合并中）
                        
        except Exception as e:
            logger.error(f"清理临时文件时出错: {e}")

    def _cleanup_orphaned_files(self):
        """清理数据库中孤立的文件记录"""
        # 获取所有存在的小组ID
        group_ids = [group.id for group in Group.query.all()]
        
        # 查找不属于任何现有小组的文件
        # 将File.group_id转换为字符串进行比较
        orphaned_files = File.query.filter(~File.group_id.cast(db.String).in_([str(gid) for gid in group_ids])).all()
        for file in orphaned_files:
            logger.info(f"删除孤立文件记录: {file.original_filename} (ID: {file.id})")
            db.session.delete(file)
            
        # 查找不属于任何现有文件的文件版本
        file_ids = [file.id for file in File.query.all()]
        # 将FileVersion.file_id转换为字符串进行比较
        orphaned_versions = FileVersion.query.filter(~FileVersion.file_id.cast(db.String).in_([str(fid) for fid in file_ids])).all()
        for version in orphaned_versions:
            logger.info(f"删除孤立文件版本记录: {version.id}")
            db.session.delete(version)
            
        if orphaned_files or orphaned_versions:
            db.session.commit()
            logger.info(f"清理了 {len(orphaned_files)} 个孤立文件记录和 {len(orphaned_versions)} 个孤立文件版本记录")

    def _cleanup_expired_sessions(self):
        """清理过期的session文件"""
        session_dir = self.app.config.get('SESSION_FILE_DIR')
        if not session_dir or not os.path.exists(session_dir):
            return
            
        # 计算过期时间
        session_lifetime_hours = self.app.config.get('CLEAN_INTERVAL_HOUR_DELETE_CLIENT_SESSION', 720)
        cutoff_time = time.time() - (session_lifetime_hours * 3600)
        
        deleted_count = 0
        try:
            # 遍历session目录下的所有文件
            for item in os.listdir(session_dir):
                item_path = os.path.join(session_dir, item)
                # 检查是否为文件（而非目录）且已过期
                if os.path.isfile(item_path) and os.path.getmtime(item_path) < cutoff_time:
                    try:
                        os.remove(item_path)
                        deleted_count += 1
                        logger.info(f"删除过期session文件: {item_path}")
                    except Exception as e:
                        logger.error(f"删除过期session文件失败 {item_path}: {e}")
                        
            logger.info(f"清理了 {deleted_count} 个过期session文件")
        except Exception as e:
            logger.error(f"清理session文件时出错: {e}")