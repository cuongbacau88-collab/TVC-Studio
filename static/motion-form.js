(function(){
'use strict';
const IMAGE_EXTENSIONS=new Set(['png','jpg','jpeg','webp']);
const VIDEO_EXTENSIONS=new Set(['mp4','mov','webm']);
const IMAGE_TYPES=new Set(['image/png','image/jpeg','image/webp']);
const VIDEO_TYPES=new Set(['video/mp4','video/quicktime','video/webm']);
const MAX_IMAGE_BYTES=25*1024*1024;
const MAX_VIDEO_BYTES=300*1024*1024;
const MIN_DURATION=10;
const MAX_DURATION=20;

const extension=file=>(file?.name?.split('.').pop()||'').toLowerCase();
const formatSize=bytes=>(bytes/(1024*1024)).toLocaleString('vi-VN',{maximumFractionDigits:1})+' MB';
function fileError(file,kind){
  if(!file)return kind==='image'?'Vui lòng chọn ảnh nhân vật.':'Vui lòng chọn video mẫu.';
  const isImage=kind==='image',extensions=isImage?IMAGE_EXTENSIONS:VIDEO_EXTENSIONS;
  const types=isImage?IMAGE_TYPES:VIDEO_TYPES,max=isImage?MAX_IMAGE_BYTES:MAX_VIDEO_BYTES;
  if(!extensions.has(extension(file))||(file.type&&!types.has(file.type))){
    return isImage?'Ảnh không hợp lệ. Hỗ trợ PNG, JPG, JPEG hoặc WEBP.':'Video không hợp lệ. Hỗ trợ MP4, MOV hoặc WEBM.';
  }
  if(file.size>max){
    return (isImage?'Ảnh':'Video')+' vượt quá dung lượng cho phép '+formatSize(max)+'.';
  }
  return '';
}
function readVideoDuration(file){
  return new Promise((resolve,reject)=>{
    const video=document.createElement('video');
    const url=URL.createObjectURL(file);
    const cleanup=()=>{video.removeAttribute('src');video.load();URL.revokeObjectURL(url)};
    video.preload='metadata';
    video.onloadedmetadata=()=>{const duration=video.duration;cleanup();Number.isFinite(duration)?resolve(duration):reject(new Error())};
    video.onerror=()=>{cleanup();reject(new Error())};
    video.src=url;
  });
}
function create(form,{onValidityChange=()=>{}}={}){
  const imageInput=form.elements.image,motionInput=form.elements.motion;
  const imageName=document.getElementById('imgName'),motionName=document.getElementById('vidName');
  const imagePreview=document.getElementById('imagePreview'),motionPreview=document.getElementById('motionPreview');
  const imageError=document.getElementById('imageError'),motionError=document.getElementById('motionError');
  const durationNote=document.getElementById('motionDurationNote');
  const aspectInput=document.getElementById('aspectRatio');
  let imageValid=false,motionValid=false,motionDuration=null;
  let imageUrl='',motionUrl='',validationToken=0;
  const revoke=(kind)=>{
    if(kind==='image'&&imageUrl){URL.revokeObjectURL(imageUrl);imageUrl=''}
    if(kind==='motion'&&motionUrl){URL.revokeObjectURL(motionUrl);motionUrl=''}
  };
  const showError=(node,message)=>{node.textContent=message;node.hidden=!message};
  const update=()=>onValidityChange(imageValid&&motionValid&&['9:16','16:9'].includes(aspectInput.value));
  const clearPreview=(kind)=>{
    const preview=kind==='image'?imagePreview:motionPreview;
    revoke(kind);preview.replaceChildren();preview.hidden=true;
  };
  function validateImage(){
    const file=imageInput.files?.[0],error=fileError(file,'image');
    imageName.textContent=file?.name||'Chưa chọn ảnh';
    imageValid=!error;showError(imageError,error);clearPreview('image');
    if(imageValid){
      imageUrl=URL.createObjectURL(file);
      const image=document.createElement('img');image.src=imageUrl;image.alt='Xem trước ảnh nhân vật';
      image.onerror=()=>{imageValid=false;showError(imageError,'Không thể đọc ảnh đã chọn. Vui lòng chọn file ảnh khác.');clearPreview('image');update()};
      imagePreview.append(image);imagePreview.hidden=false;
    }
    update();return imageValid;
  }
  async function validateMotion(){
    const token=++validationToken,file=motionInput.files?.[0],basicError=fileError(file,'motion');
    motionName.textContent=file?.name||'Chưa chọn video';
    motionValid=false;motionDuration=null;showError(motionError,basicError);clearPreview('motion');
    durationNote.textContent='⏱ Video chuyển động phải có thời lượng từ 10s đến 20s.';
    update();
    if(basicError)return false;
    durationNote.textContent='⏱ Đang kiểm tra thời lượng video…';
    try{
      const duration=await readVideoDuration(file);
      if(token!==validationToken)return false;
      motionDuration=duration;
      if(duration<MIN_DURATION||duration>MAX_DURATION){
        const shown=duration.toLocaleString('vi-VN',{maximumFractionDigits:1});
        showError(motionError,'Video dài '+shown+' giây. Vui lòng chọn video từ 10 đến 20 giây.');
        durationNote.textContent='⏱ Thời lượng không hợp lệ: '+shown+' giây.';
        update();return false;
      }
      motionValid=true;
      durationNote.textContent='✓ Thời lượng hợp lệ: '+duration.toLocaleString('vi-VN',{maximumFractionDigits:1})+' giây.';
      motionUrl=URL.createObjectURL(file);
      const video=document.createElement('video');video.src=motionUrl;video.controls=true;video.playsInline=true;video.preload='metadata';
      video.onerror=()=>{motionValid=false;showError(motionError,'Không thể đọc video đã chọn. Vui lòng chọn file video khác.');clearPreview('motion');update()};
      motionPreview.append(video);motionPreview.hidden=false;
    }catch{
      if(token!==validationToken)return false;
      showError(motionError,'Không thể đọc thời lượng video. Vui lòng chọn file MP4, MOV hoặc WEBM hợp lệ.');
      durationNote.textContent='⏱ Không đọc được thời lượng video.';
    }
    update();return motionValid;
  }
  imageInput.addEventListener('change',validateImage);
  motionInput.addEventListener('change',validateMotion);
  document.querySelectorAll('.simple-aspect').forEach(button=>button.addEventListener('click',()=>queueMicrotask(update)));
  window.addEventListener('pagehide',()=>{validationToken++;revoke('image');revoke('motion')});
  window.addEventListener('pageshow',event=>{
    if(!event.persisted)return;
    validateImage();
    validateMotion();
  });
  update();
  return {
    isValid:()=>imageValid&&motionValid&&['9:16','16:9'].includes(aspectInput.value),
    firstError:()=>imageError.textContent||motionError.textContent||(!imageInput.files?.length?'Vui lòng chọn ảnh nhân vật.':!motionInput.files?.length?'Vui lòng chọn video mẫu.':''),
    async validateForSubmit(){
      const validImage=validateImage();
      const selected=motionInput.files?.[0];
      if(!selected)return validateMotion().then(()=>false);
      if(!motionValid||motionDuration===null)await validateMotion();
      return validImage&&this.isValid();
    },
    cleanup:()=>{validationToken++;revoke('image');revoke('motion')},
    reset:()=>{validationToken++;revoke('image');revoke('motion');imageValid=false;motionValid=false;motionDuration=null;showError(imageError,'');showError(motionError,'');imagePreview.replaceChildren();motionPreview.replaceChildren();imagePreview.hidden=true;motionPreview.hidden=true;imageName.textContent='Chưa chọn ảnh';motionName.textContent='Chưa chọn video';update()}
  };
}
window.TVCMotionForm={create,fileError,readVideoDuration,limits:{MAX_IMAGE_BYTES,MAX_VIDEO_BYTES,MIN_DURATION,MAX_DURATION}};
})();