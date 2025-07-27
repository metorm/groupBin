# GroupBin 技术文档

## 项目概述

GroupBin 是一个基于 Flask 的文件共享平台，支持大文件分片上传、小组管理、文件版本控制等功能。该项目专为需要临时或长期文件共享的团队设计，具有简洁的界面和强大的功能。

## 技术架构

### 后端技术栈
- **Python 3.x**: 主要编程语言
- **Flask**: Web 框架
- **Flask-SQLAlchemy**: ORM 数据库工具
- **SQLite**: 默认数据库（可配置为其他数据库）
- **Flask-Login**: 用户认证管理
- **Flask-WTF**: CSRF 保护
- **Flask-CORS**: 跨域资源共享支持

### 前端技术栈
- **Bootstrap 5**: 响应式界面框架
- **Resumable.js**: 大文件分片上传库
- **Bootstrap Icons**: 图标库
- **原生 JavaScript**: 交互逻辑处理

### 核心功能模块

#### 1. 小组管理 (Group Management)
- 小组创建与管理
- 密码保护机制
- 只读模式支持
- 自动过期与手动刷新
- 小组链接复制功能

#### 2. 文件上传 (File Upload)
- 大文件分片上传（基于 Resumable.js）
- 单文件和多文件上传支持
- 断点续传功能
- 文件大小限制配置
- 分片大小可配置

#### 3. 文件管理 (File Management)
- 文件版本控制
- 文件描述和上传者信息
- 文件下载和删除
- 文件列表展示

#### 4. 权限控制 (Access Control)
- 小组密码验证
- 只读/读写权限控制
- CSRF 保护
- 文件访问控制

## 项目结构

```
groupbin/
├── app/                    # Flask 应用主目录
│   ├── __init__.py         # 应用初始化
│   ├── models.py           # 数据模型定义
│   ├── routes/             # 路由控制器
│   │   ├── main.py         # 主页路由
│   │   ├── group.py        # 小组相关路由
│   │   └── file.py         # 文件相关路由
│   ├── templates/          # HTML 模板
│   ├── static/             # 静态资源
│   │   ├── css/            # 样式文件
│   │   ├── js/             # JavaScript 文件
│   │   └── svg/            # SVG 图标
│   └── utils/              # 工具函数
│       └── file_handling.py # 文件处理工具
├── config.py              # 配置文件
├── run.py                 # 应用启动文件
├── .env                   # 环境变量配置
└── environment.yml        # Conda 环境配置
```

## 核心组件详解

### 数据模型

#### Group (小组)
- `id`: UUID 主键
- `name`: 小组名称
- `created_at`: 创建时间
- `expires_at`: 过期时间
- `password_hash`: 密码哈希值
- `is_readonly`: 是否为只读模式
- `created_duration_hours`: 创建时设置的有效期
- `creator`: 创建者信息
- `allow_convert_to_readonly`: 是否允许转为只读

#### File (文件)
- `id`: UUID 主键
- `group_id`: 所属小组ID（外键）
- `original_filename`: 原始文件名
- `stored_filename`: 存储文件名（UUID）
- `description`: 文件描述
- `size`: 文件大小（字节）
- `uploaded_at`: 上传时间
- `content_type`: 内容类型

#### FileVersion (文件版本)
- `id`: UUID 主键
- `file_id`: 所属文件ID（外键）
- `stored_filename`: 存储文件名（UUID）
- `uploaded_at`: 上传时间
- `uploader`: 上传者
- `comment`: 版本注释
- `size`: 文件大小（字节）

### 文件上传机制

#### Resumable.js 集成
项目使用 Resumable.js 实现大文件分片上传，具有以下特点：
1. **分片上传**: 将大文件分割成小块分别上传
2. **断点续传**: 支持上传中断后继续上传
3. **并发控制**: 同时上传多个分片以提高效率
4. **错误重试**: 自动重试失败的分片

#### 上传流程
1. 前端使用 Resumable.js 将文件分片上传到后端
2. 后端接收每个分片并保存到临时目录
3. 当所有分片上传完成后，后端合并分片生成完整文件
4. 合并后的文件移动到最终存储位置
5. 数据库记录文件信息

#### 并发处理
为防止多个请求同时处理同一个文件的分片合并，项目实现了基于文件锁的并发控制：
1. 使用文件锁机制防止重复合并
2. 只有处理最后一个分片的请求才会触发合并操作
3. 其他请求检测到锁存在时直接返回

### 配置管理

#### 环境变量 (.env)
- `SECRET_KEY`: Flask 密钥
- `SQLALCHEMY_DATABASE_URI`: 数据库连接字符串
- `UPLOAD_FOLDER`: 文件上传目录
- `MAX_UPLOAD_SIZE_MB`: 最大上传文件大小（MB）
- `CHUNK_SIZE_MB`: 分片大小（MB）
- `MAX_RECENT_GROUPS`: 最近小组数量限制
- `DEFAULT_GROUP_DURATION_HOURS`: 默认小组有效期（小时）
- `MAX_GROUP_DURATION_HOURS`: 最大小组有效期（小时）
- `SITE_NAME`: 站点名称
- `SITE_DESCRIPTION`: 站点描述
- `FOOTER_TEXT`: 页脚文本
- `AUTH_DELAY_SECONDS`: 认证延迟时间（秒）
- `EXPIRED_FILE_CLEANUP_DAYS`: 过期文件清理天数
- `UNIFIED_PUBLIC_PASSWORD`: 统一密码

#### 配置类 (config.py)
- `Config`: 基础配置类
- `DevelopmentConfig`: 开发环境配置
- `ProductionConfig`: 生产环境配置

## 关键技术实现

### 大文件上传处理

#### 分片合并机制
1. 每个分片上传到临时目录
2. 检测所有分片是否上传完成
3. 只有最后一个分片的请求触发合并操作
4. 使用文件锁防止并发合并
5. 合并完成后移动文件到最终位置

#### 文件锁机制
为防止并发问题，项目实现了基于文件的锁机制：
```python
# 创建锁文件
lock_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tmp', f"{request.remote_addr}_{resumable_identifier}.lock")

# 尝试获取锁
fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
```

### 多文件上传支持

前端通过跟踪已上传完成的文件数量来正确处理多文件上传：
1. 使用 `completedFiles` 计数器跟踪完成的文件
2. 在所有文件上传完成后才刷新页面
3. 提供上传进度反馈

### 错误处理与日志记录

#### 日志系统
- 使用 Flask 内置日志系统
- 记录关键操作和错误信息
- 支持不同日志级别

#### 异常处理
- 数据库操作异常处理
- 文件操作异常处理
- 网络请求异常处理

## 部署与运维

### 环境要求
- Python 3.7+
- SQLite 3+ (或其他兼容 SQLAlchemy 的数据库)
- pip 或 conda 包管理器

### 安装步骤
1. 克隆项目代码
2. 创建虚拟环境
3. 安装依赖: `pip install -r requirements.txt` 或使用 `environment.yml`
4. 配置 `.env` 文件
5. 初始化数据库: `python run.py`
6. 启动服务: `python run.py`

### 配置说明
- 修改 `.env` 文件中的配置项
- 根据需要调整分片大小和上传限制
- 配置合适的日志级别

## 性能优化

### 文件系统优化
- 使用 UUID 生成唯一文件名避免冲突
- 实现文件写入完成检测机制
- 采用分片上传减少内存占用

### 数据库优化
- 合理设计索引
- 使用级联删除维护数据一致性
- 批量操作减少数据库访问

### 并发优化
- 文件锁机制防止重复操作
- 分片并发上传提高效率
- 连接池优化数据库访问

## 安全考虑

### 认证与授权
- 小组密码保护
- CSRF 保护
- 只读模式控制

### 数据安全
- 密码哈希存储
- 文件路径安全处理
- 输入验证与过滤

### 网络安全
- HTTPS 支持
- CORS 配置
- 请求频率限制

## 扩展性设计

### 模块化架构
- 功能模块分离
- 可插拔组件设计
- 清晰的接口定义

### 可配置性
- 环境变量配置
- 动态参数调整
- 灵活的扩展点

## 常见问题与解决方案

### 上传失败问题
- 检查分片大小配置
- 验证文件系统权限
- 确认网络连接稳定性

### 并发冲突问题
- 检查文件锁机制
- 验证临时目录权限
- 确认系统时间同步

### 性能问题
- 调整分片大小
- 优化数据库索引
- 增加系统资源

## 后续维护建议

1. 定期清理过期文件和小组
2. 监控系统日志和错误报告
3. 根据使用情况调整配置参数
4. 定期备份数据库和重要文件
5. 关注安全更新和漏洞修复