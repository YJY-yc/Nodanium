// content.js - 页面内增强拦截（下载链接点击）
(function () {
  const FILE_RE = /\.(zip|rar|7z|tar|gz|bz2|exe|msi|dmg|iso|apk|deb|rpm|pdf|epub|mp3|mp4|mkv|avi|mov|flv|webm|cab|jar|txt|json|csv|xlsx|xls|docx|doc|pptx|ppt)(\?.*)?(#.*)?$/i;
  const schemeOk = (u) => /^https?:$/.test((u || '').split(':')[0]) || /^blob:/i.test(u || '');
  const isFileUrl = (href) => {
    if (/^blob:/i.test(href || '')) return true;
    try {
      const u = new URL(href);
      return FILE_RE.test(u.pathname);
    } catch (e) { return false; }
  };

  function sendToBackground(url, force) {
    chrome.runtime.sendMessage({ type: 'manualDownload', url }, () => {
      if (chrome.runtime.lastError) { /* background 不可用 */ }
    });
  }

  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    const a = event.target.closest && event.target.closest('a[href]');
    if (!a) return;

    const hasDownloadAttr = a.hasAttribute('download');
    const href = a.href;
    if (!schemeOk(href)) return;

    // 带 download 属性的链接：明确下载
    if (hasDownloadAttr) {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      sendToBackground(href, true);
      return;
    }

    // 中键 / 自定义下载类链接
    if (a.rel && /\b(download|downloadable)\b/i.test(a.rel)) {
      event.preventDefault();
      sendToBackground(href, true);
    }
  }, true);

  // 捕获通过 JS 创建的 blob / data 下载（webkit 前缀兼容）
  ['click', 'auxclick', 'contextmenu'].forEach((type) => {
    document.addEventListener(type, (e) => {
      const a = e.target && e.target.closest ? e.target.closest('a[download]') : null;
      if (a && a.href && /^blob:|data:/i.test(a.href) && !e.defaultPrevented) {
        e.preventDefault();
        sendToBackground(a.href, true);
      }
    }, true);
  });

  console.log('Nodanium 下载器内容脚本已加载');
})();
