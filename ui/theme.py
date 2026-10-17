"""Chrome + neon-green industrial theme. Backgrounds are device-specific (media queries)."""
import streamlit as st

from core import store
from core.validators import safe_html


def inject(settings):
    try:
        m, d = store.asset_url("bg-mobile.jpg"), store.asset_url("bg-desktop.jpg")
    except Exception:
        m = d = None
    try:
        op = min(1.0, max(0.0, float(settings.get("overlay_opacity", 0.76))))
    except Exception:
        op = 0.76
    bgm = 'background-image:url("%s");' % safe_html(m) if m else ""
    bgd = 'background-image:url("%s");' % safe_html(d) if d else ""
    st.markdown("""<style>
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton, [data-testid="stStatusWidget"]{display:none !important}
header[data-testid="stHeader"]{background:transparent}
.stApp,[data-testid="stAppViewContainer"]{background-color:#0b1013;background-size:cover;background-position:center;background-repeat:no-repeat}
@media (max-width:768px){[data-testid="stAppViewContainer"]{%s}}
@media (min-width:769px){[data-testid="stAppViewContainer"]{%s}}
[data-testid="stAppViewContainer"]::before{content:"";position:fixed;inset:0;background:rgba(7,11,13,%.2f);pointer-events:none;z-index:0}
.block-container,[data-testid="stMainBlockContainer"]{max-width:720px;position:relative;z-index:1;background:rgba(36,44,48,.62);
 backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid rgba(200,210,215,.35);border-radius:14px;
 padding:1.2rem 1rem 6rem 1rem;margin-top:.8rem}
h1,h2,h3,h4{color:#39ff14 !important}
.stApp,.stMarkdown,label,p,span,li{color:#e8eef0}
.sq-head{display:flex;align-items:center;margin-bottom:.6rem}
.sq-title{font-size:1.5rem;font-weight:800;color:#39ff14;letter-spacing:.5px}
.sq-foot{text-align:center;font-size:.82rem;color:#9fb0b5;margin-top:1.5rem}
.sq-foot a{color:#39ff14}
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button,[data-testid^="stBaseLinkButton"],.stLinkButton a{
 background:linear-gradient(180deg,#2b3236,#11161a) !important;border:1px solid #8a979c !important;border-radius:10px !important;
 min-height:44px;font-weight:600;color:#39ff14 !important;transition:box-shadow .15s}
.stButton>button p,.stDownloadButton>button p,[data-testid="stFormSubmitButton"]>button p,.stLinkButton a p{color:#39ff14 !important}
.stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover,.stLinkButton a:hover{box-shadow:0 0 12px rgba(57,255,20,.6)}
.stButton>button:disabled,.stDownloadButton>button:disabled{background:#2a2f31 !important;border-color:#4a5356 !important;box-shadow:none !important}
.stButton>button:disabled p{color:#7b8487 !important}
[class*="st-key-del_"] button{border-color:#ff3b3b !important}
[class*="st-key-del_"] button p{color:#ff3b3b !important}
[class*="st-key-del_"] button:hover{box-shadow:0 0 12px rgba(255,59,59,.6) !important}
.st-key-basketbar{position:fixed;left:0;right:0;bottom:0;z-index:60;padding:8px 14px;background:rgba(10,14,16,.94);border-top:1px solid #39ff14}
.st-key-hp_wrap{position:absolute !important;left:-9999px;height:0;overflow:hidden}
.it{display:flex;gap:10px;align-items:center;margin:.4rem 0 .2rem 0}
.it img,.it .ph{width:72px;height:72px;min-width:72px;object-fit:contain;background:#fff;border-radius:8px}
.it .ph{display:flex;align-items:center;justify-content:center;background:#2a3236;color:#8a979c;font-size:.68rem;text-align:center}
.badge{display:inline-block;padding:1px 9px;border-radius:10px;font-size:.76rem;font-weight:700}
.badge.ok{background:#0f3d12;color:#39ff14;border:1px solid #39ff14}
.badge.wait{background:#3b2c05;color:#ffb300;border:1px solid #ffb300}
.crumb{font-size:.85rem;color:#9fb0b5;margin:.3rem 0}
</style>""" % (bgm, bgd, op), unsafe_allow_html=True)
