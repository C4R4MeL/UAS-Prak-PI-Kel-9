import re, unicodedata
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

# ---------- Stopword: bawaan Sastrawi + domain cerpen + hasil analisis DF ----------
BASE_SW = set(StopWordRemoverFactory().get_stop_words())

# kata tema yang TIDAK boleh dibuang walau ada di daftar bawaan
KEEP_TERMS = {"ibu", "bapak", "ayah", "adik", "kakak", "istri", "suami", "anak",
              "saudara", "teman", "sahabat", "kota", "desa", "perang"}

DIALOG_SW = {"ujar", "kata", "katanya", "berkata", "bertanya", "tanya", "tanyanya",
             "jawab", "jawabnya", "menjawab", "ucap", "ucapnya", "seru", "serunya",
             "sahut", "sahutnya", "bisik", "bisiknya", "gumam", "gumamnya", "ujarnya",
             "kataku", "katamu"}

NARASI_SW = {"tiba", "lalu", "kemudian", "sambil", "seraya", "sebuah", "seorang",
             "sesuatu", "akhirnya", "sebelum", "sesudah", "ketika", "waktu", "hari",
             "saat", "pun", "lah", "kah", "nya", "dia", "aku", "kamu", "kami", "kita",
             "mereka", "kau", "puluh", "tengah", "milik"}

# kata kerja/keterangan generik dengan document frequency sangat tinggi
DF_SW = {"tinggal", "dengar", "temu", "duduk", "pikir", "pandang", "diam", "penuh",
         "salah", "bawa", "buka", "cari", "tahun"}

STOP = (BASE_SW - KEEP_TERMS) | DIALOG_SW | NARASI_SW | DF_SW

# koreksi salah stem Sastrawi yang ditemukan pada korpus ini
STEM_OVERRIDE = {"mengenali": "kenal", "dikenali": "kenal", "dikenalinya": "kenal",
                 "gerakan": "gerak", "gerakannya": "gerak",
                 "disyahkan": "sah", "syah": "sah"}

_stemmer = StemmerFactory().create_stemmer()
_cache = {}

def _stem(w):
    if w in STEM_OVERRIDE:
        return STEM_OVERRIDE[w]
    if w not in _cache:
        s = _stemmer.stem(w)
        _cache[w] = s.split("-")[0] if "-" in s else s
    return _cache[w]

def clean_text(t):
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"<[^>]+>", " ", t)                                  # sisa HTML
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)                    # URL
    t = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]", " ", t)     # emoji/simbol
    t = re.sub(r"[“”„‟«»\"'‘’`´]", " ", t)                          # tanda kutip dialog
    t = re.sub(r"[–—―‒]", " ", t)                                   # tanda pisah dialog
    t = re.sub(r"(?m)^\s*[\*\-_=~#•·]{2,}\s*$", " ", t)             # garis pemisah dekoratif
    t = re.sub(r"\b(bersambung|tamat)\b", " ", t, flags=re.I)
    t = re.sub(r"\b(cerpen|cerita pendek)\s+(karya|oleh)\b", " ", t, flags=re.I)
    t = re.sub(r"\b(baca juga|related|share this|like this|bagikan)\b.*", " ", t, flags=re.I)
    return t

def tokenize(t):
    # case folding + pertahankan tanda hubung di dalam kata (kata ulang)
    return re.findall(r"[a-z]+(?:-[a-z]+)*", t.lower())

def preprocess(text, title=""):
    toks = tokenize(clean_text(title + " . " + text))
    toks = [w for w in toks if len(w) > 2 and w not in STOP]
    toks = [_stem(w) for w in toks]
    return [w for w in toks if len(w) > 2 and w not in STOP]
