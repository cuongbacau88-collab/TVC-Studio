(function(){
'use strict';
const interactive='a,button,input,select,textarea,label,video,[role="button"]';
const openCard=card=>{const href=card.dataset.serviceHref;if(href)location.assign(href)};
document.addEventListener('click',event=>{
  const card=event.target.closest('[data-service-href]');
  if(!card||event.target.closest(interactive))return;
  openCard(card);
});
document.addEventListener('keydown',event=>{
  if(event.key!=='Enter'&&event.key!==' ')return;
  const card=event.target.closest('[data-service-href]');
  if(!card||event.target.closest(interactive))return;
  event.preventDefault();
  openCard(card);
});
})();