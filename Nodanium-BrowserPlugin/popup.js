// popup.js - 弹出窗口交互

document.addEventListener('DOMContentLoaded', () => {
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const testBtn = document.getElementById('testBtn');
  const manualUrl = document.getElementById('manualUrl');
  const sendManualBtn = document.getElementById('sendManualBtn');
  const clearCacheBtn = document.getElementById('clearCacheBtn');

  // 更新状态
  function updateStatus(online, message) {
    if (online) {
      statusDot.className = 'status-dot online';
      statusText.textContent = message || '已连接';
    } else {
      statusDot.className = 'status-dot offline';
      statusText.textContent = message || '未连接';
    }
  }

  // 测试连接
  testBtn.addEventListener('click', async () => {
    testBtn.disabled = true;
    testBtn.textContent = '⏳ 测试中...';
    updateStatus(false, '测试中...');

    try {
      const response = await chrome.runtime.sendMessage({ type: 'ping' });
      if (response && response.status === 'ok') {
        updateStatus(true, '✅ 已连接');
      } else {
        updateStatus(false, '❌ 连接失败');
      }
    } catch (error) {
      updateStatus(false, `❌ ${error.message || '连接失败'}`);
    } finally {
      testBtn.disabled = false;
      testBtn.textContent = '🔗 测试连接';
    }
  });

  // 发送手动输入的URL
  sendManualBtn.addEventListener('click', async () => {
    const url = manualUrl.value.trim();
    if (!url) {
      alert('请输入下载链接');
      return;
    }

    try {
      new URL(url);
    } catch {
      alert('请输入有效的URL');
      return;
    }

    sendManualBtn.disabled = true;
    sendManualBtn.textContent = '⏳ 发送中...';

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'manualDownload',
        url: url
      });
      
      if (response && response.success) {
        alert('✅ 已发送到 Nodanium');
        manualUrl.value = '';
      } else {
        alert('❌ 发送失败: ' + (response?.error || '未知错误'));
      }
    } catch (error) {
      alert('❌ 发送失败: ' + error.message);
    } finally {
      sendManualBtn.disabled = false;
      sendManualBtn.textContent = '发送';
    }
  });

  // 清除缓存
  clearCacheBtn.addEventListener('click', () => {
    if (confirm('确定要清除所有缓存数据吗？')) {
      chrome.storage.sync.clear(() => {
        chrome.storage.local.clear(() => {
          alert('✅ 缓存已清除');
          updateStatus(false, '已重置');
        });
      });
    }
  });

  // 初始状态
  updateStatus(true, '就绪');
});