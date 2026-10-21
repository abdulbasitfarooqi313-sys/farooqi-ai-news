// فاروقی اے آئی نیوز — ہر خبر کے موضوع کا متحرک منظر (770×690، نیوی/سنہری/نیلا)
// data-a: "spin:<deg/s>[:cx:cy]" · "float:<px>:<phase>" · "pulse:<speed>" · "blink:<speed>" · "dash:<speed>"
(function(){
const G='#f0cf6a',G2='#d4a53d',B='#7cc4ff',B2='#3d7dff',N='#0a1550',W='#eef3ff';
const defs=`<defs>
<radialGradient id="bgR" cx="50%" cy="42%" r="70%"><stop offset="0" stop-color="#1f46b8"/><stop offset=".55" stop-color="#0e2272"/><stop offset="1" stop-color="#060d3c"/></radialGradient>
<linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe9a8"/><stop offset=".5" stop-color="${G}"/><stop offset="1" stop-color="#b8862c"/></linearGradient>
<linearGradient id="blue" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a9dcff"/><stop offset="1" stop-color="#2f6be8"/></linearGradient>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b3b9e"/><stop offset="1" stop-color="#0b1a5e"/></linearGradient>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="soft"><feGaussianBlur stdDeviation="2"/></filter></defs>`;
function grid(){let s='<g opacity=".28" stroke="'+B2+'" stroke-width="1.2">';
 for(let i=-8;i<=8;i++)s+=`<line x1="${385+i*48}" y1="470" x2="${385+i*150}" y2="690"/>`;
 for(let j=0;j<6;j++){const y=470+Math.pow(j/5,1.6)*220;s+=`<line x1="0" y1="${y.toFixed(0)}" x2="770" y2="${y.toFixed(0)}"/>`;}return s+'</g>';}
function stars(n,seed){let s='<g>';let r=seed||7;const rnd=()=>{r=(r*9301+49297)%233280;return r/233280;};
 for(let i=0;i<n;i++){const x=rnd()*770,y=rnd()*440,c=rnd()>.7?G:B;s+=`<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${(1.5+rnd()*2.5).toFixed(1)}" fill="${c}" data-a="blink:${(1+rnd()*2).toFixed(2)}:${(rnd()*6).toFixed(2)}"/>`;}return s+'</g>';}
function ring(cx,cy,r,sp,col){return `<g data-a="spin:${sp}:${cx}:${cy}"><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${col||B}" stroke-width="2.5" stroke-dasharray="26 14" opacity=".7"/></g>`;}
function orbit(cx,cy,r,sp,items){let s=`<g data-a="spin:${sp}:${cx}:${cy}">`;items.forEach((it,i)=>{const a=i/items.length*2*Math.PI,x=cx+r*Math.cos(a),y=cy+r*Math.sin(a);
 s+=`<g transform="translate(${x.toFixed(1)} ${y.toFixed(1)})"><g data-a="spin:${-sp}:0:0"><circle r="34" fill="${N}" stroke="${G}" stroke-width="2.5"/>${it}</g></g>`;});return s+'</g>';}
// چھوٹے آئیکن (مرکز 0,0)
const ic={
 bolt:`<path d="M-6-18 L-14 4 H-2 L-8 20 L14-6 H2 L8-18Z" fill="${G}"/>`,
 chat:`<path d="M-18-12h36v22h-20l-10 9v-9h-6z" fill="none" stroke="${B}" stroke-width="3" stroke-linejoin="round"/><circle cx="-8" cy="-1" r="2.5" fill="${G}"/><circle cx="0" cy="-1" r="2.5" fill="${G}"/><circle cx="8" cy="-1" r="2.5" fill="${G}"/>`,
 code:`<path d="M-8-10-18 0l10 10M8-10 18 0 8 10" fill="none" stroke="${B}" stroke-width="3.5" stroke-linecap="round"/>`,
 img:`<rect x="-17" y="-13" width="34" height="26" rx="4" fill="none" stroke="${B}" stroke-width="3"/><path d="M-13 9-3-2 4 5 8 1 13 9z" fill="${G}"/><circle cx="7" cy="-6" r="3" fill="${G}"/>`,
 mic:`<rect x="-6" y="-18" width="12" height="22" rx="6" fill="${G}"/><path d="M-12 0a12 12 0 0 0 24 0M0 12v7" fill="none" stroke="${B}" stroke-width="3"/>`,
 globe:`<circle r="16" fill="none" stroke="${B}" stroke-width="3"/><ellipse rx="7" ry="16" fill="none" stroke="${G}" stroke-width="2.5"/><path d="M-16 0h32" stroke="${G}" stroke-width="2.5"/>`,
 lock:`<rect x="-12" y="-3" width="24" height="18" rx="3" fill="${G}"/><path d="M-7-3v-6a7 7 0 0 1 14 0v6" fill="none" stroke="${B}" stroke-width="3.5"/>`,
 heart:`<path d="M0 14-14 0a8 8 0 0 1 14-10A8 8 0 0 1 14 0z" fill="${G}"/>`,
 coin:`<circle r="15" fill="url(#gold)"/><text y="6" text-anchor="middle" font-family="Arial" font-weight="700" font-size="17" fill="${N}">$</text>`,
 gear:`<g fill="none" stroke="${B}" stroke-width="3.5"><circle r="8"/><path d="M0-17v6M0 11v6M-17 0h6M11 0h6M-12-12l4 4M8 8l4 4M12-12l-4 4M-8 8l-4 4"/></g>`,
 cloud:`<path d="M-15 8a8 8 0 0 1 1-16 11 11 0 0 1 21-2 8 8 0 0 1 8 18z" fill="none" stroke="${B}" stroke-width="3"/>`,
 book:`<path d="M-17-11q9-4 17 1 8-5 17-1v22q-9-4-17 1-8-5-17-1z" fill="none" stroke="${G}" stroke-width="3" stroke-linejoin="round"/><path d="M0-10v21" stroke="${G}" stroke-width="2.5"/>`,
 chip:`<rect x="-11" y="-11" width="22" height="22" rx="3" fill="${G}"/><path d="M-6-17v6M0-17v6M6-17v6M-6 11v6M0 11v6M6 11v6M-17-6h6M-17 0h6M-17 6h6M11-6h6M11 0h6M11 6h6" stroke="${B}" stroke-width="2.5"/>`,
 wifi:`<path d="M-16-4a23 23 0 0 1 32 0M-10 3a14 14 0 0 1 20 0" fill="none" stroke="${B}" stroke-width="3.5" stroke-linecap="round"/><circle cy="11" r="3.5" fill="${G}"/>`,
};
// بڑے مرکزی منظر
const hero={
ai:`${ring(385,250,190,14)}${ring(385,250,150,-22,G)}
 <g filter="url(#glow)"><path d="M385 110c-70 0-118 46-118 104 0 28 10 50 26 66-6 24 2 48 26 56 6 22 30 34 54 28 4-1 8-3 12-6 4 3 8 5 12 6 24 6 48-6 54-28 24-8 32-32 26-56 16-16 26-38 26-66 0-58-48-104-118-104z" fill="url(#glass)" stroke="url(#gold)" stroke-width="5"/></g>
 <path d="M385 112v270" stroke="${G}" stroke-width="3" stroke-dasharray="8 7" data-a="dash:30"/>
 ${[[320,180],[350,240],[310,290],[360,320],[450,180],[420,240],[460,290],[410,320],[385,200]].map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="9" fill="${i%2?B:G}" data-a="pulse:${2+i%3}:${i}"/>`).join('')}
 <g stroke="${B}" stroke-width="2.5" fill="none" opacity=".85"><path d="M320 180 350 240 310 290 360 320 385 200 320 180M450 180 420 240 460 290 410 320 385 200 450 180M350 240 420 240"/></g>`,
robot:`${ring(385,250,190,12)}
 <g data-a="float:10:0"><rect x="365" y="78" width="40" height="10" rx="5" fill="${G}"/><circle cx="385" cy="70" r="13" fill="${G}" data-a="pulse:3:0" filter="url(#glow)"/><path d="M385 82v28" stroke="${G}" stroke-width="6"/>
 <rect x="275" y="110" width="220" height="170" rx="46" fill="url(#glass)" stroke="url(#gold)" stroke-width="6"/>
 <rect x="303" y="150" width="164" height="78" rx="34" fill="#061040" stroke="${B}" stroke-width="3"/>
 <ellipse cx="345" cy="189" rx="18" ry="20" fill="${B}" filter="url(#glow)" data-a="blink:0.35:0"/><ellipse cx="425" cy="189" rx="18" ry="20" fill="${B}" filter="url(#glow)" data-a="blink:0.35:0"/>
 <path d="M345 252q40 18 80 0" fill="none" stroke="${G}" stroke-width="6" stroke-linecap="round"/>
 <rect x="258" y="170" width="20" height="56" rx="8" fill="${G}"/><rect x="492" y="170" width="20" height="56" rx="8" fill="${G}"/>
 <rect x="310" y="292" width="150" height="110" rx="30" fill="url(#glass)" stroke="url(#gold)" stroke-width="5"/>
 <circle cx="385" cy="345" r="22" fill="none" stroke="${B}" stroke-width="5"/><circle cx="385" cy="345" r="9" fill="${G}" data-a="pulse:2:1"/></g>`,
chip:`<g data-a="dash:-40">${[...Array(12)].map((_,i)=>{const a=i/12*6.283,x=385+300*Math.cos(a),y=250+190*Math.sin(a);return `<path d="M385 250L${x.toFixed(0)} ${y.toFixed(0)}" stroke="${i%2?G:B}" stroke-width="3" stroke-dasharray="14 18" opacity=".7"/>`;}).join('')}</g>
 <g filter="url(#glow)"><rect x="265" y="130" width="240" height="240" rx="26" fill="url(#glass)" stroke="url(#gold)" stroke-width="6"/></g>
 ${[...Array(7)].map((_,i)=>{const o=155+i*30;return `<rect x="${o-6}" y="98" width="12" height="32" rx="4" fill="${G}"/><rect x="${o-6}" y="370" width="12" height="32" rx="4" fill="${G}"/><rect x="233" y="${o-6}" width="32" height="12" rx="4" fill="${G}"/><rect x="505" y="${o-6}" width="32" height="12" rx="4" fill="${G}"/>`;}).join('')}
 <rect x="315" y="180" width="140" height="140" rx="12" fill="#061040" stroke="${B}" stroke-width="3"/>
 <text x="385" y="268" text-anchor="middle" font-family="Arial" font-weight="800" font-size="62" fill="url(#gold)" data-a="pulse:1.5:0">AI</text>`,
phone:`${ring(385,250,200,10)}
 <g data-a="float:8:0"><rect x="290" y="70" width="190" height="370" rx="34" fill="#050b33" stroke="url(#gold)" stroke-width="7"/>
 <rect x="306" y="96" width="158" height="318" rx="18" fill="url(#glass)"/><rect x="360" y="80" width="50" height="8" rx="4" fill="${G2}"/>
 ${[0,1,2].map(r=>[0,1,2].map(c=>`<rect x="${322+c*48}" y="${120+r*52}" width="36" height="36" rx="10" fill="${(r+c)%2?B2:G2}" opacity=".9" data-a="pulse:${1.5+((r*3+c)%4)*.4}:${r*3+c}"/>`).join('')).join('')}
 <rect x="322" y="290" width="126" height="40" rx="20" fill="#061040" stroke="${B}" stroke-width="2.5"/><circle cx="342" cy="310" r="9" fill="${G}" data-a="pulse:2:2"/>
 <rect x="358" y="306" width="74" height="8" rx="4" fill="${B}" opacity=".7"/><rect x="322" y="345" width="126" height="44" rx="12" fill="${G}" opacity=".18"/></g>`,
health:`${ring(385,250,190,-10,G)}
 <g filter="url(#glow)"><path d="M385 380 250 245a78 78 0 0 1 135-100 78 78 0 0 1 135 100z" fill="url(#glass)" stroke="url(#gold)" stroke-width="6" data-a="beat:1.1"/></g>
 <path d="M220 260h90l22-50 30 100 26-80 18 30h144" fill="none" stroke="${B}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="40 1000" data-a="dash:-260" filter="url(#glow)"/>
 <path d="M220 260h90l22-50 30 100 26-80 18 30h144" fill="none" stroke="${B}" stroke-width="3" opacity=".35"/>
 <rect x="370" y="160" width="30" height="80" rx="6" fill="${G}"/><rect x="345" y="185" width="80" height="30" rx="6" fill="${G}"/>`,
car:`${grid()}<g data-a="dash:-120"><path d="M385 470 385 690" stroke="${G}" stroke-width="8" stroke-dasharray="40 40"/></g>
 <g data-a="float:4:0"><path d="M200 350q10-70 70-90l40-50q20-22 60-22h90q38 0 60 22l50 50q60 20 70 90v40H200z" fill="url(#glass)" stroke="url(#gold)" stroke-width="6" stroke-linejoin="round"/>
 <path d="M315 220h65v50h-110zM400 220h55q18 0 30 14l30 36h-115z" fill="#061040" stroke="${B}" stroke-width="3"/>
 <circle cx="290" cy="392" r="40" fill="#050b33" stroke="${G}" stroke-width="7"/><circle cx="480" cy="392" r="40" fill="#050b33" stroke="${G}" stroke-width="7"/>
 <g data-a="spin:200:290:392"><path d="M290 362v60M260 392h60" stroke="${B}" stroke-width="4"/></g><g data-a="spin:200:480:392"><path d="M480 362v60M450 392h60" stroke="${B}" stroke-width="4"/></g>
 <ellipse cx="560" cy="330" rx="16" ry="10" fill="${B}" filter="url(#glow)" data-a="pulse:1.2:0"/></g>
 <g opacity=".75" data-a="spin:30:385:300"><circle cx="385" cy="300" r="250" fill="none" stroke="${B}" stroke-width="2" stroke-dasharray="4 22"/></g>`,
space:`${stars(60,3)}<circle cx="560" cy="150" r="70" fill="url(#blue)" opacity=".85"/><ellipse cx="560" cy="150" rx="115" ry="24" fill="none" stroke="${G}" stroke-width="4" transform="rotate(-18 560 150)"/>
 <g data-a="float:14:0"><g transform="rotate(35 330 280)"><path d="M330 120q46 50 46 150v70h-92v-70q0-100 46-150z" fill="url(#glass)" stroke="url(#gold)" stroke-width="6"/>
 <circle cx="330" cy="215" r="24" fill="#061040" stroke="${B}" stroke-width="5"/><path d="M284 300l-36 50h36zM376 300l36 50h-36z" fill="${G}"/>
 <path d="M300 340q30 90 60 0" fill="${G}" filter="url(#glow)" data-a="flame:8"/><path d="M314 340q16 50 32 0" fill="#fff8d8"/></g></g>`,
finance:`${grid()}
 ${[0,1,2,3,4,5].map(i=>{const h=[90,140,120,190,170,250][i];return `<rect x="${170+i*75}" y="${430-h}" width="48" height="${h}" rx="6" fill="${i%2?'url(#blue)':'url(#gold)'}" opacity=".9" data-a="grow:${1.4}:${i*0.15}"/>`;}).join('')}
 <path d="M170 360 260 300 330 320 410 230 490 250 600 140" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
 <path d="M575 130h40v40" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
 <g data-a="float:10:1"><circle cx="150" cy="140" r="38" fill="url(#gold)"/><text x="150" y="155" text-anchor="middle" font-family="Arial" font-weight="800" font-size="42" fill="${N}">$</text></g>`,
security:`${ring(385,240,190,16)}${ring(385,240,150,-24,G)}
 <g filter="url(#glow)"><path d="M385 80 520 130v90c0 90-60 150-135 180-75-30-135-90-135-180v-90z" fill="url(#glass)" stroke="url(#gold)" stroke-width="7"/></g>
 <rect x="335" y="225" width="100" height="80" rx="12" fill="${G}"/><path d="M355 225v-30a30 30 0 0 1 60 0v30" fill="none" stroke="${B}" stroke-width="10"/>
 <circle cx="385" cy="258" r="10" fill="${N}"/><rect x="380" y="262" width="10" height="24" rx="4" fill="${N}"/>
 <g font-family="monospace" font-size="20" fill="${B}" opacity=".55">${[...Array(8)].map((_,i)=>`<text x="${60+i*90}" y="${80+(i%3)*30}" data-a="fall:${40+i*7}:${i*40}">${(i*37%2)?'1011':'0110'}</text>`).join('')}</g>`,
education:`${ring(385,260,190,10,G)}
 <g data-a="float:8:0"><path d="M385 130 560 200 385 270 210 200z" fill="url(#gold)" stroke="#b8862c" stroke-width="3"/>
 <path d="M280 230v70q105 50 210 0v-70l-105 42z" fill="url(#glass)" stroke="url(#gold)" stroke-width="5"/>
 <path d="M540 208v80" stroke="${G}" stroke-width="5"/><circle cx="540" cy="296" r="11" fill="${G}" data-a="pulse:2:0"/></g>
 <path d="M240 400q72-30 145 6 73-36 145-6v-60q-72-30-145 6-73-36-145-6z" fill="url(#glass)" stroke="${B}" stroke-width="5" stroke-linejoin="round"/><path d="M385 346v60" stroke="${B}" stroke-width="4"/>`,
law:`${ring(385,250,200,8,G)}
 <path d="M385 100v300M305 410h160" stroke="url(#gold)" stroke-width="12" stroke-linecap="round"/><circle cx="385" cy="96" r="16" fill="${G}"/>
 <g data-a="tilt:6:385:150"><path d="M225 150h320" stroke="url(#gold)" stroke-width="10" stroke-linecap="round"/>
 <path d="M245 150 205 260M245 150l40 110M525 150l-40 110M525 150l40 110" stroke="${B}" stroke-width="3"/>
 <path d="M190 260h110a55 30 0 0 1-110 0zM470 260h110a55 30 0 0 1-110 0z" fill="url(#gold)"/>
 <g transform="translate(245 236) scale(.8)">${ic.chip}</g><g transform="translate(525 236) scale(.8)">${ic.book}</g></g>`,
data:`${grid()}
 ${[0,1,2].map(i=>`<g transform="translate(${200+i*130} ${150+Math.abs(i-1)*30})"><rect width="110" height="${260-Math.abs(i-1)*30}" rx="10" fill="url(#glass)" stroke="url(#gold)" stroke-width="4"/>
 ${[0,1,2,3,4].map(r=>`<rect x="14" y="${18+r*44}" width="82" height="30" rx="5" fill="#061040" stroke="${B2}" stroke-width="2"/><circle cx="30" cy="${33+r*44}" r="5" fill="${(r+i)%2?G:B}" data-a="blink:${.6+((r+i)%3)*.3}:${r+i}"/><rect x="44" y="${30+r*44}" width="40" height="6" rx="3" fill="${B}" opacity=".6"/>`).join('')}</g>`).join('')}
 <g data-a="float:10:0"><path d="M300 110a42 42 0 0 1 4-84 58 58 0 0 1 112-10 42 42 0 0 1 52 94z" fill="url(#glass)" stroke="${B}" stroke-width="5" filter="url(#glow)"/></g>`,
media:`${ring(385,250,200,-12)}
 <g data-a="float:8:0"><rect x="215" y="120" width="340" height="230" rx="22" fill="url(#glass)" stroke="url(#gold)" stroke-width="6"/>
 <path d="M240 320 330 220 400 290 450 245 530 320z" fill="url(#blue)" opacity=".9"/><circle cx="480" cy="180" r="26" fill="${G}" filter="url(#glow)" data-a="pulse:2:0"/>
 <circle cx="385" cy="235" r="44" fill="rgba(5,11,51,.6)" stroke="${G}" stroke-width="5"/><path d="M372 212v46l38-23z" fill="${G}"/></g>
 <g data-a="spin:25:560:390"><path d="M560 340l12 36 38 0-31 22 12 36-31-22-31 22 12-36-31-22h38z" fill="${G}" opacity=".9"/></g>`,
};
const sats={ai:[ic.chat,ic.code,ic.img,ic.mic,ic.globe,ic.bolt],robot:[ic.gear,ic.chip,ic.bolt,ic.wifi,ic.code,ic.chat],chip:[],phone:[ic.wifi,ic.chat,ic.img,ic.mic],
 health:[ic.heart,ic.chip,ic.gear,ic.globe],car:[],space:[],finance:[ic.coin,ic.globe,ic.chip],security:[],education:[ic.book,ic.chat,ic.globe,ic.code],
 law:[ic.globe,ic.book],data:[],media:[ic.img,ic.mic,ic.chat,ic.code]};
window.NF_TOPICS=Object.keys(hero);
window.nfScene=function(topic){topic=hero[topic]?topic:'ai';const s=sats[topic]||[];
 return `<svg viewBox="0 0 770 690" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">${defs}
 <rect width="770" height="690" fill="url(#bgR)"/>${topic==='space'?'':stars(26,topic.length*13)}<g transform="translate(0 70)">${hero[topic]}${s.length?orbit(385,250,290,9,s):''}</g>
 <rect width="770" height="690" fill="url(#vig)" opacity="0"/></svg>`;};
window.nfAnimate=function(root,t){root.querySelectorAll('[data-a]').forEach(e=>{const p=e.dataset.a.split(':'),k=p[0],v=+p[1];
 if(k==='spin'){const cx=p[2]||0,cy=p[3]||0;e.setAttribute('transform',`rotate(${(v*t%360).toFixed(2)} ${cx} ${cy})`);}
 else if(k==='float'){e.setAttribute('transform',`translate(0 ${(v*Math.sin(t*1.6+(+p[2]||0))).toFixed(2)})`);}
 else if(k==='pulse'){e.setAttribute('opacity',(.55+.45*Math.sin(t*v+(+p[2]||0))).toFixed(2));}
 else if(k==='blink'){const c=(t*v+(+p[2]||0))%3;e.setAttribute('opacity',c<.12?.1:1);}
 else if(k==='dash'){e.setAttribute('stroke-dashoffset',(v*t).toFixed(1));}
 else if(k==='beat'){const b=Math.pow(Math.max(0,Math.sin(t*Math.PI*2/v)),8);e.setAttribute('transform',`translate(385 250) scale(${(1+.06*b).toFixed(3)}) translate(-385 -250)`);}
 else if(k==='flame'){e.setAttribute('transform',`translate(330 340) scale(1 ${(1+.25*Math.sin(t*v)).toFixed(3)}) translate(-330 -340)`);}
 else if(k==='grow'){const g=Math.min(1,Math.max(0,(t-(+p[2]||0))/v));const s=1-Math.pow(1-g,3);e.setAttribute('transform',`translate(0 430) scale(1 ${s.toFixed(3)}) translate(0 -430)`);}
 else if(k==='tilt'){e.setAttribute('transform',`rotate(${(v*Math.sin(t*1.3)).toFixed(2)} ${p[2]} ${p[3]})`);}
 else if(k==='fall'){e.setAttribute('transform',`translate(0 ${((v*t+(+p[2]||0))%520).toFixed(1)})`);}
 });};
})();
