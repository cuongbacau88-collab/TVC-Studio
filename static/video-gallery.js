(function(){
'use strict';
const root=document.getElementById('videoGallery');if(!root)return;
const valid=item=>item&&item.id&&item.title&&item.video_url&&item.poster_url&&item.duration&&item.method&&new URL(item.video_url,location.origin).origin===location.origin&&new URL(item.poster_url,location.origin).origin===location.origin;
fetch('/static/video-gallery.json',{cache:'no-store'}).then(response=>response.ok?response.json():Promise.reject()).then(data=>{
 const items=Array.isArray(data.items)?data.items.filter(valid):[];if(!items.length)return;
 root.className='video-gallery-carousel';root.innerHTML=items.map((item,index)=>`<button type="button" class="gallery-card" data-gallery="${index}"><span class="gallery-poster"><img src="${item.poster_url}" alt="" loading="lazy"><i>▶</i></span><b>${item.title}</b><small>${item.topic||''} · ${item.duration}s</small><em>${item.method}</em></button>`).join('');
 const modal=document.getElementById('galleryModal'),video=document.getElementById('galleryModalVideo');
 function close(){video.pause();video.removeAttribute('src');video.load();modal.hidden=true;document.body.classList.remove('gallery-modal-open')}
 root.querySelectorAll('[data-gallery]').forEach(button=>button.onclick=()=>{const item=items[+button.dataset.gallery];video.src=item.video_url;video.muted=true;video.preload='metadata';document.getElementById('galleryModalTitle').textContent=item.title;document.getElementById('galleryModalMeta').textContent=`${item.method} · ${item.reference_count||0} nội dung tham chiếu`;document.getElementById('galleryModalPrompt').textContent=item.public_prompt||'Prompt mẫu không được công khai.';document.getElementById('galleryUseIdea').onclick=()=>{if(item.public_prompt){document.querySelector('[name=prompt]').value=item.public_prompt}close();window.scrollTo({top:0,behavior:'smooth'})};modal.hidden=false;document.body.classList.add('gallery-modal-open')});
 modal.querySelector('[data-close-gallery]').onclick=close;modal.addEventListener('click',event=>{if(event.target===modal)close()});document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!modal.hidden)close()});
}).catch(()=>{});
})();
