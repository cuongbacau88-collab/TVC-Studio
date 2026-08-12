const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const toast=$('#toast'); function say(t){toast.textContent=t;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2400)}
let me=null, selectedPack='creator';

let toolbarLang=localStorage.getItem('tvc_lang')||'vi';
function syncToolbar(){
  const c=$('#toolbarCredits'), a=$('#toolbarAccount');
  if(c && me)c.textContent=Number(me.credits||0).toLocaleString('vi-VN',{maximumFractionDigits:1});
  if(a && me)a.textContent=me.name||'Tài Khoản';
}
function initToolbar(){
  const buttons=$$('.lang-switch button');
  buttons.forEach(b=>{
    b.classList.toggle('active',b.dataset.lang===toolbarLang);
    b.onclick=()=>{
      toolbarLang=b.dataset.lang;localStorage.setItem('tvc_lang',toolbarLang);
      buttons.forEach(x=>x.classList.toggle('active',x===b));
      say(toolbarLang==='vi'?'Đã chọn Tiếng Việt':'English UI will be added later');
    };
  });
  const menu=$('#toolbarMenu');
  if(menu)menu.onclick=()=>document.querySelector('.global-actions')?.classList.toggle('open');
  document.querySelectorAll('.global-actions a[href^="/app#"]').forEach(a=>{
    a.addEventListener('click',e=>{
      const hash=(new URL(a.href,location.origin)).hash;
      const map={'#jobs':'jobs','#affiliate':'affiliate','#wallet':'wallet','#account':'account'};
      if(map[hash]){e.preventDefault();goto(map[hash]);}
    });
  });
}


async function api(url,opt={}){
  const r=await fetch(url,opt);let j={};try{j=await r.json()}catch{};
  if(!r.ok)throw new Error(j.detail||'Có lỗi xảy ra');return j
}
function referralFromUrl(){
  const p=new URLSearchParams(location.search);
  return (p.get('ref')||'').trim();
}
async function boot(){
  initToolbar();
  const ref=referralFromUrl();
  if(ref && $('#rReferral')) $('#rReferral').value=ref;
  try{
    me=await api('/api/me');showDashboard();await refreshAll();
    const initialHash=location.hash;
    const hashMap={'#affiliate':'affiliate','#jobs':'jobs','#wallet':'wallet','#account':'account','#create':'create'};
    if(hashMap[initialHash]) goto(hashMap[initialHash]);
  }catch{showAuth()}
}
function showAuth(){$('#authGate').classList.remove('hidden');$('#dashboard').classList.add('hidden')}
function showDashboard(){
  $('#authGate').classList.add('hidden');$('#dashboard').classList.remove('hidden');
  $('#credits').textContent=me.credits;$('#walletCredits').textContent=me.credits;
  $('#avatar').textContent=(me.name||me.email).slice(0,2).toUpperCase();syncToolbar()
}
$$('[data-auth]').forEach(b=>b.onclick=()=>{
  $$('[data-auth]').forEach(x=>x.classList.remove('active'));b.classList.add('active');
  $('#loginForm').classList.toggle('hidden',b.dataset.auth!=='login');
  $('#registerForm').classList.toggle('hidden',b.dataset.auth!=='register')
});
$('#doLogin').onclick=async()=>{
  try{
    await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:$('#lEmail').value,password:$('#lPass').value})});
    location.reload()
  }catch(e){$('#authMsg').textContent=e.message}
}
$('#doRegister').onclick=async()=>{
  try{
    await api('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        name:$('#rName').value,email:$('#rEmail').value,password:$('#rPass').value,
        referral_code:$('#rReferral').value
      })});
    say('Đăng ký thành công, hãy đăng nhập');document.querySelector('[data-auth="login"]').click()
  }catch(e){$('#authMsg').textContent=e.message}
}
async function logout(){await fetch('/api/logout',{method:'POST'});location.reload()}
$('#logout').onclick=logout;$('#logout2').onclick=logout;

const meta={
  create:['Tạo video mới','Ảnh nhân vật + video chuyển động'],
  jobs:['Job của tôi','Theo dõi hàng đợi và tải kết quả'],
  wallet:['Ví credits','Nạp điểm và lịch sử credits'],
  affiliate:['Kiếm tiền Affiliate','Giới thiệu khách hàng và nhận hoa hồng'],
  account:['Tài khoản','Thông tin tài khoản']
};
function goto(tab){
  $$('.side').forEach(x=>x.classList.toggle('active',x.dataset.tab===tab));
  $$('.tab').forEach(x=>x.classList.remove('active'));
  $('#tab-'+tab).classList.add('active');
  $('#pageTitle').textContent=meta[tab][0];$('#pageSub').textContent=meta[tab][1];
  history.replaceState(null,'',tab==='affiliate'?'#affiliate':location.pathname+location.search);
  if(tab==='jobs')loadJobs();if(tab==='wallet')loadWallet();if(tab==='affiliate')loadAffiliate()
}
$$('.side').forEach(b=>b.onclick=()=>goto(b.dataset.tab));
$$('[data-goto]').forEach(b=>b.onclick=()=>goto(b.dataset.goto));

const form=$('#jobForm');
form.image.onchange=()=>{$('#imgName').textContent=form.image.files[0]?.name||'Chọn ảnh'};
form.motion.onchange=()=>{$('#vidName').textContent=form.motion.files[0]?.name||'Chọn video'};
$('#quality').onchange=()=>$('#cost').textContent=($('#quality').value==='720'?20:10)+' credits';
form.onsubmit=async e=>{
  e.preventDefault();const fd=new FormData(form);
  try{
    const j=await api('/api/jobs',{method:'POST',body:fd});say('Đã tạo job #'+j.job_id);
    me=await api('/api/me');showDashboard();goto('jobs')
  }catch(err){say(err.message)}
}
function stateText(s){return {waiting:'Đang chờ',running:'Đang render',done:'Hoàn thành',failed:'Lỗi',uploading:'Đang tải'}[s]||s}
async function loadJobs(){
  try{
    const jobs=await api('/api/jobs');
    $('#jobsList').innerHTML=jobs.length?jobs.map(j=>`<div class="job">
      <div class="thumb">🎬</div>
      <div><b>#${j.id} • ${j.model}</b><small>${j.quality}p • ${j.aspect_ratio} • ${new Date(j.created_at).toLocaleString('vi-VN')}</small>${j.error?`<small style="color:#ff7a88">${j.error}</small>`:''}</div>
      <div><progress value="${j.progress}" max="100"></progress><small>${j.progress}%</small></div>
      <div class="state ${j.status}">${stateText(j.status)}${j.has_output?`<br><a class="mini-btn" href="/api/jobs/${j.id}/output">Tải video</a>`:''}</div>
    </div>`).join(''):'<div class="panel-card">Chưa có job nào.</div>'
  }catch(e){say(e.message)}
}
$('#refreshJobs').onclick=loadJobs;

$$('.packs button').forEach(b=>b.onclick=()=>{
  $$('.packs button').forEach(x=>x.classList.remove('active'));b.classList.add('active');selectedPack=b.dataset.pack
});
$('#requestTopup').onclick=async()=>{
  try{
    const j=await api('/api/topups',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({package:selectedPack,note:$('#topupNote').value})});
    say('Đã gửi yêu cầu nạp #'+j.topup_id);loadWallet()
  }catch(e){say(e.message)}
}
async function loadWallet(){
  try{
    me=await api('/api/me');showDashboard();
    const [tops,led]=await Promise.all([api('/api/topups'),api('/api/ledger')]);
    $('#topupList').innerHTML=tops.length?tops.map(x=>`<div class="simple-row"><b>#${x.id} • ${x.package} • ${x.credits} credits</b><span>${x.status} • ${x.amount_vnd.toLocaleString('vi-VN')}đ</span></div>`).join(''):'<div class="simple-row">Chưa có yêu cầu nạp.</div>';
    $('#ledgerList').innerHTML=led.length?led.map(x=>`<div class="simple-row"><b>${x.reason}</b><span style="color:${x.delta>=0?'#61df94':'#ff8490'}">${x.delta>0?'+':''}${x.delta}</span></div>`).join(''):'<div class="simple-row">Chưa có giao dịch.</div>'
  }catch(e){say(e.message)}
}

function formatCredits(n){return Number(n||0).toLocaleString('vi-VN',{minimumFractionDigits:0,maximumFractionDigits:2})}
function formatVnd(n){return Number(n||0).toLocaleString('vi-VN')+' VND'}
function affRewardType(t){return t==='tier_override'?'Thưởng cấp dưới':'Hoa hồng trực tiếp'}
function withdrawalState(s){return {pending:'Đang chờ duyệt',paid:'Đã thanh toán',rejected:'Từ chối'}[s]||s}

async function loadAffiliate(){
  try{
    const [s,rewards,withdrawals]=await Promise.all([
      api('/api/affiliate/summary'),api('/api/affiliate/rewards'),api('/api/affiliate/withdrawals')
    ]);
    $('#affTier').textContent=s.tier.name;
    $('#affRate').textContent=`Phần thưởng: ${s.tier.rate_percent}%`;
    $('#affAvailable').textContent=formatCredits(s.available);
    $('#affAvailableVnd').textContent='≈ '+formatVnd(s.available_vnd);
    $('#affTotal').textContent=formatCredits(s.total_rewards);
    $('#affRefs').textContent=s.direct_referrals;
    $('#affPayingRefs').textContent=`${s.paying_referrals} khách đã nạp`;
    $('#affLink').textContent=s.referral_link;
    $('#affCode').textContent=s.referral_code;
    $('#affRankBar').style.width=s.progress_percent+'%';
    if(s.tier.key==='gold'){
      $('#affNextTier').textContent='Đã đạt Vàng';
      $('#affRankText').textContent=`${formatCredits(s.tier.sales_credits)} credits doanh số`;
    }else{
      $('#affNextTier').textContent='Tiếp theo: Vàng';
      $('#affRankText').textContent=`${formatCredits(s.tier.sales_credits)} / 1.000 credits`;
    }
    if(s.referrer){
      $('#referrerState').innerHTML=`<span class="linked-ref">✓ Đã liên kết với <b>${s.referrer.name}</b> • ${s.referrer.referral_code}</span>`;
      $('#applyReferralCode').disabled=true;$('#applyReferralBtn').disabled=true;
    }else{
      $('#referrerState').innerHTML=`<span class="muted">Chưa nhập mã giới thiệu. Khách có mã được +${s.buyer_bonus_percent}% credits mỗi lần nạp được duyệt.</span>`;
      $('#applyReferralCode').disabled=false;$('#applyReferralBtn').disabled=false;
      const ref=referralFromUrl();if(ref&&!$('#applyReferralCode').value)$('#applyReferralCode').value=ref;
    }

    $('#affiliateRewardList').innerHTML=rewards.length?rewards.map(r=>`<div class="simple-row affiliate-row">
      <div><b>${affRewardType(r.reward_type)}</b><span>Từ ${r.source_name} • ${new Date(r.created_at).toLocaleString('vi-VN')}</span></div>
      <strong class="money">+${formatCredits(r.amount_credits)}</strong>
    </div>`).join(''):'<div class="simple-row">Chưa có hoa hồng.</div>';

    $('#affiliateWithdrawalList').innerHTML=withdrawals.length?withdrawals.map(w=>`<div class="simple-row affiliate-row">
      <div><b>#${w.id} • ${withdrawalState(w.status)}</b><span>${formatCredits(w.amount_credits)} credits • ${formatVnd(w.amount_vnd)} • ${w.method}</span></div>
      <strong class="${w.status==='paid'?'money':w.status==='rejected'?'bad':'pending-text'}">${w.status}</strong>
    </div>`).join(''):'<div class="simple-row">Chưa có yêu cầu rút.</div>';
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
$('#withdrawBtn').onclick=async()=>{
  try{
    const j=await api('/api/affiliate/withdrawals',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        amount_credits:$('#withdrawAmount').value,
        method:$('#withdrawMethod').value,
        account:$('#withdrawAccount').value,
        note:$('#withdrawNote').value
      })});
    say('Đã gửi yêu cầu rút #'+j.withdrawal_id);$('#withdrawAmount').value='';loadAffiliate()
  }catch(e){say(e.message)}
}

async function refreshAll(){
  await loadJobs();await loadWallet();
  $('#accountInfo').innerHTML=`<p><b>${me.name}</b></p><p>${me.email}</p><p>Vai trò: ${me.role}</p><p>Ngày tạo: ${new Date(me.created_at).toLocaleString('vi-VN')}</p>`
}
setInterval(()=>{if(me&&document.querySelector('#tab-jobs.active'))loadJobs()},5000);
boot();
