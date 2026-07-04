// content.js - 在页面中运行，增强拦截

// 拦截页面中的下载链接点击
document.addEventListener('click', (event) => {
  const target = event.target.closest('a[download]');
  if (target) {
    // 如果链接有download属性，是明确的下载链接
    console.log('检测到下载链接点击:', target.href);
    // 阻止默认行为
    event.preventDefault();
    // 通知background（但background已经通过downloads API拦截了）
    // 这里可以不做额外处理，避免重复
  }
}, true);

console.log('Nodanium下载器内容脚本已加载');