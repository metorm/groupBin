/**
 * 小组访问历史Cookie管理器
 * 完全客户端实现，不依赖后端存储
 */
const GroupHistoryManager = {
    // 默认配置
    config: {
        cookieName: 'group_history',
        cookiePath: '/',
        maxItems: 10,
        cookieExpiresDays: 30
    },

    /**
     * 获取当前小组历史记录
     * @returns {Array} 小组历史记录数组
     */
    getHistory() {
        try {
            const cookieValue = document.cookie
                .split('; ')
                .find(row => row.startsWith(`${this.config.cookieName}=`))
                ?.split('=')[1];

            if (!cookieValue) return [];

            return JSON.parse(decodeURIComponent(cookieValue));
        } catch (error) {
            console.error('Failed to parse group history cookie:', error);
            return [];
        }
    },

    /**
     * 更新小组历史记录
     * @param {Object} groupInfo 小组信息对象
     * @param {string} groupInfo.id 小组ID
     * @param {string} groupInfo.name 小组名称
     * @param {string} [groupInfo.description] 小组描述
     * @param {string} groupInfo.expiresAt 小组过期时间(UTC)
     */
    updateHistory(groupInfo) {
        if (!groupInfo || !groupInfo.id || !groupInfo.name) {
            console.error('[HistoryManager] 无效的groupInfo:', groupInfo);
            return;
        }

        // 获取当前历史记录
        let history = this.getHistory() || [];

        // 检查是否已存在该记录并移除（用于置顶最新访问）
        const existingIndex = history.findIndex(item => item.id === groupInfo.id);
        if (existingIndex > -1) {
            const removedItem = history.splice(existingIndex, 1)[0];
            console.log('[HistoryManager] 已移除旧记录，ID:', removedItem.id);
        }

        // 1. 仅保留ID和截断后的名称（不记录时间戳）
        // 2. 使用宽字符截断函数处理名称（18字符限制）
        const truncatedName = this.truncateWideString(groupInfo.name, 18);
        const minimalGroupInfo = {
            id: groupInfo.id,
            expiresAt: groupInfo.expiresAt,
            name: truncatedName
        };

        // 将新记录添加到开头（最新记录在前）
        history.unshift(minimalGroupInfo);

        // 3. 循环删除最旧记录直到Cookie长度低于4000字节
        let cookieString = `${this.config.cookieName}=${encodeURIComponent(JSON.stringify(history))}; path=${this.config.cookiePath}; max-age=${this.config.cookieExpiresDays * 24 * 60 * 60}; SameSite=Lax`;

        // 检查并调整Cookie大小
        while (cookieString.length > 4000 && history.length > 0) {
            const removedItem = history.pop(); // 删除最后一条（最旧的）记录
            console.warn('[HistoryManager] Cookie超过大小限制，已删除最旧记录:', removedItem.id);
            // 重新生成Cookie字符串
            cookieString = `${this.config.cookieName}=${encodeURIComponent(JSON.stringify(history))}; path=${this.config.cookiePath}; max-age=${this.config.cookieExpiresDays * 24 * 60 * 60}; SameSite=Lax`;
        }

        // 保存到Cookie
        document.cookie = cookieString;
        console.log('[HistoryManager] 历史记录已更新，当前记录数:', history.length);
    },

    /**
     * 从历史记录中移除指定小组
     * @param {string} groupId 小组ID
     */
    removeFromHistory(groupId) {
        let history = this.getHistory().filter(item => item.id !== groupId);
        this._saveHistory(history);
    },

    /**
     * 将历史记录保存到Cookie
     * @param {Array} history 小组历史记录数组
     */
    _saveHistory(history) {
        document.cookie = `${this.config.cookieName}=${encodeURIComponent(JSON.stringify(history))}; path=/; max-age=${this.config.cookieExpiresDays * 24 * 60 * 60}; SameSite=Lax`;
    },

    /**
     * 处理小组访问错误（404或过期）
     * @param {string} groupId 小组ID
     */
    handleGroupError(groupId) {
        this.removeFromHistory(groupId);
    },

    // 宽字符截断辅助函数
    truncateWideString(str, maxLength) {
        let length = 0;
        let result = '';

        for (let i = 0; i < str.length; i++) {
            // 宽字符（如中文、日文、韩文等）算2个长度单位
            const charLength = /[\u4e00-\u9fa5\u3000-\u303f\uFF00-\uFFEF]/.test(str[i]) ? 2 : 1;

            if (length + charLength > maxLength) {
                break;
            }

            result += str[i];
            length += charLength;
        }

        return result;
    }
};

// 暴露到全局作用域
window.GroupHistoryManager = GroupHistoryManager;
