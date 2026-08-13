(function(){
  'use strict';

  const host=document.querySelector('[data-global-toolbar],.global-toolbar');
  if(!host)return;

  const labels={
    vi:{models:'Trang Chủ',history:'Lịch Sử',affiliate:'Giới Thiệu',wallet:'Nạp VIP',account:'Tài Khoản',login:'Đăng Nhập',greeting:'Chào bạn,',topup:'Nạp Thêm Lượt',support:'Hỗ Trợ',profile:'Hồ Sơ Của Tôi',commission:'Giới Thiệu Nhận Hoa Hồng',logout:'Đăng Xuất'},
    en:{models:'Home',history:'History',affiliate:'Referral',wallet:'Top Up',account:'Account',login:'Log In',greeting:'Hello,',topup:'Add Usage',support:'Support',profile:'My Profile',commission:'Referral Commission',logout:'Log Out'}
  };
  let signedIn=false;
  let menuOpen=false;

  host.className='global-toolbar liquid-toolbar';
  host.dataset.globalToolbar='';
  host.innerHTML=`<div class="global-toolbar-inner">
    <div class="toolbar-left"><div class="lang-switch liquid-pill" aria-label="Language"><button data-lang="vi">VN</button><span>|</span><button data-lang="en">EN</button></div></div>
    <a class="global-brand centered-brand" href="/" aria-label="TVC Studio AI"><span class="brand-glass-orb"><img src="/static/images/logo-tvc.png" alt="TVC Studio"></span><strong>TVC Studio <b>AI</b></strong></a>
    <nav class="global-actions liquid-nav" aria-label="Điều hướng chính">
      <a href="/" class="tool-pill liquid-pill" data-tool="models"><span class="mobile-tool-icon">✦</span><span class="mobile-tool-label" data-toolbar-label="models">Trang Chủ</span></a>
      <a href="/app#jobs" class="tool-pill liquid-pill" data-tool="history"><span class="mobile-tool-icon">◷</span><span class="mobile-tool-label" data-toolbar-label="history">Lịch Sử</span></a>
      <a href="/app#affiliate" class="tool-pill liquid-pill" data-tool="affiliate"><span class="mobile-tool-icon">ⓢ</span><span class="mobile-tool-label" data-toolbar-label="affiliate">Giới Thiệu</span></a>
      <a href="/app#wallet" class="tool-pill liquid-pill" data-tool="wallet"><span class="mobile-tool-icon mobile-credit-icon"><b id="mobileToolbarCredits">0</b></span><span class="mobile-tool-label" data-toolbar-label="wallet">Nạp VIP</span></a>
      <button type="button" class="tool-pill liquid-pill tvc-account-trigger" data-tool="account" id="toolbarAccountTrigger" aria-expanded="false" aria-controls="toolbarAccountMenu"><span class="mobile-tool-icon mobile-account-icon" id="toolbarAccountIcon">↪</span><span class="mobile-tool-label" id="toolbarAccountLabel">Đăng Nhập</span></button>
    </nav>
    <section class="tvc-account-menu" id="toolbarAccountMenu" aria-label="Menu tài khoản" hidden>
      <header><span class="tvc-account-avatar" id="toolbarAccountAvatar">T</span><div><small id="toolbarGreeting">Chào bạn,</small><strong id="toolbarAccountEmail"></strong></div></header>
      <nav>
        <a href="/app#jobs"><span>◷</span><b data-account-label="history">Lịch Sử</b></a>
        <a href="/app#wallet"><span>◇</span><b data-account-label="topup">Nạp Thêm Lượt</b></a>
        <a href="/contact"><span>?</span><b data-account-label="support">Hỗ Trợ</b></a>
        <a href="/app#account"><span>◎</span><b data-account-label="profile">Hồ Sơ Của Tôi</b></a>
        <a href="/app#affiliate"><span>ⓢ</span><b data-account-label="commission">Giới Thiệu Nhận Hoa Hồng</b></a>
        <button type="button" class="tvc-account-logout" id="toolbarLogout"><span>↪</span><b data-account-label="logout">Đăng Xuất</b></button>
      </nav>
    </section>
  </div>`;

  const trigger=host.querySelector('#toolbarAccountTrigger');
  const menu=host.querySelector('#toolbarAccountMenu');

  function language(){
    return localStorage.getItem('tvc_lang')==='en'?'en':'vi';
  }

  function routeTool(){
    if(location.pathname==='/app'){
      const exact={jobs:'history',affiliate:'affiliate',wallet:'wallet',account:'account'};
      return exact[location.hash.slice(1)]||'models';
    }
    return 'models';
  }

  function setActive(tool){
    host.querySelectorAll('[data-tool]').forEach(tab=>{
      tab.classList.remove('active','selected','current','mobile-active');
      tab.removeAttribute('aria-current');
    });
    host.querySelector(`[data-tool="${tool}"]`)?.setAttribute('aria-current','page');
  }

  function applyLanguage(lang){
    const dictionary=labels[lang]||labels.vi;
    document.documentElement.lang=lang;
    localStorage.setItem('tvc_lang',lang);
    host.querySelectorAll('.lang-switch button').forEach(button=>button.classList.toggle('active',button.dataset.lang===lang));
    host.querySelectorAll('[data-toolbar-label]').forEach(node=>{node.textContent=dictionary[node.dataset.toolbarLabel]});
    host.querySelectorAll('[data-account-label]').forEach(node=>{node.textContent=dictionary[node.dataset.accountLabel]});
    host.querySelector('#toolbarGreeting').textContent=dictionary.greeting;
    host.querySelector('#toolbarAccountLabel').textContent=signedIn?dictionary.account:dictionary.login;
  }

  function closeMenu(restore=true){
    menuOpen=false;
    menu.hidden=true;
    trigger.setAttribute('aria-expanded','false');
    if(restore)setActive(routeTool());
  }

  function openMenu(){
    if(!signedIn)return;
    menuOpen=true;
    menu.hidden=false;
    trigger.setAttribute('aria-expanded','true');
    setActive(routeTool());
    menu.querySelector('a,button')?.focus({preventScroll:true});
  }

  function applySignedOut(){
    signedIn=false;
    closeMenu(false);
    host.dataset.authState='signed-out';
    trigger.dataset.authState='signed-out';
    host.querySelector('#toolbarAccountIcon').textContent='↪';
    host.querySelector('#toolbarAccountLabel').textContent=labels[language()].login;
    host.querySelector('#toolbarAccountEmail').textContent='';
    host.querySelector('#toolbarAccountAvatar').textContent='';
    host.querySelector('#mobileToolbarCredits').textContent='0';
    setActive(routeTool());
  }

  function applySignedIn(me){
    signedIn=true;
    host.dataset.authState='signed-in';
    trigger.dataset.authState='signed-in';
    const initial=(me.name||me.email||'T').trim().slice(0,1).toUpperCase();
    host.querySelector('#toolbarAccountIcon').textContent=initial;
    host.querySelector('#toolbarAccountAvatar').textContent=initial;
    host.querySelector('#toolbarAccountEmail').textContent=me.email||'';
    host.querySelector('#toolbarAccountLabel').textContent=labels[language()].account;
    host.querySelector('#mobileToolbarCredits').textContent=Number(me.usage_balance||me.credits||0).toLocaleString('vi-VN',{maximumFractionDigits:1});
    setActive(routeTool());
  }

  async function syncAccount(){
    try{
      const response=await fetch('/api/me',{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw new Error('signed-out');
      applySignedIn(await response.json());
    }catch{
      applySignedOut();
    }
  }

  trigger.addEventListener('click',()=>{
    if(!signedIn){
      closeMenu(false);
      location.href='/app#login';
      return;
    }
    menuOpen?closeMenu():openMenu();
  });

  document.addEventListener('click',event=>{
    if(menuOpen&&!host.contains(event.target))closeMenu();
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&menuOpen){
      closeMenu();
      trigger.focus({preventScroll:true});
    }
  });
  host.querySelectorAll('.global-actions [data-tool]:not([data-tool="account"])').forEach(tab=>tab.addEventListener('click',()=>closeMenu(false)));
  menu.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>closeMenu(false)));
  host.querySelector('#toolbarLogout').addEventListener('click',async()=>{
    closeMenu(false);
    try{await fetch('/api/logout',{method:'POST',credentials:'same-origin'});}finally{
      applySignedOut();
      location.href='/';
    }
  });
  host.querySelectorAll('.lang-switch button').forEach(button=>button.addEventListener('click',()=>applyLanguage(button.dataset.lang)));

  window.addEventListener('hashchange',()=>{closeMenu(false);setActive(routeTool())});
  window.addEventListener('popstate',()=>{closeMenu(false);setActive(routeTool())});
  window.addEventListener('pageshow',()=>syncAccount());
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)syncAccount()});
  document.addEventListener('tvc-auth-change',()=>syncAccount());

  window.TVCGlobalToolbar={setActive,syncAccount,closeMenu};
  applyLanguage(language());
  setActive(routeTool());
  syncAccount();
})();
