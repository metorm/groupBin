/**
 * 格式化剩余时间显示
 * @param {string} expiresAt - UTC格式的过期时间字符串
 * @returns {string} 格式化后的剩余时间文本
 */
function formatTimeDifference(expiresAt) {
    const expiresDate = new Date(expiresAt);
    const now = new Date();
    const diffMs = expiresDate - now;

    // 已过期
    if (diffMs <= 0) {
        return '已过期';
    }

    // 计算时间差
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    // 格式化显示
    if (diffDays > 0) {
        const remainingHours = diffHours % 24;
        return `${diffDays}天${remainingHours > 0 ? `${remainingHours}小时` : ''}`;
    } else if (diffHours > 0) {
        const remainingMinutes = diffMinutes % 60;
        return `${diffHours}小时${remainingMinutes > 0 ? `${remainingMinutes}分钟` : ''}`;
    } else {
        return `${diffMinutes}分钟`;
    }
}

/**
 * 格式化文件大小显示
 * @param {number} bytes - 文件大小（字节）
 * @returns {string} 格式化后的文件大小文本
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 更新页面上所有过期时间显示
 */
function updateAllExpirationTimes() {
    // 更新历史记录中的时间显示
    document.querySelectorAll('.expiration-time').forEach(element => {
        const expiresAt = element.dataset.expiresAt;
        if (expiresAt) {
            element.textContent = formatTimeDifference(expiresAt);
        }
    });
}

// 初始加载时更新一次
document.addEventListener('DOMContentLoaded', updateAllExpirationTimes);

// 每分钟更新一次
setInterval(updateAllExpirationTimes, 60000);


// 通用文件上传处理
function initializeUploadForms() {
    document.querySelectorAll('.upload-form:not([data-initialized])').forEach(form => {
        const formId = form.id || `form-${Date.now()}`; // 为表单生成唯一标识
        form.id = formId; // 确保ID存在
        form.dataset.initialized = "true"; // 添加初始化标记

        // 添加事件绑定日志
        console.log(`[${new Date().toISOString()}] 为表单 ${formId} 绑定提交事件`);

        form.addEventListener('submit', handleFormSubmit);
    });
}

async function handleFormSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.innerHTML;
    const formId = form.id;
    const fileInput = form.querySelector('input[type="file"]');
    const files = fileInput.files;

    // 防止重复提交
    if (form.dataset.submitting === 'true' || files.length === 0) return;
    form.dataset.submitting = 'true';
    submitButton.disabled = true;
    submitButton.innerHTML = '处理中...';

    try {
        const csrfToken = getCookie('csrf_token');
        const actionUrl = form.action;
        const uploadPromises = [];

        console.log(`[${new Date().toISOString()}] 开始上传 ${files.length} 个文件`);

        // 为每个文件创建单独的上传请求
        Array.from(files).forEach(file => {
            const formData = new FormData();
            // 复制表单其他字段
            Array.from(form.elements).forEach(element => {
                if (element.name && element.type !== 'file') {
                    formData.append(element.name, element.value);
                }
            });
            // 添加单个文件
            formData.append(fileInput.name, file, file.name);

            // 创建上传Promise
            uploadPromises.push(new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', actionUrl);
                xhr.withCredentials = true;
                xhr.setRequestHeader('X-CSRFToken', csrfToken);

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        console.log(`[${new Date().toISOString()}] 文件 ${file.name} 上传成功`);
                        resolve(file.name);
                    } else {
                        reject(new Error(`文件 ${file.name} 上传失败: HTTP ${xhr.status}`));
                    }
                };

                xhr.onerror = () => reject(new Error(`文件 ${file.name} 网络错误`));
                xhr.send(formData);
            }));
        });

        // 等待所有上传完成
        const results = await Promise.allSettled(uploadPromises);
        const successCount = results.filter(r => r.status === 'fulfilled').length;

        // 显示汇总结果
        showNotification(`${successCount}/${files.length} 个文件上传成功`, successCount === files.length ? 'success' : 'warning');
        console.log(`[${new Date().toISOString()}] 所有文件上传完成，成功 ${successCount} 个`);

        // 全部完成后刷新页面
        if (successCount > 0) {
            // 重置表单
            form.reset();
            // 短暂延迟后刷新，确保用户看到成功提示
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }

    } catch (error) {
        console.error(`[${new Date().toISOString()}] 上传处理错误: ${error.message}`);
        showNotification(`上传失败: ${error.message}`, 'danger');
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = originalButtonText;
        form.dataset.submitting = 'false';
    }
}

// 工具函数：获取Cookie
function getCookie(name) {
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

// 工具函数：显示通知
function showNotification(message, type) {
    console.log("开始显示通知……");

    // 创建toast元素
    const toast = document.createElement('div');

    // 设置背景颜色映射
    const typeColors = {
        success: '#10b981', // 绿色
        danger: '#ef4444',  // 红色
        info: '#3b82f6',    // 蓝色
        warning: '#f59e0b'  // 黄色
    };

    const bgColor = typeColors[type] || '#3b82f6';

    // 设置内联样式确保可见性
    toast.style.position = 'fixed';
    toast.style.top = '50%';
    toast.style.left = '50%';
    toast.style.transform = 'translate(-50%, -50%)';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
    toast.style.color = 'white';
    toast.style.backgroundColor = bgColor;
    toast.style.zIndex = '9999';
    toast.style.fontFamily = 'sans-serif';
    toast.style.fontSize = '32px';
    toast.style.textAlign = 'center';

    // 设置内容
    toast.textContent = message;

    // 添加到页面
    document.body.appendChild(toast);

    // 3秒后自动关闭
    setTimeout(() => {
        // 添加淡出动画
        toast.style.transition = 'opacity 0.3s ease-out';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 1200);
}

// 页面加载时初始化所有上传表单，确保只初始化一次
if (typeof uploadFormsInitialized === 'undefined') {
    var uploadFormsInitialized = false;
}

document.addEventListener('DOMContentLoaded', function () {
    if (!uploadFormsInitialized) {
        initializeUploadForms();
        uploadFormsInitialized = true;
    }
});

// 通用UTC时间转换为本地时间函数
document.addEventListener('DOMContentLoaded', function () {
    const convertUtcToLocalTime = () => {
        const utcElements = document.querySelectorAll('.utc-time');
        utcElements.forEach(element => {
            const utcTime = element.getAttribute('data-utc');
            if (!utcTime) return;

            const date = new Date(utcTime);
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');

            // 根据规范，只显示月、日和时间，隐去年份
            const localTimeString = `${month}-${day} ${hours}:${minutes}`;
            element.textContent = localTimeString;
        });
    };

    // 执行转换
    convertUtcToLocalTime();

    // 暴露全局函数供动态内容加载后调用
    window.convertUtcToLocalTime = convertUtcToLocalTime;
});