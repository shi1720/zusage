self.addEventListener('push', event => {
  let data = {title:'Zusage',body:'Your next step is ready.',url:'/nudges'};
  try { data = {...data,...event.data.json()}; } catch {}
  event.waitUntil(self.registration.showNotification(data.title,{body:data.body,tag:'zusage-follow-up',data:{url:data.url}}));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || '/nudges',self.location.origin);
  event.waitUntil(clients.openWindow(url.origin===self.location.origin?url.href:self.location.origin+'/nudges'));
});
