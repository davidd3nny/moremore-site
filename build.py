#!/usr/bin/env python3
"""
Сборка сайта More&More.

Берёт содержимое из content/ (меню, данные заведения, афиша), шаблон src/page.html и стили src/style.css,
шрифты и логотип из assets/, картинки афиши из afisha/. Готовый сайт кладёт в dist/.

Запуск на компьютере:  python3 build.py        (Python 3.9+ и пакеты: pip3 install --user pillow tomli)
На GitHub то же самое делает робот (Actions) после каждой правки и раз в сутки, в начале дня по Баку.
"""
import base64, datetime, html, json, pathlib, re, shutil, sys, urllib.parse
try:
    import tomllib                    # Python 3.11 и новее
except ModuleNotFoundError:           # системный Python 3.9 на Mac: pip3 install --user tomli pillow
    import tomli as tomllib

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"
BAKU = datetime.timezone(datetime.timedelta(hours=4))
LANGS = ("az", "ru", "en")


class ContentError(Exception):
    """Ошибка в файлах content/: сообщение понятное человеку, без трассировки."""


def load(name):
    path = ROOT / "content" / name
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ContentError("Ошибка в файле content/%s: %s. Проверьте кавычки, запятые и скобки в этом месте." % (name, e))


def T(s, where="текст"):
    """«AZ | RU | EN» → словарь по языкам. Строка без « | » годится для всех трёх."""
    parts = [x.strip() for x in str(s).split("|")]
    if len(parts) == 1:
        parts = parts * 3
    if len(parts) != 3:
        raise ContentError("%s: нужно три языка через « | » (AZ | RU | EN) или одна строка: %s" % (where, s))
    return dict(zip(LANGS, parts))


# ------------------------------------------------------------------ подписи интерфейса
UI = {k: T(v) for k, v in {
    "tag": "Dəniz məhsulları restoranı | Ресторан морепродуктов | Seafood restaurant",
    "menu": "Menyu | Меню | Menu",
    "book": "Masa sifariş et | Забронировать стол | Book a table",
    "route": "Yol | Как добраться | Directions",
    "bar": "Bar | Бар | Bar",
    "contacts": "Əlaqə | Контакты | Contacts",
    "kitchen": "Mətbəx | Кухня | Kitchen",
    "signature": "Müəllif kokteylləri | Авторские коктейли | Signature cocktails",
    "classic": "Klassik kokteyllər | Классические коктейли | Classic cocktails",
    "noalc": "Alkoqolsuz | Без алкоголя | Alcohol-free",
    "lemonade": "Limonadlar | Лимонады | Lemonades",
    "tea": "Çay | Чай | Tea",
    "coffee": "Qəhvə | Кофе | Coffee",
    "coffeeTea": "Qəhvə və çay | Кофе и чай | Coffee & tea",
    "soft": "Su, şirə, sərinləşdirici | Вода, соки, напитки | Water, juices, soft drinks",
    "spirits": "Spirtli içkilər | Крепкие напитки | Spirits",
    "bottleShot": "şüşə / porsiya | бутылка / порция | bottle / serving",
    "hookah": "Qəlyan | Кальян | Hookah",
    "hours": "İş saatları | Часы работы | Opening hours",
    "address": "Ünvan | Адрес | Address",
    "call": "Zəng et | Позвонить | Call",
    "openMap": "Google Maps-də aç | Открыть в Google Maps | Open in Google Maps",
    "waText": "Salam! More&More-da masa sifariş etmək istəyirəm. | Здравствуйте! Хочу забронировать стол в More&More. | Hello! I’d like to book a table at More&More.",
    "waEvent": "Salam! «%s» üçün masa sifariş etmək istəyirəm. | Здравствуйте! Хочу забронировать стол на «%s». | Hello! I’d like to book a table for “%s”.",
    "service": "Qiymətlər manatla | Цены в манатах | Prices in manat",
    "draft": "Konsept · qaralama | Концепт · черновик | Concept · draft",
    "concept": "Konsept sayt, qaralama. Menyu və qiymətlər More&More-un monyo.az səhifəsindən götürülüb. | Концепт сайта, черновик. Меню и цены взяты со страницы More&More на monyo.az. | Website concept, draft. Menu and prices come from More&More’s page on monyo.az.",
    "credit": "Dizayn: David Izmailov | Дизайн: David Izmailov | Design: David Izmailov",
    "open": "İndi açıqdır | Сейчас открыто | Open now",
    "closed": "İndi bağlıdır | Сейчас закрыто | Closed now",
    "lang": "Dil | Язык | Language",
    "afisha": "Afişa | Афиша | What’s on",
    "afKick": "Tezliklə More&More-da | Скоро в More&More | Coming up at More&More",
    "close": "Bağla | Закрыть | Close",
    "more": "Ətraflı | Подробнее | Details",
    "gram": "q | г | g",
}.items()}
DAYS = {"az": ["B.e.", "Ç.a.", "Ç.", "C.a.", "C.", "Ş.", "B."],
        "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
        "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
COCK_DEFAULT = "#E9D8C8"


# ------------------------------------------------------------------ мелкие помощники разметки
def esc(s):
    return html.escape(str(s), quote=True)


def L(d, tag="span", cls=""):
    """Текст на трёх языках: три соседних элемента, видимый выбирает CSS."""
    c = (" " + cls) if cls else ""
    return "".join('<%s class="l-%s%s" lang="%s">%s</%s>' % (tag, k, c, k, esc(d[k]), tag) for k in LANGS)


def price(p):
    if isinstance(p, str):
        star = p.endswith("*")
        p = p.rstrip("*")
        return '<b class="pr">%s<i class="m">₼</i>%s</b>' % (esc(p.replace(" / ", "<sep>/</sep>")).replace("&lt;sep&gt;", '<span class="sl">').replace("&lt;/sep&gt;", "</span>"), "*" if star else "")
    return '<b class="pr">%d<i class="m">₼</i></b>' % p


def item_row(name, p):
    return '<li class="it"><span class="nm">%s</span><span class="dots" aria-hidden="true"></span>%s</li>' % (L(T(name, "меню")), price(p))


def section(sid, title, n, body, cls=""):
    return ('<section class="sec %s" id="%s"><header class="sh"><span class="no">%02d</span><h2>%s</h2>'
            '<i class="wv" aria-hidden="true"></i></header>%s</section>') % (cls, sid, n, L(T(title)), body)


def ui_str(key):
    d = UI[key]
    return "%s | %s | %s" % (d["az"], d["ru"], d["en"])


def wa_link(number, text):
    return "https://wa.me/%s?text=%s" % (number, urllib.parse.quote(text))


# ------------------------------------------------------------------ меню
def kitchen(menu):
    out, nav, n = [], [], 0
    for sec in menu["kitchen"]:
        sid, title = sec["id"], sec["title"]
        n += 1
        nav.append('<a href="#%s">%s</a>' % (sid, L(T(title))))
        if "sets" in sec:
            cards = "".join('<article class="set"><div class="set-h"><h3>%s</h3>%s</div><p>%s</p></article>'
                            % (L(T(s["name"])), price(s["price"]), L(T(s["about"]))) for s in sec["sets"])
            out.append(section(sid, title, n, '<div class="sets">%s</div>' % cards, "sec-sets"))
        elif "caviar" in sec:
            tins = []
            for c in sec["caviar"]:
                ss = "".join('<li><span class="g">%s <i>%s</i></span>%s</li>' % (g, L(UI["gram"]), price(p)) for g, p in c["sizes"])
                tins.append('<article class="tin"><div class="lid" aria-hidden="true"></div><h3>%s</h3><ul>%s</ul></article>' % (L(T(c["name"])), ss))
            out.append(section(sid, title, n, '<div class="tins">%s</div>' % "".join(tins), "sec-caviar"))
        else:
            rows = "".join(item_row(nm, p) for nm, p in sec["items"])
            if "note" in sec:   # «На льду»: пометка сверху и сноска снизу
                body = '<p class="note">%s</p><ul class="list">%s</ul>' % (L(T(sec["note"])), rows)
                if sec.get("footnote"):
                    body += '<p class="note sm">%s</p>' % L(T(sec["footnote"]))
                out.append(section(sid, title, n, body, "sec-ice"))
            else:
                out.append(section(sid, title, n, '<ul class="list">%s</ul>' % rows))
    return "".join(out), "".join(nav), n


GLASS = ('<svg class="glass" viewBox="0 0 48 56" aria-hidden="true">'
         '<path d="M9.5 14 Q24 30 38.5 14 Z" fill="%s" stroke="none"/>'
         '<path d="M5 10 Q24 38 43 10 M24 24 V47 M15 49.5 Q24 45.5 33 49.5"/>'
         '<circle cx="39.5" cy="9" r="5" fill="#F7F2EC"/><path d="M39.5 4.5 V13.5 M35.6 6.8 L43.4 11.2 M35.6 11.2 L43.4 6.8" stroke-width=".8"/></svg>')


def row(name, p):
    return '<li class="it"><span class="nm">%s</span><span class="dots" aria-hidden="true"></span>%s</li>' % (name, price(p))


def bar(menu, n0):
    b, out, n = menu["bar"], [], n0
    n += 1
    cards = "".join('<article class="cock">%s<h3>%s</h3><p>%s</p>%s</article>'
                    % (GLASS % (x[3] if len(x) > 3 else COCK_DEFAULT), esc(x[0]), esc(x[1]), price(x[2])) for x in b["signature"])
    out.append(section("signature", ui_str("signature"), n, '<div class="cocks">%s</div>' % cards, "sec-sig"))
    n += 1
    rows = "".join('<li class="it it2"><span class="nm"><span>%s</span><small>%s</small></span><span class="dots" aria-hidden="true"></span>%s</li>'
                   % (esc(a), esc(c), price(p)) for a, c, p in b["classic"])
    out.append(section("classic", ui_str("classic"), n, '<ul class="list two">%s</ul>' % rows))
    n += 1
    out.append(section("noalc", ui_str("noalc"), n, '<ul class="list">%s</ul><h3 class="sub">%s</h3><ul class="list">%s</ul>'
                       % ("".join(row(esc(a), p) for a, p in b["noalc"]), L(UI["lemonade"]), "".join(row(esc(a), p) for a, p in b["lemonade"]))))
    n += 1
    out.append(section("coffee", ui_str("coffeeTea"), n,
                       '<div class="cols"><div><h3 class="sub">%s</h3><ul class="list">%s</ul></div><div><h3 class="sub">%s</h3><ul class="list">%s</ul></div></div>'
                       % (L(UI["coffee"]), "".join(row(esc(a), p) for a, p in b["coffee"]), L(UI["tea"]), "".join(row(esc(a), p) for a, p in b["tea"]))))
    n += 1
    out.append(section("soft", ui_str("soft"), n, '<ul class="list">%s</ul>'
                       % "".join(row(L(T(a)) if "|" in a else esc(a), p) for a, p in b["soft"])))
    n += 1
    groups = []
    for g in b["spirits"]:
        rows = "".join('<li class="it"><span class="nm">%s</span><span class="dots" aria-hidden="true"></span><b class="pr">%s<i class="m">₼</i>%s</b></li>'
                       % (esc(x[0]), x[1], ('<span class="sl">/</span>%s<i class="m">₼</i>' % x[2]) if len(x) > 2 and x[2] else "") for x in g["items"])
        groups.append('<details class="grp"><summary><span>%s</span><em>%d</em></summary><ul class="list">%s</ul></details>' % (esc(g["group"]), len(g["items"]), rows))
    out.append(section("spirits", ui_str("spirits"), n, '<p class="note">%s</p>%s' % (L(UI["bottleShot"]), "".join(groups))))
    n += 1
    out.append(section("hookah", ui_str("hookah"), n, '<ul class="list">%s</ul>' % "".join(row(esc(a), p) for a, p in b["hookah"])))
    return "".join(out)


# ------------------------------------------------------------------ заведение
def hours_list(venue):
    h = venue.get("hours", {})
    out = []
    for i, k in enumerate(DAY_KEYS):
        if k not in h or len(h[k]) != 2 or not all(re.fullmatch(r"\d\d:\d\d", t) for t in h[k]):
            raise ContentError('content/venue.toml, часы: для «%s» нужно ["ЧЧ:ММ", "ЧЧ:ММ"], например ["12:00", "00:00"]' % k)
        out.append((i, h[k][0], h[k][1]))
    return out


def hours_table(hours):
    return '<table class="hrs">%s</table>' % "".join(
        '<tr data-day="%d"><th>%s</th><td>%s – %s</td></tr>' % (d, L({k: DAYS[k][d] for k in DAYS}), a, b) for d, a, b in hours)


# ------------------------------------------------------------------ афиша
def iso(v, where):
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", v.strip()):
        datetime.date.fromisoformat(v.strip())
        return v.strip()
    raise ContentError("%s: дата должна быть в виде ГГГГ-ММ-ДД, например \"2026-10-17\", а сейчас: %r" % (where, v))


def afisha_image(ev):
    """Картинку афиши уменьшаем до 1080 и 540 пикселей по ширине, сохраняем как JPEG под именем события."""
    from PIL import Image, ImageOps
    src = ROOT / "afisha" / ev["image"]
    if not src.is_file():
        raise ContentError('Афиша «%s»: нет файла afisha/%s. Загрузите картинку в папку afisha/ или поправьте имя в content/afisha.toml.' % (ev["id"], ev["image"]))
    im = ImageOps.exif_transpose(Image.open(src))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (247, 242, 236))
        bg.paste(im, mask=im.split()[3])
        im = bg
    else:
        im = im.convert("RGB")
    out = DIST / "afisha"
    out.mkdir(parents=True, exist_ok=True)
    res = []
    for width, suffix in ((1080, ""), (540, "-s")):
        x = im if im.width <= width else im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        name = "%s%s.jpg" % (ev["id"], suffix)
        x.save(out / name, "JPEG", quality=82, optimize=True, progressive=True)
        res.append(("afisha/" + name, x.width, x.height))
    return res


def event_cta(ev, venue, title):
    btn = (ev.get("button") or "").strip()
    if btn == "book":
        return "".join('<a class="btn btn-fill l-%s" lang="%s" href="%s" target="_blank" rel="noopener">%s</a>'
                       % (k, k, esc(wa_link(venue["whatsapp"], UI["waEvent"][k] % title[k])), esc(UI["book"][k])) for k in LANGS)
    if btn == "call":
        return '<a class="btn btn-fill" href="tel:%s">%s</a>' % (esc(venue["phone"]), L(UI["call"]))
    if btn.startswith("http"):
        return '<a class="btn btn-fill" href="%s" target="_blank" rel="noopener">%s <span aria-hidden="true">↗</span></a>' % (esc(btn), L(UI["more"]))
    if btn:
        raise ContentError('Афиша «%s»: button может быть "book", "call", ссылкой https://... или "", а сейчас: %s' % (ev["id"], btn))
    return ""


def afisha(af, venue, today):
    cards, dialogs, ids = [], [], set()
    for i, ev in enumerate(af.get("event", []), 1):
        where = "content/afisha.toml, событие №%d" % i
        for key in ("id", "from", "to", "image", "title"):
            if key not in ev:
                raise ContentError("%s: не хватает поля «%s»" % (where, key))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", ev["id"]):
            raise ContentError('%s: id только латиницей в нижнем регистре, цифры и дефис, например "karaoke-17-okt", а сейчас: %s' % (where, ev["id"]))
        if ev["id"] in ids:
            raise ContentError("%s: id «%s» уже есть, придумайте другой" % (where, ev["id"]))
        ids.add(ev["id"])
        start, end = iso(ev["from"], where + ", from"), iso(ev["to"], where + ", to")
        if end < start:
            raise ContentError("%s: дата to (%s) раньше from (%s)" % (where, end, start))
        if end < today:          # прошедшие события на сайт не попадают
            continue
        (big, bw, bh), (small, sw, sh) = afisha_image(ev)
        title, when, text = T(ev["title"], where), T(ev.get("when", ""), where), T(ev.get("text", ""), where)
        cta = event_cta(ev, venue, title)
        eid, dates = ev["id"], 'data-from="%s" data-to="%s"' % (start, end)
        hidden = " hidden" if start > today else ""   # будущие ждут своей даты
        cards.append(
            '<article class="ev" data-ev="%s" %s%s>'
            '<button class="ev-pic" type="button" data-open="%s"><img src="%s" width="%d" height="%d" alt="%s" loading="lazy"><span class="vh">%s</span></button>'
            '<div class="ev-body">%s<h3>%s</h3>%s<div class="ev-cta">%s</div></div></article>'
            % (eid, dates, hidden, eid, small, sw, sh, esc(title["az"]), L(UI["more"]),
               ('<p class="ev-when">%s</p>' % L(when)) if when["az"] else "", L(title),
               ('<p class="ev-text">%s</p>' % L(text)) if text["az"] else "", cta))
        dialogs.append(
            '<dialog class="promo" id="promo-%s" data-id="%s" %s data-popup="%d" aria-labelledby="promo-t-%s">'
            '<div class="promo-card" tabindex="-1" autofocus><form method="dialog" class="promo-xf"><button class="promo-x" type="submit"><span class="vh">%s</span><span aria-hidden="true">×</span></button></form>'
            '<div class="promo-pic" style="--bg:url(\'%s\')"><img src="%s" width="%d" height="%d" alt="%s"></div>'
            '<div class="promo-body">%s<h2 id="promo-t-%s">%s</h2>%s<div class="promo-cta">%s</div></div></div></dialog>'
            % (eid, eid, dates, 1 if ev.get("popup", True) else 0, eid, L(UI["close"]), small, big, bw, bh, esc(title["az"]),
               ('<p class="promo-when">%s</p>' % L(when)) if when["az"] else "", eid, L(title),
               ('<p class="promo-text">%s</p>' % L(text)) if text["az"] else "", cta))
    if not cards:
        return "", ""
    section_html = ('<section class="afisha" id="afisha"><div class="wrap"><header class="part-h"><p class="kick">%s</p><h2 class="big">%s</h2></header></div>'
                    '<div class="ev-row%s">%s</div></section>') % (L(UI["afKick"]), L(UI["afisha"]), " one" if len(cards) == 1 else "", "".join(cards))
    return section_html, "".join(dialogs)


# ------------------------------------------------------------------ море, шрифты, логотип
def wave(y, amp, seg, w=2880, h=240, close=True):
    d = "M0 %g Q%g %g %g %g" % (y, seg / 2, y - amp, seg, y) + "".join(" T%g %g" % (seg * k, y) for k in range(2, w // seg + 1))
    return d + (" V%d H0 Z" % h if close else "")


def sea():
    # от горизонта к берегу: дальние волны мельче и медленнее; 1440 / шаг всегда чётное, поэтому петля без шва
    layers = [(44, 5, 120, "#C3DAE8", 70), (80, 8, 144, "#A9CADF", 56), (118, 10, 180, "#8DB6D5", 44),
              (160, 12, 240, "#6C9BC4", 36), (204, 12, 360, "#F7F2EC", 30)]
    out = []
    for i, (y, a, s, c, dur) in enumerate(layers, 1):
        crest = ('<path d="%s" fill="none" stroke="#FFFFFF" stroke-opacity=".75" stroke-width="2.5" vector-effect="non-scaling-stroke"/>'
                 % wave(y - 3, a, s, close=False)) if i == len(layers) else ""
        out.append('<svg class="w w%d" viewBox="0 0 2880 240" preserveAspectRatio="none" style="animation-duration:%ds"><path d="%s" fill="%s"/>%s</svg>'
                   % (i, dur, wave(y, a, s), c, crest))
        if i == 1:
            out.append('<div class="glint"></div>')
    return "".join(out)


def font_face(family, file, weight, style="normal"):
    data = base64.b64encode((ROOT / "assets" / "fonts" / file).read_bytes()).decode()
    return "@font-face{font-family:'%s';src:url(data:font/woff;base64,%s) format('woff');font-weight:%s;font-style:%s;font-display:swap}" % (family, data, weight, style)


def logo_svg():
    """Логотип заведения, обведённый в вектор по их картинке: один путь, цвет задаёт CSS."""
    lg = json.loads((ROOT / "assets" / "logo.json").read_text())
    d = "".join(g["d"] for g in lg["groups"])
    return ('<svg class="logo" viewBox="0 0 %d %d" width="%d" height="%d" aria-hidden="true" focusable="false">'
            '<path fill-rule="evenodd" d="%s"/></svg>') % (lg["W"], lg["H"], lg["W"] // 8, lg["H"] // 8, d)


# ------------------------------------------------------------------ сборка
def build(today=None):
    today = today or datetime.datetime.now(BAKU).date().isoformat()
    menu, venue, af = load("menu.toml"), load("venue.toml"), load("afisha.toml")
    for key in ("phone", "phone_show", "whatsapp", "address", "map", "instagram", "tiktok"):
        if key not in venue:
            raise ContentError("content/venue.toml: не хватает поля «%s»" % key)
    draft = bool(venue.get("draft", True))
    hours = hours_list(venue)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    k_html, k_nav, n = kitchen(menu)
    b_html = bar(menu, n)
    af_html, dialogs = afisha(af, venue, today)
    css = (ROOT / "src" / "style.css").read_text(encoding="utf-8")
    fonts = (font_face("Cormorant", "yari-cormorant.woff", "300 600") + font_face("Cormorant", "yari-cormorant-italic.woff", "300 600", "italic")
             + font_face("Ysabeau", "mecmeyi-ysabeau.woff", "400 700") + font_face("Manat", "manat.woff", "400 700"))
    book = "".join('<a class="btn btn-book l-%s" lang="%s" href="%s" target="_blank" rel="noopener">%s</a>'
                   % (k, k, esc(wa_link(venue["whatsapp"], UI["waText"][k])), esc(UI["book"][k])) for k in LANGS)
    page = (ROOT / "src" / "page.html").read_text(encoding="utf-8")
    footnote = ('<p>%s <a href="%s" target="_blank" rel="noopener">monyo.az</a></p>' % (L(UI["concept"]), esc(venue.get("menu_source", "")))) if draft else ""
    rep = {
        "{{FONTS}}": fonts, "{{CSS}}": css,
        "{{ROBOTS}}": '<meta name="robots" content="noindex, nofollow">' if draft else '<meta name="robots" content="index, follow">',
        "{{DESC}}": esc("More&More: dəniz məhsulları restoranı, Port Baku Walk." + (" Konsept sayt, qaralama." if draft else "")),
        "{{DRAFT}}": ('<p class="draft">%s</p>' % L(UI["draft"])) if draft else "<span></span>",
        "{{FOOTNOTE}}": footnote, "{{COORDS}}": esc(venue.get("coords", "")),
        "{{TAG}}": L(UI["tag"]), "{{WHERE}}": L(T(venue["address"], "content/venue.toml, address")),
        "{{MENU}}": L(UI["menu"]), "{{BAR}}": L(UI["bar"]), "{{CONTACTS}}": L(UI["contacts"]), "{{KITCHEN}}": L(UI["kitchen"]),
        "{{BOOK}}": book, "{{ROUTE}}": L(UI["route"]), "{{MAP}}": esc(venue["map"]),
        "{{NAV}}": k_nav, "{{KHTML}}": k_html, "{{BHTML}}": b_html, "{{AFISHA}}": af_html, "{{DIALOGS}}": dialogs,
        "{{HOURS_H}}": L(UI["hours"]), "{{HOURS}}": hours_table(hours), "{{ADDRESS_H}}": L(UI["address"]),
        "{{CALL}}": L(UI["call"]), "{{TEL}}": "tel:" + esc(venue["phone"]), "{{PHONE}}": esc(venue["phone_show"]), "{{WA}}": esc("https://wa.me/" + venue["whatsapp"]),
        "{{OPENMAP}}": L(UI["openMap"]), "{{IG}}": esc(venue["instagram"]), "{{TT}}": esc(venue["tiktok"]), "{{CREDIT}}": L(UI["credit"]),
        "{{SERVICE}}": L(UI["service"]), "{{OPEN}}": L(UI["open"]), "{{CLOSED}}": L(UI["closed"]), "{{LANG}}": L(UI["lang"]),
        "{{HOURS_JSON}}": json.dumps(hours), "{{SEA}}": sea(), "{{LOGO}}": logo_svg(),
    }
    for a, b in rep.items():
        assert a in page, "в шаблоне нет " + a
        page = page.replace(a, b)
    left = re.findall(r"\{\{[A-Z_]+\}\}", page)
    assert not left, left
    (DIST / "index.html").write_text(page, encoding="utf-8")
    (DIST / "robots.txt").write_text("User-agent: *\n%s\n" % ("Disallow: /" if draft else "Allow: /"), encoding="utf-8")
    n_ev = af_html.count('class="ev"')
    print("Готово: dist/index.html, %d КБ. Кухня: %d разделов. Афиша: %d событ. Черновик: %s. Дата (Баку): %s"
          % ((DIST / "index.html").stat().st_size // 1024, len(menu["kitchen"]), n_ev, "да" if draft else "нет", today))


if __name__ == "__main__":
    try:
        build(sys.argv[1] if len(sys.argv) > 1 else None)
    except ContentError as e:
        print("\n✖ " + str(e) + "\n", file=sys.stderr)
        sys.exit(1)
