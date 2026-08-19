(function(){
  'use strict';
  const RETURN_KEY='tvc_login_return_to';
  function safeInternalReturn(value){
    if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//'))return null;
    try{const url=new URL(value,location.origin);if(url.origin!==location.origin)return null;return url.pathname+url.search+url.hash}catch{return null}
  }
  function currentReturn(){return safeInternalReturn(location.pathname+location.search+location.hash)||'/'}
  function storeReturn(value){const safe=safeInternalReturn(value);if(safe)sessionStorage.setItem(RETURN_KEY,safe);return safe}
  function loginUrl(value=(location.pathname==='/app'&&['#login','#register'].includes(location.hash)?resolveReturn():currentReturn())){const safe=storeReturn(value)||'/app';return `/app?return_to=${encodeURIComponent(safe)}#login`}
  function resolveReturn(){const query=safeInternalReturn(new URLSearchParams(location.search).get('return_to'));if(query&&query!=='/')return query;const saved=safeInternalReturn(sessionStorage.getItem(RETURN_KEY));if(saved&&saved!=='/')return saved;if(location.pathname==='/app'&&['#jobs','#affiliate','#wallet','#account','#create'].includes(location.hash))return currentReturn();return '/app'}
  function consumeReturn(){const target=resolveReturn();sessionStorage.removeItem(RETURN_KEY);if(!target||target==='/')return '/';return target}
  window.TVCReturnNavigation={safeInternalReturn,currentReturn,storeReturn,loginUrl,resolveReturn,consumeReturn};

  const host=document.querySelector('[data-global-toolbar],.global-toolbar');
  if(!host)return;
  window.__tvcToolbarAbort?.abort();
  document.querySelectorAll('[data-toolbar-portal="true"]').forEach(node=>node.remove());
  const toolbarAbort=new AbortController(),signal=toolbarAbort.signal;
  window.__tvcToolbarAbort=toolbarAbort;
  const listen=(target,type,handler,options={})=>target.addEventListener(type,handler,{...options,signal});

  document.body.classList.add('tvc-fixed-toolbar');

  const labels={
    vi:{models:'Trang Chủ',history:'Lịch Sử',affiliate:'Giới Thiệu',wallet:'Nạp VIP',account:'Tài Khoản',login:'Đăng Nhập',greeting:'Chào bạn,',topup:'Nạp Thêm Xu',support:'Hỗ Trợ',profile:'Hồ Sơ Của Tôi',commission:'Giới Thiệu Nhận Hoa Hồng',logout:'Đăng Xuất'},
    en:{models:'Home',history:'History',affiliate:'Referral',wallet:'Top Up',account:'Account',login:'Log In',greeting:'Hello,',topup:'Add Usage',support:'Support',profile:'My Profile',commission:'Referral Commission',logout:'Log Out'}
  };
  let signedIn=false;
  let menuOpen=false;

  host.className='global-toolbar liquid-toolbar';
  host.dataset.globalToolbar='';
  host.innerHTML=`<div class="global-toolbar-inner">
    <div class="toolbar-left"><div class="lang-switch liquid-pill" aria-label="Language"><button data-lang="vi">VN</button><span>|</span><button data-lang="en">EN</button></div></div>
    <a class="global-brand centered-brand" href="/" aria-label="TVC Studio AI"><span class="brand-glass-orb"><img src="/static/images/logo-tvc.png" alt="TVC logo"></span><strong>Studio <b>AI</b></strong></a>
    <nav class="global-actions liquid-nav" aria-label="Điều hướng chính">
      <button type="button" class="tool-pill liquid-pill mobile-menu-tool menu-tab" data-tool="menu" id="aiToolsTrigger" aria-expanded="false" aria-controls="aiToolsDrawer"><span class="mobile-tool-icon" aria-hidden="true">☰</span><span class="mobile-tool-label">Menu</span></button>
      <a href="/" class="tool-pill liquid-pill home-tab" data-tool="models"><span class="mobile-tool-icon">✦</span><span class="mobile-tool-label" data-toolbar-label="models">Trang Chủ</span></a>
      <a href="/app#jobs" class="tool-pill liquid-pill history-tab" data-tool="history"><span class="mobile-tool-icon">◷</span><span class="mobile-tool-label" data-toolbar-label="history">Lịch Sử</span></a>
      <a href="/app#affiliate" class="tool-pill liquid-pill about-tab" data-tool="affiliate"><span class="mobile-tool-icon">ⓢ</span><span class="mobile-tool-label" data-toolbar-label="affiliate">Giới Thiệu</span></a>
      <a href="/app#wallet" class="tool-pill liquid-pill vip-tab" data-tool="wallet"><span class="mobile-tool-icon mobile-credit-icon"><b id="mobileToolbarCredits">0</b></span><span class="mobile-tool-label" data-toolbar-label="wallet">Nạp VIP</span></a>
      <button type="button" class="tool-pill liquid-pill tvc-account-trigger account-tab login-tab" data-tool="account" id="toolbarAccountTrigger" aria-expanded="false" aria-controls="toolbarAccountMenu"><span class="mobile-tool-icon mobile-account-icon" id="toolbarAccountIcon">↪</span><span class="mobile-tool-label" id="toolbarAccountLabel">Đăng Nhập</span></button>
    </nav>
    <section class="tvc-account-menu" id="toolbarAccountMenu" aria-label="Menu tài khoản" hidden>
      <header><span class="tvc-account-avatar" id="toolbarAccountAvatar">T</span><div><small id="toolbarGreeting" class="text-slate-800 font-medium">Chào bạn,</small><strong id="toolbarAccountEmail" class="text-slate-800 font-medium"></strong></div></header>
      <nav>
        <a href="/app#jobs" class="text-slate-800 font-medium"><span class="text-slate-800 font-medium">◷</span><b data-account-label="history" class="text-slate-800 font-medium">Lịch Sử</b></a>
        <a href="/app#wallet" class="text-slate-800 font-medium"><span class="text-slate-800 font-medium">◇</span><b data-account-label="topup" class="text-slate-800 font-medium">Nạp Thêm Xu</b></a>
        <a href="/contact" class="text-slate-800 font-medium"><span class="text-slate-800 font-medium">?</span><b data-account-label="support" class="text-slate-800 font-medium">Hỗ Trợ</b></a>
        <a href="/app#account" class="text-slate-800 font-medium"><span class="text-slate-800 font-medium">◎</span><b data-account-label="profile" class="text-slate-800 font-medium">Hồ Sơ Của Tôi</b></a>
        <a href="/app#affiliate" class="text-slate-800 font-medium"><span class="text-slate-800 font-medium">ⓢ</span><b data-account-label="commission" class="text-slate-800 font-medium">Giới Thiệu Nhận Hoa Hồng</b></a>
        <button type="button" class="tvc-account-logout text-slate-800 font-medium" id="toolbarLogout"><span class="text-slate-800 font-medium">↪</span><b data-account-label="logout" class="text-slate-800 font-medium">Đăng Xuất</b></button>
      </nav>
    </section>
  </div>`;

  const navRow=host.querySelector('.global-actions');
  const menuTab=navRow.querySelector(':scope > [data-tool="menu"]');
  function ensureMenuTabFirst(){
    if(navRow.firstElementChild!==menuTab)navRow.prepend(menuTab);
  }
  ensureMenuTabFirst();
  const navOrderObserver=new MutationObserver(ensureMenuTabFirst);
  navOrderObserver.observe(navRow,{childList:true});
  signal.addEventListener('abort',()=>navOrderObserver.disconnect(),{once:true});

  const trigger=host.querySelector('#toolbarAccountTrigger');
  const menu=host.querySelector('#toolbarAccountMenu');
  host.querySelector('.toolbar-left').insertAdjacentHTML('afterbegin','<button type="button" class="ai-tools-trigger desktop-ai-tools-trigger liquid-pill" id="aiToolsDesktopTrigger" aria-expanded="false" aria-controls="aiToolsDrawer"><span aria-hidden="true">☰</span><span>Công cụ AI</span></button>');
  host.insertAdjacentHTML('beforeend',`<div class="ai-tools-overlay" id="aiToolsOverlay" hidden></div><aside class="ai-tools-drawer flex flex-col h-full" id="aiToolsDrawer" aria-label="Công cụ AI" aria-hidden="true">
    <div class="drawer-scroll flex flex-col h-full overflow-y-auto w-full">
      <header class="drawer-header"><a href="/" class="drawer-brand"><img src="/static/images/logo-tvc.png" alt="TVC logo"><b>Studio AI</b></a><button type="button" id="aiToolsClose" aria-label="Đóng menu">×</button></header>
      <div class="drawer-account"><span class="tvc-account-avatar" id="drawerAvatar">T</span><div class="drawer-account-text"><b id="drawerEmail">Chưa đăng nhập</b><small><span id="drawerCredits">0</span> lượt</small></div><a id="drawerLogin" href="/app#login">Đăng Nhập</a></div>
      <div class="drawer-language"><span>Ngôn ngữ</span><div class="lang-switch liquid-pill" aria-label="Language"><button data-lang="vi">VN</button><span>|</span><button data-lang="en">EN</button></div></div>
      <a class="zalo-community-link drawer-zalo-link" href="https://zalo.me/g/zjsk2eclgz9dejbfsmgz" target="_blank" rel="noopener noreferrer" aria-label="Tham gia nhóm Zalo (mở trong tab mới)" title="Tham gia nhóm Zalo"><span class="zalo-community-icon" aria-hidden="true">Z</span><span>Tham gia nhóm Zalo</span><span class="zalo-external" aria-hidden="true">↗</span></a>
      <div class="drawer-menu-list">
        <details open class="menu-group active open"><summary class="menu-header">Tạo video</summary><nav class="submenu" style="display: block;"><a href="/app">AI Motion Studio <em>Viral</em></a><a href="/services/video_generation">AI Video Creator <em>Mới</em></a><button type="button" disabled>Tạo Video Review <em>Sắp ra mắt</em></button><button type="button" disabled>Video dạng câu chuyện <em>Sắp ra mắt</em></button></nav></details>
        <details open class="menu-group active open"><summary class="menu-header">Chỉnh sửa ảnh</summary><nav class="submenu" style="display: block;"><a href="/services/outfit_change">AI Đổi Trang Phục <em>Miễn phí</em></a><a href="/services/background_change">AI Đổi Bối Cảnh <em>Miễn phí</em></a><a href="/services/image_upscale">AI Nâng Cấp Ảnh <em>Miễn phí</em></a><button type="button" disabled>Lookbook Thời Trang <em>Sắp ra mắt</em></button><button type="button" disabled>Tạo Ảnh Trends <em>Sắp ra mắt</em></button></nav></details>
        <details class="menu-group"><summary class="menu-header">KOL và thương hiệu</summary><nav class="submenu"><button type="button" disabled>KOL của tôi <em>Sắp ra mắt</em></button><button type="button" disabled>Nhân bản giọng nói <em>Sắp ra mắt</em></button><button type="button" disabled>Hồ sơ nhân vật <em>Sắp ra mắt</em></button></nav></details>
        <details class="menu-group"><summary class="menu-header">Quản lý</summary><nav class="submenu"><a href="/app#jobs">Lịch Sử</a><a href="/app#wallet">Lượt của tôi</a><a href="/app#wallet">Nạp Thêm Lượt</a><a href="/app#account">Hồ Sơ Của Tôi</a><a href="/app#affiliate">Giới Thiệu Nhận Hoa Hồng</a><a href="/contact">Hỗ Trợ</a></nav></details>
      </div>
    </div></aside>`);
  const toolsTrigger=host.querySelector('#aiToolsTrigger'),desktopToolsTrigger=host.querySelector('#aiToolsDesktopTrigger');
  const toolsDrawer=host.querySelector('#aiToolsDrawer'),toolsOverlay=host.querySelector('#aiToolsOverlay');
  document.body.append(toolsOverlay,toolsDrawer);
  toolsDrawer.dataset.toolbarPortal='true';toolsOverlay.dataset.toolbarPortal='true';
  toolsOverlay.hidden=true;toolsOverlay.style.display='none';toolsOverlay.style.pointerEvents='none';
  let overlayTimer=0,gesture=null,drawerClosing=false,closeAnimationDone=false,backdropSequenceActive=false;
  function resetDrag(){gesture=null;toolsDrawer.classList.remove('dragging');toolsDrawer.style.removeProperty('transform')}
  function finalizeClose(){
    if(!drawerClosing||!closeAnimationDone||backdropSequenceActive)return;
    drawerClosing=false;clearTimeout(overlayTimer);
    toolsOverlay.hidden=true;toolsOverlay.style.display='none';toolsOverlay.style.pointerEvents='none';
    document.body.classList.remove('ai-tools-open');
  }
  function closeTools(){
    if(drawerClosing||!toolsDrawer.classList.contains('open'))return;
    drawerClosing=true;closeAnimationDone=false;clearTimeout(overlayTimer);resetDrag();
    toolsDrawer.classList.remove('open');toolsDrawer.setAttribute('aria-hidden','true');
    toolsTrigger.setAttribute('aria-expanded','false');desktopToolsTrigger.setAttribute('aria-expanded','false');setActive(routeTool());
    listen(toolsDrawer,'transitionend',event=>{
      if(event.target===toolsDrawer&&event.propertyName==='transform'){closeAnimationDone=true;finalizeClose()}
    },{once:true});
    overlayTimer=setTimeout(()=>{backdropSequenceActive=false;closeAnimationDone=true;finalizeClose()},450);
  }
  function openTools(focusClose=true){
    drawerClosing=false;closeAnimationDone=false;backdropSequenceActive=false;clearTimeout(overlayTimer);resetDrag();closeMenu(false);
    toolsOverlay.hidden=false;toolsOverlay.style.display='';toolsOverlay.style.pointerEvents='';document.body.classList.add('ai-tools-open');
    requestAnimationFrame(()=>toolsDrawer.classList.add('open'));toolsDrawer.setAttribute('aria-hidden','false');
    toolsTrigger.setAttribute('aria-expanded','true');desktopToolsTrigger.setAttribute('aria-expanded','true');setActive('menu');
    if(focusClose)toolsDrawer.querySelector('#aiToolsClose').focus({preventScroll:true});
  }
  function consumeBackdrop(event){
    event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();
    if(event.type==='pointerdown'||event.type==='touchstart')backdropSequenceActive=true;
    if(toolsDrawer.classList.contains('open'))closeTools();
    if(event.type==='click'){backdropSequenceActive=false;finalizeClose()}
  }
  const toggleTools=()=>toolsDrawer.classList.contains('open')?closeTools():openTools();
  listen(toolsTrigger,'click',toggleTools);listen(desktopToolsTrigger,'click',toggleTools);
  ['pointerdown','pointerup','touchstart','touchend','click'].forEach(type=>listen(toolsOverlay,type,consumeBackdrop,{passive:false,capture:true}));
  listen(toolsDrawer.querySelector('#aiToolsClose'),'click',closeTools);toolsDrawer.querySelectorAll('a').forEach(link=>listen(link,'click',closeTools));
  function blockedGestureTarget(target){
    if(!(target instanceof Element))return false;
    if(target.closest('input,textarea,select,button,a,video,[data-no-drawer-gesture],[draggable="true"],.carousel,.video-gallery-carousel,.upload-tile,.add-reference,.reference-actions,.global-toolbar,.liquid-toolbar,.global-actions,.tool-pill'))return true;
    for(let node=target;node&&node!==document.body;node=node.parentElement){const style=getComputedStyle(node);if(['auto','scroll'].includes(style.overflowX)&&node.scrollWidth>node.clientWidth)return true}
    return false;
  }
  const point=event=>{const item=event.touches?.[0]||event.changedTouches?.[0]||event;return{x:item.clientX,y:item.clientY}};
  function startOpenGesture(event){
    if(innerWidth>768||toolsDrawer.classList.contains('open')||blockedGestureTarget(event.target))return;
    const p=point(event);if(p.x<24||p.x>80)return;gesture={kind:'open',x:p.x,y:p.y,horizontal:false};
  }
  function startCloseGesture(event){
    if(!toolsDrawer.classList.contains('open')||blockedGestureTarget(event.target))return;
    const p=point(event);gesture={kind:'close',x:p.x,y:p.y,horizontal:false};
  }
  function moveGesture(event){
    if(!gesture)return;const p=point(event),dx=p.x-gesture.x,dy=p.y-gesture.y;
    if(Math.abs(dy)>30&&!gesture.horizontal){resetDrag();return}
    if(!gesture.horizontal){
      if(Math.abs(dx)<10)return;
      if(Math.abs(dx)<=Math.abs(dy)*1.35||(gesture.kind==='open'&&dx<0)||(gesture.kind==='close'&&dx>0)){resetDrag();return}
      gesture.horizontal=true;toolsDrawer.classList.add('dragging');
      if(gesture.kind==='open'){toolsOverlay.hidden=false;document.body.classList.add('ai-tools-open')}
    }
    event.preventDefault();const offset=gesture.kind==='open'?Math.max(0,dx):Math.min(0,dx);
    toolsDrawer.style.transform=gesture.kind==='open'?'translateX(calc(-105% + '+offset+'px))':'translateX('+offset+'px)';
  }
  function endGesture(event){
    if(!gesture)return;const active=gesture,dx=point(event).x-active.x;resetDrag();
    if(active.kind==='open'){
      if(active.horizontal&&dx>=60)openTools(false);
      else{toolsDrawer.classList.remove('open');toolsOverlay.hidden=true;document.body.classList.remove('ai-tools-open');setActive(routeTool())}
    }else if(active.horizontal&&dx<=-60)closeTools();else toolsDrawer.classList.add('open');
  }
  if('PointerEvent'in window){
    listen(document,'pointerdown',startOpenGesture,{passive:true});listen(toolsDrawer,'pointerdown',startCloseGesture,{passive:true});
    listen(document,'pointermove',moveGesture,{passive:false});listen(document,'pointerup',endGesture,{passive:true});listen(document,'pointercancel',endGesture,{passive:true});
  }else{
    listen(document,'touchstart',startOpenGesture,{passive:true});listen(toolsDrawer,'touchstart',startCloseGesture,{passive:true});
    listen(document,'touchmove',moveGesture,{passive:false});listen(document,'touchend',endGesture,{passive:true});listen(document,'touchcancel',endGesture,{passive:true});
  }

  function language(){
    return localStorage.getItem('tvc_lang')==='en'?'en':'vi';
  }

  function routeTool(){
    if(location.pathname==='/history'||location.pathname==='/lich-su')return'history';
    if(location.pathname==='/app'){
      const exact={jobs:'history',affiliate:'affiliate',wallet:'wallet',account:'account'};
      return exact[location.hash.slice(1)]||(location.hash==='#login'||location.hash==='#register'?'account':'models');
    }
    if(location.pathname==='/'||location.pathname==='/index.html')return'models';
    if(location.pathname==='/about'||location.pathname==='/gioi-thieu')return'affiliate';
    if(location.pathname==='/pricing'||location.pathname==='/nap-vip'||location.pathname==='/bang-gia')return'wallet';
    return null;
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
    [...host.querySelectorAll('.lang-switch button'),...toolsDrawer.querySelectorAll('.lang-switch button')].forEach(button=>button.classList.toggle('active',button.dataset.lang===lang));
    host.querySelectorAll('[data-toolbar-label]').forEach(node=>{node.textContent=dictionary[node.dataset.toolbarLabel]});
    host.querySelectorAll('[data-account-label]').forEach(node=>{node.textContent=dictionary[node.dataset.accountLabel]});
    host.querySelector('#toolbarGreeting').textContent=dictionary.greeting;
    host.querySelector('#toolbarAccountLabel').textContent=signedIn?dictionary.account:dictionary.login;
    ensureMenuTabFirst();
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
    window.TVCSignedIn=false;
    window.TVCCurrentUser=null;
    closeMenu(false);
    host.dataset.authState='signed-out';
    trigger.dataset.authState='signed-out';
    host.querySelector('#toolbarAccountIcon').textContent='↪';
    host.querySelector('#toolbarAccountLabel').textContent=labels[language()].login;
    host.querySelector('#toolbarAccountEmail').textContent='';
    host.querySelector('#toolbarAccountAvatar').textContent='';
    host.querySelector('#mobileToolbarCredits').textContent='0';
    toolsDrawer.querySelector('#drawerEmail').textContent='Chưa đăng nhập';
    toolsDrawer.querySelector('#drawerCredits').textContent='0';
    toolsDrawer.querySelector('#drawerAvatar').textContent='T';
    toolsDrawer.querySelector('#drawerLogin').hidden=false;
    toolsDrawer.querySelector('#drawerLogin').href=loginUrl();
    ensureMenuTabFirst();
    setActive(routeTool());
  }

  function applySignedIn(me){
    signedIn=true;
    window.TVCSignedIn=true;
    window.TVCCurrentUser=me;
    host.dataset.authState='signed-in';
    trigger.dataset.authState='signed-in';
    const initial=(me.name||me.email||'T').trim().slice(0,1).toUpperCase();
    host.querySelector('#toolbarAccountIcon').textContent=initial;
    host.querySelector('#toolbarAccountAvatar').textContent=initial;
    host.querySelector('#toolbarAccountEmail').textContent=me.email||'';
    host.querySelector('#toolbarAccountLabel').textContent=labels[language()].account;
    host.querySelector('#mobileToolbarCredits').textContent=Number(me.usage_balance||me.credits||0).toLocaleString('vi-VN',{maximumFractionDigits:1});
    toolsDrawer.querySelector('#drawerEmail').textContent=me.email||'';
    toolsDrawer.querySelector('#drawerCredits').textContent=Number(me.usage_balance||me.credits||0).toLocaleString('vi-VN',{maximumFractionDigits:1});
    toolsDrawer.querySelector('#drawerAvatar').textContent=initial;
    toolsDrawer.querySelector('#drawerLogin').hidden=true;
    ensureMenuTabFirst();
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
  window.tvcSyncAccount = syncAccount;

  trigger.addEventListener('click',e=>{
    e.preventDefault();
    if(!signedIn){
      closeMenu(false);
      if(typeof window.tvcOpenLoginModal === 'function'){
        window.tvcOpenLoginModal(location.pathname + location.search + location.hash);
      } else if(typeof window.showAuth === 'function'){
        window.showAuth(location.pathname + location.search + location.hash);
      } else {
        location.href=loginUrl();
      }
      return;
    }
    menuOpen?closeMenu():openMenu();
  });

  listen(document,'click',event=>{
    if(menuOpen&&!host.contains(event.target))closeMenu();
  });
  listen(document,'keydown',event=>{
    if(event.key==='Escape'&&menuOpen){
      closeMenu();
      trigger.focus({preventScroll:true});
    }
    if(event.key==='Escape'&&toolsDrawer.classList.contains('open')){
      closeTools();
      toolsTrigger.focus({preventScroll:true});
    }
  });
  host.querySelectorAll('.global-actions [data-tool]:not([data-tool="account"])').forEach(tab=>{
    tab.addEventListener('pointerdown',()=>{
      setActive(tab.dataset.tool);
    });
    tab.addEventListener('click',e=>{
      closeMenu(false);
      setActive(tab.dataset.tool);
      const tool=tab.dataset.tool;
      if(tool==='models'){
        if(location.pathname==='/' || location.pathname==='/index.html'){
          e.preventDefault();
          window.scrollTo({top:0,behavior:'smooth'});
        } else {
          location.href='/';
        }
      } else if(tool==='affiliate'){
        if(location.pathname==='/app'){
          e.preventDefault();
          if(typeof window.tvcGotoTab==='function') window.tvcGotoTab('affiliate',{source:'toolbar'});
        } else {
          location.href='/app#affiliate';
        }
      } else if(tool==='wallet'){
        if(location.pathname==='/app'){
          e.preventDefault();
          if(typeof window.tvcGotoTab==='function') window.tvcGotoTab('wallet',{source:'toolbar'});
        } else {
          location.href='/app#wallet';
        }
      } else if(tool==='history'){
        if(location.pathname==='/app'){
          e.preventDefault();
          if(typeof window.tvcGotoTab==='function'){
            window.tvcGotoTab('jobs');
          }
        } else {
          location.href='/app#jobs';
        }
      }
    });
  });
  menu.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>closeMenu(false)));
  host.querySelector('#toolbarLogout').addEventListener('click',async()=>{
    closeMenu(false);
    try{await fetch('/api/logout',{method:'POST',credentials:'same-origin'});}finally{
      applySignedOut();
      location.href='/';
    }
  });
  [...host.querySelectorAll('.lang-switch button'),...toolsDrawer.querySelectorAll('.lang-switch button')].forEach(button=>listen(button,'click',()=>applyLanguage(button.dataset.lang)));

  listen(window,'hashchange',()=>{closeMenu(false);setActive(routeTool())});
  listen(window,'popstate',()=>{closeMenu(false);setActive(routeTool())});
  listen(window,'pageshow',()=>syncAccount());
  listen(document,'visibilitychange',()=>{if(!document.hidden)syncAccount()});
  listen(document,'tvc-auth-change',()=>syncAccount());

  function updateToolbarHeight(){
    document.documentElement.style.setProperty('--header-height',Math.ceil(host.getBoundingClientRect().height)+'px');
    document.documentElement.style.setProperty('--tvc-toolbar-height',`${Math.ceil(host.getBoundingClientRect().height)}px`);
  }
  let toolbarResizeObserver=null;
  if('ResizeObserver' in window){
    toolbarResizeObserver=new ResizeObserver(updateToolbarHeight);toolbarResizeObserver.observe(host);
  }else{
    listen(window,'resize',updateToolbarHeight,{passive:true});
  }
  signal.addEventListener('abort',()=>toolbarResizeObserver?.disconnect(),{once:true});
  listen(window,'orientationchange',updateToolbarHeight,{passive:true});
  document.fonts?.ready.then(updateToolbarHeight);

  window.TVCGlobalToolbar={setActive,syncAccount,closeMenu};
  applyLanguage(language());
  setActive(routeTool());
  requestAnimationFrame(updateToolbarHeight);
  syncAccount();
})();
