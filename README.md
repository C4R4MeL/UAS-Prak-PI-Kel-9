# Mesin Pencari Cerpen Indonesia

Sistem penelusuran informasi untuk korpus cerpen berbahasa Indonesia yang dikumpulkan sendiri lewat crawling. Proyek ini membangun seluruh alurnya, dari pengumpulan data, preprocessing khusus cerpen, dan indexing di Elasticsearch, sampai perbandingan dua model retrieval (BM25 dan LM Dirichlet) terhadap baseline, query expansion, relevance feedback Rocchio, evaluasi dengan penilaian relevansi manual, dan antarmuka pencarian berbasis Streamlit.

Proyek ini dikerjakan sebagai UAS Praktikum Penelusuran Informasi, Informatika, Universitas Syiah Kuala.

| Nama | NIM |
|---|---|
| Muhammad Farhan Alafif | 2408107010075 |

## Latar belakang dan permasalahan

Cerpen berbeda dari berita atau artikel informatif. Panjangnya beragam, penuturannya naratif dengan banyak dialog, dan kosakatanya cenderung sastrawi. Kebutuhan pencariannya pun biasanya tematik ("ibu menunggu anak pulang", "perang dan pengungsian"), bukan fakta yang tertulis eksplisit. Dua pilihan desain langsung memengaruhi kualitas hasil: cara teks diproses sebelum diindeks, dan model yang dipakai untuk memberi skor.

Proyek ini menjawab tiga pertanyaan pada korpus cerpen:

1. Apakah preprocessing yang dirancang untuk cerpen memperbaiki hasil dibandingkan `StandardAnalyzer`?
2. Mana yang lebih cocok untuk korpus ini, BM25 atau LM Dirichlet?
3. Bagaimana query expansion dengan sinonim dan relevance feedback Rocchio mengubah query dan peringkat?

## Gambaran sistem

```
Crawling (sitemap WordPress)
   └─ raw_all.jsonl            1.497 halaman
        └─ Penyaringan cerpen + duplicate checking
             └─ raw_corpus.json            503 cerpen unik
                  └─ Custom preprocessing (preprocess.py)
                       └─ clean_corpus.json
                            └─ Elasticsearch: tiga indeks
                                 ├─ cerpen_bm25      (token custom, BM25)
                                 ├─ cerpen_lmd       (token custom, LM Dirichlet)
                                 └─ cerpen_baseline  (teks mentah, StandardAnalyzer, BM25)

Query ─ preprocess.py yang sama ─ (opsional: sinonim / Rocchio) ─ Elasticsearch ─ peringkat
```

Query diproses dengan modul `preprocess.py` yang sama dengan saat indexing, sehingga istilah query dan istilah indeks dibentuk dengan cara yang identik.

## Korpus

Korpus dikumpulkan dari dua blog cerpen berbasis WordPress. Daftar URL posting diambil dari `sitemap.xml`, tiap halaman diunduh dengan jeda 1 detik, dan `robots.txt` kedua situs tidak melarang halaman posting.

| Sumber | Posting di sitemap | Dokumen akhir | Karakter |
|---|---|---|---|
| `cerpenkompas.wordpress.com` | 462 | 460 | cerpen koran, bergaya sastra |
| `kumpulanfiksi.wordpress.com` | 999 | 43 | sebagian besar puisi; yang diambil hanya kategori Cerpen dan Cerita Mini |

Berkas `raw_all.jsonl` berisi 1.497 halaman. Angka itu juga mencakup 36 halaman dari sebuah blog Blogspot yang dicoba pada tahap awal dan tidak dipakai, karena halaman-halaman yang diperiksa hanya berisi daftar judul (13 kata).

Sumber lain yang dicoba dan ditinggalkan: `cerpenmu.com` tidak dapat diakses, dan `storial.co` ternyata memuat artikel tentang menulis berbahasa Inggris dengan kurang dari 500 URL.

**Penyaringan.** Dari `cerpenkompas` diambil seluruh posting dengan panjang minimal 300 kata. Dari `kumpulanfiksi` hanya yang berkategori Cerpen atau Cerita Mini, tanpa kategori Puisi, Catatan, Ulasan Karya, atau Esai, dengan panjang minimal 300 kata. Cerita bersambung dikeluarkan karena tiap posting hanya satu bab. Hasilnya 505 dokumen.

**Duplicate checking.** Dua tahap: hash MD5 pada teks ternormalisasi untuk duplikat persis, lalu cosine similarity pada vektor TF-IDF dengan ambang 0,95. Ditemukan dua duplikat, keduanya dari `cerpenkompas`: satu duplikat persis dan satu dengan kemiripan 0,9945. Keduanya dibuang dan dicatat di `duplicates_report.csv`, sehingga korpus akhir berisi **503 cerpen unik**.

**Karakteristik.** Rata-rata panjang dokumen 1.587 kata. Sekitar 91% dokumen berasal dari `cerpenkompas`, jadi korpus condong ke cerpen koran bergaya sastra dengan tema sosial dan keluarga yang dominan.

Korpus mentah (`raw_corpus.json`) dan korpus hasil preprocessing (`clean_corpus.json`) disimpan terpisah.

## Preprocessing

Preprocessing ditulis sebagai satu modul, `preprocess.py`, dan dipakai identik untuk indexing, query, serta aplikasi pencarian.

1. **Cleaning khusus cerpen.** Membuang sisa HTML, URL, emoji dan simbol, tanda kutip dan tanda pisah dialog, garis pemisah dekoratif, penanda "bersambung/tamat", label "Cerpen karya", serta sisa teks "baca juga/related/share".
2. **Case folding dan tokenisasi.** Tanda hubung di dalam kata dipertahankan supaya kata ulang seperti *ragu-ragu* tetap utuh sebelum di-stem.
3. **Stopword bertingkat** (total 837 kata):
   - daftar bawaan Sastrawi, dikurangi `KEEP_TERMS` (ibu, ayah, anak, istri, suami, kota, desa, dan beberapa lainnya). Daftar bawaan Sastrawi memuat kata-kata ini, padahal di cerpen kata tersebut adalah tema inti. Tanpa pengecualian ini, query "ibu menunggu anak pulang" kehilangan kata *ibu*;
   - kata pengantar dialog (*ujar, katanya, jawabnya*, dan sejenisnya);
   - kata narasi umum (*lalu, kemudian, sambil*, dan sejenisnya);
   - kata kerja dan keterangan generik dengan document frequency sangat tinggi (*tinggal, dengar, temu, duduk*, dan sejenisnya).
4. **Stemming** dengan Sastrawi, ditambah kamus koreksi `STEM_OVERRIDE` untuk kesalahan stem yang ditemukan pada korpus ini (*mengenali*, *gerakan*, *disyahkan*).

Stopword domain tidak ditentukan secara acak. Kandidatnya diambil dari term dengan document frequency tertinggi, lalu dipilah: kata kerja dan keterangan generik dibuang, sedangkan kata benda tematik (*rumah, anak, hidup, perempuan*) dipertahankan. Setelah preprocessing, rata-rata dokumen berisi 704 token.

Contoh hasil pada awal salah satu cerpen:

```
Sebelum: Lelaki jangkung berwajah terang yang membukakan pintu terlihat takjub begitu
         mengenali saya. Pastinya dia sama sekali tidak menyangka akan kedatangan saya ...
Sesudah: lelaki jangkung wajah terang pintu takjub kenal sangka ramah sila ragu pilih amben
```

## Arsitektur dan teknologi

| Komponen | Teknologi |
|---|---|
| Bahasa | Python 3 |
| Crawling | `requests`, `BeautifulSoup` |
| Preprocessing | PySastrawi, `re`, `unicodedata` |
| Mesin pencari | Elasticsearch 8.11 (berbasis Apache Lucene), klien Python `elasticsearch` 8.11 |
| Analisis | `pandas`, `numpy`, `scipy`, `scikit-learn`, `matplotlib` |
| Antarmuka | Streamlit |

Elasticsearch dipakai sebagai pengganti PyLucene, yang termasuk alternatif resmi pada ketentuan tugas. Tiga indeks dibuat dengan satu shard supaya statistik koleksi (document frequency dan panjang rata-rata dokumen) konsisten. Token hasil preprocessing diindeks dengan analyzer `whitespace` sehingga Elasticsearch tidak memproses ulang teks tersebut. Indeks baseline menerima teks mentah dengan analyzer `standard`. Field `content` menyimpan term vector, yang dipakai untuk posting list dan Rocchio.

Posting list direkonstruksi lewat API Elasticsearch: dokumen yang memuat sebuah term diambil dengan query `term`, lalu frekuensi term dibaca dari term vector. Sebagai contoh, term *rumah* muncul di 430 dari 503 dokumen, *kenal* di 304, dan *nelayan* di 17.

## Model retrieval

**BM25** (k1 = 1,2; b = 0,75):

$$\text{score}(D,Q)=\sum_{t\in Q}\text{IDF}(t)\cdot\frac{f(t,D)\,(k_1+1)}{f(t,D)+k_1\left(1-b+b\,\frac{|D|}{\text{avgdl}}\right)},\qquad \text{IDF}(t)=\ln\!\left(1+\frac{N-n_t+0{,}5}{n_t+0{,}5}\right)$$

`k1` mengatur kejenuhan frekuensi term dan `b` mengatur normalisasi terhadap panjang dokumen. Karena panjang cerpen sangat bervariasi, `b` relevan untuk korpus ini.

**LM Dirichlet** (μ = 2000, nilai bawaan Lucene):

$$\text{score}(D,Q)=\sum_{t\in Q\cap D}\left[\ln\!\left(1+\frac{f(t,D)}{\mu\,p(t\mid C)}\right)+\ln\frac{\mu}{|D|+\mu}\right]$$

dengan $p(t\mid C)$ probabilitas term pada seluruh koleksi. Parameter μ adalah pseudo-count smoothing: makin besar, makin kuat estimasi dokumen ditarik ke model koleksi. Implementasi Lucene membatasi skor agar tidak negatif.

**Baseline.** BM25 dengan parameter yang sama pada teks mentah dan `StandardAnalyzer`, tanpa stemming dan tanpa stopword bahasa Indonesia. Karena modelnya sama dengan konfigurasi BM25, selisih hasil keduanya berasal dari preprocessing.

Parameter kedua model tidak dituning pada data uji.

## Query expansion dan Rocchio

**Query expansion.** Kamus sinonim buatan sendiri (`synonyms.json`) berisi 21 pasangan istilah yang sesuai ranah cerpen, misalnya *ibu* → bunda, emak, mama; *badai* → topan, prahara, ombak; *surau* → langgar, musala. Sinonim dari kata asli query diproses dengan pipeline yang sama, lalu dikirim sebagai klausa tambahan dengan bobot 0,5, sedangkan istilah asli berbobot 1,0. Pada enam query demonstrasi, top-3 hasil berubah pada lima query dan tidak berubah pada "kiai dan surau di desa". Expansion tidak dimasukkan ke perhitungan metrik karena dokumen baru yang muncul karenanya belum dinilai relevansinya.

**Rocchio.** Query baru dibentuk dari vektor query asli dan vektor dokumen yang dinilai pengguna:

$$\vec{q}_{baru}=\alpha\,\vec{q}_0+\frac{\beta}{|D_r|}\sum_{d\in D_r}\vec{d}-\frac{\gamma}{|D_{nr}|}\sum_{d\in D_{nr}}\vec{d}$$

dengan α = 1,0, β = 0,75, γ = 0,15. Vektor dokumen adalah TF-IDF, $(1+\ln \text{tf})\cdot\ln(N/\text{df})$ dengan normalisasi L2, yang dihitung dari term vector indeks Elasticsearch. Hanya term berbobot positif yang dikirim kembali ke indeks sebagai query berbobot (maksimal 15 term), dan term baru yang muncul di kurang dari 3 dokumen dibuang.

Pada demonstrasi untuk query "ibu menunggu anak pulang", umpan balik berasal dari penilaian manual terhadap top-10 hasil awal: dua dokumen relevan (*Anak-anak Peluru* dan *Jendela Tua*) dan delapan tidak relevan. Query bertambah dari 4 menjadi 15 term. Term tambahan yang terbentuk antara lain *rantau*, *gadang*, *almanak*, *jagung*, *etek*, *jahit*, dan *payakumbuh*. Sebagian bersifat tematik (*rantau*), tetapi banyak yang berupa nama tempat atau kata khas dua cerpen umpan balik. Ini gejala umum Rocchio ketika dokumen relevan sangat sedikit. Selain itu, karena hanya term berbobot positif yang dikirim, γ hanya menurunkan bobot term yang juga muncul di dokumen tidak relevan dan tidak mengeluarkan dokumen tersebut dari hasil: salah satu dokumen yang ditandai tidak relevan (*Langit Malam*) tetap muncul setelah feedback.

## Evaluasi

**Query dan penilaian.** Evaluasi memakai 12 query tematik: ibu menunggu anak pulang; nelayan melaut dan badai; pengkhianatan sahabat; kemiskinan dan perjuangan hidup di kota; korupsi pejabat dan kekuasaan; kematian suami dan kesedihan istri; merantau dan rindu kampung halaman; cinta yang tidak sampai; perang dan pengungsian; hantu dan arwah gentayangan; perselingkuhan dalam rumah tangga; dan kiai dan surau di desa.

Penilaian relevansi dilakukan manual (0/1) oleh anggota kelompok berdasarkan isi dokumen, bukan skor algoritma. Sebuah cerpen dinilai relevan bila tema utama ceritanya sesuai dengan query. Cerpen yang kata kuncinya hanya muncul sekilas dinilai tidak relevan.

**Pooling.** Dokumen yang dinilai adalah gabungan top-10 dari ketiga konfigurasi untuk tiap query, disajikan dalam urutan acak tanpa menampilkan metode atau skor. Hasilnya 193 dokumen (11 sampai 21 per query) dengan 46 dokumen relevan (2 sampai 7 per query). Penilaian yang sama dipakai untuk ketiga konfigurasi.

**Metrik.** Untuk tiap query dengan K = 10 dan R dokumen relevan dalam pool:

$$P@10=\frac{\sum_{i=1}^{10} r_i}{10},\quad \text{Recall}=\frac{\sum_{i=1}^{10} r_i}{R},\quad F1=\frac{2\cdot P@10\cdot \text{Recall}}{P@10+\text{Recall}},\quad AP=\frac{1}{R}\sum_{i=1}^{10} P@i\cdot r_i$$

MAP adalah rata-rata AP seluruh query. Dokumen yang tidak ada di pool dianggap tidak relevan, dan Recall dihitung terhadap dokumen relevan di dalam pool.

## Hasil dan analisis

![Perbandingan tiga konfigurasi](evaluasi_grafik.png)

| Konfigurasi | P@10 | Recall | F1 | MAP |
|---|---|---|---|---|
| Baseline (StandardAnalyzer + BM25) | 0,250 | 0,663 | 0,349 | 0,330 |
| BM25 + custom preprocessing | 0,283 | 0,717 | 0,391 | 0,388 |
| LM Dirichlet + custom preprocessing | 0,300 | 0,769 | 0,415 | 0,488 |

Selisih antar konfigurasi dibaca bersama ukuran ketidakpastiannya, yaitu uji Wilcoxon signed-rank pada selisih AP per query dan interval kepercayaan 95% bootstrap (5.000 pengambilan ulang):

| Perbandingan | Selisih MAP | Menang / kalah / seri | Wilcoxon p | CI 95% bootstrap |
|---|---|---|---|---|
| BM25 vs baseline | +0,057 | 7 / 5 / 0 | 0,569 | [−0,099; +0,235] |
| LM Dirichlet vs BM25 | +0,100 | 6 / 4 / 2 | 0,139 | [+0,023; +0,183] |
| LM Dirichlet vs baseline | +0,157 | 8 / 4 / 0 | 0,077 | [+0,016; +0,313] |

AP per query:

| q | Query | R | AP baseline | AP BM25 | AP LM Dirichlet |
|---|---|---|---|---|---|
| 1 | ibu menunggu anak pulang | 5 | 0,240 | 0,244 | 0,352 |
| 2 | nelayan melaut dan badai | 5 | 0,534 | 0,232 | 0,522 |
| 3 | pengkhianatan sahabat | 2 | 0,292 | 0,500 | 0,500 |
| 4 | kemiskinan dan perjuangan hidup di kota | 3 | 0,407 | 0,178 | 0,083 |
| 5 | korupsi pejabat dan kekuasaan | 2 | 0,350 | 0,100 | 0,500 |
| 6 | kematian suami dan kesedihan istri | 2 | 0,000 | 0,250 | 0,243 |
| 7 | merantau dan rindu kampung halaman | 5 | 0,167 | 0,679 | 0,800 |
| 8 | cinta yang tidak sampai | 7 | 0,571 | 0,571 | 0,556 |
| 9 | perang dan pengungsian | 2 | 0,417 | 0,226 | 0,450 |
| 10 | hantu dan arwah gentayangan | 6 | 0,384 | 0,386 | 0,370 |
| 11 | perselingkuhan dalam rumah tangga | 3 | 0,333 | 1,000 | 1,000 |
| 12 | kiai dan surau di desa | 4 | 0,270 | 0,288 | 0,475 |

**Urutan konfigurasi.** Rata-rata keempat metrik konsisten: LM Dirichlet, lalu BM25 dengan preprocessing custom, lalu baseline. Selisih paling jelas pada MAP, artinya dokumen relevan cenderung muncul lebih awal pada peringkat LM Dirichlet.

**Pengaruh preprocessing.** MAP rata-rata naik dari 0,330 menjadi 0,388 dan Recall dari 0,663 menjadi 0,717, tetapi kenaikan ini tidak konsisten antar query. BM25 custom lebih baik pada 7 query dan lebih buruk pada 5, dengan selisih besar pada q2, q4, q5, dan q9. Uji kemaknaannya tidak meyakinkan (p = 0,569, interval mencakup nol). Data ini belum cukup untuk menyimpulkan bahwa preprocessing custom meningkatkan kualitas secara umum, hanya bahwa ada kecenderungan naik pada rata-rata dengan variasi besar antar query. Penjelasan yang masuk akal tetapi belum diuji: stemming menyatukan variasi kata (*menunggu*, *menanti*, *penantian*) sehingga jangkauan dokumen relevan bertambah, sementara pada query tertentu stemming atau pembuangan stopword menghilangkan kata yang membedakan dokumen relevan.

**Perbandingan model.** LM Dirichlet unggul atas BM25 dengan selisih MAP +0,100 dan interval bootstrap yang tidak mencakup nol, walau uji Wilcoxon (p = 0,139) tidak mencapai tingkat 0,05. Ini perbedaan paling meyakinkan pada data ini. Salah satu penjelasan yang mungkin adalah panjang cerpen yang sangat bervariasi, sehingga smoothing Dirichlet (μ = 2000) memperlakukan dokumen panjang berbeda dari normalisasi panjang BM25 (b = 0,75). Penjelasan ini hipotesis karena `b` dan μ tidak dituning.

## Keterbatasan

- Hanya 12 query dengan rata-rata sekitar 4 dokumen relevan per query dalam pool. P@10 maksimum yang mungkin rata-rata hanya 0,383, sehingga nilai P@10 yang rendah mencerminkan batas ini dan bukan semata kualitas sistem. P@10 dibaca bersama MAP.
- Pool dibentuk dari sistem yang dibandingkan. Dokumen relevan yang tidak pernah masuk top-10 ketiganya tidak ikut dinilai, sehingga Recall terhadap seluruh korpus tidak diketahui.
- Penilaian dikerjakan satu kelompok tanpa pengukuran kesepakatan antar penilai.
- Korpus condong ke satu sumber dan satu gaya (cerpen koran), sehingga hasilnya belum tentu berlaku untuk genre populer seperti cerpen remaja atau horor.
- Sastrawi masih menghasilkan sejumlah kesalahan stem (misalnya *pelayar* menjadi *layar*). Koreksi di `STEM_OVERRIDE` hanya mencakup kasus yang ditemukan.
- Parameter `k1`, `b`, dan μ tidak dituning.
- Pengaruh query expansion terhadap kualitas belum diukur secara kuantitatif.

## Antarmuka pencarian

`app.py` adalah aplikasi Streamlit terpisah dari notebook. Aplikasi ini memakai tiga indeks Elasticsearch, `preprocess.py`, dan `synonyms.json` yang sama dengan eksperimen. Fiturnya:

- input query dan tombol cari;
- pilihan metode: BM25, LM Dirichlet, atau baseline;
- opsi query expansion dengan sinonim, dengan tampilan query setelah diproses dan sinonim yang ditambahkan;
- daftar hasil berisi peringkat, skor, judul dengan tautan ke sumber, dan potongan isi dengan kata kunci disorot;
- filter sumber, riwayat pencarian, dan tab Evaluasi yang menampilkan tabel dan grafik metrik.

Menjalankan:

```bash
pip install -r requirements.txt
# Elasticsearch 8.11 berjalan di localhost:9200 dan tiga indeks sudah dibangun (notebook, bagian 6)
streamlit run app.py
```

Folder yang berisi `preprocess.py`, `synonyms.json`, dan `evaluasi_ringkasan.csv` dibaca dari lokasi `app.py`, atau dari variabel lingkungan `UAS_PI_DIR`. Alamat Elasticsearch dapat diubah dengan `ES_URL` (bawaan `http://localhost:9200`). Karena indeks hanya hidup selama Elasticsearch berjalan, indeks perlu dibangun ulang dengan notebook setelah Elasticsearch dimulai ulang.

## Struktur direktori

```
.
├── README.md
├── UAS_PI_Cerpen_Final.ipynb
├── app.py
├── preprocess.py
├── requirements.txt
├── synonyms.json
├── raw_all.jsonl
├── raw_corpus.json
├── clean_corpus.json
├── duplicates_report.csv
├── judgment_sheet.csv
├── judgment_sheet_filled.csv
├── pool_info.json
├── evaluasi_ringkasan.csv
├── evaluasi_per_query.csv
├── evaluasi_grafik.png
└── evaluasi_ap_per_query.png
```

| Berkas | Isi |
|---|---|
| `UAS_PI_Cerpen_Final.ipynb` | Notebook utama: crawling, penyaringan, preprocessing, indexing, model, query expansion, Rocchio, evaluasi, dan analisis |
| `app.py` | Aplikasi pencarian Streamlit |
| `preprocess.py` | Modul preprocessing yang dipakai notebook dan aplikasi; ditulis oleh notebook |
| `requirements.txt` | Dependensi Python |
| `synonyms.json` | Kamus sinonim (21 pasangan) |
| `raw_all.jsonl` | Seluruh halaman hasil crawling (1.497 halaman), sebelum penyaringan |
| `raw_corpus.json` | Korpus mentah terpilih: 503 cerpen unik (judul, isi, URL, sumber, kategori) |
| `clean_corpus.json` | Korpus hasil preprocessing, terpisah dari korpus mentah |
| `duplicates_report.csv` | Bukti duplicate checking: dokumen yang dibuang, yang dipertahankan, metode, dan skor kemiripan |
| `judgment_sheet.csv` | Pool dokumen untuk dinilai (urutan acak, kolom nilai kosong) |
| `judgment_sheet_filled.csv` | Penilaian relevansi manual (0/1), dipakai untuk semua konfigurasi |
| `pool_info.json` | Asal tiap dokumen pool: metode dan peringkat yang mengambilnya |
| `evaluasi_ringkasan.csv` | Rata-rata P@10, Recall, F1, dan MAP per konfigurasi |
| `evaluasi_per_query.csv` | Metrik per query untuk tiap konfigurasi |
| `evaluasi_grafik.png` | Grafik perbandingan metrik rata-rata |
| `evaluasi_ap_per_query.png` | Grafik AP per query |

## Reproduksi

Notebook dikembangkan di Google Colab. Notebook memuat berkas yang sudah ada (`raw_all.jsonl`, `raw_corpus.json`, `clean_corpus.json`, `judgment_sheet.csv`) dan tidak menghitung ulangnya, supaya nomor dokumen tetap sesuai dengan penilaian relevansi, yang mengacu pada urutan `raw_corpus.json`. Pembangunan ulang dari nol dapat dipicu dengan `FORCE_CRAWL`, `FORCE_CORPUS`, dan `FORCE_REPROCESS`, tetapi lembar penilaian relevansi harus dibuat dan dinilai ulang karena nomor dokumennya akan berubah.

Di luar Colab, notebook membutuhkan Elasticsearch 8.x di `localhost:9200`. Folder kerja ditentukan oleh variabel `WORK_DIR` pada bagian konfigurasi dan secara bawaan berupa direktori aktif.

## Dependensi

Lihat `requirements.txt`.

| Paket | Kegunaan |
|---|---|
| `elasticsearch==8.11.0` | klien Elasticsearch, versi sama dengan server |
| `PySastrawi` | stemming dan daftar stopword bahasa Indonesia |
| `requests`, `beautifulsoup4` | crawling dan parsing HTML |
| `pandas`, `numpy`, `scipy`, `scikit-learn`, `matplotlib` | pengolahan data, uji statistik, dedup TF-IDF, grafik |
| `streamlit` | antarmuka pencarian |

## Referensi

- Adriani, M., Asian, J., Nazief, B., Tahaghoghi, S. M. M., & Williams, H. E. (2007). Stemming Indonesian: A confix-stripping approach. *ACM Transactions on Asian Language Information Processing*, 6(4).
- Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to Information Retrieval*. Cambridge University Press.
- Robertson, S., & Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and Trends in Information Retrieval*, 3(4), 333–389.
- Rocchio, J. J. (1971). Relevance feedback in information retrieval. Dalam G. Salton (Ed.), *The SMART Retrieval System: Experiments in Automatic Document Processing* (hlm. 313–323). Prentice-Hall.
- Zhai, C., & Lafferty, J. (2004). A study of smoothing methods for language models applied to information retrieval. *ACM Transactions on Information Systems*, 22(2), 179–214.
- Elastic. *Elasticsearch Reference 8.11: Similarity module*. https://www.elastic.co/guide/en/elasticsearch/reference/8.11/index-modules-similarity.html
- Apache Lucene. Dokumentasi API kelas `BM25Similarity` dan `LMDirichletSimilarity`.
- PySastrawi, pustaka stemmer bahasa Indonesia. https://github.com/har07/PySastrawi
