"""دو اینکر (ڈیجیٹل آرٹ، SVG): مرد — سوٹ اور داڑھی، ہونٹ آواز کے ساتھ ہلتے ہیں؛
خاتون — مکمل سیاہ عبایا، حجاب اور نقاب، چہرہ ڈھکا، صرف آنکھیں (پلکیں جھپکتی ہیں)۔
دونوں ایک ہی نیوز ڈیسک پر۔ ہر کیفیت (منہ بند/کھلا، آنکھیں کھلی/بند) کی الگ شفاف تصویر بنتی ہے۔
"""
from __future__ import annotations

AW, AH = 700, 730   # اینکر کی تصویر کا سائز (اسکرین کے بائیں حصے میں)

DEFS = """
<defs>
 <linearGradient id="suit" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22355f"/><stop offset="1" stop-color="#121d38"/></linearGradient>
 <linearGradient id="abaya" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c1d24"/><stop offset="1" stop-color="#08090d"/></linearGradient>
 <linearGradient id="desk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d4fbf"/><stop offset=".08" stop-color="#0d2a73"/><stop offset="1" stop-color="#06143d"/></linearGradient>
 <linearGradient id="deskTop" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#5fb6ff"/><stop offset=".5" stop-color="#bfe6ff"/><stop offset="1" stop-color="#5fb6ff"/></linearGradient>
 <radialGradient id="skin" cx=".45" cy=".4" r=".7"><stop offset="0" stop-color="#d7a07c"/><stop offset="1" stop-color="#b47a56"/></radialGradient>
 <radialGradient id="glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="rgba(60,150,255,.35)"/><stop offset="1" stop-color="rgba(60,150,255,0)"/></radialGradient>
</defs>"""


def _desk(logo: str) -> str:
    img = f'<image href="{logo}" x="300" y="636" width="100" height="100" clip-path="circle(48px at 50px 50px)"/>' if logo else ""
    return ('<ellipse cx="350" cy="560" rx="330" ry="140" fill="url(#glow)"/>'
            '<path d="M20 600 L680 600 L700 730 L0 730 Z" fill="url(#desk)"/>'
            '<rect x="20" y="596" width="660" height="8" rx="4" fill="url(#deskTop)"/>'
            '<rect x="60" y="640" width="580" height="3" fill="rgba(140,200,255,.35)"/>' + img)


def _eyes(cx: int, cy: int, blink: bool, lid: str = "#5a3a2a") -> str:
    out = []
    for dx in (-38, 38):
        x = cx + dx
        if blink:
            out.append(f'<path d="M{x-18} {cy} Q{x} {cy+6} {x+18} {cy}" stroke="{lid}" stroke-width="4" fill="none" stroke-linecap="round"/>')
        else:
            out.append(f'<ellipse cx="{x}" cy="{cy}" rx="18" ry="11" fill="#fff"/>'
                       f'<circle cx="{x}" cy="{cy+1}" r="8" fill="#3b2416"/><circle cx="{x}" cy="{cy+1}" r="4" fill="#0b0705"/>'
                       f'<circle cx="{x+3}" cy="{cy-3}" r="2.2" fill="#fff"/>'
                       f'<path d="M{x-19} {cy-2} Q{x} {cy-15} {x+19} {cy-2}" stroke="{lid}" stroke-width="3" fill="none"/>')
    return "".join(out)


def male(mouth: int = 0, blink: bool = False, logo: str = "") -> str:
    """mouth: 0 بند، 1 تھوڑا کھلا، 2 کھلا"""
    m = {0: '<path d="M326 392 Q350 398 374 392" stroke="#5b2a20" stroke-width="5" fill="none" stroke-linecap="round"/>',
         1: '<ellipse cx="350" cy="394" rx="21" ry="8" fill="#4a1a14"/><rect x="333" y="387" width="34" height="4" rx="2" fill="#f4efe8"/>',
         2: '<ellipse cx="350" cy="398" rx="23" ry="15" fill="#3e140f"/><rect x="332" y="385" width="36" height="5" rx="2" fill="#f4efe8"/>'
            '<ellipse cx="350" cy="407" rx="13" ry="5" fill="#b4504a"/>'}[mouth]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {AW} {AH}" width="{AW}" height="{AH}">{DEFS}
 <path d="M120 640 Q130 470 250 440 L450 440 Q570 470 580 640 Z" fill="url(#suit)"/>
 <path d="M300 440 L350 560 L400 440 Z" fill="#f2f4f8"/>
 <path d="M338 452 L362 452 L370 545 L350 575 L330 545 Z" fill="#9b1c2a"/><path d="M338 452 L362 452 L356 470 L344 470 Z" fill="#7a1220"/>
 <path d="M250 440 L300 440 L350 600 L285 520 Z" fill="#1a2a4c"/><path d="M450 440 L400 440 L350 600 L415 520 Z" fill="#1a2a4c"/>
 <rect x="318" y="395" width="64" height="58" fill="#a8704e"/>
 <ellipse cx="252" cy="310" rx="16" ry="28" fill="url(#skin)"/><ellipse cx="448" cy="310" rx="16" ry="28" fill="url(#skin)"/>
 <ellipse cx="350" cy="300" rx="98" ry="122" fill="url(#skin)"/>
 <path d="M252 300 Q248 170 350 168 Q452 170 448 300 Q440 230 400 215 Q350 205 300 215 Q258 232 252 300 Z" fill="#17110d"/>
 <path d="M256 320 Q262 420 350 438 Q438 420 444 320 Q430 380 400 392 Q375 372 350 374 Q325 372 300 392 Q270 380 256 320 Z" fill="#1d1510"/>
 <path d="M312 368 Q350 352 388 368 Q370 376 350 372 Q330 376 312 368 Z" fill="#1d1510"/>
 {m}
 <path d="M290 262 Q312 250 334 260" stroke="#1d1510" stroke-width="7" fill="none" stroke-linecap="round"/>
 <path d="M366 260 Q388 250 410 262" stroke="#1d1510" stroke-width="7" fill="none" stroke-linecap="round"/>
 {_eyes(350, 290, blink)}
 <path d="M350 300 Q343 335 336 345 Q350 352 364 345" stroke="#8d5a3d" stroke-width="3.5" fill="none" stroke-linecap="round"/>
 <path d="M150 640 Q165 600 215 592 L275 600 L270 640 Z" fill="url(#suit)"/><path d="M550 640 Q535 600 485 592 L425 600 L430 640 Z" fill="url(#suit)"/>
 <ellipse cx="300" cy="600" rx="38" ry="18" fill="url(#skin)"/><ellipse cx="400" cy="600" rx="38" ry="18" fill="url(#skin)"/>
 {_desk(logo)}
</svg>'''


def female(blink: bool = False, logo: str = "") -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {AW} {AH}" width="{AW}" height="{AH}">{DEFS}
 <path d="M110 640 Q118 455 250 425 L450 425 Q582 455 590 640 Z" fill="url(#abaya)"/>
 <path d="M235 470 Q350 520 465 470" stroke="#2a2c36" stroke-width="3" fill="none"/>
 <path d="M240 440 Q230 300 260 230 Q300 160 350 158 Q400 160 440 230 Q470 300 460 440 Q420 470 350 472 Q280 470 240 440 Z" fill="url(#abaya)"/>
 <path d="M262 300 Q262 250 300 228 Q350 205 400 228 Q438 250 438 300 Z" fill="#14151b"/>
 <rect x="276" y="272" width="148" height="40" rx="18" fill="#c99877"/>
 {_eyes(350, 292, blink, lid="#3a241a")}
 <path d="M270 300 L430 300 L428 312 L272 312 Z" fill="#101117"/>
 <path d="M266 306 Q350 300 434 306 Q446 380 420 430 Q350 452 280 430 Q254 380 266 306 Z" fill="#0d0e13"/>
 <path d="M282 330 Q350 340 418 330" stroke="#22242d" stroke-width="2" fill="none"/>
 <path d="M140 640 Q155 598 210 590 L280 598 L276 640 Z" fill="url(#abaya)"/><path d="M560 640 Q545 598 490 590 L420 598 L424 640 Z" fill="url(#abaya)"/>
 <ellipse cx="300" cy="600" rx="36" ry="17" fill="#c99877"/><ellipse cx="400" cy="600" rx="36" ry="17" fill="#c99877"/>
 <rect x="262" y="590" width="20" height="22" rx="6" fill="#0d0e13"/><rect x="418" y="590" width="20" height="22" rx="6" fill="#0d0e13"/>
 {_desk(logo)}
</svg>'''
