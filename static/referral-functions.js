/**
 * REFERRAL PAGE - Enhanced JavaScript Functions
 * Handles all referral dashboard interactions
 */

/**
 * Load and display all referral data
 */
async function loadAffiliate(){
  const $ = id => document.getElementById(id);
  
  if(!me){
    if($('refDirectCount')) $('refDirectCount').textContent='0';
    if($('affLink')) $('affLink').textContent='—';
    if($('affCode')) $('affCode').textContent='—';
    if($('referrerState')) $('referrerState').innerHTML='<span class="muted">Vui lòng đăng nhập để sử dụng tính năng giới thiệu.</span>';
    if($('referralUserList')) $('referralUserList').innerHTML=`<div class="referral-users-empty">
      <div class="referral-users-empty-icon">👥</div>
      <p class="referral-users-empty-title">Chưa đăng nhập</p>
      <p class="referral-users-empty-desc">Đăng nhập để xem thông tin giới thiệu của bạn.</p>
    </div>`;
    return;
  }

  try{
    const [summary,refs,rewards]=await Promise.all([
      api('/api/affiliate/summary'),
      api('/api/referrals'),
      api('/api/affiliate/rewards')
    ]);

    // Update stats
    if($('refDirectCount')) $('refDirectCount').textContent=summary.direct_referrals||0;
    if($('refCurrentTier')) $('refCurrentTier').textContent=summary.tier?.name||'Bạc';
    if($('refCommissionRate')) $('refCommissionRate').textContent=`Hoa hồng ${summary.tier?.rate_percent||10}%`;
    if($('refAvailableRewards')) $('refAvailableRewards').textContent=Number(summary.available||0).toLocaleString('vi-VN');
    if($('refAvailableVnd')) $('refAvailableVnd').textContent=`${Number(summary.available_vnd||0).toLocaleString('vi-VN')} ₫`;
    if($('refTotalRewards')) $('refTotalRewards').textContent=Number(summary.total_rewards||0).toLocaleString('vi-VN');

    // Update tier rates
    if($('refSilverRulePercent')) $('refSilverRulePercent').textContent=`${summary.commission_rates?.silver_percent||10}%`;
    if($('refGoldRulePercent')) $('refGoldRulePercent').textContent=`${summary.commission_rates?.gold_percent||15}%`;
    if($('refGoldThresholdAmount')) $('refGoldThresholdAmount').textContent=Number(summary.commission_rates?.gold_threshold_credits||1000).toLocaleString('vi-VN')+' Xu';

    // Show current tier badge
    if($('tierSilverBadge')) $('tierSilverBadge').style.display = summary.tier?.key === 'silver' ? 'block' : 'none';
    if($('tierGoldBadge')) $('tierGoldBadge').style.display = summary.tier?.key === 'gold' ? 'block' : 'none';

    // Update progress
    if(summary.tier?.next_sales_credits){
      if($('tierProgressSection')) $('tierProgressSection').style.display='block';
      if($('refTierProgressBar')) $('refTierProgressBar').style.width=`${Math.min(100, Number(summary.progress_percent||0))}%`;
      if($('refTierProgressText')) $('refTierProgressText').textContent=`${Number(summary.tier.sales_credits||0).toLocaleString('vi-VN')} / ${Number(summary.tier.next_sales_credits).toLocaleString('vi-VN')} Xu doanh số đủ điều kiện • Còn ${Number(summary.credits_to_gold||0).toLocaleString('vi-VN')} Xu để đạt hạng Vàng`;
    }else{
      if($('tierProgressSection')) $('tierProgressSection').style.display='none';
    }

    // Update referral links/codes
    if($('affLink')) $('affLink').textContent=summary.referral_link||'—';
    if($('affCode')) $('affCode').textContent=summary.referral_code||'—';

    // Handle referrer status
    if(summary.referrer){
      if($('referralApplySection')) $('referralApplySection').style.display='none';
      if($('referrerState')) $('referrerState').innerHTML=`<span class="referral-apply-status">✓ Tài khoản đã được ghi nhận người giới thiệu: <b>${summary.referrer.name}</b> (${summary.referrer.referral_code})</span>`;
    }else{
      if($('referralApplySection')) $('referralApplySection').style.display='block';
      if($('referrerState')) $('referrerState').innerHTML='';
      if($('applyReferralCode')) $('applyReferralCode').disabled=false;
      if($('applyReferralBtn')) $('applyReferralBtn').disabled=false;
      
      // Auto-fill from URL
      const ref=referralFromUrl();
      if(ref && $('applyReferralCode') && !$('applyReferralCode').value){
        $('applyReferralCode').value=ref;
      }
    }

    // Display referred users
    renderReferredUsers(refs);

    // Display commission history
    renderCommissionHistory(rewards);

  }catch(e){
    console.error(e);
    if(window.say) say(e.message);
  }
}

/**
 * Render referred users table/cards
 */
function renderReferredUsers(refs){
  const container=document.getElementById('referralUserList');
  
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
  const container=document.getElementById('referralRewardList');

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
      const el=document.getElementById(target?.substring(1));
      const text=el?.textContent||'';
      
      if(!text||text==='—'){
        if(window.say) say('Không có nội dung để sao chép');
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
        
        if(window.say) say('Đã sao chép');
      }catch(err){
        console.error('Copy failed:', err);
        if(window.say) say('Sao chép thất bại');
      }
    });
  });
}

/**
 * Setup CTA buttons
 */
function setupCTAButtons(){
  const affLinkEl=document.getElementById('affLink');
  const linkText=affLinkEl?.textContent||'—';

  const ctaCopyLink=document.getElementById('ctaCopyLink');
  if(ctaCopyLink){
    ctaCopyLink.addEventListener('click', async()=>{
      if(!linkText||linkText==='—'){
        if(window.say) say('Chưa có link giới thiệu');
        return;
      }
      try{
        await navigator.clipboard.writeText(linkText);
        if(window.say) say('Đã sao chép link giới thiệu');
      }catch(err){
        if(window.say) say('Sao chép thất bại');
      }
    });
  }

  const ctaShare=document.getElementById('ctaShare');
  if(ctaShare){
    ctaShare.addEventListener('click', async()=>{
      if(!linkText||linkText==='—'){
        if(window.say) say('Chưa có link giới thiệu');
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
          if(window.say) say('Đã sao chép link. Gửi cho bạn bè của bạn!');
        }catch(err){
          if(window.say) say('Sao chép thất bại');
        }
      }
    });
  }
}

/**
 * Setup FAQ accordion
 */
function setupFAQAccordion(){
  document.querySelectorAll('.referral-faq-trigger').forEach(trigger=>{
    trigger.addEventListener('click', ()=>{
      const id=trigger.dataset.faq;
      const content=document.getElementById(`faq-${id}`);
      const isOpen=content.classList.contains('open');

      // Close all
      document.querySelectorAll('.referral-faq-content').forEach(c=>c.classList.remove('open'));
      document.querySelectorAll('.referral-faq-trigger').forEach(t=>t.classList.remove('open'));

      // Open clicked
      if(!isOpen){
        content.classList.add('open');
        trigger.classList.add('open');
      }
    });
  });
}

/**
 * Setup apply referral code form
 */
function setupApplyReferralForm(){
  const applyBtn=document.getElementById('applyReferralBtn');
  const applyCode=document.getElementById('applyReferralCode');
  
  if(applyBtn && applyCode){
    applyBtn.addEventListener('click', async()=>{
      const code=applyCode.value?.trim();
      
      if(!code){
        if(window.say) say('Vui lòng nhập mã giới thiệu');
        return;
      }

      // Validate: can't use own code
      const ownCode=document.getElementById('affCode')?.textContent;
      if(code===ownCode){
        if(window.say) say('Bạn không thể sử dụng mã giới thiệu của chính mình');
        return;
      }

      try{
        applyBtn.disabled=true;
        const result=await api('/api/affiliate/apply-code',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({code})
        });
        
        if(window.say) say(`✓ Đã liên kết với ${result.referrer_name}`);
        await loadAffiliate();
      }catch(e){
        if(window.say) say(e.message);
      }finally{
        applyBtn.disabled=false;
      }
    });

    // Allow Enter key
    applyCode.addEventListener('keypress', (e)=>{
      if(e.key==='Enter'){
        applyBtn.click();
      }
    });
  }
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
  // Setup event listeners
  setupCopyButtons();
  setupCTAButtons();
  setupFAQAccordion();
  setupApplyReferralForm();

  // Refresh button
  const refreshBtn=document.getElementById('refreshAffiliate');
  if(refreshBtn){
    refreshBtn.addEventListener('click', loadAffiliate);
  }

  // Load data
  loadAffiliate();
}

// Initialize when referral tab is clicked or page loads
document.addEventListener('DOMContentLoaded', ()=>{
  const tabAffiliate=document.getElementById('tab-affiliate');
  if(tabAffiliate){
    // Check if already active
    if(tabAffiliate.classList.contains('active')){
      initReferralPage();
    }
    
    // Watch for changes
    const observer=new MutationObserver(()=>{
      if(tabAffiliate.classList.contains('active')){
        initReferralPage();
      }
    });
    observer.observe(tabAffiliate, {attributes:true, attributeFilter:['class']});
  }
});

// Also try immediate initialization if DOM is ready
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded', initReferralPage);
}else{
  // DOM already loaded
  setTimeout(initReferralPage, 100);
}
