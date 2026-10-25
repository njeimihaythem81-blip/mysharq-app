"""Chrome + neon-green industrial theme. Backgrounds are device-specific (media queries)."""
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
    import streamlit as st
    st.markdown(build_css(bgm, bgd, op), unsafe_allow_html=True)


def build_css(bgm, bgd, op):
    """Pure function (no Streamlit): the whole stylesheet. Uses tokens, NOT % formatting, because the CSS has literal % signs."""
    css = """<style>
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton, [data-testid="stStatusWidget"]{display:none !important}
header[data-testid="stHeader"]{background:transparent}
.stApp,[data-testid="stAppViewContainer"]{background-color:#0b1013;background-size:cover;background-position:center;background-repeat:no-repeat}
@media (max-width:768px){[data-testid="stAppViewContainer"]{__BGM__}}
@media (min-width:769px){[data-testid="stAppViewContainer"]{__BGD__}}
[data-testid="stAppViewContainer"]::before{content:"";position:fixed;inset:0;background:rgba(7,11,13,__OP__);pointer-events:none;z-index:0}
.block-container,[data-testid="stMainBlockContainer"]{max-width:720px;position:relative;z-index:1;background:rgba(36,44,48,.62);
 backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid rgba(200,210,215,.35);border-radius:14px;
 padding:1.2rem 1rem 2.5rem 1rem;margin-top:.8rem}
h1,h2,h3,h4{color:#39ff14 !important}
.stApp,.stMarkdown,label,p,span,li{color:#e8eef0}
.sq-head{display:flex;align-items:center;margin-bottom:.6rem}
.sq-title{font-size:1.5rem;font-weight:800;color:#39ff14;letter-spacing:.5px}
.sq-foot{text-align:center;font-size:.82rem;color:#9fb0b5;margin-top:1.5rem}
.sq-foot a{color:#39ff14}
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button,[data-testid^="stBaseLinkButton"],.stLinkButton a{
 background:linear-gradient(180deg,#b4bcc0 0%,#7b858a 46%,#566066 54%,#8a949a 100%) !important;border:1px solid #d3dade !important;border-radius:10px !important;
 min-height:44px;font-weight:700;color:#39ff14 !important;transition:box-shadow .15s;box-shadow:inset 0 1px 0 rgba(255,255,255,.55),0 1px 3px rgba(0,0,0,.45)}
.stButton>button p,.stButton>button span,.stDownloadButton>button p,.stDownloadButton>button span,[data-testid="stFormSubmitButton"]>button p,.stLinkButton a p,.stLinkButton a span{
 color:#39ff14 !important;text-shadow:0 0 1px #000,0 0 2px #000,0 1px 2px rgba(0,0,0,.85)}
.stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover,.stLinkButton a:hover{box-shadow:0 0 12px rgba(57,255,20,.75),inset 0 1px 0 rgba(255,255,255,.55) !important}
.stButton>button:disabled,.stDownloadButton>button:disabled{background:linear-gradient(180deg,#6f777b,#4a5155) !important;border-color:#8a949a !important;box-shadow:none !important}
.stButton>button:disabled p,.stButton>button:disabled span{color:#9aa5a0 !important;text-shadow:none}
[class*="st-key-del_"] button{border-color:#ff3b3b !important}
[class*="st-key-del_"] button p{color:#ff3b3b !important}
[class*="st-key-del_"] button:hover{box-shadow:0 0 12px rgba(255,59,59,.6) !important}
.st-key-basketbar{position:sticky;top:.5rem;z-index:100;display:flex !important;flex-direction:column;align-items:flex-end;background:none;border:none;padding:0 0 .3rem 0;margin:0}
.st-key-basketbar button{min-height:42px;padding:.2rem .9rem}
.st-key-hp_wrap{position:absolute !important;left:-9999px;height:0;overflow:hidden}
.it{display:flex;gap:10px;align-items:center;margin:.4rem 0 .2rem 0}
.it img,.it .ph{width:72px;height:72px;min-width:72px;object-fit:contain;background:#fff;border-radius:8px}
.it .ph{display:flex;align-items:center;justify-content:center;background:#2a3236;color:#8a979c;font-size:.68rem;text-align:center}
.badge{display:inline-block;padding:1px 9px;border-radius:10px;font-size:.76rem;font-weight:700}
.badge.ok{background:#0f3d12;color:#39ff14;border:1px solid #39ff14}
.badge.wait{background:#3b2c05;color:#ffb300;border:1px solid #ffb300}
.crumb{font-size:.85rem;color:#9fb0b5;margin:.3rem 0}
.st-key-tilegrid{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}
@media (min-width:769px){.st-key-tilegrid{grid-template-columns:repeat(4,minmax(0,1fr))}}
[class*="st-key-tile_"]{position:relative;background:rgba(20,26,29,.55);border:1px solid rgba(200,210,215,.3);border-radius:12px;padding:6px;gap:.35rem !important}
[class*="st-key-tile_"] [data-testid="stMarkdownContainer"] p{margin:0}
.timg{aspect-ratio:1/1;background:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.timg img{width:100%;height:100%;object-fit:contain}
.tph{width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#2a3236;color:#8a979c;font-size:2.2rem;font-weight:800}
[class*="st-key-tbtn_"] button{min-height:44px;height:auto;white-space:normal;line-height:1.2;padding:.4rem .3rem}
[class*="st-key-tbtn_"] button::after{content:"";position:absolute;inset:0;border-radius:12px}
</style>"""
    return css.replace("__BGM__", bgm).replace("__BGD__", bgd).replace("__OP__", "%.2f" % op)
