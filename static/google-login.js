(function(){
  'use strict';

  const qs=(s,r=document)=>r.querySelector(s);
  const currentLang=()=>document.documentElement.lang==='en'?'en':'vi';
  let googleInitialized=false;
  let googleClientId='';

  function referralCode(){
    try{return (new URLSearchParams(location.search).get('ref')||'').trim();}catch{return '';}
  }

  function signedOutMarkup(){
    return `
      <div class="account-login-mini" id="accountSignedOutPanel">
        <div class="account-login-mini-head">
          <span class="account-login-lock">⌾</span>
          <div>
            <strong data-login-title>Đăng nhập</strong>
            <small data-login-sub>Tiếp tục với TVC Studio AI</small>
          </div>
        </div>
        <div class="google-signin-shell"><div class="google-signin-button" data-google-button></div></div>
        <div class="account-login-or"><span></span><b>hoặc</b><span></span></div>
        <a class="account-email-login" href="/app#login" data-email-login>Đăng nhập bằng Email</a>
        <a class="account-register-link" href="/app#register" data-register-link>Chưa có tài khoản? <b>Đăng ký</b></a>
        <div class="account-google-error" data-google-error hidden></div>
      </div>`;
  }

  function ensureSignedOutPanel(){
    const pop=qs('#accountPopover');
    if(!pop) return null;
    let panel=qs('#accountSignedOutPanel',pop);
    if(!panel){
      pop.insertAdjacentHTML('afterbegin',signedOutMarkup());
      panel=qs('#accountSignedOutPanel',pop);
    }
    return panel;
  }

  function existingSignedInNodes(pop,panel){
    return [...pop.children].filter(el=>el!==panel);
  }

  function setToolbarLoggedOut(){
    const currentTrigger=qs('#toolbarAccountTrigger');
    if(currentTrigger){
      currentTrigger.dataset.authState='signed-out';
      const label=qs('#toolbarAccountLabel',currentTrigger),icon=qs('#toolbarAccountIcon',currentTrigger);
      if(label)label.textContent=currentLang()==='en'?'Log In':'Đăng Nhập';
      if(icon)icon.textContent='↪';
      return;
    }
    const details=qs('#accountMenuDetails');
    const pop=qs('#accountPopover');
    if(!details||!pop) return;
    const panel=ensureSignedOutPanel();
    if(!panel) return;
    existingSignedInNodes(pop,panel).forEach(el=>el.style.display='none');
    panel.style.display='block';
    details.dataset.authState='signed-out';

    const lang=currentLang();
    const label=qs('#accountMenuSummary .mobile-tool-label');
    const icon=qs('#accountMenuSummary .mobile-account-icon');
    if(label){
      label.removeAttribute('data-i18n');
      label.textContent=lang==='en'?'Log in':'Đăng nhập';
    }
    if(icon) icon.textContent='⌾';
    const title=qs('[data-login-title]',panel), sub=qs('[data-login-sub]',panel), email=qs('[data-email-login]',panel), reg=qs('[data-register-link]',panel);
    if(title) title.textContent=lang==='en'?'Log in':'Đăng nhập';
    if(sub) sub.textContent=lang==='en'?'Continue to TVC Studio AI':'Tiếp tục với TVC Studio AI';
    if(email) email.textContent=lang==='en'?'Log in with Email':'Đăng nhập bằng Email';
    if(reg) reg.innerHTML=lang==='en'?'No account? <b>Sign up</b>':'Chưa có tài khoản? <b>Đăng ký</b>';
    if(email&&window.TVCReturnNavigation)email.href=window.TVCReturnNavigation.loginUrl();
    if(reg&&window.TVCReturnNavigation){const target=window.TVCReturnNavigation.resolveReturn();window.TVCReturnNavigation.storeReturn(target);reg.href=`/app?return_to=${encodeURIComponent(target)}#register`;}
  }

  function setToolbarLoggedIn(me){
    const currentTrigger=qs('#toolbarAccountTrigger');
    if(currentTrigger){
      currentTrigger.dataset.authState='signed-in';
      const label=qs('#toolbarAccountLabel',currentTrigger),icon=qs('#toolbarAccountIcon',currentTrigger);
      if(label)label.textContent=currentLang()==='en'?'Account':'Tài Khoản';
      if(icon)icon.textContent=(me?.name||me?.email||'T').slice(0,1).toUpperCase();
      return;
    }
    const details=qs('#accountMenuDetails');
    const pop=qs('#accountPopover');
    if(!details||!pop) return;
    const panel=ensureSignedOutPanel();
    if(panel) panel.style.display='none';
    existingSignedInNodes(pop,panel).forEach(el=>el.style.display='');
    details.dataset.authState='signed-in';

    const label=qs('#accountMenuSummary .mobile-tool-label');
    const icon=qs('#accountMenuSummary .mobile-account-icon');
    if(label){
      label.setAttribute('data-i18n','account');
      label.textContent=currentLang()==='en'?'Account':'Tài Khoản';
    }
    if(icon) icon.textContent=(me?.name||me?.email||'T').slice(0,1).toUpperCase();
  }

  function showGoogleError(message,root=document){
    root.querySelectorAll('[data-google-error]').forEach(el=>{
      el.hidden=!message;
      el.textContent=message||'';
    });
    const gate=qs('#googleAuthGateError');
    if(gate){gate.hidden=!message;gate.textContent=message||'';}
  }

  async function handleCredential(resp){
    if(!resp?.credential) return;
    showGoogleError('');
    try{
      const r=await fetch('/api/auth/google',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        credentials:'same-origin',
        body:JSON.stringify({credential:resp.credential,referral_code:referralCode()})
      });
      let j={}; try{j=await r.json();}catch{}
      if(!r.ok) throw new Error(j.detail||'Google Login thất bại');
      if(location.pathname==='/app')location.href=window.TVCReturnNavigation?.consumeReturn()||'/';else location.reload();
    }catch(err){
      showGoogleError(err.message||'Google Login thất bại');
    }
  }
  window.tvcGoogleCredential=handleCredential;

  function renderGoogleButtons(){
    if(!googleInitialized||!window.google?.accounts?.id) return;
    document.querySelectorAll('[data-google-button]').forEach(box=>{
      if(box.dataset.rendered==='1') return;
      box.dataset.rendered='1';
      google.accounts.id.renderButton(box,{
        type:'standard',
        theme:'outline',
        size:'large',
        shape:'pill',
        text:'signin_with',
        width:260
      });
    });
  }

  function injectGateGoogle(){
    const card=qs('#authGate .auth-card');
    if(!card||qs('#googleAuthGate',card)) return;
    const tabs=qs('.auth-tabs',card);
    const wrap=document.createElement('div');
    wrap.id='googleAuthGate';
    wrap.className='google-auth-gate';
    wrap.innerHTML=`<div class="google-signin-button" data-google-button></div><div class="account-login-or"><span></span><b>hoặc</b><span></span></div><div id="googleAuthGateError" class="account-google-error" hidden></div>`;
    if(tabs) tabs.insertAdjacentElement('afterend',wrap); else card.prepend(wrap);
  }

  async function waitForGoogle(maxMs=7000){
    const start=Date.now();
    while(Date.now()-start<maxMs){
      if(window.google?.accounts?.id) return true;
      await new Promise(r=>setTimeout(r,100));
    }
    return false;
  }

  async function initGoogle(){
    try{
      const r=await fetch('/api/auth/google-config',{credentials:'same-origin'});
      const cfg=await r.json();
      if(!cfg.enabled||!cfg.client_id){
        showGoogleError(currentLang()==='en'?'Google Login is not configured.':'Google Login chưa được cấu hình.');
        return;
      }
      googleClientId=cfg.client_id;
      if(!await waitForGoogle()){
        showGoogleError(currentLang()==='en'?'Could not load Google Login.':'Không tải được Google Login.');
        return;
      }
      if(!googleInitialized){
        google.accounts.id.initialize({
          client_id:googleClientId,
          callback:handleCredential,
          ux_mode:'popup',
          auto_select:false,
          cancel_on_tap_outside:true
        });
        googleInitialized=true;
      }
      renderGoogleButtons();
    }catch{
      showGoogleError(currentLang()==='en'?'Could not initialize Google Login.':'Không khởi tạo được Google Login.');
    }
  }

  function bindLocalLinks(){
    document.addEventListener('click',e=>{
      const email=e.target.closest?.('[data-email-login]');
      const reg=e.target.closest?.('[data-register-link]');
      if(!email&&!reg) return;
      if(location.pathname==='/app'){
        e.preventDefault();
        qs('#accountMenuDetails')?.removeAttribute('open');
        const gate=qs('#authGate'); if(gate) gate.classList.remove('hidden');
        const dash=qs('#dashboard'); if(dash) dash.classList.add('hidden');
        const target=reg?'register':'login';
        qs(`[data-auth="${target}"]`)?.click();
        const returnTo=window.TVCReturnNavigation?.resolveReturn()||'/';window.TVCReturnNavigation?.storeReturn(returnTo);
        history.replaceState(null,'',`/app?return_to=${encodeURIComponent(returnTo)}#${target}`);
      }
    });
  }

  async function syncAuthState(){
    ensureSignedOutPanel();
    injectGateGoogle();
    try{
      const r=await fetch('/api/me',{credentials:'same-origin'});
      if(!r.ok) throw new Error();
      const me=await r.json();
      setToolbarLoggedIn(me);
    }catch{
      setToolbarLoggedOut();
    }
    await initGoogle();
  }

  document.addEventListener('DOMContentLoaded',()=>{
    bindLocalLinks();
    syncAuthState();
    document.querySelectorAll('.lang-switch button').forEach(btn=>{
      btn.addEventListener('click',()=>setTimeout(syncAuthState,0));
    });
  });
})();
