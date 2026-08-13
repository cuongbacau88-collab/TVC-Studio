(function(){
  'use strict';
  const host=document.querySelector('[data-global-toolbar],.global-toolbar');
  if(!host)return;
  const hash=location.hash||'#create';
  const active=location.pathname==='/app'?(hash==='#jobs'?'history':hash==='#affiliate'?'affiliate':hash==='#wallet'?'wallet':hash==='#account'?'account':'models'):'models';
  host.className='global-toolbar liquid-toolbar';
  host.dataset.globalToolbar='';
  host.innerHTML=`<div class="global-toolbar-inner">
    <div class="toolbar-left"><div class="lang-switch liquid-pill" aria-label="Language"><button data-lang="vi">VN</button><span>|</span><button data-lang="en">EN</button></div></div>
    <a class="global-brand centered-brand" href="/" aria-label="TVC Studio AI"><span class="brand-glass-orb"><img src="/static/images/logo-tvc.png" alt="TVC Studio"></span><strong>TVC Studio <b>AI</b></strong></a>
    <nav class="global-actions liquid-nav" aria-label="Điều hướng chính">
      <a href="/" class="tool-pill liquid-pill" data-tool="models"><span class="mobile-tool-icon">✦</span><span class="mobile-tool-label" data-i18n="models">Trang Chủ</span></a>
      <a href="/app#jobs" class="tool-pill liquid-pill" data-tool="history"><span class="mobile-tool-icon">◷</span><span class="mobile-tool-label" data-i18n="history">Lịch Sử</span></a>
      <a href="/app#affiliate" class="tool-pill liquid-pill" data-tool="affiliate"><span class="mobile-tool-icon">ⓢ</span><span class="mobile-tool-label" data-i18n="earn">Giới Thiệu</span></a>
      <a href="/app#wallet" class="tool-pill liquid-pill" data-tool="wallet"><span class="mobile-tool-icon mobile-credit-icon"><b id="mobileToolbarCredits">0</b></span><span class="mobile-tool-label" data-i18n="topup">Nạp VIP</span></a>
      <a href="/app#account" class="tool-pill liquid-pill" data-tool="account"><span class="mobile-tool-icon mobile-account-icon">◉</span><span class="mobile-tool-label" data-i18n="account">Tài Khoản</span></a>
    </nav>
  </div>`;
  const selected=host.querySelector(`[data-tool="${active}"]`);
  selected?.setAttribute('aria-current','page');
  requestAnimationFrame(()=>selected?.scrollIntoView({block:'nearest',inline:'center'}));
  const lang=localStorage.getItem('tvc_lang')||'vi';
  host.querySelectorAll('.lang-switch button').forEach(button=>{
    button.classList.toggle('active',button.dataset.lang===lang);
    button.addEventListener('click',()=>{
      localStorage.setItem('tvc_lang',button.dataset.lang);
      document.documentElement.lang=button.dataset.lang;
      host.querySelectorAll('.lang-switch button').forEach(item=>item.classList.toggle('active',item===button));
      document.dispatchEvent(new CustomEvent('tvc-language-change',{detail:{language:button.dataset.lang}}));
    });
  });
  fetch('/api/me',{credentials:'same-origin'})
    .then(response=>response.ok?response.json():null)
    .then(me=>{
      if(!me)return;
      const balance=host.querySelector('#mobileToolbarCredits');
      if(balance)balance.textContent=Number(me.usage_balance||0).toLocaleString('vi-VN');
    }).catch(()=>{});
})();
