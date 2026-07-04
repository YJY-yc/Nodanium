// background.js - 拦截下载并转发给 Nodanium
// 使用 chrome API（Manifest V3 推荐）

const HOST_NAME = 'com.nodanium.downloader';

// 拦截下载事件
chrome.downloads.onCreated.addListener(async (downloadItem) => {
  console.log('📥 拦截到下载:', downloadItem.url);
  
  // 1. 取消浏览器自带下载
  try {
    await chrome.downloads.cancel(downloadItem.id);
    await chrome.downloads.erase({ id: downloadItem.id });
  } catch (e) {
    console.log('取消浏览器下载:', e);
  }
  
  // 2. 获取当前页面的Cookie
  try {
    const cookies = await getCookiesForUrl(downloadItem.url);
    
    // 3. 获取Referer
    const referer = downloadItem.referrer || new URL(downloadItem.url).origin;
    
    // 4. 发送到 Nodanium
    await sendToNodanium({
      url: downloadItem.url,
      filename: downloadItem.filename || getFilenameFromUrl(downloadItem.url),
      cookies: cookies,
      referer: referer,
      userAgent: navigator.userAgent,
      timestamp: Date.now()
    });
    
    showNotification('✅ 下载已转发', `Nodanium 开始下载: ${getFilenameFromUrl(downloadItem.url)}`);
    
  } catch (error) {
    console.error('❌ 转发失败:', error);
    showNotification('❌ 转发失败', error.message || '请确保 Nodanium 已正确安装');
  }
});

// 获取Cookie
function getCookiesForUrl(url) {
  return new Promise((resolve) => {
    try {
      chrome.cookies.getAll({ url: url }, (cookies) => {
        if (chrome.runtime.lastError) {
          console.warn('获取Cookie失败:', chrome.runtime.lastError);
          resolve('');
          return;
        }
        const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join('; ');
        resolve(cookieStr);
      });
    } catch (e) {
      resolve('');
    }
  });
}

// 从URL提取文件名
function getFilenameFromUrl(url) {
  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname;
    const filename = pathname.split('/').pop() || 'download';
    return decodeURIComponent(filename);
  } catch {
    return 'download';
  }
}

// 发送到 Nodanium
function sendToNodanium(data) {
  return new Promise((resolve, reject) => {
    try {
      const port = chrome.runtime.connectNative(HOST_NAME);
      
      // 设置超时
      const timeout = setTimeout(() => {
        port.disconnect();
        reject(new Error('连接超时，请确保 Nodanium 在环境变量中'));
      }, 5000);
      
      port.onMessage.addListener((response) => {
        clearTimeout(timeout);
        console.log('Nodanium 响应:', response);
        resolve(response);
      });
      
      port.onDisconnect.addListener(() => {
        clearTimeout(timeout);
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(`连接断开: ${error.message || 'Nodanium 未响应'}`));
        } else {
          resolve({ status: 'ok', message: '已发送' });
        }
      });
      
      // 发送数据
      port.postMessage(data);
      
    } catch (error) {
      reject(new Error(`发送失败: ${error.message}`));
    }
  });
}

// 显示通知
function showNotification(title, message) {
  try {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon.png',
      title: title,
      message: message,
      priority: 2
    });
  } catch (e) {
    console.log(`${title}: ${message}`);
  }
}

// 监听来自popup的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'manualDownload') {
    // 手动添加下载链接
    getCookiesForUrl(message.url).then((cookies) => {
      const referer = new URL(message.url).origin;
      sendToNodanium({
        url: message.url,
        filename: getFilenameFromUrl(message.url),
        cookies: cookies,
        referer: referer,
        userAgent: navigator.userAgent,
        timestamp: Date.now()
      }).then(() => {
        sendResponse({ success: true });
      }).catch((error) => {
        sendResponse({ success: false, error: error.message });
      });
    });
    return true; // 异步响应
  }
  
  if (message.type === 'ping') {
    // 测试连接
    sendToNodanium({ type: 'ping' })
      .then(() => sendResponse({ status: 'ok' }))
      .catch(() => sendResponse({ status: 'error' }));
    return true;
  }
});

console.log('🚀 Nodanium 下载拦截器已启动');
console.log('📌 等待下载事件...');