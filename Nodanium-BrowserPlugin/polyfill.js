// 浏览器API兼容层
if (typeof browser === 'undefined') {
  globalThis.browser = chrome;
}

// Firefox使用browser.，Chrome使用chrome.
// 这个polyfill让所有浏览器都使用browser.前缀