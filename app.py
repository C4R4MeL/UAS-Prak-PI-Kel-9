"""Antarmuka pencarian cerpen (Streamlit).

Aplikasi ini memakai komponen yang dihasilkan notebook:
  - tiga indeks Elasticsearch: cerpen_bm25, cerpen_lmd, cerpen_baseline
  - preprocess.py  (pipeline preprocessing yang sama dengan saat indexing)
  - synonyms.json  (kamus sinonim untuk query expansion)
  - evaluasi_ringkasan.csv (opsional, untuk tab Evaluasi)

Konfigurasi lewat variabel lingkungan:
  UAS_PI_DIR  folder berisi preprocess.py dan berkas pendukung (bawaan: folder app.py)
  ES_URL      alamat Elasticsearch (bawaan: http://localhost:9200)

Menjalankan:  streamlit run app.py
"""
import os
import sys
import re
import json
import html

import pandas as pd
import streamlit as st
from elasticsearch import Elasticsearch

BASE = os.environ.get("UAS_PI_DIR", os.path.dirname(os.path.abspath(__file__)))
ES_URL = os.environ.get("ES_URL", "http://localhost:9200")
sys.path.insert(0, BASE)
import preprocess  # noqa: E402  (modul yang sama dengan yang dipakai saat indexing)

INDEX = {
    "BM25 + preprocessing custom": "cerpen_bm25",
    "LM Dirichlet + preprocessing custom": "cerpen_lmd",
    "Baseline: BM25 + StandardAnalyzer": "cerpen_baseline",
}
SUMBER = ["cerpenkompas", "kumpulanfiksi"]

st.set_page_config(page_title="Cari Cerpen", page_icon="📖", layout="wide")


@st.cache_resource
def get_es():
    return Elasticsearch(ES_URL)


@st.cache_data
def load_synonyms():
    with open(os.path.join(BASE, "synonyms.json"), encoding="utf-8") as f:
        return json.load(f)


es = get_es()
SYN = load_synonyms()


def run_search(label, query, k, expand):
    """Mengembalikan (hits, query_diproses, tambahan_sinonim, himpunan_token_untuk_highlight)."""
    idx = INDEX[label]
    baseline = idx == "cerpen_baseline"
    words = re.findall(r"[a-zA-Z]+", query.lower())
    extra = [s for w in words for s in SYN.get(w, [])]

    if baseline:
        orig_q, ext_q = query, " ".join(extra)
        qtokens = set(words) | (set(extra) if expand else set())
    else:
        orig = preprocess.preprocess(query)
        ext = [t for t in preprocess.preprocess(" ".join(extra)) if t not in orig]
        orig_q, ext_q = " ".join(orig), " ".join(dict.fromkeys(ext))
        qtokens = set(orig) | (set(ext) if expand else set())

    if not orig_q.strip():
        return [], orig_q, "", qtokens

    should = [{"match": {"content": {"query": orig_q, "boost": 1.0}}}]
    if expand and ext_q:
        should.append({"match": {"content": {"query": ext_q, "boost": 0.5}}})
    res = es.search(index=idx, size=k, _source=["title", "url", "source", "snippet"],
                    query={"bool": {"should": should}})
    return res["hits"]["hits"], orig_q, (ext_q if expand else ""), qtokens


def highlight(snippet, qtokens, baseline):
    out = []
    for w in snippet.split():
        core = re.sub(r"[^\w-]", "", w).lower()
        hit = False
        if core:
            if baseline:
                hit = core in qtokens
            else:
                hit = any(t in qtokens for t in preprocess.preprocess(core))
        out.append(f"<mark>{html.escape(w)}</mark>" if hit else html.escape(w))
    return " ".join(out)


if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Pengaturan")
    method = st.radio("Metode retrieval", list(INDEX.keys()))
    expand = st.checkbox("Query expansion (sinonim)", value=False)
    k = st.slider("Jumlah hasil", 5, 20, 10)
    src_filter = st.multiselect("Filter sumber", SUMBER, default=SUMBER)
    st.divider()
    st.subheader("Riwayat pencarian")
    for h in st.session_state.history[-8:][::-1]:
        st.caption("• " + h)

st.title("📖 Mesin Pencari Cerpen")
try:
    n_docs = es.count(index="cerpen_bm25")["count"]
    st.caption(f"Korpus {n_docs} cerpen · Elasticsearch · BM25 vs LM Dirichlet vs baseline")
except Exception:
    st.caption("Elasticsearch belum dapat dihubungi")

tab_cari, tab_eval = st.tabs(["Pencarian", "Evaluasi"])

with tab_cari:
    with st.form("form_cari"):
        query = st.text_input("Masukkan query", placeholder="contoh: ibu menunggu anak pulang")
        cari = st.form_submit_button("Cari")

    if cari and query.strip():
        st.session_state.history.append(query.strip())
        try:
            hits, orig_q, ext_q, qtokens = run_search(method, query.strip(), k, expand)
        except Exception as e:
            st.error(f"Tidak bisa menghubungi Elasticsearch: {e}")
            st.stop()

        st.markdown(
            f"**Metode:** {method}  \n**Query setelah diproses:** `{orig_q}`"
            + (f"  \n**Tambahan sinonim:** `{ext_q}`" if ext_q else "")
        )
        shown = [h for h in hits if h["_source"]["source"] in src_filter]
        if not shown:
            st.warning("Tidak ada hasil.")
        baseline = INDEX[method] == "cerpen_baseline"
        for rank, h in enumerate(shown, 1):
            s = h["_source"]
            with st.container(border=True):
                st.markdown(f"**{rank}. [{s['title']}]({s['url']})**  ·  skor `{h['_score']:.3f}`  ·  _{s['source']}_")
                st.markdown(highlight(s["snippet"], qtokens, baseline) + " …", unsafe_allow_html=True)

with tab_eval:
    path = os.path.join(BASE, "evaluasi_ringkasan.csv")
    if os.path.exists(path):
        tab = pd.read_csv(path, index_col=0)
        st.subheader("Perbandingan tiga konfigurasi (12 query uji)")
        st.dataframe(tab)
        st.bar_chart(tab[["F1", "MAP"]])
    else:
        st.info("Berkas evaluasi_ringkasan.csv belum tersedia.")
