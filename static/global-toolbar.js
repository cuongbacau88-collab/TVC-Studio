(function(){
  'use strict';
  const RETURN_KEY='tvc_login_return_to';
  function safeInternalReturn(value){
    if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//'))return null;
    try{const url=new URL(value,location.origin);if(url.origin!==location.origin)return null;return url.pathname+url.search+url.hash}catch{return null}
  }
  function currentReturn(){return safeInternalReturn(location.pathname+location.search+location.hash)||'/'}
  function storeReturn(value){const safe=safeInternalReturn(value);if(safe)sessionStorage.setItem(RETURN_KEY,safe);return safe}
  function loginUrl(value=(location.pathname==='/app'&&['#login','#register'].includes(location.hash)?resolveReturn():currentReturn())){const safe=storeReturn(value)||'/';return `/app?return_to=${encodeURIComponent(safe)}#login`}
  function resolveReturn(){const query=safeInternalReturn(new URLSearchParams(location.search).get('return_to'));if(query)return query;const saved=safeInternalReturn(sessionStorage.getItem(RETURN_KEY));if(saved)return saved;if(location.pathname==='/app'&&['#jobs','#affiliate','#wallet','#account','#create'].includes(location.hash))return currentReturn();return '/'}
  function consumeReturn(){const target=resolveReturn();sessionStorage.removeItem(RETURN_KEY);return target}
  window.TVCReturnNavigation={safeInternalReturn,currentReturn,storeReturn,loginUrl,resolveReturn,consumeReturn};

  const host=document.querySelector('[data-global-toolbar],.global-toolbar');
  if(!host)return;

  document.body.classList.add('tvc-fixed-toolbar');

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
  host.querySelector('.toolbar-left').insertAdjacentHTML('afterbegin','<button type="button" class="ai-tools-trigger liquid-pill" id="aiToolsTrigger" aria-expanded="false" aria-controls="aiToolsDrawer"><span aria-hidden="true">☰</span><span>Công cụ AI</span></button>');
  host.insertAdjacentHTML('beforeend',`<div class="ai-tools-overlay" id="aiToolsOverlay" hidden></div><aside class="ai-tools-drawer" id="aiToolsDrawer" aria-label="Công cụ AI" aria-hidden="true">
    <header><a href="/" class="drawer-brand"><img src="/static/images/logo-tvc.png" alt=""><b>TVC Studio AI</b></a><button type="button" id="aiToolsClose" aria-label="Đóng menu">×</button></header>
    <div class="drawer-account"><span class="tvc-account-avatar" id="drawerAvatar">T</span><div><b id="drawerEmail">Chưa đăng nhập</b><small><span id="drawerCredits">0</span> lượt</small></div><a id="drawerLogin" href="/app#login">Đăng Nhập</a></div>
    <div class="drawer-scroll">
      <details open><summary>Điều hướng</summary><nav><a href="/">Trang Chủ</a><a href="/app#jobs">Lịch Sử</a><a href="/about">Giới Thiệu</a><a href="/app#wallet">Nạp VIP</a><a href="/app#account">Tài Khoản</a></nav></details>
      <details open><summary>Tạo video</summary><nav><a href="/app">AI Motion Studio <em>Viral</em></a><a href="/services/video_generation">AI Video Creator <em>Mới</em></a><button type="button" disabled>Tạo Video Review <em>Sắp ra mắt</em></button><button type="button" disabled>Video dạng câu chuyện <em>Sắp ra mắt</em></button></nav></details>
      <details><summary>Chỉnh sửa ảnh</summary><nav><a href="/services/outfit_change">AI Đổi Trang Phục <em>Miễn phí</em></a><a href="/services/background_change">AI Đổi Bối Cảnh <em>Miễn phí</em></a><a href="/services/image_upscale">AI Nâng Cấp Ảnh <em>Miễn phí</em></a><button type="button" disabled>Lookbook Thời Trang <em>Sắp ra mắt</em></button><button type="button" disabled>Tạo Ảnh Trends <em>Sắp ra mắt</em></button></nav></details>
      <details><summary>KOL và thương hiệu</summary><nav><button type="button" disabled>KOL của tôi <em>Sắp ra mắt</em></button><button type="button" disabled>Nhân bản giọng nói <em>Sắp ra mắt</em></button><button type="button" disabled>Hồ sơ nhân vật <em>Sắp ra mắt</em></button></nav></details>
      <details><summary>Quản lý</summary><nav><a href="/app#jobs">Lịch Sử</a><a href="/app#wallet">Lượt của tôi</a><a href="/app#wallet">Nạp Thêm Lượt</a><a href="/app#account">Hồ Sơ Của Tôi</a><a href="/app#affiliate">Giới Thiệu Nhận Hoa Hồng</a><a href="/contact">Hỗ Trợ</a></nav></details>
    </div></aside>`);
  const toolsTrigger=host.querySelector('#aiToolsTrigger'),toolsDrawer=host.querySelector('#aiToolsDrawer'),toolsOverlay=host.querySelector('#aiToolsOverlay');
  function closeTools(){toolsDrawer.classList.remove('open');toolsDrawer.setAttribute('aria-hidden','true');toolsOverlay.hidden=true;toolsTrigger.setAttribute('aria-expanded','false');document.body.classList.remove('ai-tools-open')}
  function openTools(){closeMenu(false);toolsOverlay.hidden=false;requestAnimationFrame(()=>toolsDrawer.classList.add('open'));toolsDrawer.setAttribute('aria-hidden','false');toolsTrigger.setAttribute('aria-expanded','true');document.body.classList.add('ai-tools-open');host.querySelector('#aiToolsClose').focus({preventScroll:true})}
  toolsTrigger.addEventListener('click',()=>toolsDrawer.classList.contains('open')?closeTools():openTools());
  toolsOverlay.addEventListener('click',closeTools);host.querySelector('#aiToolsClose').addEventListener('click',closeTools);toolsDrawer.querySelectorAll('a').forEach(link=>link.addEventListener('click',closeTools));

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
    host.querySelector('#drawerEmail').textContent='Chưa đăng nhập';
    host.querySelector('#drawerCredits').textContent='0';
    host.querySelector('#drawerAvatar').textContent='T';
    host.querySelector('#drawerLogin').hidden=false;
    host.querySelector('#drawerLogin').href=loginUrl();
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
    host.querySelector('#drawerEmail').textContent=me.email||'';
    host.querySelector('#drawerCredits').textContent=Number(me.usage_balance||me.credits||0).toLocaleString('vi-VN',{maximumFractionDigits:1});
    host.querySelector('#drawerAvatar').textContent=initial;
    host.querySelector('#drawerLogin').hidden=true;
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
      location.href=loginUrl();
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
    if(event.key==='Escape'&&toolsDrawer.classList.contains('open')){
      closeTools();
      toolsTrigger.focus({preventScroll:true});
    }
      trigger.focus({preventScroll:true});
    }
  });
  host.querySelectorAll('.global-actions [data-tool]:not([data-tool="account"])').forEach(tab=>tab.addEventListener('pointerdown',()=>{
    setActive(tab.dataset.tool);
  }));
  host.querySelectorAll('.global-actions [data-tool]:not([data-tool="account"])').forEach(tab=>tab.addEventListener('click',()=>setActive(tab.dataset.tool)));
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

  function updateToolbarHeight(){
    document.documentElement.style.setProperty('--header-height',Math.ceil(host.getBoundingClientRect().height)+'px');
    document.documentElement.style.setProperty('--tvc-toolbar-height',`${Math.ceil(host.getBoundingClientRect().height)}px`);
  }
  if('ResizeObserver' in window){
    new ResizeObserver(updateToolbarHeight).observe(host);
  }else{
    window.addEventListener('resize',updateToolbarHeight,{passive:true});
  }
  window.addEventListener('orientationchange',updateToolbarHeight,{passive:true});
  document.fonts?.ready.then(updateToolbarHeight);

  window.TVCGlobalToolbar={setActive,syncAccount,closeMenu};
  applyLanguage(language());
  setActive(routeTool());
  requestAnimationFrame(updateToolbarHeight);
  syncAccount();
})();
