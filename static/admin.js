const $=s=>document.querySelector(s);const toast=$('#toast');
function say(t){toast.textContent=t;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2200)}
async function api(url,opt={}){const r=await fetch(url,opt);let j={};try{j=await r.json()}catch{};if(!r.ok)throw new Error(j.detail||'Lỗi');return j}
async function boot(){try{const me=await api('/api/me');if(me.role!=='admin')throw new Error('Không có quyền admin');await load()}catch(e){alert(e.message);location.href='/'}}
async function load(){
 const [s,t,u,j,aw,au]=await Promise.all([
   api('/api/admin/stats'),api('/api/admin/topups'),api('/api/admin/users'),api('/api/admin/jobs'),
   api('/api/admin/affiliate/withdrawals'),api('/api/admin/affiliate/users')
 ]);
 $('#stats').innerHTML=[
   ['Người dùng',s.users],['Waiting',s.waiting],['Running',s.running],['Done',s.done],
   ['Topup chờ',s.pending_topups],['Rút chờ',s.pending_withdrawals],['Affiliate thưởng',s.affiliate_rewards]
 ].map(x=>`<div class="stat"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('');
 $('#topups').innerHTML=table(['ID','Khách','Gói','Tiền','Lượt','Trạng thái',''],t.map(x=>[
   x.id,x.email,x.package,x.amount_vnd.toLocaleString('vi-VN')+'đ',x.credits,x.status,
   x.status==='pending'?`<button class="mini-btn approve" onclick="approve(${x.id})">Duyệt</button> <button class="mini-btn reject" onclick="rejectT(${x.id})">Từ chối</button>`:''
 ]));
 $('#users').innerHTML=table(['ID','Email','Tên','Lượt','Role',''],u.map(x=>[
   x.id,x.email,x.name,x.credits,x.role,`<button class="mini-btn" onclick="addCredits(${x.id},'${x.email}')">± Lượt</button>`
 ]));
 $('#jobs').innerHTML=table(['ID','Khách','Model','Quality','Cost','Status','Progress','Error'],j.map(x=>[
   x.id,x.email,x.model,x.quality+'p',x.cost,x.status,x.progress+'%',x.error||''
 ]));
 $('#affiliateWithdrawals').innerHTML=table(['ID','Khách','Lượt','VND','Method','Account','Status',''],aw.map(x=>[
   x.id,x.email,x.amount_credits,Number(x.amount_vnd).toLocaleString('vi-VN')+'đ',x.method,x.account,x.status,
   x.status==='pending'?`<button class="mini-btn approve" onclick="payWithdrawal(${x.id})">Đã trả</button> <button class="mini-btn reject" onclick="rejectWithdrawal(${x.id})">Từ chối</button>`:''
 ]));
 $('#affiliateUsers').innerHTML=table(['ID','Email','Mã','Hạng','Rate','Refs','Doanh số','Thưởng','Có thể rút','Người GT'],au.map(x=>[
   x.id,x.email,x.referral_code,x.tier,x.rate_percent+'%',x.direct_referrals,x.sales_credits,x.total_rewards,x.available,x.referrer?.email||''
 ]));
}
function table(headers,rows){return `<table class="table"><thead><tr>${headers.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(x=>`<td>${x??''}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
window.approve=async id=>{try{const j=await api(`/api/admin/topups/${id}/approve`,{method:'POST'});say(`Đã duyệt • bonus ${j.buyer_bonus||0} • commission ${j.direct_commission||0}`);load()}catch(e){say(e.message)}}
window.rejectT=async id=>{try{await api(`/api/admin/topups/${id}/reject`,{method:'POST'});say('Đã từ chối');load()}catch(e){say(e.message)}}
window.addCredits=async(id,email)=>{const d=prompt(`Cộng/trừ lượt cho ${email}. Ví dụ 100 hoặc -20:`);if(!d)return;try{await api(`/api/admin/users/${id}/credits`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delta:Number(d),reason:'Admin điều chỉnh'})});say('Đã cập nhật');load()}catch(e){say(e.message)}}
window.payWithdrawal=async id=>{const note=prompt('Ghi chú thanh toán (tuỳ chọn):')||'';try{await api(`/api/admin/affiliate/withdrawals/${id}/paid`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin_note:note})});say('Đã đánh dấu thanh toán');load()}catch(e){say(e.message)}}
window.rejectWithdrawal=async id=>{const note=prompt('Lý do từ chối:')||'';try{await api(`/api/admin/affiliate/withdrawals/${id}/reject`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin_note:note})});say('Đã từ chối yêu cầu rút');load()}catch(e){say(e.message)}}
$('#refresh').onclick=load;$('#logout').onclick=async()=>{await fetch('/api/logout',{method:'POST'});location.href='/'};boot();
