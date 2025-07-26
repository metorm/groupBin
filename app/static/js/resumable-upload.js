/**
 * 初始化Resumable.js上传组件
 * @param {Object} options - 配置选项
 * @param {string} options.target - 上传目标URL
 * @param {boolean} options.allowMultiple - 是否允许多选
 * @param {string} options.csrfToken - CSRF令牌
 * @param {string} options.groupId - 小组ID
 * @param {string} options.fileId - 文件ID（用于版本上传）
 * @param {boolean} options.isVersionUpload - 是否为版本上传
 */
function initializeResumableUpload(options) {
    // 检查必要的元素是否存在
    if (!document.getElementById('resumable-browse') || 
        !document.getElementById('resumable-upload')) {
        return;
    }
    
    // 获取可能不存在的元素
    var fileInput = document.getElementById('resumable-file-input');
    var uploaderElement = document.getElementById('resumable-uploader');
    var descriptionElement = document.getElementById('resumable-description');
    var commentElement = document.getElementById('resumable-comment');
    var fileListElement = document.getElementById('file-list');
    var selectedFilesListElement = document.getElementById('selected-files-list');
    var fileCountElement = document.getElementById('file-count');
    var uploadArea = document.getElementById('resumable-upload-area');
    var browseFolderButton = document.getElementById('resumable-browse-folder');
    
    // 如果必要元素不存在，则不初始化
    if (!uploaderElement || !fileInput || !uploadArea) {
        return;
    }
    
    // 获取allow_multiple参数
    var allowMultiple = options.allowMultiple;
    
    // 创建Resumable实例
    var r = new Resumable({
        target: options.target,
        chunkSize: 1024*1024, // 1MB
        simultaneousUploads: 3,
        testChunks: true,
        throttleProgressCallbacks: 1,
        method: "multipart",
        headers: {
            'X-CSRFToken': options.csrfToken
        },
        query: {
            uploader: uploaderElement.value,
            description: descriptionElement ? descriptionElement.value : '',
            comment: commentElement ? commentElement.value : ''
        }
    });
    
    // 检查浏览器是否支持
    if(!r.support) {
        alert('您的浏览器不支持分块上传，请更换浏览器或直接使用普通上传。');
    } else {
        // 分配事件
        // 文件选择按钮事件
        document.getElementById('resumable-browse').addEventListener('click', function() {
            fileInput.click();
        });
        
        // 文件夹选择按钮事件（仅在多选模式下存在）
        if (browseFolderButton && allowMultiple) {
            r.assignBrowse(browseFolderButton, true, true); // 第三个参数表示允许目录选择
        }
        
        // 文件拖拽区域
        r.assignDrop(document.getElementById('resumable-upload-area'));
        
        // 文件输入变化事件
        fileInput.addEventListener('change', function(e) {
            if (this.files) {
                for (var i = 0; i < this.files.length; i++) {
                    r.addFile(this.files[i]);
                }
                this.value = ''; // 清空输入框，以便下次选择相同文件时也能触发change事件
            }
        });
        
        // 文件添加事件
        r.on('fileAdded', function(file) {
            updateFileList();
            document.getElementById('resumable-upload').disabled = false;
        });
        
        // 文件移除事件
        r.on('fileRemoved', function(file) {
            updateFileList();
            if (r.files.length === 0) {
                document.getElementById('resumable-upload').disabled = true;
            }
        });
        
        // 上传按钮事件
        document.getElementById('resumable-upload').addEventListener('click', function() {
            // 更新上传参数
            r.opts.query.uploader = uploaderElement.value;
            if (descriptionElement) {
                r.opts.query.description = descriptionElement.value;
            }
            if (commentElement) {
                r.opts.query.comment = commentElement.value;
            }
            
            r.upload();
        });
        
        // 上传进度事件
        r.on('progress', function() {
            var progress = Math.floor(r.progress() * 100);
            document.getElementById('resumable-progress').style.display = 'block';
            document.getElementById('resumable-progress-bar').style.width = progress + '%';
            document.getElementById('resumable-progress-text').textContent = '上传进度: ' + progress + '%';
        });
        
        // 文件成功上传事件
        r.on('fileSuccess', function(file, message) {
            document.getElementById('resumable-progress-text').textContent = '上传成功!';
            setTimeout(function() {
                // 检查是否为版本上传，如果是则跳转到版本历史页面
                if (options.isVersionUpload && options.groupId && options.fileId) {
                    window.location.href = '/file/version_history/' + options.groupId + '/' + options.fileId;
                } else {
                    location.reload();
                }
            }, 1000);
        });
        
        // 文件上传错误事件
        r.on('fileError', function(file, message) {
            document.getElementById('resumable-progress-text').textContent = '上传失败: ' + message;
        });
        
        // 更新文件列表显示
        function updateFileList() {
            // 清空现有列表
            fileListElement.innerHTML = '';
            
            // 更新文件计数
            var fileCount = r.files.length;
            if (fileCount === 0) {
                fileCountElement.textContent = '（尚未选择文件）';
                selectedFilesListElement.style.display = 'none';
            } else {
                fileCountElement.textContent = `（已选择 ${fileCount} 个文件）`;
                selectedFilesListElement.style.display = 'block';
                
                // 添加每个文件到列表
                r.files.forEach(function(file) {
                    var li = document.createElement('li');
                    li.className = 'list-group-item d-flex justify-content-between align-items-center';
                    li.innerHTML = `
                        <div>
                            <div>${file.fileName}</div>
                            <small class="text-muted">${formatFileSize(file.size)}</small>
                        </div>
                        <button class="btn btn-sm btn-danger remove-file" data-file-unique-id="${file.uniqueIdentifier}">移除</button>
                    `;
                    fileListElement.appendChild(li);
                });
                
                // 为移除按钮添加事件监听器
                document.querySelectorAll('.remove-file').forEach(function(button) {
                    button.addEventListener('click', function() {
                        var fileUniqueId = this.getAttribute('data-file-unique-id');
                        var fileToRemove = r.files.find(function(file) {
                            return file.uniqueIdentifier === fileUniqueId;
                        });
                        if (fileToRemove) {
                            r.removeFile(fileToRemove);
                        }
                    });
                });
            }
        }
    }
    
    // 格式化文件大小的辅助函数
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}