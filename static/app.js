
const TVC_I18N = {
  vi:{
    topup:"Nạp VIP", account:"Tài Khoản", balance:"Số dư", accountSettings:"Tài khoản", hello:"Xin chào", profile:"Hồ Sơ Của Tôi", affiliateMenu:"Giới Thiệu", addTVC:"Nạp thêm",
    wallet:"Ví xu", earn:"Giới Thiệu", logout:"Đăng xuất", models:"Trang Chủ", history:"Lịch Sử",
    chooseModelEyebrow:"CHỌN MODEL", chooseToolSubtitle:"Chọn một công cụ bên dưới để bắt đầu tạo nội dung.",
    creditPayment:"Thanh toán bằng xu", refundNote:"Job lỗi được hoàn xu tự động",
    modelMotionTitle:"AI Motion Studio", modelMotionDesc:"Sao chép chuyển động chân thực từ video mẫu, giữ trọn thần thái nhân vật.",
    createNow:"Tạo ngay",
    modelBgTitle:"AI Đổi Bối Cảnh", modelBgDesc:"Thay bối cảnh phía sau nhưng giữ nguyên nhân vật.",
    modelOutfitImageTitle:"AI Đổi Trang Phục", modelOutfitImageDesc:"Thay trang phục cho nhân vật, ưu tiên giữ nguyên khuôn mặt và danh tính.",
    modelUpscaleTitle:"AI Nâng Cấp Ảnh", modelUpscaleDesc:"Nâng độ phân giải ảnh, ưu tiên giữ khuôn mặt và chi tiết.",
    comingSoon:"Sắp mở", processKicker:"QUY TRÌNH", processTitle:"3 bước để khách tạo video.",
    process1Title:"Chọn model", process1Desc:"Khách chọn công cụ phù hợp với nhu cầu.",
    process2Title:"Tải dữ liệu", process2Desc:"Upload ảnh, video mẫu và nhập prompt nếu cần.",
    process3Title:"Nhận kết quả", process3Desc:"Job vào queue, GPU xử lý và trả file về tài khoản.",
    creditsKicker:"HỆ THỐNG XU", creditsTitle:"Dùng xu cho từng dịch vụ.",
    creditsDesc:"Hệ thống hỗ trợ tài khoản, xu, hàng đợi job, hoàn xu khi lỗi và admin duyệt nạp.",
    dashboardCta:"Vào dashboard →", createVideoNav:"✨ Tạo video", myJobsNav:"▤ Job của tôi",
    walletNav:"◈ Ví xu", earnNav:"🔗 Giới thiệu", accountNav:"⚙ Tài khoản",
    login:"Đăng nhập", register:"Đăng ký", welcomeBack:"Chào mừng quay lại", createAccount:"Tạo tài khoản",
    createVideoTitle:"Tạo video mới", characterImage:"Ảnh nhân vật", motionVideo:"Video chuyển động", model:"Model",
    aspect:"Tỷ lệ", quality:"Chất lượng", prompt:"Prompt", cost:"Chi phí", createVideo:"Tạo video",
    tips:"MẸO", betterVideo:"Để video ổn hơn", myJobs:"Job của tôi", topupRequest:"Tạo yêu cầu nạp điểm",
    topupHistory:"Lịch sử nạp", creditLedger:"Biến động xu", affiliateTitle:"Giới Thiệu Bạn Bè",
    affiliateSubtitle:"Chia sẻ link hoặc mã giới thiệu của bạn",
    shareReward:"Chia Sẻ & Nhận Thưởng", enterReferral:"Nhập Mã Giới Thiệu",
  },
  en:{
    topup:"VIP Top-up", account:"Account", balance:"Balance", accountSettings:"Account settings", hello:"Hello", profile:"My Profile", affiliateMenu:"Referral", addTVC:"Add TVC",
    wallet:"Usage wallet", earn:"Referral", logout:"Log out", models:"Choose Model", history:"History",
    chooseModelEyebrow:"CHOOSE A MODEL", chooseToolSubtitle:"Choose a tool below to start creating content.",
    creditPayment:"Pay per use", refundNote:"Uses are automatically refunded if a job fails",
    modelMotionTitle:"AI Motion Studio", modelMotionDesc:"Realistically copy motion from a reference video while preserving the character’s presence.",
    createNow:"Create now",
    modelBgTitle:"AI Đổi Bối Cảnh", modelBgDesc:"Replace the background while preserving the character.",
    modelOutfitImageTitle:"AI Đổi Trang Phục", modelOutfitImageDesc:"Change clothing while prioritizing face and identity preservation.",
    modelUpscaleTitle:"AI Nâng Cấp Ảnh", modelUpscaleDesc:"Increase image resolution while prioritizing facial identity and detail.",
    comingSoon:"Coming soon", processKicker:"WORKFLOW", processTitle:"3 steps to create a video.",
    process1Title:"Choose a model", process1Desc:"Pick the AI tool that matches your task.",
    process2Title:"Upload inputs", process2Desc:"Upload images, a motion video and an optional prompt.",
    process3Title:"Get the result", process3Desc:"The job enters the queue, the GPU renders it, and the result returns to your account.",
    creditsKicker:"USAGE SYSTEM", creditsTitle:"Sell AI services per job.",
    creditsDesc:"The backend already supports accounts, usage balance, job queue, automatic refunds on failure and admin-approved top-ups.",
    dashboardCta:"Open dashboard →", createVideoNav:"✨ Create Video", myJobsNav:"▤ My Jobs",
    walletNav:"◈ Usage wallet", earnNav:"🔗 Referral", accountNav:"⚙ Account",
    login:"Log in", register:"Sign up", welcomeBack:"Welcome back", createAccount:"Create account",
    createVideoTitle:"Create a new video", characterImage:"Character image", motionVideo:"Motion video", model:"Model",
    aspect:"Aspect ratio", quality:"Quality", prompt:"Prompt", cost:"Estimated cost", createVideo:"Create video",
    tips:"TIPS", betterVideo:"For better results", myJobs:"My jobs", topupRequest:"Create a top-up request",
    topupHistory:"Top-up history", creditLedger:"Usage activity", affiliateTitle:"Refer Friends",
    affiliateSubtitle:"Share your referral link or code",
    shareReward:"Share & Earn", enterReferral:"Enter Referral Code",
  }
};

function tvcApplyLanguage(lang){
  const dict=TVC_I18N[lang]||TVC_I18N.vi;
  document.documentElement.lang=lang;
  localStorage.setItem('tvc_lang',lang);
  document.querySelectorAll('[data-i18n]').forEach(el=>{
    const key=el.dataset.i18n;
    if(dict[key]!=null) el.textContent=dict[key];
  });
  document.querySelectorAll('.lang-switch button').forEach(b=>b.classList.toggle('active',b.dataset.lang===lang));
}

function tvcInitToolbar(){
  const lang=localStorage.getItem('tvc_lang')||'vi';
  tvcApplyLanguage(lang);

  document.querySelectorAll('.lang-switch button').forEach(b=>{
    b.addEventListener('click',()=>tvcApplyLanguage(b.dataset.lang));
  });

  const details=document.getElementById('accountMenuDetails');

  // Native <details> handles open/close, so the Account button works
  // even if other JS on the page is busy.
  document.addEventListener('click',e=>{
    if(details?.open && !details.contains(e.target)){
      details.open=false;
    }
  });

  document.addEventListener('keydown',e=>{
    if(e.key==='Escape' && details) details.open=false;
  });

  document.querySelectorAll('#accountPopover [data-account-action]').forEach(link=>{
    link.addEventListener('click',()=>{
      if(details) details.open=false;
    });
  });

  document.getElementById('toolbarLogout')?.addEventListener('click',async()=>{
    if(details) details.open=false;
    await fetch('/api/logout',{method:'POST'});
    location.href='/';
  });

}

async function tvcSyncToolbarAccount(){
  try{
    const r=await fetch('/api/me');
    if(!r.ok) throw new Error();
    const me=await r.json();
    const credits=Number(me.usage_balance||me.credits||0);
    const initial=(me.name||me.email||'T').slice(0,1).toUpperCase();
    const set=(id,val)=>{const e=document.getElementById(id);if(e)e.textContent=val};
    set('toolbarCredits',credits.toLocaleString('vi-VN',{maximumFractionDigits:1}));set('mobileToolbarCredits',credits.toLocaleString('vi-VN',{maximumFractionDigits:1}));
    set('toolbarAccountCredits',credits.toLocaleString('vi-VN',{maximumFractionDigits:1}));
    set('toolbarAccount',document.documentElement.lang==='en'?'Account':'Tài Khoản');
    set('toolbarAccountName',me.name||'Tài Khoản');
    set('toolbarAccountEmail',me.email||'');
    set('toolbarAccountDot',initial);
    set('toolbarAccountAvatar',initial);set('mobileAccountInitial',initial);
  }catch{
    const set=(id,val)=>{const e=document.getElementById(id);if(e)e.textContent=val};
    set('toolbarCredits','0.0');set('mobileToolbarCredits','0.0');
    set('toolbarAccountCredits','0');
    set('toolbarAccount','Tài Khoản');
    set('toolbarAccountName','Tài Khoản');
    set('toolbarAccountEmail',document.documentElement.lang==='en'?'Not signed in':'Chưa đăng nhập');
  }
}

const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const toast=$('#toast'); function say(t){toast.textContent=t;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2400)}
let me=null, selectedPack='starter';




async function api(url,opt={}){
  const token=localStorage.getItem('token');
  const headers=Object.assign({}, opt.headers||{});
  if(token && !headers['Authorization']) headers['Authorization']='Bearer '+token;
  const opts=Object.assign({credentials:'same-origin'}, opt, {headers});
  const r=await fetch(url,opts);let j={};try{j=await r.json()}catch{};
  if(!r.ok){const messages={400:'Dữ liệu gửi lên chưa hợp lệ. Vui lòng kiểm tra lại.',422:'Dữ liệu gửi lên chưa hợp lệ. Vui lòng kiểm tra lại.',401:'Phiên đăng nhập hoặc quyền truy cập không hợp lệ.',403:'Phiên đăng nhập hoặc quyền truy cập không hợp lệ.',429:'Hệ thống đang có nhiều tác vụ. Vui lòng thử lại sau.',500:'Có lỗi xảy ra khi xử lý tác vụ.',503:'GPU hiện chưa sẵn sàng. Vui lòng thử lại.'};const error=new Error(messages[r.status]||j.detail||'Không thể kết nối dịch vụ xử lý.');error.status=r.status;throw error}return j
}
function referralFromUrl(){
  const p=new URLSearchParams(location.search);
  return (p.get('ref')||'').trim();
}
async function boot(){
  tvcInitToolbar();
  const ref=referralFromUrl();
  const initialPath=location.pathname;
  const initialHash=location.hash;
  const hashMap={'#affiliate':'affiliate','#jobs':'jobs','#wallet':'wallet','#account':'account','#create':'create'};
  let targetTab='create';
  if(initialPath==='/history'||initialPath==='/lich-su') targetTab='jobs';
  else if(hashMap[initialHash]) targetTab=hashMap[initialHash];
  currentTab=targetTab;
  if(targetTab!=='create') goto(targetTab,{source:'boot'});
  else updateMobileToolState('create');

  try{
    me=await api('/api/me');showDashboard();await refreshAll();
    if(targetTab==='affiliate') loadAffiliate();
    const returnTarget=window.TVCReturnNavigation?.consumeReturn()||'/';
  }catch{
    me=null;showDashboard();
  }
  pollPendingTopup();

  if(initialHash === '#login' || initialHash === '#register'){
    showAuth();
  }
}
function showAuth(returnUrl){
  const modal=$('#authGate')||$('#loginModal');
  if(modal){
    modal.classList.remove('hidden');
    modal.classList.add('open');
    if(returnUrl){
      try{sessionStorage.setItem('authReturnTo',returnUrl)}catch(_){}
    }
    if(typeof window.tvcRenderGoogleButtons === 'function'){
      window.tvcRenderGoogleButtons();
    }
  }
}
function showAuthSessionToast(){
  const toast=$('#authSessionToast');
  if(toast) toast.hidden=false;
}
function hideAuthSessionToast(){
  const toast=$('#authSessionToast');
  if(toast) toast.hidden=true;
}
$('#authSessionToastClose')?.addEventListener('click', hideAuthSessionToast);
$('#authSessionToastLogin')?.addEventListener('click', ()=>{
  hideAuthSessionToast();
  showAuth(location.pathname + location.search + location.hash);
});
window.showAuth = showAuth;
window.tvcOpenLoginModal = showAuth;

function closeAuth(){
  const modal=$('#authGate')||$('#loginModal');
  if(modal){
    modal.classList.remove('open');
  }
}
$('#loginClose')?.addEventListener('click', closeAuth);
$('#authGate')?.addEventListener('click', e=>{
  if(e.target===$('#authGate')) closeAuth();
});
document.addEventListener('keydown', e=>{
  if(e.key==='Escape'&&$('#authGate')?.classList.contains('open')) closeAuth();
});

window.addEventListener('hashchange', () => {
  if(location.hash === '#login' || location.hash === '#register'){
    showAuth();
  }
});
function showDashboard(){
  $('#authGate')?.classList.remove('open');
  $('#dashboard')?.classList.remove('hidden');
  if(me){
    hideAuthSessionToast();
    $('#TVC').textContent=me.usage_balance;$('#walletTVC').textContent=me.usage_balance;
    if($('#avatar')) $('#avatar').textContent=(me.name||me.email).slice(0,2).toUpperCase();tvcSyncToolbarAccount();
  }else{
    $('#TVC').textContent='—';$('#walletTVC').textContent='—';
  }
}
async function logout(){await fetch('/api/logout',{method:'POST'});location.reload()}
if($('#logout')) $('#logout').onclick=logout;if($('#logout2')) $('#logout2').onclick=logout;

const meta={
  create:['Tạo video mới','Ảnh nhân vật + video chuyển động'],
  jobs:['Job của tôi','Theo dõi hàng đợi và tải kết quả'],
  wallet:['Ví lượt','Nạp VIP và lịch sử giao dịch'],
  affiliate:['Giới Thiệu','Chia sẻ link và theo dõi người được giới thiệu'],
  account:['Tài khoản','Thông tin tài khoản']
};
let currentTab='create';
let tabSwitchToken=0;

function updateMobileToolState(tab){
  const map={create:'models',jobs:'history',affiliate:'affiliate',wallet:'wallet',account:'account'};
  const tool=map[tab]||'models';
  if(window.TVCGlobalToolbar) window.TVCGlobalToolbar.setActive(tool);
}

function goto(tab,opts={}){
  if(!meta[tab]) return;

  const target=$('#tab-'+tab);
  if(!target) return;
  currentTab=tab;
  const token=++tabSwitchToken;

  $$('.side').forEach(x=>x.classList.toggle('active',x.dataset.tab===tab));
  updateMobileToolState(tab);

  if($('#pageTitle')) $('#pageTitle').textContent=meta[tab][0];
  if($('#pageSub')) $('#pageSub').textContent=meta[tab][1];

  const hash=tab==='create'?'#create':'#'+tab;
  history.replaceState(null,'',location.pathname+location.search+hash);

  $$('.tab').forEach(x=>{
    if(x!==target){
      x.classList.remove('active','tab-leaving','tab-entering','tab-entered','tab-refresh');
    }
  });
  target.classList.add('active','tab-entered');

  // Start data loading after the UI has already reacted to the tap.
  requestAnimationFrame(()=>{
    if(tab==='jobs') loadJobs();
    if(tab==='wallet') loadWallet();
    if(tab==='affiliate') loadAffiliate();
  });

  window.scrollTo({top:0,behavior:'smooth'});
}
window.tvcGotoTab=goto;

$$('.side').forEach(b=>b.onclick=()=>goto(b.dataset.tab));
$$('[data-goto]').forEach(b=>b.onclick=()=>goto(b.dataset.goto));

// On the app page, toolbar History / Affiliate / Wallet switch tabs directly.
// This avoids a document navigation/reload on mobile and makes taps feel instant.
const toolbarTabMap={history:'jobs',affiliate:'affiliate',wallet:'wallet'};
document.querySelectorAll('.global-actions [data-tool]').forEach(link=>{
  const tab=toolbarTabMap[link.dataset.tool];
  if(!tab) return;
  link.addEventListener('click',e=>{
    e.preventDefault();
    goto(tab,{source:'toolbar'});
  });
});

window.addEventListener('hashchange',()=>{
  const map={'#create':'create','#jobs':'jobs','#wallet':'wallet','#affiliate':'affiliate','#account':'account'};
  if(map[location.hash] && map[location.hash]!==currentTab){
    goto(map[location.hash],{source:'hash'});
  }
});

const form=$('#jobForm');
const renderBtns=$$('.simple-render-btn');
const renderBtnHTML=new Map(renderBtns.map(btn=>[btn,btn.innerHTML]));
let jobSubmitLocked=false;
let motionPriceCredits=null;
async function syncMotionPrice(){
  try{
    const response=await fetch('/api/tools',{cache:'no-store'});
    if(!response.ok)return;
    const tool=(await response.json()).find(item=>item.service_key==='motion_studio');
    if(!tool)return;
    motionPriceCredits=Number(tool.is_free?0:tool.price_credits||0);
    const label=motionPriceCredits===0?'Miễn phí cho mỗi video':`Tạo video AI chỉ từ ${motionPriceCredits} Xu / 1 video`;
    document.querySelectorAll('[data-motion-price-label]').forEach(node=>node.textContent=label);
    document.querySelectorAll('[data-motion-price]').forEach(node=>node.textContent=motionPriceCredits===0?'Miễn phí':`${motionPriceCredits} Xu`);
    if($('#cost'))$('#cost').textContent=motionPriceCredits===0?'Miễn phí':`${motionPriceCredits} Xu`;
    renderBtns.forEach(btn=>{renderBtnHTML.set(btn,btn.innerHTML)});
  }catch(_){ }
}
const motionForm=window.TVCMotionForm?.create(form,{onValidityChange:valid=>{
  if(!jobSubmitLocked)renderBtns.forEach(btn=>{
    btn.disabled=!valid;
    btn.setAttribute('aria-disabled',valid?'false':'true');
  });
}});

$$('.simple-aspect').forEach(btn=>btn.onclick=()=>{
  if(form.classList.contains('is-submitting')) return;
  $$('.simple-aspect').forEach(x=>x.classList.remove('active'));
  btn.classList.add('active');
  $('#aspectRatio').value=btn.dataset.aspect;
});

function jobRequestKey(){
  if(window.crypto?.randomUUID) return window.crypto.randomUUID();
  return 'job-'+Date.now()+'-'+Math.random().toString(36).slice(2);
}
function setJobSubmitLocked(locked,activeBtn=null){
  jobSubmitLocked=locked;
  form.classList.toggle('is-submitting',locked);
  form.setAttribute('aria-busy',locked?'true':'false');
  renderBtns.forEach(btn=>{
    const disabled=locked||!motionForm?.isValid();
    btn.disabled=disabled;
    btn.setAttribute('aria-disabled',disabled?'true':'false');
    if(locked && btn===activeBtn){
      btn.innerHTML='<span><b>⏳ Đang gửi tác vụ...</b><small>Không cần bấm lại</small></span><em>…</em>';
    }else if(!locked){
      btn.innerHTML=renderBtnHTML.get(btn);
    }
  });
}

form.onsubmit=async e=>{
  e.preventDefault();
  if(jobSubmitLocked) return;
  if(!me && !window.TVCSignedIn){
    showAuth(location.pathname + location.search + location.hash);
    return;
  }
  if(!motionForm||!await motionForm.validateForSubmit()){
    say(motionForm?.firstError()||'Vui lòng kiểm tra lại ảnh và video mẫu');
    return;
  }
  const submitter=e.submitter || renderBtns[0];
  setJobSubmitLocked(true,submitter);
  // One public render mode: backend also enforces one TVC per job.
  if($('#cost')) $('#cost').textContent=motionPriceCredits===0?'Miễn phí':`${motionPriceCredits ?? '—'} Xu`;
  const fd=new FormData(form);
  fd.set('request_key',jobRequestKey());
  try{
    const j=await api('/api/jobs',{method:'POST',body:fd});
    say(j.duplicate?('Job #'+j.job_id+' đã được nhận, không tạo trùng.'):('Đã tạo job #'+j.job_id));
    me=await api('/api/me');showDashboard();showMotionQueuedState(j);
  }catch(err){
    showMotionSubmitError(err);
  }finally{
    setJobSubmitLocked(false);
  }

}
function showMotionSubmitError(error){
  const state=$('#motionSubmitError');if(!state)return;
  $('#motionSubmitErrorMessage').textContent=error.message==='Failed to fetch'?'Không thể kết nối dịch vụ xử lý.':error.message;state.hidden=false;
}
function showMotionQueuedState(job){
  const state=$('#motionQueuedState');if(!state)return;
  $('#motionSubmitError').hidden=true;
  $('#motionQueuedJob').textContent=`Job #${job.job_id}`;
  $('#motionQueuedHistory').href=`/app?job=${encodeURIComponent(job.job_id)}#jobs`;
  state.hidden=false;form.hidden=true;window.scrollTo({top:0,behavior:'smooth'});
}
$('#motionContinueButton').onclick=()=>{
  const state=$('#motionQueuedState');if(!state)return;
  const aspect=$('#aspectRatio')?.value||'9:16',prompt=form.elements.prompt?.value||'';
  motionForm?.reset();form.reset();if(form.elements.prompt)form.elements.prompt.value=prompt;
  if($('#aspectRatio'))$('#aspectRatio').value=aspect;
  $$('.simple-aspect').forEach(button=>button.classList.toggle('active',button.dataset.aspect===aspect));
  state.hidden=true;form.hidden=false;setJobSubmitLocked(false);window.scrollTo({top:0,behavior:'smooth'});form.elements.image?.focus();
};
$('#motionRetryButton').onclick=()=>{$('#motionSubmitError').hidden=true;form.hidden=false;form.elements.image?.focus()};
syncMotionPrice();
function stateText(s){return {waiting:'Đang chờ',running:'Đang render',upscaling:'Đang nâng cấp video lên HD',done:'Hoàn thành',failed:'Render thất bại',cancelled:'Đã hủy',uploading:'Đang tải'}[s]||s}
function jobResultUrl(j){return (j.service && j.service !== 'motion_studio')?`/api/services/${encodeURIComponent(j.service)}/jobs/${j.id}/result`:`/api/jobs/${j.id}/output`}
function jobOpenUrl(j){return (j.service && j.service !== 'motion_studio')?`/services/${encodeURIComponent(j.service)}?job=${j.id}`:null}
function jobDisplayName(j){return {motion_studio:'AI Motion Studio',video_generation:'AI Video Creator',outfit_change:'AI Đổi Trang Phục',background_change:'AI Đổi Bối Cảnh',image_upscale:'AI Nâng Cấp Ảnh'}[j.service]||(!j.service?'AI Motion Studio':j.model)}
function jobOutputExtension(j){return ['outfit_change','background_change','image_upscale'].includes(j.service)?'png':'mp4'}
async function loadJobs(){
  if(!me){
    $('#jobsList').innerHTML='<div class="panel-card">Vui lòng đăng nhập để xem danh sách job của bạn.</div>';
    return;
  }
  try{
    const jobs=await api('/api/jobs');
    const requestedJob=new URLSearchParams(location.search).get('job');
    $('#jobsList').innerHTML=jobs.length?jobs.map(j=>`<div class="job ${String(j.id)===requestedJob?'job-highlight':''}" data-job-id="${j.id}">
      <div class="thumb">🎬</div>
      <div><b>#${j.id} • ${jobDisplayName(j)}</b><small>${j.aspect_ratio} • ${new Date(j.created_at).toLocaleString('vi-VN')}</small>${j.error?`<small style="color:#ff7a88">${j.error}</small>`:''}${jobOpenUrl(j)?`<small><a class="mini-btn" href="${jobOpenUrl(j)}">Mở lại job</a></small>`:''}</div>
      <div><progress value="${j.progress}" max="100"></progress><small>${j.progress}%</small></div>
      <div class="state ${j.status}">${stateText(j.status)}${j.has_output?`<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;"><a class="mini-btn" href="${jobResultUrl(j)}" target="_blank" style="background:rgba(168,85,247,0.35);border:1px solid rgba(255,255,255,0.4);color:#fff;font-weight:700;">▶ Xem</a><a class="mini-btn" href="${jobResultUrl(j)}?download=1" download="tvc_result_${j.id}.${jobOutputExtension(j)}" style="background:rgba(217,70,239,0.35);border:1px solid rgba(255,255,255,0.4);color:#fff;font-weight:700;">⬇ Tải về</a></div>`:''}${j.can_cancel&&!j.service?`<br><button class="mini-btn cancel-job-btn" data-job-id="${j.id}" type="button">Hủy</button>`:''}</div>
    </div>`).join(''):'<div class="panel-card">Chưa có job nào.</div>';
    if(requestedJob)document.querySelector(`[data-job-id="${CSS.escape(requestedJob)}"]`)?.scrollIntoView({block:'center',behavior:'smooth'});
  }catch(e){say(e.message)}
}
$('#refreshJobs').onclick=loadJobs;
$('#jobsList').addEventListener('click',async e=>{
  const button=e.target.closest?.('.cancel-job-btn');
  if(!button||button.disabled) return;
  button.disabled=true;
  try{
    await api('/api/jobs/'+encodeURIComponent(button.dataset.jobId),{method:'DELETE'});
    say('Đã hủy job');await loadJobs();me=await api('/api/me');showDashboard();
  }catch(error){say(error.message);button.disabled=false}
});

$$('.packs button').forEach(b=>b.onclick=()=>{
  $$('.packs button').forEach(x=>{x.classList.remove('active');x.setAttribute('aria-pressed','false')});
  b.classList.add('active');b.setAttribute('aria-pressed','true');selectedPack=b.dataset.pack
});
$('#requestTopup').onclick=async()=>{
  const btn=$('#requestTopup');
  try{
    if(btn){btn.disabled=true;btn.textContent='Đang kết nối PayOS...';}
    const j=await api('/api/payments/create-link',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({package:selectedPack,note:$('#topupNote').value})});
    const checkoutUrl=j.checkoutUrl||j.checkout_url;
    if(checkoutUrl){
      sessionStorage.setItem('tvc_pending_topup',String(j.topup_id||j.topupId||j.order_code||j.orderCode));
      window.location.href=checkoutUrl;
      return;
    }
    say('Đã tạo yêu cầu nạp #'+(j.topup_id||j.order_code||''));loadWallet();
  }catch(e){say(e.message)}
  finally{
    if(btn){btn.disabled=false;btn.textContent='Thanh toán qua PayOS';}
  }
}
function packageName(key){return {starter:'Gói Thử',basic:'Gói Cơ bản',creator:'Gói Phổ biến',professional:'Gói Chuyên nghiệp'}[key]||key}
async function loadWallet(){
  if(!me){
    showAuthSessionToast();
    if($('#walletVideoRemaining')) $('#walletVideoRemaining').textContent='0';
    $('#topupList').innerHTML='<div class="simple-row">Vui lòng đăng nhập để nạp xu và xem lịch sử.</div>';
    $('#ledgerList').innerHTML='<div class="simple-row">Chưa có giao dịch.</div>';
    return;
  }
  try{
    me=await api('/api/me');showDashboard();
    const videoTurns=Math.max(0,Number(me.usage_balance||me.credits||0));
    if($('#walletVideoRemaining')) $('#walletVideoRemaining').textContent=videoTurns;
    const [tops,led]=await Promise.all([api('/api/topups'),api('/api/ledger')]);
    $('#topupList').innerHTML=tops.length?tops.map(x=>`<div class="simple-row"><b>#${x.id} • ${packageName(x.package)} • ${x.credits} xu</b><span>${x.status} • ${x.amount_vnd.toLocaleString('vi-VN')}đ</span></div>`).join(''):'<div class="simple-row">Chưa có yêu cầu nạp.</div>';
    $('#ledgerList').innerHTML=led.length?led.map(x=>`<div class="simple-row"><b>${x.reason}</b><span style="color:${x.delta>=0?'#61df94':'#ff8490'}">${x.delta>0?'+':''}${x.delta} xu</span></div>`).join(''):'<div class="simple-row">Chưa có giao dịch.</div>'
  }catch(e){say(e.message)}
}

async function refreshAll(){
  if(!me) return;
  await loadJobs();await loadWallet();
  $('#accountInfo').innerHTML=`<p><b>${me.name}</b></p><p>${me.email}</p><p>Vai trò: ${me.role}</p><p>Ngày tạo: ${new Date(me.created_at).toLocaleString('vi-VN')}</p>`
}
async function pollPendingTopup(){
  const topupId=sessionStorage.getItem('tvc_pending_topup');
  if(!topupId||!me)return;
  say('Thanh toán thành công. Đang xác nhận giao dịch...');
  for(let attempt=0;attempt<8;attempt++){
    try{
      const topup=await api(`/api/topups/${encodeURIComponent(topupId)}`);
      if(['approved','paid','completed'].includes(topup.status)){
        sessionStorage.removeItem('tvc_pending_topup');
        say(`✅ Nạp xu thành công: +${topup.credits} xu đã được cộng vào tài khoản.`);
        me=await api('/api/me');showDashboard();loadWallet();return;
      }
    }catch(error){say(error.message);return}
    await new Promise(resolve=>setTimeout(resolve,3000));
  }
}
setInterval(()=>{if(me&&document.querySelector('#tab-jobs.active'))loadJobs()},5000);
boot();
