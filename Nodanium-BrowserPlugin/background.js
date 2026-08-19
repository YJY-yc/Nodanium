// background.js - 拦截下载并转发给 Nodanium 内下载模块
const HOST_NAME = 'com.nodanium.yujy';

let hostPort = null;
let pendingReplies = new Map();
let seq = 0;

// ---------------------------------------------------------------------------
// 真实请求头缓存：通过 webRequest.onBeforeSendHeaders 捕获浏览器实际发送的
// 请求头（含 Referer / User-Agent / Accept / Authorization / Cookie 等），
// 在转交 Nodanium 时一并传给下载程序，保证下载使用与浏览器一致的请求头。
// ---------------------------------------------------------------------------
const headerCache = new Map();   // url -> { headers, ts }
const HEADER_CACHE_TTL = 60 * 60 * 1000;  // 1 小时有效
const HEADER_CACHE_MAX = 500;

function captureHeaders(details) {
  // tabId<0 表示后台/扩展自身发起的请求，跳过
  if (details.tabId < 0) return;
  const url = details.url;
  if (!/^https?:/.test(url)) return;
  const headers = {};
  (details.requestHeaders || []).forEach((h) => {
    if (h.name) headers[h.name.toLowerCase()] = h.value != null ? String(h.value) : '';
  });
  headerCache.set(url, { headers, ts: Date.now() });
  // 简单剪枝，避免无限增长
  if (headerCache.size > HEADER_CACHE_MAX) {
    const now = Date.now();
    for (const [k, v] of headerCache) {
      if (now - v.ts > HEADER_CACHE_TTL || headerCache.size > HEADER_CACHE_MAX) {
        headerCache.delete(k);
      }
    }
  }
}

function getCachedHeaders(url) {
  const hit = headerCache.get(url);
  if (hit && Date.now() - hit.ts <= HEADER_CACHE_TTL) return hit.headers;
  return null;
}

// 注册 webRequest 监听（Chrome MV3 只读；Firefox MV2 带 extraHeaders 可读敏感头）
// Chrome 传入 extraHeaders 会抛异常，因此按支持情况降级重试。
function registerWebRequest() {
  const spec = ['requestHeaders'];
  const filter = { urls: ['http://*/*', 'https://*/*'] };
  try {
    chrome.webRequest.onBeforeSendHeaders.addListener(captureHeaders, filter,
      spec.concat('extraHeaders'));
  } catch (e) {
    try {
      chrome.webRequest.onBeforeSendHeaders.addListener(captureHeaders, filter, spec);
    } catch (e2) {
      console.warn('webRequest 请求头监听失败:', e2.message);
    }
  }
}
registerWebRequest();

function getPort() {
  if (hostPort && hostPort._connected) {
    return Promise.resolve(hostPort);
  }
  return new Promise((resolve, reject) => {
    try {
      const port = chrome.runtime.connectNative(HOST_NAME);
      hostPort = port;
      port.onDisconnect.addListener(() => {
        hostPort = null;
        const err = chrome.runtime.lastError;
        if (err) {
          console.error('Native 通道断开:', err.message);
          rejectPending(err.message || '连接断开');
        }
      });
      port.onMessage.addListener((msg) => {
        resolvePending(msg);
      });
      hostPort._connected = true;
      resolve(port);
    } catch (e) {
      reject(new Error('连接失败: ' + e.message));
    }
  });
}

function rejectPending(reason) {
  pendingReplies.forEach((r) => r.reject(new Error(reason)));
  pendingReplies.clear();
}

function resolvePending(msg) {
  const id = msg && (msg.__id != null) ? msg.__id : null;
  if (id != null && pendingReplies.has(id)) {
    const item = pendingReplies.get(id);
    pendingReplies.delete(id);
    item.resolve(msg);
    return;
  }
  // 无 id 的响应，广播到最后一条
  if (pendingReplies.size === 1) {
    const [key, item] = pendingReplies.entries().next().value;
    pendingReplies.delete(key);
    item.resolve(msg);
  }
}

function postToNative(data) {
  return getPort().then((port) => {
    return new Promise((resolve, reject) => {
      const id = ++seq;
      data.__id = id;
      const timeout = setTimeout(() => {
        pendingReplies.delete(id);
        reject(new Error('等待 Nodanium 响应超时'));
      }, 8000);
      pendingReplies.set(id, {
        resolve: (msg) => { clearTimeout(timeout); resolve(msg); },
        reject: (err) => { clearTimeout(timeout); reject(err); },
      });
      port.postMessage(data);
    });
  });
}

function isDownloadsEnabled() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ enabled: true }, (items) => resolve(!!items.enabled));
  });
}

// 单文件转发（供 downloads 拦截 / 手动下载 调用）
function forwardDownload(request) {
  const url = request.url;
  // 优先使用浏览器捕获到的真实请求头；未捕获到则传空，由 host 用 cookies/referer 兜底
  const headers = request.headers || getCachedHeaders(url) || {};
  return postToNative({
    type: 'download',
    url: url,
    filename: request.filename || '',
    mime: request.mime || '',
    referer: request.referer || '',
    userAgent: navigator.userAgent,
    cookies: request.cookies || '',
    headers: headers,
    timestamp: Date.now(),
  }).then((resp) => {
    if (resp && resp.status === 'use_native') {
      // 小文件放行浏览器原生下载（不做转发提示，避免打扰）
      return resp;
    }
    if (resp && resp.status === 'ok') {
      showNotification('✅ 已转交 Nodanium', `文件: ${request.filename || request.url}`);
    } else {
      throw new Error((resp && resp.error) || 'Nodanium 拒绝下载');
    }
    return resp;
  });
}

// downloads API 拦截
chrome.downloads.onCreated.addListener((item) => {
  isDownloadsEnabled().then((enabled) => {
    if (!enabled || item.state !== 'in_progress') return;
    const url = item.url;
    const headers = getCachedHeaders(url) || {};
    getCookiesForUrl(url).then((cookies) => {
      const filename = item.filename ? item.filename.split('/').pop() : '';
      forwardDownload({
        url,
        filename,
        mime: item.mime || '',
        referer: item.referrer || new URL(url).origin,
        cookies,
        headers,
      })
        .then((resp) => {
          // 小文件放行原生下载：不取消浏览器下载
          if (resp && resp.status === 'use_native') return;
          chrome.downloads.cancel(item.id).catch(() => {});
          chrome.downloads.erase({ id: item.id }).catch(() => {});
        })
        .catch((err) => {
          showNotification('❌ 转发失败', err.message || '请检查 Nodanium 是否安装');
        });
    });
  });
});

function getCookiesForUrl(url) {
  return new Promise((resolve) => {
    try {
      chrome.cookies.getAll({ url }, (cookies) => {
        if (chrome.runtime.lastError) { resolve(''); return; }
        resolve(cookies.map((c) => `${c.name}=${c.value}`).join('; '));
      });
    } catch (e) { resolve(''); }
  });
}

function showNotification(title, message) {
  try {
    chrome.notifications.create({ type: 'basic', iconUrl: 'icons/icon.png', title, message, priority: 1 });
  } catch (e) {}
}

// 手动 / 页面消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === 'manualDownload') {
    let url = message.url;
    try { new URL(url); } catch (e) { sendResponse({ success: false, error: '无效 URL' }); return; }
    const filename = message.filename || url.split('/').pop();
    const referer = message.referer || new URL(url).origin;
    const headers = getCachedHeaders(url) || {};
    getCookiesForUrl(url).then((cookies) => {
      forwardDownload({ url, filename, mime: '', referer, cookies, headers })
        .then(() => sendResponse({ success: true }))
        .catch((err) => sendResponse({ success: false, error: err.message }));
    });
    return true;
  }
  if (message && message.type === 'ping') {
    postToNative({ type: 'ping' })
      .then((r) => sendResponse({ status: (r && r.status === 'ok') ? 'ok' : 'error' }))
      .catch(() => sendResponse({ status: 'error' }));
    return true;
  }
  if (message && message.type === 'setEnabled') {
    chrome.storage.sync.set({ enabled: !!message.value }, () => sendResponse({ success: true }));
    return true;
  }
  if (message && message.type === 'getEnabled') {
    isDownloadsEnabled().then((v) => sendResponse({ enabled: v }));
    return true;
  }
});

console.log('🚀 Nodanium 下载拦截器已启动');
