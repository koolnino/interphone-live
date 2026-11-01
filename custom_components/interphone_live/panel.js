/* Local prototype: uses Home Assistant's existing authenticated WebSocket. */
const captureWorklet = `
class Capture extends AudioWorkletProcessor {
  constructor() { super(); this.buffer=[]; this.position=0; this.previous=0; }
  process(inputs,outputs) {
    const a=inputs[0]?.[0];
    if(a) {
      const step=sampleRate/16000;
      for(let i=0;i<a.length;i++) {
        while(this.position<=i) {
          const t=this.position-i+1;
          const x=this.previous+(a[i]-this.previous)*Math.max(0,Math.min(1,t));
          this.buffer.push(Math.round(Math.max(-1,Math.min(1,x))*32767));
          this.position+=step;
          if(this.buffer.length===1280) {
            const data=new ArrayBuffer(2560), v=new DataView(data);
            this.buffer.forEach((n,k)=>v.setInt16(k*2,n,true));
            this.port.postMessage(data,[data]); this.buffer=[];
          }
        }
        this.previous=a[i];
      }
      this.position-=a.length;
    }
    for(const channel of outputs[0]||[]) channel.fill(0);
    return true;
  }
}
registerProcessor('interphone-capture',Capture);`;

class InterphoneLocalPanel extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this._session=null; this._pending=0; this._generation=0; }
  set hass(value) { this._hass=value; if(this.isConnected&&!this._initialized) this.initialize(); else if(this._initialized)this.updateVolumes(); }
  connectedCallback() { if(this._hass&&!this._initialized) this.initialize(); }
  disconnectedCallback() { this.stop(); this.removeListeners(); }
  removeListeners() {
    document.removeEventListener('visibilitychange',this._onVisibility);
    window.removeEventListener('pagehide',this._onHide);
  }
  async initialize() {
    this._initialized=true;
    this.shadowRoot.innerHTML=`
    <style>
      :host{display:block;height:100%;overflow:auto;background:var(--primary-background-color,#f5f6f8);color:var(--primary-text-color,#172535);font:16px system-ui,-apple-system,sans-serif}
      *{box-sizing:border-box}header{display:flex;align-items:center;gap:16px;padding:16px 20px;border-bottom:1px solid #8883;background:var(--card-background-color,white)}
      #menu{border:0;background:none;color:inherit;font-size:24px;padding:6px}header h1{font-size:19px;margin:0}
      main{max-width:600px;margin:32px auto;padding:0 20px 40px}.badge{font-size:12px;font-weight:700;letter-spacing:.08em;color:#247d79}
      h2{font-size:30px;line-height:1.15;margin:12px 0}p{line-height:1.55;color:var(--secondary-text-color,#526071)}
      .card{background:var(--card-background-color,white);border:1px solid #8883;border-radius:22px;padding:24px;margin:24px 0;box-shadow:0 8px 24px #00000005}
      .destination{font-size:20px;font-weight:650}select{width:100%;padding:14px 10px;border:1px solid #8886;border-radius:12px;background:var(--card-background-color,white);color:inherit;font:inherit}.label{font-size:13px;color:var(--secondary-text-color,#526071);margin-bottom:7px}
      .volume-row{margin:16px 0}.volume-heading{display:flex;justify-content:space-between;gap:12px;font-size:15px}.volume-controls{display:flex;gap:12px;align-items:center}.volume-controls input{flex:1;min-width:0;height:36px;accent-color:#176e69}.volume-controls button{width:40px;height:40px;border:1px solid #8886;background:transparent;color:inherit;border-radius:10px;font-size:22px}#volume-feedback{font-size:13px;min-height:20px}
      #speak{width:100%;min-height:92px;border:0;border-radius:18px;background:#176e69;color:white;font-size:20px;font-weight:700;cursor:pointer;touch-action:manipulation}
      #speak.live{background:#b73342}button:disabled{opacity:.5;cursor:wait}button:focus-visible{outline:3px solid #e4af37;outline-offset:4px}
      #status{min-height:50px;margin:16px 0 0;font-weight:600}#timer{font-variant-numeric:tabular-nums;float:right}
      #test{border:1px solid #8886;background:transparent;color:inherit;border-radius:12px;padding:13px 18px;cursor:pointer;font-size:15px}
      details{margin-top:20px;color:var(--secondary-text-color,#526071);font-size:14px;line-height:1.6}summary{cursor:pointer}#diagnostic{white-space:pre-wrap;font:13px ui-monospace,monospace}
      .warn{border-left:3px solid #d59a35;padding-left:12px;font-size:14px}footer{font-size:12px;color:var(--secondary-text-color,#526071)}
      @media(max-width:500px){main{margin-top:24px}.card{padding:20px}h2{font-size:27px}}
    </style>
    <header><button id="menu" aria-label="Ouvrir le menu">☰</button><h1>Interphone Live</h1></header>
    <main><span class="badge">BÊTA · VOIX EN DIRECT</span>
      <h2>Parler à la maison</h2><p>Ta voix est transmise pendant le direct, sans enregistrer de message.</p>
      <section class="card"><label class="label" for="destination">Destination</label><select id="destination" aria-label="Destination" disabled><option>Chargement…</option></select>
      <section aria-label="Volumes des enceintes"><h3>Volume avant le message</h3><p style="font-size:13px">Réglages immédiats : ils modifient aussi le volume de la musique en cours.</p><div id="volumes"></div><p id="volume-feedback" role="status"></p></section>
      <p>Commence à parler après quelques secondes. Le délai dépend de la connexion et de l’enceinte.</p>
      <button id="speak" disabled>Démarrer le direct</button><div id="status" role="status" aria-live="polite">Vérification…</div><span id="timer"></span></section>
      <p id="resume-note" class="warn"></p><p class="warn">Le direct remplace la lecture en cours sur la destination. Arrêt automatique après 60 secondes et lorsque tu quittes cet écran. Aucun retour microphone depuis la pièce.</p>
      <button id="resume" hidden>Revenir à Spotify</button><p id="return-status" role="status"></p>
      <button id="test" disabled>Tester la liaison sans microphone</button>
      <details><summary>État technique</summary><p id="diagnostic">Chargement…</p></details>
      <footer><p>Accès par ton compte Home Assistant. Le microphone n’est demandé qu’au démarrage du direct.</p></footer>
    </main>`;
    this.$('menu').onclick=()=>this.dispatchEvent(new Event('hass-toggle-menu',{bubbles:true,composed:true}));
    this.$('speak').onclick=()=>this._busy||this._session?this.stop():this.start();
    this.$('test').onclick=()=>this.test();
    this.$('resume').onclick=async()=>{try{this.showReturn(await this.call('resume'));}catch(e){this.$('return-status').textContent=this.error(e);}};
    this._onVisibility=()=>{if(document.hidden)this.stop();};
    this._onHide=()=>this.stop();
    document.addEventListener('visibilitychange',this._onVisibility);
    window.addEventListener('pagehide',this._onHide);
    try {
      const info=await this.call('info');
      const select=this.$('destination');select.replaceChildren();
      for(const d of info.destinations){const option=document.createElement('option');option.value=d.id;option.textContent=d.name+(d.available?'':' — indisponible');option.disabled=!d.available;select.append(option);}
      select.value=info.destinations.find(d=>d.id===info.default_destination&&d.available)?.id||info.destinations.find(d=>d.available)?.id||'';select.disabled=false;
      this._destinations=info.destinations;this._groupDestination=info.group_destination;
      this._warmupDestinations=info.warmup_destinations||[];this._warmupSeconds=info.warmup_seconds||0;
      this.$('resume-note').textContent=info.auto_resume?'Reprise Spotify expérimentale activée pour la destination choisie.':'Reprise Spotify automatique désactivée. Relance la musique depuis Spotify après le direct.';
      select.onchange=()=>{this.message('Destination : '+select.selectedOptions[0].textContent);this.renderVolumes();};
      this.renderVolumes();
      this.$('speak').disabled=!window.isSecureContext||!navigator.mediaDevices?.getUserMedia;
      this.$('test').disabled=false;
      this.message(this.$('speak').disabled?'Microphone indisponible : ouvrir Home Assistant en HTTPS.':'Prêt pour un essai.');
      this.showDiagnostic(info.status);this.showReturn(info.spotify_return);
    } catch(e) { this.message(this.error(e)); }
  }
  $(id){return this.shadowRoot.getElementById(id);}
  call(action,data={}){return this._hass.callWS({type:`interphone_live/${action}`,...data});}
  error(e){return e?.message||String(e);}
  message(text){if(this.$('status'))this.$('status').textContent=text;}
  showDiagnostic(s){this.$('diagnostic').textContent=JSON.stringify(s||{},null,2);}
  showReturn(info){
    this.$('return-status').textContent=info?.message||'';
    this.$('resume').hidden=info?.status!=='failed';
  }
  async followReturn(){
    for(let n=0;n<20;n++){
      await new Promise(r=>setTimeout(r,1000));
      if(this._session||!this.isConnected)return;
      try{const info=await this.call('info');this.showReturn(info.spotify_return);
        if(!['pending','restoring'].includes(info.spotify_return?.status))return;
      }catch(e){return;}
    }
  }
  renderVolumes(){
    const host=this.$('volumes');if(!host||!this._destinations)return;
    host.replaceChildren();
    const chosen=this.$('destination').value;
    for(const d of this._destinations.filter(d=>chosen===this._groupDestination?d.id!==this._groupDestination:d.id===chosen)){
      const row=document.createElement('div');row.className='volume-row';row.dataset.entity=d.entity_id||'';
      const heading=document.createElement('div');heading.className='volume-heading';
      const name=document.createElement('span');name.textContent=d.name;
      const value=document.createElement('output');value.textContent='—';heading.append(name,value);
      const controls=document.createElement('div');controls.className='volume-controls';
      const range=document.createElement('input');range.type='range';range.min='0';range.max='100';range.step='1';range.setAttribute('aria-label','Volume '+d.name);
      const minus=document.createElement('button');minus.textContent='−';minus.setAttribute('aria-label','Baisser '+d.name);
      const plus=document.createElement('button');plus.textContent='+';plus.setAttribute('aria-label','Augmenter '+d.name);
      range.onpointerdown=()=>row.dataset.dragging='true';
      range.onpointerup=()=>delete row.dataset.dragging;
      range.onpointercancel=()=>{delete row.dataset.dragging;this.updateVolumes();};
      range.oninput=()=>{value.textContent=range.value+' %';};
      range.onchange=()=>this.setVolume(d,Number(range.value),row);
      minus.onclick=()=>this.setVolume(d,Number(range.value)-5,row);
      plus.onclick=()=>this.setVolume(d,Number(range.value)+5,row);
      controls.append(minus,range,plus);row.append(heading,controls);host.append(row);
    }
    this.updateVolumes();
  }
  updateVolumes(){
    const host=this.$('volumes');if(!host)return;
    for(const row of host.children){
      const state=this._hass?.states?.[row.dataset.entity];
      const level=state?.attributes?.volume_level;
      const known=state&&!['unavailable','unknown'].includes(state.state)&&typeof level==='number'&&Number.isFinite(level);
      for(const control of row.querySelectorAll('button,input'))control.disabled=!known||!!this._session||!!this._busy||row.dataset.sending==='true';
      if(row.dataset.dragging==='true'||row.dataset.sending==='true')continue;
      row.querySelector('input').value=known?Math.round(level*100):0;
      row.querySelector('output').textContent=known?Math.round(level*100)+' %'+(state.attributes.is_volume_muted?' · muet':''):'Indisponible';
    }
  }
  async setVolume(destination,percent,row){
    if(this._session||this._busy||!destination.entity_id||!Number.isFinite(percent))return;
    const level=Math.min(100,Math.max(0,percent))/100;
    row.dataset.sending='true';this.updateVolumes();
    try{
      await this._hass.callService('media_player','volume_set',{entity_id:destination.entity_id,volume_level:level});
      this.$('volume-feedback').textContent=destination.name+' : réglage envoyé ('+Math.round(level*100)+' %).';
    }catch(e){this.$('volume-feedback').textContent='Volume non modifié : '+this.error(e);}
    finally{delete row.dataset.sending;this.updateVolumes();}
  }
  async start(){
    const generation=++this._generation; this._busy=true;this.updateVolumes();
    this.$('destination').disabled=true;this.$('test').disabled=true; this.$('speak').textContent='Annuler'; this.message('Autorise le microphone de cet iPhone…');
    try {
      const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
      if(generation!==this._generation){stream.getTracks().forEach(t=>t.stop());return;}
      this._stream=stream;
      this._context=new AudioContext({sampleRate:16000});
      await this._context.resume();
      const blob=URL.createObjectURL(new Blob([captureWorklet],{type:'application/javascript'}));
      try{await this._context.audioWorklet.addModule(blob);}finally{URL.revokeObjectURL(blob);}
      if(generation!==this._generation)return;
      const result=await this.call('start',{destination:this.$('destination').value});
      if(generation!==this._generation){await this.call('stop',{session:result.session});return;}
      this._session=result.session; this._sequence=0; this._pending=0;
      const warmup=this._warmupDestinations.includes(this.$('destination').value)?this._warmupSeconds*1000:0;
      this._warmupUntil=Date.now()+warmup;
      this._source=this._context.createMediaStreamSource(stream);
      this._processor=new AudioWorkletNode(this._context,'interphone-capture');
      this._processor.port.onmessage=event=>this.sendPCM(event.data,generation);
      this._source.connect(this._processor);this._processor.connect(this._context.destination);
      this.$('speak').textContent='Arrêter le direct';this.$('speak').classList.add('live');
      this.message(warmup?'Préparation des enceintes : attends « Parle maintenant ».':'Microphone transmis — attends le démarrage de l’enceinte.');
      this._since=Date.now();
      this._timer=setInterval(()=>{const n=Math.floor((Date.now()-this._since)/1000);this.$('timer').textContent=`${n} / 60 s`;if(warmup){const left=Math.ceil((this._warmupUntil-Date.now())/1000);this.message(left>0?`Préparation : encore ${left} s — ne parle pas encore.`:'Parle maintenant — ta voix est transmise.');}if(n>=60)this.stop();},500);
      this._busy=false;
    }catch(e){await this.stop();this.message('Échec : '+this.error(e));}
  }
  sendPCM(buffer,generation){
    if(!this._session||generation!==this._generation)return;
    // 25 × 80 ms = 2 s of bounded acknowledgements in flight.
    // Mobile round-trip latency alone must not be mistaken for upload congestion.
    if(this._pending>=25){this.stop().then(()=>this.message('Connexion trop lente : direct arrêté pour éviter l’accumulation.'));return;}
    const bytes=new Uint8Array(buffer);
    if(Date.now()<this._warmupUntil)bytes.fill(0);
    let raw='';for(const n of bytes)raw+=String.fromCharCode(n);
    this._pending++;
    this.call('audio',{session:this._session,sequence:this._sequence++,pcm:btoa(raw)})
      .catch(e=>{if(generation===this._generation)this.stop().then(()=>this.message('Direct arrêté : '+this.error(e)));})
      .finally(()=>{if(generation===this._generation)this._pending=Math.max(0,this._pending-1);});
  }
  async stop(){
    ++this._generation;
    const session=this._session;this._session=null;this._busy=false;
    clearInterval(this._timer);
    if(this._processor){this._processor.port.onmessage=null;this._processor.disconnect();this._processor=null;}
    this._source?.disconnect();this._source=null;
    this._stream?.getTracks().forEach(t=>t.stop());this._stream=null;
    const context=this._context;this._context=null;if(context)await context.close().catch(()=>{});
    if(this.$('destination'))this.$('destination').disabled=false;
    if(this.$('speak')){this.$('speak').classList.remove('live');this.$('speak').textContent='Démarrer le direct';this.$('test').disabled=false;this.$('timer').textContent='';}
    this.updateVolumes();this.message('Microphone coupé. Le son déjà en mémoire peut finir de jouer.');
    if(session)try{this.showDiagnostic(await this.call('stop',{session}));this.followReturn();}catch(e){this.message('Microphone coupé ; arrêt serveur à vérifier.');}
  }
  async test(){
    this.$('destination').disabled=true;this.$('test').disabled=true;this.$('speak').disabled=true;
    this.message('Test silencieux de 8 secondes : aucun microphone utilisé.');
    try{
      const r=await this.call('start',{test:true,destination:this.$('destination').value});this._session=r.session;this.updateVolumes();
      this._timer=setTimeout(async()=>{
        try{
          const info=await this.call('info');this.showDiagnostic(info.status);
          this.message(info.status.audio_readers>0?'Liaison audio ouverte par Music Assistant. Reste à tester la voix sur l’iPhone.':info.status.error||'Flux envoyé, mais aucune lecture détectée. Diagnostic nécessaire.');
        }catch(e){this.message(this.error(e));}
        this._session=null;this.updateVolumes();this.$('destination').disabled=false;this.$('test').disabled=false;this.$('speak').disabled=!navigator.mediaDevices?.getUserMedia;
      },10000);
    }catch(e){this.$('destination').disabled=false;this.message(this.error(e));this.$('test').disabled=false;this.$('speak').disabled=false;}
  }
}
if(!customElements.get('interphone-live-panel'))customElements.define('interphone-live-panel',InterphoneLocalPanel);
