const key=location.pathname.split('/').filter(Boolean).pop();
const $=id=>document.getElementById(id);
let config=null,currentJob=null,pollTimer=null,submitting=false;
const definitions=window.TVCServiceDefinitions||{};
const prompts={
 vi:{outfit:'Chỉ thay trang phục của nhân vật trong ảnh gốc theo ảnh trang phục tham chiếu. Giữ nguyên khuôn mặt, danh tính, kiểu tóc, tông da, tỷ lệ cơ thể, tư thế, góc máy, ánh sáng và bối cảnh. Không lấy khuôn mặt, cơ thể hoặc tư thế từ ảnh trang phục.',background:'Chỉ thay bối cảnh của ảnh gốc theo ảnh tham chiếu hoặc mô tả. Giữ nguyên tuyệt đối khuôn mặt, danh tính, kiểu tóc, trang phục, cơ thể, tư thế, góc máy và bố cục nhân vật. Ghép cảnh tự nhiên, giữ viền tóc sạch và không làm da bị ám màu theo nền.'},
 en:{outfit:'Only replace the original character’s clothing using the outfit reference. Preserve the face, identity, hairstyle, skin tone, body proportions, pose, camera angle, lighting, and background. Do not copy the face, body, or pose from the outfit image.',background:'Only replace the original image background using the reference image or description. Strictly preserve the face, identity, hairstyle, clothing, body, pose, camera angle, and character composition. Blend naturally, keep clean hair edges, and prevent background color spill on skin.'}
};
function language(){return localStorage.getItem('tvc_lang')==='en'?'en':'vi'}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function api(url,options={}){
 const response=await fetch(url,options),type=response.headers.get('content-type')||'';
 const body=type.includes('json')?await response.json():{};
 if(!response.ok)throw new Error(body.detail||'Không thể kết nối máy chủ');
 return body;
}
function requestKey(){return crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random().toString(36).slice(2)}
function fileField(name,label,required=false){
 return `<label class="service-field"><span>${label}${required?' *':''}</span><input type="file" name="${name}" accept="image/png,image/jpeg,image/webp" ${required?'required':''}><div class="file-preview" data-preview="${name}"><small>Chưa chọn ảnh</small></div></label>`;
}
function renderFields(){
 if(key==='video_generation'&&window.renderVideoCreator){window.renderVideoCreator(config);return}
 let html='';
 if(key==='video_generation'){
  html=`<p class="prompt-help">Nhân vật đang làm gì? • Bối cảnh ở đâu? • Camera chuyển động thế nào? • Ánh sáng và phong cách mong muốn?</p><label class="service-field"><span>Prompt *</span><textarea name="prompt" maxlength="2000" required placeholder="Ví dụ: Một cô gái mặc váy trắng bước chậm trên bãi biển lúc hoàng hôn, tóc bay nhẹ trong gió, camera tiến gần, ánh sáng điện ảnh, chuyển động tự nhiên."></textarea></label>
  ${fileField('reference_image','Ảnh tham chiếu (tùy chọn)')}
  <div class="field-row"><label class="service-field"><span>Tỷ lệ</span><select name="aspect_ratio">${config.aspect_ratios.map(v=>`<option>${v}</option>`).join('')}</select></label>
  <label class="service-field"><span>Thời lượng</span><select name="duration" ${config.durations.length?'':'disabled'}>${config.durations.length?config.durations.map(v=>`<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join(''):'<option>Chưa cấu hình model</option>'}</select></label></div>`;
 }else if(key==='outfit_change'){
  html=fileField('character_image','Ảnh nhân vật',true)+fileField('outfit_image','Ảnh trang phục tham chiếu',true)+`<label class="service-field"><span>Prompt bổ sung</span><textarea name="prompt" maxlength="2000">${escapeHtml(prompts[language()].outfit)}</textarea></label>`;
 }else if(key==='background_change'){
  html=fileField('source_image','Ảnh gốc',true)+fileField('background_image','Ảnh bối cảnh tham chiếu')+`<label class="service-field"><span>Mô tả bối cảnh</span><textarea name="prompt" maxlength="2000">${escapeHtml(prompts[language()].background)}</textarea></label>`;
 }else if(key==='image_upscale'){
  html=`<p class="prompt-help">Hệ thống tăng độ nét và độ phân giải nhưng cố gắng giữ nguyên khuôn mặt và nội dung ảnh.</p>`+fileField('source_image','Ảnh cần nâng cấp',true)+`<div class="field-row"><label class="service-field"><span>Mức phóng đại</span><select name="scale">${config.scales.map(v=>`<option value="${v}">${v}x</option>`).join('')}</select></label>
  <label class="check-field"><input type="checkbox" name="restore_face" value="true" ${config.face_restore_supported?'':'disabled'}><span>Phục hồi khuôn mặt${config.face_restore_supported?'':' (worker chưa hỗ trợ)'}</span></label></div>`;
 }
 $('dynamicFields').innerHTML=html;
 document.querySelectorAll('input[type=file]').forEach(input=>input.addEventListener('change',()=>{
  const box=document.querySelector(`[data-preview="${input.name}"]`);
  if(box.dataset.url)URL.revokeObjectURL(box.dataset.url);
  if(!input.files[0]){box.innerHTML='<small>Chưa chọn ảnh</small>';return}
  const url=URL.createObjectURL(input.files[0]);box.dataset.url=url;
  box.innerHTML=`<img src="${url}" alt=""><small>${escapeHtml(input.files[0].name)}</small>`;
 }));
}
function setError(message=''){
 $('formError').textContent=message;$('formError').classList.toggle('hidden',!message);
}
function setStatus(job){
 currentJob=job;$('jobState').classList.remove('hidden');$('resultPlaceholder').classList.add('hidden');
 const labels={waiting:'Đang chờ',running:'Đang xử lý',upscaling:'Đang nâng cấp video lên HD',done:'Hoàn thành',failed:'Thất bại',cancelled:'Đã hủy',uploading:'Đang gửi dữ liệu'};
 $('statusLabel').textContent=labels[job.status]||job.status;
 $('progressLabel').textContent=(job.progress||0)+'%';$('jobProgress').value=job.progress||0;
 $('jobMessage').textContent=job.error||({waiting:'Job đã vào hàng chờ.',running:'Máy chủ GPU đang xử lý.',upscaling:'Đang nâng cấp video lên HD. Không trừ thêm lượt.',done:job.upscale_fallback?'Nâng cấp HD không thành công; video gốc vẫn sẵn sàng để tải.':'Kết quả đã sẵn sàng.',failed:'Xử lý thất bại; lượt đã trừ sẽ được hoàn tự động.',cancelled:'Job đã được hủy.'}[job.status]||'');
 $('cancelButton').classList.toggle('hidden',!job.can_cancel);
 $('retryButton').classList.toggle('hidden',!['failed','cancelled'].includes(job.status));
 const done=job.status==='done',url=`/api/services/${key}/jobs/${job.id}/result`;
 ['regenerateButton','historyButton','reuseButton'].forEach(id=>$(id).classList.toggle('hidden',!done));
 $('historyButton').href='/app#jobs';

 $('downloadButton').classList.toggle('hidden',!done);
 $('downloadButton').href=url + '?download=1';
 $('downloadButton').setAttribute('download', `${key}_${job.id}.${config?.output_kind==='video'?'mp4':'png'}`);
 if(done){
  $('resultPreview').innerHTML=config.output_kind==='video'?`<video controls playsinline autoplay preload="auto" src="${url}" style="width:100%;max-height:480px;border-radius:18px;background:#000;box-shadow:0 10px 30px rgba(0,0,0,0.5);"></video>`:`<div class="comparison"><div class="before-clone"></div><img src="${url}" alt="Kết quả"></div>`;
  if(key==='image_upscale'){const source=document.querySelector('[data-preview="source_image"] img');if(source)document.querySelector('.before-clone')?.append(source.cloneNode())}
 }
 if(['waiting','running','upscaling'].includes(job.status))schedulePoll();else clearTimeout(pollTimer);
}
function schedulePoll(){clearTimeout(pollTimer);pollTimer=setTimeout(poll,Number(window.workerPollMs||4000))}
async function poll(){if(!currentJob)return;try{setStatus(await api(`/api/services/${key}/jobs/${currentJob.id}`))}catch(e){$('jobMessage').textContent=e.message;schedulePoll()}}
 if(key==='video_generation'){$('serviceGuide').textContent='Chọn phương thức phù hợp, cung cấp nội dung tham chiếu và mô tả video bạn muốn tạo. AI sẽ tạo một video hoàn toàn mới dựa trên yêu cầu của bạn.';$('serviceGuide').classList.remove('hidden')}
async function init(){
 const def=definitions[key];if(!def){location.href='/';return}
 $('serviceTitle').textContent=def.title;$('serviceDescription').textContent=def.desc;$('submitButton').textContent=def.button;
 let authenticated=false;
 try{const catalog=await api('/api/services');config=catalog.find(v=>v.key===key);window.workerPollMs=Number(config?.poll_interval||4)*1000}
 catch(e){setError(e.message);return}
 if(!config){setError('Dịch vụ không tồn tại');return}
 try{const me=await api('/api/me');authenticated=true;document.getElementById('mobileToolbarCredits').textContent=Number(me.usage_balance||0).toLocaleString('vi-VN')}
 catch(e){const notice=$('authNotice'),link=$('serviceLoginCta');notice.classList.remove('hidden');if(link&&window.TVCReturnNavigation)link.href=window.TVCReturnNavigation.loginUrl()}
 $('serviceCost').textContent=config.free?'Miễn phí • xử lý khi GPU rảnh':config.usage==null?'Mức lượt chưa được cấu hình':`${config.usage} lượt / job`;
 const unavailable=!config.configured||(key==='video_generation'&&(!config.durations.length||config.usage==null));
 if(unavailable){$('configNotice').textContent='Cấu hình dịch vụ chưa đầy đủ.';$('configNotice').classList.remove('hidden');$('submitButton').disabled=true}
 else if(config.render_mode==='worker'&&!config.worker_configured){$('configNotice').textContent='GPU worker hiện chưa online. Bạn vẫn có thể tạo job; job sẽ chờ worker và tự thất bại/hoàn lượt nếu quá thời gian.';$('configNotice').classList.remove('hidden')}
 renderFields();$('requestKey').value=requestKey();
 if(!authenticated){$('submitButton').disabled=true;$('submitButton').classList.add('hidden')}
 const requestedJob=new URLSearchParams(location.search).get('job');
 if(requestedJob&&/^\d+$/.test(requestedJob)){try{setStatus(await api(`/api/services/${key}/jobs/${requestedJob}`))}catch(e){setError(e.message)}}
}
$('serviceForm').addEventListener('submit',async event=>{
 event.preventDefault();if(submitting)return;submitting=true;setError();$('submitButton').disabled=true;$('submitButton').textContent='Đang gửi…';
 try{const data=new FormData(event.currentTarget);data.set('language',language());if(key==='video_generation'&&event.currentTarget.__creatorFiles){event.currentTarget.__creatorFiles.images.forEach(f=>data.append('reference_images',f));event.currentTarget.__creatorFiles.videos.forEach(f=>data.append('reference_videos',f))}const job=await api(`/api/services/${key}/jobs`,{method:'POST',body:data});setStatus(job)}
 catch(e){setError(e.message)}
 finally{submitting=false;$('submitButton').disabled=false;$('submitButton').textContent=definitions[key].button}
});
$('cancelButton').onclick=async()=>{try{setStatus(await api(`/api/services/${key}/jobs/${currentJob.id}`,{method:'DELETE'}))}catch(e){setError(e.message)}};
$('retryButton').onclick=()=>{clearTimeout(pollTimer);currentJob=null;$('jobState').classList.add('hidden');$('resultPlaceholder').classList.remove('hidden');$('requestKey').value=requestKey();setError()};
$('regenerateButton').onclick=()=>{if(!currentJob||currentJob.status!=='done')return;clearTimeout(pollTimer);currentJob=null;$('jobState').classList.add('hidden');$('resultPlaceholder').classList.remove('hidden');$('requestKey').value=requestKey();setError();window.scrollTo({top:0,behavior:'smooth'})};
$('reuseButton').onclick=()=>{if(!currentJob||currentJob.status!=='done')return;window.reuseVideoCreatorSettings?.();$('requestKey').value=requestKey();setError()};
init();
