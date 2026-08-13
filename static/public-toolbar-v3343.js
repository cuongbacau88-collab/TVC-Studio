
(function(){
  'use strict';

  const $=(s,r=document)=>r.querySelector(s);
  const setText=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};

  function applyLang(lang){
    const isEn=lang==='en';
    document.documentElement.lang=isEn?'en':'vi';
    localStorage.setItem('tvc_lang',isEn?'en':'vi');
    document.querySelectorAll('.lang-switch button').forEach(btn=>{
      btn.classList.toggle('active',btn.dataset.lang===(isEn?'en':'vi'));
    });

    const map={
      models:isEn?'Models':'Chọn Model',
      history:isEn?'History':'Lịch Sử',
      earn:isEn?'Referral':'Giới Thiệu',
      topup:isEn?'Top up':'Nạp VIP',
      account:isEn?'Account':'Tài Khoản'
    };
    Object.entries(map).forEach(([k,v])=>{
      document.querySelectorAll(`[data-i18n="${k}"]`).forEach(el=>el.textContent=v);
    });
  }

  async function syncAccount(){
    try{
      const r=await fetch('/api/me',{credentials:'same-origin'});
      if(!r.ok) throw new Error();
      const me=await r.json();
      const credits=Number(me.usage_balance||me.credits||0).toLocaleString('vi-VN',{maximumFractionDigits:1});
      const initial=(me.name||me.email||'T').slice(0,1).toUpperCase();
      setText('mobileToolbarCredits',credits);
      setText('toolbarAccountCredits',credits);
      setText('toolbarAccountName',me.name||'Tài Khoản');
      setText('toolbarAccountEmail',me.email||'');
      setText('toolbarAccountAvatar',initial);
      const icon=$('#accountMenuSummary .mobile-account-icon');
      if(icon) icon.textContent=initial;
    }catch{
      setText('mobileToolbarCredits','0');
      setText('toolbarAccountCredits','0');
    }
  }

  document.addEventListener('DOMContentLoaded',()=>{
    applyLang(localStorage.getItem('tvc_lang')||'vi');

    document.querySelectorAll('.lang-switch button').forEach(btn=>{
      btn.addEventListener('click',()=>applyLang(btn.dataset.lang));
    });

    const details=$('#accountMenuDetails');

    document.addEventListener('click',e=>{
      if(details?.open && !details.contains(e.target)) details.open=false;
    });
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape' && details) details.open=false;
    });
    document.querySelectorAll('#accountPopover [data-account-action]').forEach(a=>{
      a.addEventListener('click',()=>{if(details)details.open=false;});
    });

    $('#toolbarLogout')?.addEventListener('click',async()=>{
      if(details) details.open=false;
      try{await fetch('/api/logout',{method:'POST',credentials:'same-origin'});}catch{}
      location.href='/';
    });

    syncAccount();
  });
})();
