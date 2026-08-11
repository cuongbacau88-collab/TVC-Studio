const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const toast=$('#toast'); function say(t){toast.textContent=t;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2200)}
let me=null, selectedPack='creator';

async function api(url,opt={}){const r=await fetch(url,opt);let j={};try{j=await r.json()}catch{};if(!r.ok)throw new Error(j.detail||'Có lỗi xảy ra');return j}
async function boot(){
 try{me=await api('/api/me');showDashboard();await refreshAll()}catch{showAuth()}
}
function showAuth(){$('#authGate').classList.remove('hidden');$('#dashboard').classList.add('hidden')}
function showDashboard(){$('#authGate').classList.add('hidden');$('#dashboard').classList.remove('hidden');$('#credits').textContent=me.credits;$('#walletCredits').textContent=me.credits;$('#avatar').textContent=(me.name||me.email).slice(0,2).toUpperCase()}
$$('[data-auth]').forEach(b=>b.onclick=()=>{$$('[data-auth]').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#loginForm').classList.toggle('hidden',b.dataset.auth!=='login');$('#registerForm').classList.toggle('hidden',b.dataset.auth!=='register')});
$('#doLogin').onclick=async()=>{try{await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('#lEmail').value,password:$('#lPass').value})});location.reload()}catch(e){$('#authMsg').textContent=e.message}}
$('#doRegister').onclick=async()=>{try{await api('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('#rName').value,email:$('#rEmail').value,password:$('#rPass').value})});say('Đăng ký thành công, hãy đăng nhập');document.querySelector('[data-auth="login"]').click()}catch(e){$('#authMsg').textContent=e.message}}
async function logout(){await fetch('/api/logout',{method:'POST'});location.reload()} $('#logout').onclick=logout;$('#logout2').onclick=logout;

const meta={create:['Tạo video mới','Ảnh nhân vật + video chuyển động'],jobs:['Job của tôi','Theo dõi hàng đợi và tải kết quả'],wallet:['Ví credits','Nạp điểm và lịch sử credits'],account:['Tài khoản','Thông tin tài khoản']};
function goto(tab){$$('.side').forEach(x=>x.classList.toggle('active',x.dataset.tab===tab));$$('.tab').forEach(x=>x.classList.remove('active'));$('#tab-'+tab).classList.add('active');$('#pageTitle').textContent=meta[tab][0];$('#pageSub').textContent=meta[tab][1];if(tab==='jobs')loadJobs();if(tab==='wallet')loadWallet()}
$$('.side').forEach(b=>b.onclick=()=>goto(b.dataset.tab));$$('[data-goto]').forEach(b=>b.onclick=()=>goto(b.dataset.goto));
const form=$('#jobForm');form.image.onchange=()=>{$('#imgName').textContent=form.image.files[0]?.name||'Chọn ảnh'};form.motion.onchange=()=>{$('#vidName').textContent=form.motion.files[0]?.name||'Chọn video'};
$('#quality').onchange=()=>$('#cost').textContent=($('#quality').value==='720'?20:10)+' credits';
form.onsubmit=async e=>{e.preventDefault();const fd=new FormData(form);try{const j=await api('/api/jobs',{method:'POST',body:fd});say('Đã tạo job #'+j.job_id);me=await api('/api/me');showDashboard();goto('jobs')}catch(err){say(err.message)}}
function stateText(s){return {waiting:'Đang chờ',running:'Đang render',done:'Hoàn thành',failed:'Lỗi',uploading:'Đang tải'}[s]||s}
async function loadJobs(){try{const jobs=await api('/api/jobs');$('#jobsList').innerHTML=jobs.length?jobs.map(j=>`<div class="job"><div class="thumb">🎬</div><div><b>#${j.id} • ${j.model}</b><small>${j.quality}p • ${j.aspect_ratio} • ${new Date(j.created_at).toLocaleString('vi-VN')}</small>${j.error?`<small style="color:#ff7a88">${j.error}</small>`:''}</div><div><progress value="${j.progress}" max="100"></progress><small>${j.progress}%</small></div><div class="state ${j.status}">${stateText(j.status)}${j.has_output?`<br><a class="mini-btn" href="/api/jobs/${j.id}/output">Tải video</a>`:''}</div></div>`).join(''):'<div class="panel-card">Chưa có job nào.</div>'}catch(e){say(e.message)}}
$('#refreshJobs').onclick=loadJobs;
$$('.packs button').forEach(b=>b.onclick=()=>{$$('.packs button').forEach(x=>x.classList.remove('active'));b.classList.add('active');selectedPack=b.dataset.pack});
$('#requestTopup').onclick=async()=>{try{const j=await api('/api/topups',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({package:selectedPack,note:$('#topupNote').value})});say('Đã gửi yêu cầu nạp #'+j.topup_id);loadWallet()}catch(e){say(e.message)}}
async function loadWallet(){try{me=await api('/api/me');showDashboard();const [tops,led]=await Promise.all([api('/api/topups'),api('/api/ledger')]);$('#topupList').innerHTML=tops.length?tops.map(x=>`<div class="simple-row"><b>#${x.id} • ${x.package} • ${x.credits} credits</b><span>${x.status} • ${x.amount_vnd.toLocaleString('vi-VN')}đ</span></div>`).join(''):'<div class="simple-row">Chưa có yêu cầu nạp.</div>';$('#ledgerList').innerHTML=led.length?led.map(x=>`<div class="simple-row"><b>${x.reason}</b><span style="color:${x.delta>=0?'#61df94':'#ff8490'}">${x.delta>0?'+':''}${x.delta}</span></div>`).join(''):'<div class="simple-row">Chưa có giao dịch.</div>'}catch(e){say(e.message)}}
async function refreshAll(){await loadJobs();await loadWallet();$('#accountInfo').innerHTML=`<p><b>${me.name}</b></p><p>${me.email}</p><p>Vai trò: ${me.role}</p><p>Ngày tạo: ${new Date(me.created_at).toLocaleString('vi-VN')}</p>`}
setInterval(()=>{if(me&&document.querySelector('#tab-jobs.active'))loadJobs()},5000);
boot();