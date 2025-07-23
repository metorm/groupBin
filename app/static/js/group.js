// 小组文件操作JavaScript
// 从URL获取小组ID
const groupId = window.location.pathname.split('/')[2];

// 文件上传处理
document.addEventListener('DOMContentLoaded', function () {
    const fileUpload = document.getElementById('file-upload');
    const fileList = document.getElementById('file-list');
    const uploadForm = document.getElementById('upload-form');
    const uploadProgressContainer = document.getElementById('upload-progress-container');
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    const uploadStatus = document.getElementById('upload-status');

    // 监听文件选择变化，动态添加描述输入框
    if (fileUpload) {
        fileUpload.addEventListener('change', function (e) {
            const files = e.target.files;
            const fileDescriptions = document.getElementById('file-descriptions');
            fileDescriptions.innerHTML = '';

            if (files.length > 0) {
                // 显示上传区域
                document.getElementById('upload-area').style.display = 'block';
            }

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const fileDiv = document.createElement('div');
                fileDiv.className = 'file-description-item';
                fileDiv.innerHTML = `
                    <span>${file.name} (${formatFileSize(file.size)})</span>
                    <input type="text" name="file_description_${i}" placeholder="文件描述（可选）" class="form-control mt-1 mb-2">
                    <input type="hidden" name="file_name_${i}" value="${file.name}">
                `;
                fileDescriptions.appendChild(fileDiv);
            }
        });
    }

    // 处理文件上传表单提交
    if (uploadForm) {
        uploadForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const files = fileUpload.files;

            if (files.length === 0) {
                showNotification('请先选择文件', 'warning');
                return;
            }

            const formData = new FormData();
            // 添加文件和描述
            for (let i = 0; i < files.length; i++) {
                formData.append('files[]', files[i]);
                const descriptionInput = document.querySelector(`input[name="file_description_${i}"]`);
                if (descriptionInput) {
                    formData.append(`descriptions[]`, descriptionInput.value || '');
                }
            }

            // 显示上传进度
            uploadProgressContainer.style.display = 'block';
            uploadStatus.textContent = '开始上传...';

            // 发送文件上传请求
            fetch(`/group/${groupId}/upload`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrf_token')
                },
                credentials: 'include'
            })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(data => {
                            throw new Error(data.error || '上传失败');
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    uploadStatus.textContent = '上传成功！';
                    uploadProgressBar.style.width = '100%';
                    showNotification('文件上传成功', 'success');
                    // 重置表单并刷新文件列表
                    uploadForm.reset();
                    document.getElementById('file-descriptions').innerHTML = '';
                    document.getElementById('upload-area').style.display = 'none';
                    setTimeout(() => {
                        uploadProgressContainer.style.display = 'none';
                        uploadProgressBar.style.width = '0%';
                        // 重新加载页面以显示新上传的文件
                        location.reload();
                    }, 1500);
                })
                .catch(error => {
                    uploadStatus.textContent = '上传失败';
                    showNotification(`上传失败: ${error.message}`, 'danger');
                    console.error('上传错误:', error);
                });
        });
    }

    // 为所有删除按钮添加事件监听器
    document.querySelectorAll('.delete-file-btn').forEach(button => {
        button.addEventListener('click', function () {
            const fileId = this.getAttribute('data-file-id');
            const fileName = this.getAttribute('data-file-name');
            if (confirm(`确认删除文件${fileName}吗？`)) {
                // 显示删除中状态
                const row = this.closest('tr');
                row.classList.add('deleting');
                this.disabled = true;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 删除中...';

                // 发送删除请求
                fetch(`/group/${groupId}/file/${fileId}/delete`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrf_token')
                    },
                    credentials: 'include',
                    body: JSON.stringify({ file_id: fileId })
                })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(data => {
                                throw new Error(data.error || '删除失败');
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        showNotification('文件已成功删除', 'success');
                        // 添加删除动画
                        row.classList.add('deleted');
                        setTimeout(() => {
                            row.remove();
                        }, 500);
                    })
                    .catch(error => {
                        showNotification(`删除失败: ${error.message}`, 'danger');
                        row.classList.remove('deleting');
                        this.disabled = false;
                        this.innerHTML = '<i class="fas fa-trash"></i> 删除';
                        console.error('删除错误:', error);
                    });
            }
        });
    });
});

// 辅助函数：格式化文件大小
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 辅助函数：获取Cookie
export function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 辅助函数：显示通知
export function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification alert alert-${type}`;
    notification.innerHTML = `
        <div class="notification-content">${message}</div>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;

    // 添加到页面
    document.body.appendChild(notification);

    // 显示动画
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);

    // 关闭按钮事件
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    });

    // 自动关闭
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
}