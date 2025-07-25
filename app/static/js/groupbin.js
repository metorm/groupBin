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