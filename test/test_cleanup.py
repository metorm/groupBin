import unittest
import tempfile
import os
import shutil
from datetime import datetime, timedelta, timezone
from app import create_app, db
from app.models import Group, File, FileVersion
from app.utils.cleanup import CleanupTask


class CleanupTestCase(unittest.TestCase):
    def setUp(self):
        """在每个测试前设置环境"""
        self.app = create_app('testing')
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # 创建临时目录用于测试
        self.test_upload_dir = tempfile.mkdtemp()
        self.app.config['UPLOAD_FOLDER'] = self.test_upload_dir

    def tearDown(self):
        """在每个测试后清理环境"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
        # 清理临时目录
        if os.path.exists(self.test_upload_dir):
            shutil.rmtree(self.test_upload_dir)

    def test_cleanup_expired_groups_from_db(self):
        """测试清理过期很久的小组"""
        # 创建一个过期很久的小组
        old_group = Group(
            name="Old Group",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=200)  # 200小时前过期
        )
        db.session.add(old_group)
        db.session.commit()
        
        # 确保小组已创建
        groups = Group.query.all()
        self.assertEqual(len(groups), 1)
        
        # 执行清理任务
        cleanup = CleanupTask(self.app)
        cleanup._cleanup_expired_groups()
        
        # 检查小组是否被删除
        groups = Group.query.all()
        self.assertEqual(len(groups), 0)

    def test_cleanup_expired_groups_files(self):
        """测试清理过期小组的文件"""
        # 创建一个过期的小组（在删除数据但不删除数据库记录的时间范围内）
        group = Group(
            name="Recent Expired Group",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=100)  # 100小时前过期
        )
        db.session.add(group)
        db.session.commit()
        
        # 创建小组目录和文件
        group_dir = os.path.join(self.test_upload_dir, group.id)
        os.makedirs(group_dir, exist_ok=True)
        
        test_file_path = os.path.join(group_dir, "test.txt")
        with open(test_file_path, "w") as f:
            f.write("test content")
        
        # 确保目录和文件已创建
        self.assertTrue(os.path.exists(group_dir))
        self.assertTrue(os.path.exists(test_file_path))
        
        # 执行清理任务
        cleanup = CleanupTask(self.app)
        cleanup._cleanup_expired_groups()
        
        # 检查小组目录是否被删除
        self.assertFalse(os.path.exists(group_dir))

    def test_cleanup_orphaned_files_on_disk(self):
        """测试清理磁盘上的孤立文件"""
        # 创建一个正常小组
        group = Group(name="Test Group")
        db.session.add(group)
        db.session.commit()
        
        # 创建小组目录
        group_dir = os.path.join(self.test_upload_dir, group.id)
        os.makedirs(group_dir, exist_ok=True)
        
        # 创建一个属于小组的文件
        valid_file_path = os.path.join(group_dir, "valid.txt")
        with open(valid_file_path, "w") as f:
            f.write("valid content")
            
        # 创建一个孤立目录（不属于任何小组）
        orphaned_dir = os.path.join(self.test_upload_dir, "orphaned_dir")
        os.makedirs(orphaned_dir, exist_ok=True)
        
        orphaned_file_path = os.path.join(orphaned_dir, "orphaned.txt")
        with open(orphaned_file_path, "w") as f:
            f.write("orphaned content")
            
        # 创建一个孤立文件（直接在上传目录下）
        orphaned_file = os.path.join(self.test_upload_dir, "orphaned_file.txt")
        with open(orphaned_file, "w") as f:
            f.write("orphaned file content")
        
        # 确保所有文件和目录都存在
        self.assertTrue(os.path.exists(valid_file_path))
        self.assertTrue(os.path.exists(orphaned_dir))
        self.assertTrue(os.path.exists(orphaned_file_path))
        self.assertTrue(os.path.exists(orphaned_file))
        
        # 执行清理任务
        cleanup = CleanupTask(self.app)
        cleanup._cleanup_orphaned_files_on_disk()
        
        # 检查有效文件仍然存在，孤立文件和目录已被删除
        self.assertTrue(os.path.exists(valid_file_path))  # 有效文件应保留
        self.assertFalse(os.path.exists(orphaned_dir))    # 孤立目录应被删除
        self.assertFalse(os.path.exists(orphaned_file))   # 孤立文件应被删除

    def test_cleanup_orphaned_files_from_db(self):
        """测试清理数据库中的孤立文件记录"""
        # 创建一个小组
        group = Group(name="Test Group")
        db.session.add(group)
        db.session.commit()
        
        # 创建属于小组的文件
        file1 = File(
            group_id=group.id,
            original_filename="file1.txt",
            stored_filename="stored_file1.txt",
            size=100,
            content_type="text/plain"
        )
        db.session.add(file1)
        
        # 创建不属于任何小组的孤立文件
        file2 = File(
            group_id="nonexistent_group_id",
            original_filename="file2.txt",
            stored_filename="stored_file2.txt",
            size=200,
            content_type="text/plain"
        )
        db.session.add(file2)
        db.session.commit()
        
        # 确保两个文件记录都存在
        files = File.query.all()
        self.assertEqual(len(files), 2)
        
        # 执行清理任务
        cleanup = CleanupTask(self.app)
        cleanup._cleanup_orphaned_files()
        
        # 检查孤立文件是否被删除，有效文件是否保留
        files = File.query.all()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].id, file1.id)

    def test_cleanup_with_zero_interval(self):
        """测试当清理间隔设置为0时的行为"""
        # 设置清理间隔为0
        self.app.config['CLEAN_INTERVAL_HOUR'] = 0
        self.app.config['CLEAN_INTERVAL_HOUR_DELETE_DATA'] = 0
        self.app.config['CLEAN_INTERVAL_HOUR_DELETE_FROM_DB'] = 0
        
        # 创建清理任务
        cleanup = CleanupTask(self.app)
        
        # 检查是否会启动任务（应该不会启动）
        cleanup.start()
        # 由于间隔为0，任务应该不会真正启动
        self.assertIsNone(cleanup.thread)
        
    def test_cleanup_with_negative_interval(self):
        """测试当清理间隔设置为负数时的行为"""
        # 设置清理间隔为负数
        self.app.config['CLEAN_INTERVAL_HOUR'] = -1
        self.app.config['CLEAN_INTERVAL_HOUR_DELETE_DATA'] = -5
        self.app.config['CLEAN_INTERVAL_HOUR_DELETE_FROM_DB'] = -10
        
        # 创建清理任务
        cleanup = CleanupTask(self.app)
        
        # 检查是否会启动任务（应该不会启动）
        cleanup.start()
        # 由于间隔为负数，任务应该不会真正启动
        self.assertIsNone(cleanup.thread)

    def test_cleanup_with_minimum_interval(self):
        """测试当清理间隔设置为最小值（10分钟）时的行为"""
        # 设置清理间隔为最小值
        self.app.config['CLEAN_INTERVAL_HOUR'] = 1/6  # 10分钟
        self.app.config['CLEAN_INTERVAL_HOUR_DELETE_DATA'] = 1/6  # 10分钟
        self.app.config['CLEAN_INTERVAL_HOUR_DELETE_FROM_DB'] = 1/6  # 10分钟
        
        # 创建清理任务
        cleanup = CleanupTask(self.app)
        
        # 检查是否会启动任务（应该会启动）
        cleanup.start()
        # 由于间隔为正数，任务应该会启动
        self.assertIsNotNone(cleanup.thread)
        
        # 停止任务
        cleanup.stop()


if __name__ == '__main__':
    unittest.main()