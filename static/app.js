
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
  if(!r.ok)throw new Error(j.detail||'Có lỗi xảy ra');return j
}
function referralFromUrl(){
  const p=new URLSearchParams(location.search);
  return (p.get('ref')||'').trim();
}
async function boot(){
  tvcInitToolbar();
  const ref=referralFromUrl();
  try{
    me=await api('/api/me');showDashboard();await refreshAll();
    const initialHash=location.hash;
    const hashMap={'#affiliate':'affiliate','#jobs':'jobs','#wallet':'wallet','#account':'account','#create':'create'};
    currentTab=hashMap[initialHash]||'create';
    if(hashMap[initialHash]) goto(hashMap[initialHash],{source:'boot'});
    else updateMobileToolState('create');
  }catch{
    showAuth();
  }
}
function showAuth(){
  $('#authGate')?.classList.remove('hidden');
  $('#dashboard')?.classList.add('hidden');
  if(typeof window.tvcRenderGoogleButtons === 'function'){
    window.tvcRenderGoogleButtons();
  }
}
window.showAuth = showAuth;
window.addEventListener('hashchange', () => {
  if(location.hash === '#login' || location.hash === '#register'){
    showAuth();
  }
});
function showDashboard(){
  $('#authGate')?.classList.add('hidden');
  $('#dashboard')?.classList.remove('hidden');
  $('#TVC').textContent=me.usage_balance;$('#walletTVC').textContent=me.usage_balance;
  if($('#avatar')) $('#avatar').textContent=(me.name||me.email).slice(0,2).toUpperCase();tvcSyncToolbarAccount()
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
  const old=$('.tab.active');
  const same=old===target;
  currentTab=tab;
  const token=++tabSwitchToken;

  $$('.side').forEach(x=>x.classList.toggle('active',x.dataset.tab===tab));
  updateMobileToolState(tab);

  $('#pageTitle').textContent=meta[tab][0];
  $('#pageSub').textContent=meta[tab][1];

  const hash=tab==='create'?'#create':'#'+tab;
  history.replaceState(null,'',location.pathname+location.search+hash);

  // Start data loading after the UI has already reacted to the tap.
  requestAnimationFrame(()=>{
    if(tab==='jobs') loadJobs();
    if(tab==='wallet') loadWallet();
    if(tab==='affiliate') loadAffiliate();
  });

  if(same){
    target?.classList.remove('tab-refresh');
    requestAnimationFrame(()=>target?.classList.add('tab-refresh'));
    setTimeout(()=>target?.classList.remove('tab-refresh'),220);
    return;
  }

  // Fast fade/slide on mobile, softer fade on desktop.
  if(old){
    old.classList.add('tab-leaving');
  }

  target.classList.add('active','tab-entering');

  requestAnimationFrame(()=>{
    requestAnimationFrame(()=>{
      if(token!==tabSwitchToken) return;
      target.classList.add('tab-entered');
      target.classList.remove('tab-entering');
    });
  });

  setTimeout(()=>{
    if(token!==tabSwitchToken) return;
    $$('.tab').forEach(x=>{
      if(x!==target){
        x.classList.remove('active','tab-leaving','tab-entering','tab-entered','tab-refresh');
      }
    });
    target.classList.add('active','tab-entered');
  },190);
}

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
      btn.innerHTML='<span><b>⏳ Đang tạo video...</b><small>Không cần bấm lại</small></span><em>…</em>';
    }else if(!locked){
      btn.innerHTML=renderBtnHTML.get(btn);
    }
  });
}

form.onsubmit=async e=>{
  e.preventDefault();
  if(jobSubmitLocked) return;
  if(!motionForm||!await motionForm.validateForSubmit()){
    say(motionForm?.firstError()||'Vui lòng kiểm tra lại ảnh và video mẫu');
    return;
  }
  const submitter=e.submitter || renderBtns[0];
  setJobSubmitLocked(true,submitter);
  // One public render mode: backend also enforces one TVC per job.
  if($('#cost')) $('#cost').textContent='1 lượt';
  const fd=new FormData(form);
  fd.set('request_key',jobRequestKey());
  try{
    const j=await api('/api/jobs',{method:'POST',body:fd});
    say(j.duplicate?('Job #'+j.job_id+' đã được nhận, không tạo trùng.'):('Đã tạo job #'+j.job_id));
    me=await api('/api/me');showDashboard();goto('jobs');
  }catch(err){
    say(err.message);
  }finally{
    setJobSubmitLocked(false);
  }
}
function stateText(s){return {waiting:'Đang chờ',running:'Đang render',upscaling:'Đang nâng cấp video lên HD',done:'Hoàn thành',failed:'Render thất bại',cancelled:'Đã hủy',uploading:'Đang tải'}[s]||s}
function jobResultUrl(j){return (j.service && j.service !== 'motion_studio')?`/api/services/${encodeURIComponent(j.service)}/jobs/${j.id}/result`:`/api/jobs/${j.id}/output`}
function jobOpenUrl(j){return (j.service && j.service !== 'motion_studio')?`/services/${encodeURIComponent(j.service)}?job=${j.id}`:null}
function jobDisplayName(j){return {motion_studio:'AI Motion Studio',video_generation:'AI Video Creator',outfit_change:'AI Đổi Trang Phục',background_change:'AI Đổi Bối Cảnh',image_upscale:'AI Nâng Cấp Ảnh'}[j.service]||(!j.service?'AI Motion Studio':j.model)}
function jobOutputExtension(j){return ['outfit_change','background_change','image_upscale'].includes(j.service)?'png':'mp4'}
async function loadJobs(){
  try{
    const jobs=await api('/api/jobs');
    $('#jobsList').innerHTML=jobs.length?jobs.map(j=>`<div class="job">
      <div class="thumb">🎬</div>
      <div><b>#${j.id} • ${jobDisplayName(j)}</b><small>${j.aspect_ratio} • ${new Date(j.created_at).toLocaleString('vi-VN')}</small>${j.error?`<small style="color:#ff7a88">${j.error}</small>`:''}${jobOpenUrl(j)?`<small><a class="mini-btn" href="${jobOpenUrl(j)}">Mở lại job</a></small>`:''}</div>
      <div><progress value="${j.progress}" max="100"></progress><small>${j.progress}%</small></div>
      <div class="state ${j.status}">${stateText(j.status)}${j.has_output?`<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;"><a class="mini-btn" href="${jobResultUrl(j)}" target="_blank" style="background:rgba(168,85,247,0.35);border:1px solid rgba(255,255,255,0.4);color:#fff;font-weight:700;">▶ Xem</a><a class="mini-btn" href="${jobResultUrl(j)}?download=1" download="tvc_result_${j.id}.${jobOutputExtension(j)}" style="background:rgba(217,70,239,0.35);border:1px solid rgba(255,255,255,0.4);color:#fff;font-weight:700;">⬇ Tải về</a></div>`:''}${j.can_cancel&&!j.service?`<br><button class="mini-btn cancel-job-btn" data-job-id="${j.id}" type="button">Hủy</button>`:''}</div>
    </div>`).join(''):'<div class="panel-card">Chưa có job nào.</div>'
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
  try{
    me=await api('/api/me');showDashboard();
    const videoTurns=Math.max(0,Number(me.usage_balance||me.credits||0));
    if($('#walletVideoRemaining')) $('#walletVideoRemaining').textContent=videoTurns;
    const [tops,led]=await Promise.all([api('/api/topups'),api('/api/ledger')]);
    $('#topupList').innerHTML=tops.length?tops.map(x=>`<div class="simple-row"><b>#${x.id} • ${packageName(x.package)} • ${x.credits} xu</b><span>${x.status} • ${x.amount_vnd.toLocaleString('vi-VN')}đ</span></div>`).join(''):'<div class="simple-row">Chưa có yêu cầu nạp.</div>';
    $('#ledgerList').innerHTML=led.length?led.map(x=>`<div class="simple-row"><b>${x.reason}</b><span style="color:${x.delta>=0?'#61df94':'#ff8490'}">${x.delta>0?'+':''}${x.delta} xu</span></div>`).join(''):'<div class="simple-row">Chưa có giao dịch.</div>'
  }catch(e){say(e.message)}
}

function referralDate(value){
  try{return new Date(value).toLocaleString('vi-VN')}catch(_){return value||'—'}
}

async function loadAffiliate(){
  try{
    const [summary,refs]=await Promise.all([api('/api/affiliate/summary'),api('/api/referrals')]);
    if($('#refDirectCount')) $('#refDirectCount').textContent=summary.direct_referrals||0;
    $('#affLink').textContent=summary.referral_link||'—';
    $('#affCode').textContent=summary.referral_code||'—';

    if(summary.referrer){
      $('#referrerState').innerHTML=`<span class="linked-ref">✓ Đã liên kết với <b>${summary.referrer.name}</b> • ${summary.referrer.referral_code}</span>`;
      $('#applyReferralCode').disabled=true;$('#applyReferralBtn').disabled=true;
    }else{
      $('#referrerState').innerHTML='<span class="muted">Chưa gắn người giới thiệu.</span>';
      $('#applyReferralCode').disabled=false;$('#applyReferralBtn').disabled=false;
      const ref=referralFromUrl();if(ref&&!$('#applyReferralCode').value)$('#applyReferralCode').value=ref;
    }

    $('#referralUserList').innerHTML=refs.length?refs.map(r=>`<div class="simple-row referral-user-row">
      <div><b>${r.name||'Người dùng TVC'}</b><span>${r.email_masked||'—'}</span></div>
      <span>${referralDate(r.created_at)}</span>
    </div>`).join(''):'<div class="simple-row">Chưa có người được giới thiệu.</div>';
  }catch(e){say(e.message)}
}
$('#refreshAffiliate').onclick=loadAffiliate;
$('#copyAffLink').onclick=async()=>{await navigator.clipboard.writeText($('#affLink').textContent);say('Đã copy link giới thiệu')};
$('#copyAffCode').onclick=async()=>{await navigator.clipboard.writeText($('#affCode').textContent);say('Đã copy mã giới thiệu')};
$('#applyReferralBtn').onclick=async()=>{
  try{
    const j=await api('/api/affiliate/apply-code',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({code:$('#applyReferralCode').value})});
    say('Đã liên kết với '+j.referrer_name);loadAffiliate()
  }catch(e){say(e.message)}
}

async function refreshAll(){
  await loadJobs();await loadWallet();
  $('#accountInfo').innerHTML=`<p><b>${me.name}</b></p><p>${me.email}</p><p>Vai trò: ${me.role}</p><p>Ngày tạo: ${new Date(me.created_at).toLocaleString('vi-VN')}</p>`
}
setInterval(()=>{if(me&&document.querySelector('#tab-jobs.active'))loadJobs()},5000);
boot();
