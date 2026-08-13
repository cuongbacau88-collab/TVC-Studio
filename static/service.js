const key=location.pathname.split('/').filter(Boolean).pop();
const $=id=>document.getElementById(id);
let config=null,currentJob=null,pollTimer=null,submitting=false;
const definitions={
 video_generation:{title:'AI Tạo Video',desc:'Tạo video từ prompt và ảnh tham chiếu tùy chọn.',button:'Tạo video'},
 outfit_change:{title:'AI Đổi Trang Phục',desc:'Thay trang phục, ưu tiên giữ khuôn mặt và danh tính.',button:'Đổi trang phục'},
 background_change:{title:'AI Đổi Bối Cảnh',desc:'Thay bối cảnh bằng ảnh tham chiếu hoặc mô tả.',button:'Đổi bối cảnh'},
 image_upscale:{title:'AI Nâng Cấp Ảnh',desc:'Tăng độ phân giải và so sánh ảnh trước/sau.',button:'Nâng cấp ảnh'}
};
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
 let html='';
 if(key==='video_generation'){
  html=`<label class="service-field"><span>Prompt *</span><textarea name="prompt" maxlength="2000" required placeholder="Mô tả video bạn muốn tạo"></textarea></label>
  ${fileField('reference_image','Ảnh tham chiếu (tùy chọn)')}
  <div class="field-row"><label class="service-field"><span>Tỷ lệ</span><select name="aspect_ratio">${config.aspect_ratios.map(v=>`<option>${v}</option>`).join('')}</select></label>
  <label class="service-field"><span>Thời lượng</span><select name="duration" ${config.durations.length?'':'disabled'}>${config.durations.length?config.durations.map(v=>`<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join(''):'<option>Chưa cấu hình model</option>'}</select></label></div>`;
 }else if(key==='outfit_change'){
  html=fileField('character_image','Ảnh nhân vật',true)+fileField('outfit_image','Ảnh trang phục tham chiếu',true)+`<label class="service-field"><span>Prompt bổ sung</span><textarea name="prompt" maxlength="2000" placeholder="Yêu cầu thêm (tùy chọn)"></textarea></label>`;
 }else if(key==='background_change'){
  html=fileField('source_image','Ảnh gốc',true)+fileField('background_image','Ảnh bối cảnh tham chiếu')+`<label class="service-field"><span>Mô tả bối cảnh</span><textarea name="prompt" maxlength="2000" placeholder="Nhập mô tả nếu không tải ảnh bối cảnh"></textarea></label>`;
 }else if(key==='image_upscale'){
  html=fileField('source_image','Ảnh cần nâng cấp',true)+`<div class="field-row"><label class="service-field"><span>Mức phóng đại</span><select name="scale">${config.scales.map(v=>`<option value="${v}">${v}x</option>`).join('')}</select></label>
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
 $('downloadButton').classList.toggle('hidden',!done);$('downloadButton').href=url;
 if(done){
  $('resultPreview').innerHTML=config.output_kind==='video'?`<video controls playsinline src="${url}"></video>`:`<div class="comparison"><div class="before-clone"></div><img src="${url}" alt="Kết quả"></div>`;
  if(key==='image_upscale'){const source=document.querySelector('[data-preview="source_image"] img');if(source)document.querySelector('.before-clone')?.append(source.cloneNode())}
 }
 if(['waiting','running','upscaling'].includes(job.status))schedulePoll();else clearTimeout(pollTimer);
}
function schedulePoll(){clearTimeout(pollTimer);pollTimer=setTimeout(poll,Number(window.workerPollMs||4000))}
async function poll(){if(!currentJob)return;try{setStatus(await api(`/api/services/${key}/jobs/${currentJob.id}`))}catch(e){$('jobMessage').textContent=e.message;schedulePoll()}}
async function init(){
 const def=definitions[key];if(!def){location.href='/';return}
 $('serviceTitle').textContent=def.title;$('serviceDescription').textContent=def.desc;$('submitButton').textContent=def.button;
 try{const [catalog,me]=await Promise.all([api('/api/services'),api('/api/me')]);config=catalog.find(v=>v.key===key);window.workerPollMs=Number(config?.poll_interval||4)*1000;$('balance').textContent=Number(me.usage_balance||0).toLocaleString('vi-VN')}
 catch(e){if(e.message.includes('đăng nhập')||e.message.includes('Phiên'))$('authNotice').classList.remove('hidden');setError(e.message);return}
 if(!config){setError('Dịch vụ không tồn tại');return}
 $('serviceCost').textContent=config.free?'Miễn phí • xử lý khi GPU rảnh':config.usage==null?'Mức lượt chưa được cấu hình':`${config.usage} lượt / job`;
 const unavailable=!config.configured||(key==='video_generation'&&(!config.durations.length||config.usage==null));
 if(unavailable){$('configNotice').textContent=!config.configured?'Dịch vụ chưa kết nối máy chủ xử lý.':'Model chưa được cấu hình thời lượng hoặc mức lượt sử dụng.';$('configNotice').classList.remove('hidden');$('submitButton').disabled=true}
 renderFields();$('requestKey').value=requestKey();
}
$('serviceForm').addEventListener('submit',async event=>{
 event.preventDefault();if(submitting)return;submitting=true;setError();$('submitButton').disabled=true;$('submitButton').textContent='Đang gửi…';
 try{const job=await api(`/api/services/${key}/jobs`,{method:'POST',body:new FormData(event.currentTarget)});setStatus(job)}
 catch(e){setError(e.message)}
 finally{submitting=false;$('submitButton').disabled=false;$('submitButton').textContent=definitions[key].button}
});
$('cancelButton').onclick=async()=>{try{setStatus(await api(`/api/services/${key}/jobs/${currentJob.id}`,{method:'DELETE'}))}catch(e){setError(e.message)}};
$('retryButton').onclick=()=>{clearTimeout(pollTimer);currentJob=null;$('jobState').classList.add('hidden');$('resultPlaceholder').classList.remove('hidden');$('requestKey').value=requestKey();setError()};
init();
