(()=> {
const $=id=>document.getElementById(id);
const status=$('vkStatus'), tools=$('vkTools'), connect=$('vkConnectBtn'), results=$('vkResults');
if(!status||!tools||!connect||!results)return;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=s=>{s=Number(s)||0;return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
async function api(url,opts){const r=await fetch(url,opts);const d=await r.json();if(!r.ok)throw Error(d.error||'Ошибка запроса');return d}
function render(items){if(!items.length){results.innerHTML='<div class="empty"><b>Ничего не найдено</b>Попробуй другое название или проверь доступ к аудио в ВК.</div>';return}
results.innerHTML=items.map((t,i)=>'<div class="track"><div class="cover c'+(i%4+1)+'">♫</div><div class="track-info"><div class="track-title">'+esc(t.title)+'</div><div class="track-artist">'+esc(t.artist)+' · '+time(t.duration)+'</div></div><button class="track-action vk-play" data-index="'+i+'" aria-label="Воспроизвести">▶</button><a class="track-action" href="'+esc(t.vk_url)+'" target="_blank" rel="noopener" aria-label="Открыть ВК" style="text-decoration:none">↗</a></div>').join('');
results.querySelectorAll('.vk-play').forEach(b=>b.onclick=()=>{const t=items[Number(b.dataset.index)];if(t.url){const audio=document.getElementById('audioPlayer');audio.src=t.url;audio.play().catch(()=>window.open(t.vk_url,'_blank','noopener'));document.getElementById('nowTitle').textContent=t.title;document.getElementById('nowArtist').textContent=t.artist+' · ВКонтакте';document.getElementById('playBtn').textContent='Ⅱ'}else{window.open(t.vk_url,'_blank','noopener')}});
}
async function statusCheck(){try{const d=await api('/api/vk/status');if(d.connected){status.textContent='Подключено'+(d.name?' · '+d.name:'');connect.style.display='none';tools.style.display='block'}else{status.textContent='Подключи ВКонтакте для поиска и своей музыки';connect.style.display='inline-block';tools.style.display='none'}}catch(e){status.textContent='Не удалось проверить подключение'}}
connect.onclick=()=>{location.href='/api/vk/login'};
$('vkSearchBtn').onclick=async()=>{const q=$('vkSearchInput').value.trim();if(!q){$('vkSearchInput').focus();return}results.innerHTML='<div class="empty">Ищем музыку…</div>';try{render((await api('/api/vk/search?q='+encodeURIComponent(q))).items||[])}catch(e){results.innerHTML='<div class="empty"><b>Поиск не выполнен</b>'+esc(e.message)+'</div>'}};
$('vkSearchInput').addEventListener('keydown',e=>{if(e.key==='Enter')$('vkSearchBtn').click()});
$('vkMyAudioBtn').onclick=async()=>{results.innerHTML='<div class="empty">Загружаем твою музыку…</div>';try{render((await api('/api/vk/my-audio')).items||[])}catch(e){results.innerHTML='<div class="empty"><b>Не удалось загрузить музыку</b>'+esc(e.message)+'</div>'}};
$('vkLogoutBtn').onclick=async()=>{try{await api('/api/vk/logout',{method:'POST'});results.innerHTML='';statusCheck()}catch(e){status.textContent=e.message}};
const params=new URLSearchParams(location.search);if(params.has('vk_connected')){history.replaceState({},'',location.pathname);status.textContent='ВКонтакте подключён';}else if(params.has('vk_error')){status.textContent='Не удалось подключить ВК: '+params.get('vk_error');history.replaceState({},'',location.pathname)}
statusCheck();
})();