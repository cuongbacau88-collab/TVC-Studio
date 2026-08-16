(function(){
'use strict';
const definitions=Object.freeze({
  video_generation:Object.freeze({
    title:'AI Video Creator',
    desc:'Biến prompt hoặc ảnh tham chiếu thành video chuyển động bằng AI.',
    button:'Tạo video',
    output:'video'
  }),
  outfit_change:Object.freeze({
    title:'AI Đổi Trang Phục',
    desc:'Dùng ảnh nhân vật và trang phục tham chiếu để tạo ảnh mới, ưu tiên giữ khuôn mặt và danh tính.',
    button:'Đổi trang phục',
    output:'image'
  }),
  background_change:Object.freeze({
    title:'AI Đổi Bối Cảnh',
    desc:'Dùng ảnh gốc cùng ảnh bối cảnh hoặc mô tả để tạo ảnh với bối cảnh mới.',
    button:'Đổi bối cảnh',
    output:'image'
  }),
  image_upscale:Object.freeze({
    title:'AI Nâng Cấp Ảnh',
    desc:'Nâng độ phân giải và độ nét để tạo ảnh chất lượng cao hơn.',
    button:'Nâng cấp ảnh',
    output:'image'
  })
});
window.TVCServiceDefinitions=definitions;
const key=location.pathname.split('/').filter(Boolean).pop();
const definition=definitions[key];
if(!definition)return;
const apply=()=>{
  const title=document.getElementById('serviceTitle');
  const description=document.getElementById('serviceDescription');
  const submit=document.getElementById('submitButton');
  const authText=document.querySelector('#authNotice p');
  const authButton=document.querySelector('#serviceLoginCta strong');
  const gallery=document.getElementById('serviceReferenceGallery');
  if(title)title.textContent=definition.title;
  if(description)description.textContent=definition.desc;
  if(submit)submit.textContent=definition.button;
  if(authText)authText.textContent=definition.output==='video'?'Đăng nhập để bắt đầu tạo video và theo dõi kết quả trong Lịch Sử.':'Đăng nhập để xử lý ảnh và theo dõi kết quả trong Lịch Sử.';
  if(authButton)authButton.textContent=definition.output==='video'?'Đăng nhập để tạo video':'Đăng nhập để xử lý ảnh';
  if(gallery)gallery.hidden=definition.output!=='video';
  document.title=definition.title+' — TVC Studio AI';
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply,{once:true});
else apply();
})();