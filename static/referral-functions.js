/**
 * REFERRAL PAGE - Enhanced JavaScript Functions
 * Handles all referral dashboard interactions
 */

/**
 * Load and display all referral data
 */
async function loadAffiliate(){
  const $ = id => document.getElementById(id);
  const setText=(id,value)=>{const node=$(id);if(node) node.textContent=value;};
  const setStyle=(id,property,value)=>{const node=$(id);if(node) node.style[property]=value;};
  const setValue=(id,value)=>{const node=$(id);if(node) node.value=value;};
  if(!me){
    const directCount=$('refDirectCount');
    const affLink=$('affLink');
    const affCode=$('affCode');
    const referrerState=$('referrerState');
    const referralUserList=$('referralUserList');
    if(directCount) directCount.textContent='0';
    if(affLink) affLink.textContent='—';
    if(affCode) affCode.textContent='—';
    if(referrerState) referrerState.innerHTML='<span class="muted">Vui lòng đăng nhập để sử dụng tính năng giới thiệu.</span>';
    if(referralUserList) referralUserList.innerHTML=`<div class="referral-users-empty">
      <div class="referral-users-empty-icon">👥</div>
      <p class="referral-users-empty-title">Chưa đăng nhập</p>
      <p class="referral-users-empty-desc">Đăng nhập để xem thông tin giới thiệu của bạn.</p>
    </div>`;
    return;
  }

  try{
    const [summary,refs,rewards,wallet]=await Promise.all([
      api('/api/affiliate/summary'),
      api('/api/referrals'),
      api('/api/affiliate/rewards'),
      api('/api/affiliate/wallet')
    ]);

    // Update stats
    setText('refDirectCount',summary.direct_referrals||0);
    setText('refCurrentTier',summary.tier?.name||'Bạc');
    setText('refCommissionRate',`Hoa hồng ${summary.tier?.rate_percent||10}%`);
    setText('refAvailableRewards',Number(summary.available||0).toLocaleString('vi-VN'));
    setText('refAvailableVnd',`${Number(summary.available_vnd||0).toLocaleString('vi-VN')} ₫`);
    setText('refTotalRewards',Number(summary.total_rewards||0).toLocaleString('vi-VN'));

    // Update tier rates
    setText('refSilverRulePercent',`${summary.commission_rates?.silver_percent||10}%`);
    setText('refGoldRulePercent',`${summary.commission_rates?.gold_percent||15}%`);
    setText('refGoldThresholdAmount',Number(summary.commission_rates?.gold_threshold_credits||1000).toLocaleString('vi-VN')+' Xu');

    // Show current tier badge
    setStyle('tierSilverBadge','display',summary.tier?.key === 'silver' ? 'block' : 'none');
    setStyle('tierGoldBadge','display',summary.tier?.key === 'gold' ? 'block' : 'none');

    // Update progress
    if(summary.tier?.next_sales_credits){
      setStyle('tierProgressSection','display','block');
      setStyle('refTierProgressBar','width',`${Math.min(100, Number(summary.progress_percent||0))}%`);
      setText('refTierProgressText',`${Number(summary.tier.sales_credits||0).toLocaleString('vi-VN')} / ${Number(summary.tier.next_sales_credits).toLocaleString('vi-VN')} Xu doanh số đủ điều kiện • Còn ${Number(summary.credits_to_gold||0).toLocaleString('vi-VN')} Xu để đạt hạng Vàng`);
    }else{
      setStyle('tierProgressSection','display','none');
    }

    // Update referral links/codes
    setText('affLink',summary.referral_link||'—');
    setText('affCode',summary.referral_code||'—');

    // Handle referrer status
    if(summary.referrer){
      setStyle('referralApplySection','display','none');
      const referrerState=$('referrerState');
      if(referrerState) referrerState.innerHTML=`<span class="referral-apply-status">✓ Tài khoản đã được ghi nhận người giới thiệu: <b>${summary.referrer.name}</b> (${summary.referrer.referral_code})</span>`;
    }else{
      setStyle('referralApplySection','display','block');
      const referrerState=$('referrerState');
      if(referrerState) referrerState.innerHTML='';
      const applyReferralCode=$('applyReferralCode');
      const applyReferralBtn=$('applyReferralBtn');
      if(applyReferralCode) applyReferralCode.disabled=false;
      if(applyReferralBtn) applyReferralBtn.disabled=false;

      // Auto-fill from URL
      const ref=referralFromUrl();
      if(ref&&!applyReferralCode?.value){
        setValue('applyReferralCode',ref);
      }
    }

    // Display referred users
    renderReferredUsers(refs);

    // Display commission history
    renderCommissionHistory(rewards);
    renderAffiliateWallet(wallet);

  }catch(e){
    console.error(e);
    say(e.message);
  }
}

function getAffiliateWalletState(wallet = {}){
  const availableVnd = Number(wallet.available_vnd || 0);
  const minimumVnd = Number(wallet.minimum_withdrawal_vnd || 50000);
  const vndPerCredit = Number(wallet.vnd_per_credit || 1000);
  return {
    availableVnd,
    minimumVnd,
    vndPerCredit,
    canWithdraw: availableVnd >= minimumVnd,
    canConvert: availableVnd > 0,
  };
}

function renderAffiliateWallet(wallet){
  const money=value=>Number(value||0).toLocaleString('vi-VN')+' ₫';
  const available=document.getElementById('affiliateWalletAvailable');
  const pending=document.getElementById('affiliateWalletPending');
  const reserved=document.getElementById('affiliateWalletReserved');
  if(available) available.textContent=money(wallet.available_vnd);
  if(pending) pending.textContent=money(wallet.pending_vnd);
  if(reserved) reserved.textContent=money(wallet.reserved_vnd);
  const history=document.getElementById('affiliateWalletHistory');
  if(history) history.innerHTML=[...(wallet.conversions||[]).map(item=>`<div class="simple-list-row">${new Date(item.created_at).toLocaleDateString('vi-VN')} · Đổi sang Xu · ${money(item.affiliate_amount_vnd)} · +${item.credits_received} Xu · Hoàn thành</div>`), ...(wallet.withdrawals||[]).map(item=>`<div class="simple-list-row">${new Date(item.created_at).toLocaleDateString('vi-VN')} · Rút tiền · ${money(item.amount_vnd)} · ${item.bank_name||item.method} · ${item.status}</div>`)].join('');
}

/**
 * Render referred users table/cards
 */
function renderReferredUsers(refs){
  const container=$('#referralUserList');
  if(!container) return;

  if(!refs||refs.length===0){
    container.innerHTML=`<div class="referral-users-empty">
      <div class="referral-users-empty-icon">👥</div>
      <p class="referral-users-empty-title">Bạn chưa có lượt giới thiệu nào</p>
      <p class="referral-users-empty-desc">Chia sẻ link của bạn để bắt đầu.</p>
      <button class="referral-users-empty-btn" onclick="document.querySelector('[data-copy=link]').click()">Sao Chép Link Giới Thiệu</button>
    </div>`;
    return;
  }

  // Desktop: table, Mobile: cards
  let html='<table class="referral-users-table"><thead><tr>';
  html+='<th>Người Dùng</th><th>Ngày Tham Gia</th><th>Trạng Thái</th><th>Doanh Số</th><th>Hoa Hồng</th>';
  html+='</tr></thead><tbody>';

  refs.forEach(r=>{
    const status=r.status||'Đã đăng ký';
    const statusClass=status.includes('Đủ')?'completed':status.includes('Chờ')?'pending':'active';
    const email=r.email_masked||'—';
    const doanhs=Number(r.sales_credits||0).toLocaleString('vi-VN')+' Xu';
    const reward=r.reward_credits?Number(r.reward_credits).toLocaleString('vi-VN')+' Xu':'—';
    const date=new Date(r.created_at).toLocaleDateString('vi-VN');

    html+=`<tr data-label="user">
      <td data-label="user"><b>${r.name||'Người dùng TVC'}</b><br><small>${email}</small></td>
      <td data-label="date">${date}</td>
      <td data-label="status"><span class="referral-users-badge ${statusClass}">${status}</span></td>
      <td data-label="sales">${doanhs}</td>
      <td data-label="reward">${reward}</td>
    </tr>`;
  });

  html+='</tbody></table>';
  container.innerHTML=html;
}

/**
 * Render commission history table/cards
 */
function renderCommissionHistory(rewards){
  const container=$('#referralRewardList');
  if(!container) return;

  if(!rewards||rewards.length===0){
    container.innerHTML=`<div class="referral-history-empty">
      <div class="referral-history-empty-icon">💰</div>
      <p class="referral-history-empty-text">Chưa có lịch sử hoa hồng.</p>
    </div>`;
    return;
  }

  let html='<table class="referral-history-table"><thead><tr>';
  html+='<th>Ngày</th><th>Loại Thưởng</th><th>Người Được Giới Thiệu</th><th>Doanh Số</th><th>Tỷ Lệ</th><th>Phần Thưởng</th><th>Trạng Thái</th>';
  html+='</tr></thead><tbody>';

  rewards.forEach(r=>{
    const typeMap={
      'direct':'Thưởng Trực Tiếp',
      'buyer_bonus':'Thưởng Khách Mới',
      'tier_override':'Thưởng Cấp Trên'
    };
    const type=typeMap[r.reward_type]||'Thưởng Referral';
    const status=r.status==='approved'?'Đã Ghi Nhận':r.status==='pending'?'Chờ Duyệt':'Đã Hủy';
    const date=new Date(r.created_at).toLocaleDateString('vi-VN');
    const rate=(r.rate*100||0).toFixed(0)+'%';
    const doanhs=Number(r.source_credits||0).toLocaleString('vi-VN')+' Xu';
    const reward=Number(r.amount_credits||0).toLocaleString('vi-VN')+' Xu';

    html+=`<tr>
      <td data-label="date">${date}</td>
      <td data-label="type">${type}</td>
      <td data-label="source">${r.source_name||'Giao dịch Referral'}</td>
      <td data-label="sales">${doanhs}</td>
      <td data-label="rate">${rate}</td>
      <td data-label="reward" class="referral-history-amount">+${reward}</td>
      <td data-label="status">${status}</td>
    </tr>`;
  });

  html+='</tbody></table>';
  container.innerHTML=html;
}

/**
 * Setup copy-to-clipboard for all copy buttons
 */
function setupCopyButtons(){
  document.querySelectorAll('.referral-copy-btn').forEach(btn=>{
    btn.addEventListener('click', async(e)=>{
      e.preventDefault();
      const target=btn.dataset.target;
      const text=$(target)?.textContent||'';

      if(!text||text==='—'){
        say('Không có nội dung để sao chép');
        return;
      }

      try{
        await navigator.clipboard.writeText(text);
        const original=btn.textContent;
        btn.classList.add('copied');
        btn.textContent='✓ Đã Sao Chép';

        setTimeout(()=>{
          btn.classList.remove('copied');
          btn.textContent=original;
        }, 2000);

        say('Đã sao chép');
      }catch(err){
        console.error('Copy failed:', err);
        say('Sao chép thất bại');
      }
    });
  });
}

/**
 * Setup CTA buttons
 */
function setupCTAButtons(){
  const getLinkText=()=>$('#affLink')?.textContent?.trim()||'';

  $('#ctaCopyLink')?.addEventListener('click', async()=>{
    const linkText=getLinkText();
    if(!linkText||linkText==='—'){
      say('Chưa có link giới thiệu');
      return;
    }
    try{
      await navigator.clipboard.writeText(linkText);
      say('Đã sao chép link giới thiệu');
    }catch(err){
      say('Sao chép thất bại');
    }
  });

  $('#ctaShare')?.addEventListener('click', async()=>{
    const linkText=getLinkText();
    if(!linkText||linkText==='—'){
      say('Chưa có link giới thiệu');
      return;
    }

    // Try Web Share API
    if(navigator.share){
      try{
        await navigator.share({
          title:'Giới Thiệu TVC Studio AI',
          text:'Chia sẻ TVC Studio AI - Công cụ AI tạo video chuyên nghiệp',
          url:linkText
        });
      }catch(err){
        if(err.name!=='AbortError'){
          console.error('Share failed:', err);
        }
      }
    }else{
      // Fallback: copy link
      try{
        await navigator.clipboard.writeText(linkText);
        say('Đã sao chép link. Gửi cho bạn bè của bạn!');
      }catch(err){
        say('Sao chép thất bại');
      }
    }
  });
}

// The referral tab can render its FAQ after initialization, so handle late-created triggers too.
document.addEventListener('click', event=>{
  const trigger=event.target.closest('.referral-faq-trigger');
  if(!trigger) return;
  const content=document.getElementById(`faq-${trigger.dataset.faq}`);
  if(!content) return;
  const shouldOpen=!content.classList.contains('open');
  document.querySelectorAll('.referral-faq-content').forEach(item=>item.classList.remove('open'));
  document.querySelectorAll('.referral-faq-trigger').forEach(item=>item.classList.remove('open'));
  if(shouldOpen){
    content.classList.add('open');
    trigger.classList.add('open');
  }
});

/**
 * Setup apply referral code form
 */
function setupApplyReferralForm(){
  $('#applyReferralBtn')?.addEventListener('click', async()=>{
    const code=$('#applyReferralCode')?.value?.trim();

    if(!code){
      say('Vui lòng nhập mã giới thiệu');
      return;
    }

    // Validate: can't use own code
    const ownCode=$('#affCode')?.textContent;
    if(code===ownCode){
      say('Bạn không thể sử dụng mã giới thiệu của chính mình');
      return;
    }

    try{
      if($('#applyReferralBtn')) $('#applyReferralBtn').disabled=true;
      const result=await api('/api/affiliate/apply-code',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({code})
      });

      say(`✓ Đã liên kết với ${result.referrer_name}`);
      await loadAffiliate();
    }catch(e){
      say(e.message);
    }finally{
      if($('#applyReferralBtn')) $('#applyReferralBtn').disabled=false;
    }
  });

  // Allow Enter key
  $('#applyReferralCode')?.addEventListener('keypress', (e)=>{
    if(e.key==='Enter'){
      $('#applyReferralBtn')?.click();
    }
  });
}

/**
 * Get referral code from URL
 */
function referralFromUrl(){
  const params=new URLSearchParams(window.location.search);
  return params.get('ref')||'';
}

/**
 * Format referral date
 */
function referralDate(dateStr){
  if(!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('vi-VN');
}

/**
 * Initialize all referral page functionality
 */
function initReferralPage(){
  const tabAffiliate=$('#tab-affiliate');
  if(!tabAffiliate || tabAffiliate.dataset.referralInitialized==='true') return;
  tabAffiliate.dataset.referralInitialized='true';

  // Setup event listeners
  setupCopyButtons();
  setupCTAButtons();
  setupApplyReferralForm();

  const stateFromWallet = () => getAffiliateWalletState(window.__affiliateWallet || {});

  // Refresh button
  $('#refreshAffiliate')?.addEventListener('click', loadAffiliate);

  $('#affiliateWithdrawBtn')?.addEventListener('click', ()=>{
    const wallet = window.__affiliateWallet || {};
    const { availableVnd, minimumVnd } = getAffiliateWalletState(wallet);
    if(availableVnd <= 0){
      say('Ví đang hơi nhẹ 😄 Kiếm thêm hoa hồng rồi quay lại rút nhé!');
      return;
    }
    if(availableVnd < minimumVnd){
      const missing = minimumVnd - availableVnd;
      say(`Sắp đủ rồi 😄 Bạn cần tối thiểu ${minimumVnd.toLocaleString('vi-VN')}đ để rút. Hiện ví đang có ${availableVnd.toLocaleString('vi-VN')}đ.\nCòn thiếu: ${missing.toLocaleString('vi-VN')}đ`);
      return;
    }
    const dialog=$('#affiliateWithdrawDialog');
    if(dialog){
      const availableLabel = $('#affiliateWithdrawAvailable');
      const minimumLabel = $('#affiliateWithdrawMinimum');
      if(availableLabel) availableLabel.textContent = `${availableVnd.toLocaleString('vi-VN')}đ`;
      if(minimumLabel) minimumLabel.textContent = `${minimumVnd.toLocaleString('vi-VN')}đ`;
      dialog.hidden=false;
    }
  });

  $('#affiliateWithdrawCancel')?.addEventListener('click', ()=>{ const dialog=$('#affiliateWithdrawDialog'); if(dialog) dialog.hidden=true; });
  $('#affiliateWithdrawForm')?.addEventListener('submit', async event=>{
    event.preventDefault();
    const form = event.target;
    const wallet = window.__affiliateWallet || {};
    const { availableVnd, minimumVnd } = getAffiliateWalletState(wallet);
    const formData = Object.fromEntries(new FormData(form));
    const amount = Number(formData.amount_vnd || 0);
    const requiredFields = [formData.account_name, formData.bank_name, formData.account, formData.method];
    if(requiredFields.some(field => !String(field || '').trim())){
      say('Thiếu chỗ nhận tiền rồi 😄 Hãy điền đầy đủ thông tin ngân hàng trước nhé!');
      return;
    }
    if(!Number.isFinite(amount) || amount <= 0){
      say('Nhập một số tiền hợp lệ để rút nhé 😄');
      return;
    }
    if(amount > availableVnd){
      say(`Ví chưa giàu tới mức đó đâu 😄 Bạn chỉ có thể rút tối đa ${availableVnd.toLocaleString('vi-VN')}đ.`);
      return;
    }
    if(amount < minimumVnd){
      say(`Thêm chút nữa là được 😄 Mức rút tối thiểu hiện là ${minimumVnd.toLocaleString('vi-VN')}đ.`);
      return;
    }
    const submitBtn = form.querySelector('button[type="submit"]');
    if(submitBtn){ submitBtn.disabled=true; submitBtn.textContent='Đang xử lý...'; }
    try{
      await api('/api/affiliate/withdrawals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(formData)});
      say('Yêu cầu rút tiền đã được gửi 🎉 Admin sẽ kiểm tra và xử lý cho bạn.');
      form.reset();
      const dialog=$('#affiliateWithdrawDialog'); if(dialog) dialog.hidden=true;
      await loadAffiliate();
    }catch(error){
      say(error.message);
    }finally{
      if(submitBtn){ submitBtn.disabled=false; submitBtn.textContent='Gửi yêu cầu rút'; }
    }
  });

  $('#affiliateConvertBtn')?.addEventListener('click', ()=>{
    const wallet = window.__affiliateWallet || {};
    const { availableVnd, vndPerCredit } = getAffiliateWalletState(wallet);
    if(availableVnd <= 0){
      say('Chưa có hoa hồng để đổi rồi 😄 Kiếm thêm chút nữa rồi quay lại nhé!');
      return;
    }
    const dialog=$('#affiliateConvertDialog');
    if(dialog){
      const availableLabel = $('#affiliateConvertAvailable');
      const rateLabel = $('#affiliateConvertRate');
      const amountInput = $('#affiliateConvertAmount');
      const previewLabel = $('#affiliateConvertPreview');
      if(availableLabel) availableLabel.textContent = `${availableVnd.toLocaleString('vi-VN')}đ`;
      if(rateLabel) rateLabel.textContent = `1 Xu = ${vndPerCredit.toLocaleString('vi-VN')}đ`;
      if(amountInput){ amountInput.value=''; }
      if(previewLabel){ previewLabel.textContent = '0 Xu'; }
      dialog.hidden=false;
    }
  });

  $('#affiliateConvertAmount')?.addEventListener('input', event=>{
    const wallet = window.__affiliateWallet || {};
    const { vndPerCredit } = getAffiliateWalletState(wallet);
    const amount = Number(event.target.value || 0);
    const preview = $('#affiliateConvertPreview');
    if(preview){
      const credits = Number.isFinite(amount) && amount > 0 ? amount / vndPerCredit : 0;
      preview.textContent = `${credits.toLocaleString('vi-VN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} Xu`;
    }
  });

  $('#affiliateConvertForm')?.addEventListener('submit', async event=>{
    event.preventDefault();
    const form=event.target;
    const wallet=window.__affiliateWallet || {};
    const { availableVnd, vndPerCredit } = getAffiliateWalletState(wallet);
    const amount = Number(new FormData(form).get('amount_vnd') || 0);
    if(!Number.isFinite(amount) || amount <= 0){
      say('Nhập một số tiền hợp lệ để đổi sang Xu nhé 😄');
      return;
    }
    if(amount > availableVnd){
      say(`Ví chưa đủ lực 😄 Bạn chỉ có thể đổi tối đa ${availableVnd.toLocaleString('vi-VN')}đ.`);
      return;
    }
    const credits = amount / vndPerCredit;
    const confirmed = window.confirm(`Bạn đang đổi:\n${amount.toLocaleString('vi-VN')}đ Affiliate\n→\n${credits.toLocaleString('vi-VN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} Xu\n\nXu sau khi đổi chỉ dùng cho dịch vụ và không thể đổi ngược thành tiền Affiliate.\n\nXác nhận đổi?`);
    if(!confirmed) return;
    const submitBtn = form.querySelector('button[type="submit"]');
    if(submitBtn){ submitBtn.disabled=true; submitBtn.textContent='Đang xử lý...'; }
    try{
      const key=`affiliate-convert-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const result=await api('/api/affiliate/convert',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount_vnd:amount,idempotency_key:key})});
      say(`Đổi thành công 🎉 ${amount.toLocaleString('vi-VN')}đ đã biến thành ${Number(result.transaction.credits_received).toLocaleString('vi-VN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} Xu để bạn dùng dịch vụ!`);
      form.reset();
      const dialog=$('#affiliateConvertDialog'); if(dialog) dialog.hidden=true;
      await loadAffiliate();
    }catch(error){
      say(error.message);
    }finally{
      if(submitBtn){ submitBtn.disabled=false; submitBtn.textContent='Xác nhận đổi'; }
    }
  });

  $('#affiliateConvertCancel')?.addEventListener('click', ()=>{ const dialog=$('#affiliateConvertDialog'); if(dialog) dialog.hidden=true; });

  // Load data
  loadAffiliate();
}

// Initialize when referral tab is clicked or page loads
if(document.getElementById('tab-affiliate')){
  initReferralPage();
}

// Also reinitialize when switching to referral tab
const tabAffiliate=document.getElementById('tab-affiliate');
if(tabAffiliate){
  const observer=new MutationObserver(()=>{
    if(tabAffiliate.classList.contains('active')){
      // Tab became active, reinitialize
      setTimeout(initReferralPage, 100);
    }
  });
  observer.observe(tabAffiliate, {attributes:true, attributeFilter:['class']});
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded', initReferralPage, {once:true});
}else{
  initReferralPage();
}
