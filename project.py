import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pymysql
from pymysql.constants import FIELD_TYPE
import os

st.set_page_config(
    page_title="SPK Risiko Diabetes - AHP",
    layout="wide"
)

# Kriteria
KRITERIA = {
    "Glucose": "Glukosa",
    "BMI": "BMI",
    "Age": "Usia",
    "BloodPressure": "Tekanan Darah",
    "DiabetesPedigreeFunction": "Riwayat Keluarga",
    "Insulin": "Insulin",
}
KEYS   = list(KRITERIA.keys())
LABELS = list(KRITERIA.values())

MAT_DEFAULT = np.array([
    [1, 3, 3, 5, 3, 7],
    [1/3, 1, 2, 3, 2, 5],
    [1/3, 1/2, 1, 2, 2, 5],
    [1/5, 1/3, 1/2, 1, 1/2, 3],
    [1/3, 1/2, 1/2, 2, 1, 4],
    [1/7, 1/5, 1/5, 1/3, 1/4, 1],
], dtype=float)

RI = {1:0, 2:0, 3:0.58, 4:0.90, 5:1.12,
      6:1.24, 7:1.32, 8:1.41, 9:1.45, 10:1.49}

# ==========================================
# --- LOAD DATA UTAMA (MURNI HANYA CSV) ---
# ==========================================
@st.cache_data
def load_csv_data():
    nama_file_csv = "diabetes.csv" 
    if not os.path.exists(nama_file_csv) and os.path.exists("diabetes (1).csv"):
        nama_file_csv = "diabetes (1).csv"
        
    try:
        return pd.read_csv(nama_file_csv)
    except FileNotFoundError:
        return pd.DataFrame(columns=KEYS + ["Outcome"])

# Data untuk Tab 1, 2, 3, 4 murni hanya dari CSV
df = load_csv_data()

# ==========================================
# --- KONEKSI DATABASE MYSQL (XAMPP) -------
# ==========================================
def get_db_connection():
    """Membuka koneksi ke MySQL lokal (XAMPP) dengan konversi tipe data otomatis"""
    konversi_tipe = pymysql.converters.conversions.copy()
    # Float / Decimal
    konversi_tipe[FIELD_TYPE.FLOAT]      = float
    konversi_tipe[FIELD_TYPE.DOUBLE]     = float
    konversi_tipe[FIELD_TYPE.DECIMAL]    = float
    konversi_tipe[FIELD_TYPE.NEWDECIMAL] = float
    # Integer
    konversi_tipe[FIELD_TYPE.TINY]       = int
    konversi_tipe[FIELD_TYPE.SHORT]      = int
    konversi_tipe[FIELD_TYPE.LONG]       = int
    konversi_tipe[FIELD_TYPE.LONGLONG]   = int
    konversi_tipe[FIELD_TYPE.INT24]      = int
    # String / bytes
    konversi_tipe[FIELD_TYPE.VAR_STRING] = lambda x: x.decode("utf-8") if isinstance(x, bytes) else str(x)
    konversi_tipe[FIELD_TYPE.STRING]     = lambda x: x.decode("utf-8") if isinstance(x, bytes) else str(x)
    konversi_tipe[FIELD_TYPE.BLOB]       = lambda x: x.decode("utf-8") if isinstance(x, bytes) else str(x)

    return pymysql.connect(
        host="127.0.0.1",
        user="root",        
        password="",        
        database="diabetes", 
        charset="utf8mb4",
        conv=konversi_tipe,
        cursorclass=pymysql.cursors.DictCursor
    )


# --- FUNGSI PERHITUNGAN AHP ---
def hitung_bobot(mat):
    n     = mat.shape[0]
    norm  = mat / mat.sum(axis=0)
    bobot = norm.mean(axis=1)
    lam   = (mat @ bobot / bobot).mean()
    ci    = (lam - n) / (n - 1)
    cr    = ci / RI[n]
    return bobot, lam, ci, cr

def normalisasi(df_input):
    out = df_input[KEYS].copy().astype(float)
    for col in KEYS:
        mn, mx = out[col].min(), out[col].max()
        out[col] = (out[col] - mn) / (mx - mn) if mx > mn else 0.5
    return out

def level_risiko(skor_input, batas_r, batas_t):
    if skor_input < batas_r:
        return "Rendah"
    elif skor_input < batas_t:
        return "Sedang"
    else:
        return "Tinggi"

# Sidebar pengaturan
with st.sidebar:
    st.header("Pengaturan")

    st.subheader("Batas Klasifikasi")
    batas_rendah = st.slider("Batas Rendah–Sedang", 0.20, 0.55, 0.35, 0.01)
    batas_tinggi = st.slider("Batas Sedang–Tinggi", 0.40, 0.80, 0.60, 0.01)

    st.subheader("Edit bobot kriteria AHP")
    edit_mat = st.checkbox("Edit manual")

    if edit_mat:
        mat = np.ones((6, 6))
        for i in range(6):
            for j in range(i+1, 6):
                v = st.number_input(
                    f"{LABELS[i]} vs {LABELS[j]}", 1, 9, 3, key=f"m{i}{j}"
                )
                mat[i][j] = v
                mat[j][i] = 1 / v
    else:
        mat = MAT_DEFAULT.copy()

# Proses Kalkulasi Bobot AHP Global
bobot, lam_max, ci, cr = hitung_bobot(mat)
bobot_dict = dict(zip(KEYS, bobot))

# Perhitungan AHP Khusus Data CSV (Tab 1, 2, 3, 4)
if not df.empty:
    norm_df = normalisasi(df)
    skor = norm_df[KEYS].values @ bobot
    df_hasil = df.copy()
    df_hasil["Skor AHP"] = skor
    df_hasil["Risiko"] = [level_risiko(s, batas_rendah, batas_tinggi) for s in skor]

    # Ranking global
    df_hasil = df_hasil.sort_values(
        "Skor AHP",
        ascending=False
    ).reset_index(drop=True)
    df_hasil["Ranking"] = range(1, len(df_hasil) + 1)
else:
    df_hasil = pd.DataFrame()

# Header Utama Aplikasi
st.title("SPK Penentuan Tingkat Risiko Diabetes")
st.caption("Metode AHP (Analytical Hierarchy Process)")
st.divider()

# Definisi Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Ringkasan", 
    "Bobot & Konsistensi", 
    "Cek Pasien", 
    "Data Lengkap", 
    "Kelola Data Pasien (CRUD)"
])

# --- TABS 1 - RINGKASAN ---
with tab1:
    if df_hasil.empty:
        st.warning("Data dari file CSV kosong.")
    else:
        jumlah = df_hasil["Risiko"].value_counts()
        total  = len(df_hasil)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Pasien", total)
        c2.metric("Risiko Rendah", jumlah.get("Rendah", 0))
        c3.metric("Risiko Sedang", jumlah.get("Sedang", 0))
        c4.metric("Risiko Tinggi", jumlah.get("Tinggi", 0))

        st.write("")
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Distribusi Tingkat Risiko")
            fig, ax = plt.subplots()
            warna = {"Rendah":"#5cb85c", "Sedang":"#f0ad4e", "Tinggi":"#d9534f"}
            lbl_pie, sz = [], []
            for lv in ["Rendah","Sedang","Tinggi"]:
                n = jumlah.get(lv, 0)
                if n > 0:
                    lbl_pie.append(f"{lv} ({n})")
                    sz.append(n)
            if sz:
                ax.pie(sz, labels=lbl_pie,
                       colors=[warna[l.split()[0]] for l in lbl_pie],
                       autopct="%1.1f%%", startangle=90,
                       wedgeprops={"edgecolor":"white","linewidth":1.5})
                ax.axis("equal")
                st.pyplot(fig)
            else:
                st.info("Tidak ada data untuk grafik.")
            plt.close()

        with col_b:
            st.subheader("Sebaran Skor AHP")
            fig2, ax2 = plt.subplots()
            ax2.hist(skor, bins=25, color="#5b9bd5", edgecolor="white")
            ax2.axvline(batas_rendah, color="#5cb85c", linewidth=2,
                        linestyle="--", label=f"Batas Rendah ({batas_rendah:.2f})")
            ax2.axvline(batas_tinggi, color="#d9534f", linewidth=2,
                        linestyle="--", label=f"Batas Tinggi ({batas_tinggi:.2f})")
            ax2.set_xlabel("Skor")
            ax2.set_ylabel("Jumlah Pasien")
            ax2.legend()
            st.pyplot(fig2)
            plt.close()

        st.subheader("Bobot Kriteria")
        fig3, ax3 = plt.subplots(figsize=(8, 3))
        idx_sort = np.argsort(bobot)
        ax3.barh([LABELS[i] for i in idx_sort], bobot[idx_sort], color="#5b9bd5")
        ax3.set_xlabel("Bobot Prioritas")
        for bar, val in zip(ax3.patches, bobot[idx_sort]):
            ax3.text(val + 0.003, bar.get_y() + bar.get_height()/2,
                     f"{val:.4f}", va="center", fontsize=8)
        st.pyplot(fig3)
        plt.close()


# --- TABS 2 - BOBOT DAN KONSISTENSI ---
with tab2:
    if df_hasil.empty:
        st.warning("Data tidak tersedia.")
    else:
        st.subheader("Matriks Perbandingan Berpasangan")
        mat_df = pd.DataFrame(mat, index=LABELS, columns=LABELS)

        def sorot_diagonal(s):
            row_idx = LABELS.index(s.name)
            return ["background-color: #dce9f7" if row_idx == j else ""
                    for j, _ in enumerate(s)]

        st.dataframe(
            mat_df.style.format("{:.3f}").apply(sorot_diagonal, axis=1),
            use_container_width=True
        )

        st.subheader("Bobot Prioritas")
        bobot_df = pd.DataFrame({
            "Kriteria":    LABELS,
            "Bobot":       bobot,
            "Persentase":  [f"{b*100:.2f}%" for b in bobot]
        }).sort_values("Bobot", ascending=False).reset_index(drop=True)
        bobot_df.index += 1
        st.dataframe(
            bobot_df.style.format({"Bobot":"{:.4f}"}),
            use_container_width=True
        )

        st.subheader("Jenis Kriteria (Benefit / Cost)")
        jenis_df = pd.DataFrame({
            "Kriteria": LABELS,
            "Jenis": ["Benefit"] * 6,
            "Keterangan": [f"Semakin tinggi {l.lower()} → semakin berisiko" for l in LABELS]
        })
        st.dataframe(jenis_df, use_container_width=True)

        st.subheader("Uji Konsistensi")
        d1, d2, d3 = st.columns(3)
        d1.metric("λ maks", f"{lam_max:.4f}")
        d2.metric("CI", f"{ci:.4f}")
        d3.metric("CR", f"{cr:.4f}")

        if cr <= 0.1:
            st.success(f"CR = {cr:.4f} ≤ 0.10 → Matriks konsisten.")
        else:
            st.error(f"CR = {cr:.4f} > 0.10 → Matriks tidak konsisten, perlu direvisi.")


# --- TABS 3 - CEK PASIEN ---
with tab3:
    if df_hasil.empty:
        st.warning("Data tidak tersedia.")
    else:
        st.subheader("Penilaian Risiko Pasien (Data CSV)")
        mode = st.radio("Sumber data:", ["Pilih dari dataset", "Input manual"], horizontal=True)

        if mode == "Pilih dari dataset":
            idx  = st.number_input("Nomor baris pasien", 0, len(df)-1, 0)
            baris = df.iloc[int(idx)]
        else:
            r1, r2, r3, r4 = st.columns(4)
            g   = r1.number_input("Glukosa", 0, 300, 120)
            bm  = r2.number_input("BMI", 0.0, 70.0, 28.0, step=0.1)
            age = r3.number_input("Usia", 10, 100, 35)
            bp  = r4.number_input("Tekanan Darah", 0, 200, 72)
            ins = r1.number_input("Insulin", 0, 900, 80)
            dpf = r2.number_input("Riwayat Keluarga", 0.0, 3.0, 0.5, step=0.01)
       
            baris = pd.Series({
                "Glucose": g, "BloodPressure": bp,
                "Insulin": ins, "BMI": bm,
                "DiabetesPedigreeFunction": dpf, "Age": age
            })

        norm_vals = {}
        for col in KEYS:
            mn = df[col].min(); mx = df[col].max()
            v  = float(baris[col])
            norm_vals[col] = (v - mn) / (mx - mn) if mx > mn else 0.5

        skor_ind = sum(norm_vals[k] * bobot_dict[k] for k in KEYS)
        level = level_risiko(skor_ind, batas_rendah, batas_tinggi)

        st.divider()
        cr1, cr2 = st.columns([1, 2])

        with cr1:
            st.metric("Skor AHP", f"{skor_ind:.4f}")
            if level == "Rendah":
                st.info("Risiko rendah. Tetap jaga pola makan dan olahraga.")
            elif level == "Sedang":
                st.warning("Risiko sedang. Disarankan konsultasi ke dokter.")
            else:
                st.error("Risiko tinggi. Segera periksa ke dokter.")

        with cr2:
            st.write("**Kontribusi tiap kriteria:**")
            det_df = pd.DataFrame({
                "Kriteria": LABELS,
                "Nilai Asli": [float(baris[k]) for k in KEYS],
                "Nilai Normalisasi": [norm_vals[k] for k in KEYS],
                "Bobot": bobot,
                "Kontribusi": [norm_vals[k] * bobot_dict[k] for k in KEYS],
            }).sort_values("Kontribusi", ascending=False).reset_index(drop=True)
            det_df.index += 1
            st.dataframe(
                det_df.style.format({
                    "Nilai Asli":"{:.1f}", "Nilai Normalisasi":"{:.3f}",
                    "Bobot":"{:.4f}", "Kontribusi":"{:.4f}"
                }),
                use_container_width=True
            )


# --- TABS 4 - DATA LENGKAP ---
with tab4:
    if df_hasil.empty:
        st.warning("Data tidak tersedia.")
    else:
        st.subheader("Proses Ranking Risiko Diabetes (Data CSV)")
        st.subheader("Top 10 Pasien Risiko Tertinggi")

        top10 = df_hasil.sort_values("Skor AHP", ascending=False).head(10).copy()
        top10["Ranking"] = range(1, len(top10) + 1)

        st.dataframe(
            top10[["Ranking", "Glucose", "BMI", "Age", "Skor AHP", "Risiko"]],
            use_container_width=True
        )

        st.subheader("Hasil Penilaian Seluruh Pasien")
        f1, f2 = st.columns(2)

        filter_r = f1.multiselect(
            "Filter risiko:", ["Rendah", "Sedang", "Tinggi"], default=["Rendah", "Sedang", "Tinggi"]
        )
        filter_o = f2.selectbox("Filter outcome:", ["Semua", "Positif (1)", "Negatif (0)"])

        tampil = df_hasil[df_hasil["Risiko"].isin(filter_r)].copy()

        if "Outcome" in tampil.columns:
            if filter_o == "Positif (1)":
                tampil = tampil[tampil["Outcome"] == 1]
            elif filter_o == "Negatif (0)":
                tampil = tampil[tampil["Outcome"] == 0]

        tampil = tampil.sort_values("Skor AHP", ascending=False).reset_index(drop=True)
        tampil.index += 1

        def warnai(val):
            if val == "Tinggi": return "background-color:#fde8e8"
            if val == "Sedang": return "background-color:#fff8e1"
            if val == "Rendah": return "background-color:#e8f5e9"
            return ""

        kolom = ["Risiko", "Skor AHP"] + KEYS + (["Outcome"] if "Outcome" in tampil.columns else [])

        st.dataframe(
            tampil[kolom].rename(columns=KRITERIA).style.map(warnai, subset=["Risiko"])
            .format({
                "Skor AHP": "{:.4f}", "BMI": "{:.1f}", "DiabetesPedigreeFunction": "{:.3f}"
            }),
            use_container_width=True, height=420
        )
        st.caption(f"Menampilkan {len(tampil)} dari {len(df_hasil)} pasien")

        if "Outcome" in df_hasil.columns and df_hasil["Outcome"].nunique() > 0:
            st.subheader("Tabulasi Risiko vs Outcome Aktual")
            crosstab = pd.crosstab(df_hasil["Risiko"], df_hasil["Outcome"], rownames=["Risiko AHP"], colnames=["Outcome"])
            st.dataframe(crosstab, use_container_width=True)

        st.subheader("Kesimpulan")
        tertinggi = df_hasil.sort_values("Skor AHP", ascending=False).iloc[0]
        terendah = df_hasil.sort_values("Skor AHP", ascending=True).iloc[0]

        st.success(f"Pasien dengan risiko diabetes tertinggi memiliki skor AHP sebesar {tertinggi['Skor AHP']:.4f} dengan kategori risiko {tertinggi['Risiko']}.")
        st.info(f"Pasien dengan risiko diabetes terendah memiliki skor AHP sebesar {terendah['Skor AHP']:.4f} dengan kategori risiko {terendah['Risiko']}.")
        st.write(f"Berdasarkan hasil perhitungan metode AHP, sebagian besar pasien berada pada kategori risiko {jumlah.idxmax()} sebanyak {jumlah.max()} pasien.")


# --- TABS 5 - KELOLA DATA PASIEN (CRUD + LIVE ANALISIS AHP) ---
with tab5:
    st.subheader("Pengelolaan Data Pasien Database")
    st.caption("Kelola data disertai kalkulasi skor AHP & tingkat risiko pasien secara real-time.")

    crud_mode = st.radio("Pilih Operasi CRUD Database:", ["Lihat Data (Read)", "Tambah Data (Create)", "Ubah Data (Update)", "Hapus Data (Delete)"], horizontal=True)
    st.divider()

    def warnai_crud(val):
        if val == "Tinggi": return "background-color:#fde8e8"
        if val == "Sedang": return "background-color:#fff8e1"
        if val == "Rendah": return "background-color:#e8f5e9"
        return ""

    COL_RENAME = {
        "id": "id",
        "skor_ahp": "Skor AHP",
        "risiko": "Risiko",
        "glucose": "Glucose",
        "bmi": "BMI",
        "age": "Age",
        "bloodpressure": "BloodPressure",
        "diabetespedigreefunction": "DiabetesPedigreeFunction",
        "insulin": "Insulin",
        "outcome": "Outcome",
    }

    def hitung_ahp(df):
        """Hitung skor AHP dan risiko dari dataframe, return df dengan kolom tambahan."""
        for col in KEYS:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        norm = normalisasi(df)
        skor = norm[KEYS].values @ bobot
        df["Skor AHP"] = skor
        df["Risiko"]   = [level_risiko(s, batas_rendah, batas_tinggi) for s in skor]
        return df

    def fetch_db():
        """Ambil data dari MySQL, rename kolom agar cocok dengan KEYS."""
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pasien ORDER BY id")
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns=COL_RENAME)
        return df

    # ── 1. READ ──────────────────────────────────────────────────────────────
    if crud_mode == "Lihat Data (Read)":
        st.markdown("**Data Tersimpan di database + Hasil SPK AHP:**")
        try:
            df_db = fetch_db()
            if df_db.empty:
                st.info("Database kosong. Gunakan menu Tambah Data.")
            else:
                # Pastikan kolom numerik
                for col in KEYS:
                    df_db[col] = pd.to_numeric(df_db[col], errors="coerce").fillna(0.0)
                df_db["Skor AHP"] = pd.to_numeric(df_db["Skor AHP"], errors="coerce")
                # Baris lama yang belum punya skor: hitung ulang
                mask_null = df_db["Skor AHP"].isna()
                if mask_null.any():
                    norm_tmp = normalisasi(df_db[mask_null].copy())
                    df_db.loc[mask_null, "Skor AHP"] = norm_tmp[KEYS].values @ bobot
                    df_db.loc[mask_null, "Risiko"]   = [level_risiko(s, batas_rendah, batas_tinggi) for s in df_db.loc[mask_null, "Skor AHP"]]

                kolom_susun = ["id", "Skor AHP", "Risiko"] + KEYS
                st.dataframe(
                    df_db[kolom_susun].style.applymap(warnai_crud, subset=["Risiko"])
                    .format({"Skor AHP": "{:.4f}", "BMI": "{:.1f}", "DiabetesPedigreeFunction": "{:.3f}"}),
                    use_container_width=True
                )
                st.caption(f"Total {len(df_db)} baris dari database.")
        except Exception as e:
            st.error(f"Gagal membaca data: {e}")

    # ── 2. CREATE ─────────────────────────────────────────────────────────────
    elif crud_mode == "Tambah Data (Create)":
        st.markdown("**Form Tambah Data Baru**")
        with st.form("form_tambah", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            g_add   = c1.number_input("Glukosa",        0,   300, 120)
            bp_add  = c2.number_input("Tekanan Darah",  0,   200,  70)
            ins_add = c3.number_input("Insulin",        0,   900,  80)
            c4, c5, c6 = st.columns(3)
            bm_add  = c4.number_input("BMI",            0.0, 70.0, 25.0, step=0.1)
            dpf_add = c5.number_input("DPF (Riwayat Keluarga)", 0.0, 3.0, 0.5, step=0.01)
            age_add = c6.number_input("Usia",           1,   120,  30)
            if st.form_submit_button("Simpan ke database"):
                try:
                    # Hitung skor AHP dari input sebelum disimpan
                    df_temp = pd.DataFrame([{
                        "Glucose": g_add, "BMI": bm_add, "Age": age_add,
                        "BloodPressure": bp_add, "DiabetesPedigreeFunction": dpf_add,
                        "Insulin": ins_add
                    }])
                    df_temp = hitung_ahp(df_temp)
                    skor_add  = float(df_temp["Skor AHP"].iloc[0])
                    risiko_add = str(df_temp["Risiko"].iloc[0])

                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO pasien (skor_ahp, risiko, glucose, bmi, age, bloodpressure, diabetespedigreefunction, insulin) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (skor_add, risiko_add, g_add, bm_add, age_add, bp_add, dpf_add, ins_add)
                        )
                    conn.commit()
                    conn.close()
                    st.success(f"Data berhasil disimpan! Skor AHP: {skor_add:.4f} | Risiko: {risiko_add}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")

    # ── 3. UPDATE ─────────────────────────────────────────────────────────────
    elif crud_mode == "Ubah Data (Update)":
        st.markdown("**Form Edit Data Pasien**")
        try:
            df_db = fetch_db()
            if df_db.empty:
                st.info("Tidak ada data untuk diubah.")
            else:
                st.dataframe(df_db, use_container_width=True)
                id_edit  = st.number_input("ID Pasien yang ingin diedit:", min_value=int(df_db["id"].min()), max_value=int(df_db["id"].max()))
                row_edit = df_db[df_db["id"] == id_edit]
                if not row_edit.empty:
                    r = row_edit.iloc[0]
                    with st.form("form_edit"):
                        c1, c2, c3 = st.columns(3)
                        g_up   = c1.number_input("Glukosa",       0,   300, int(r["Glucose"]))
                        bp_up  = c2.number_input("Tekanan Darah", 0,   200, int(r["BloodPressure"]))
                        ins_up = c3.number_input("Insulin",       0,   900, int(r["Insulin"]))
                        c4, c5, c6 = st.columns(3)
                        bm_up  = c4.number_input("BMI",           0.0, 70.0,  float(r["BMI"]),                      step=0.1)
                        dpf_up = c5.number_input("DPF",           0.0,  3.0,  float(r["DiabetesPedigreeFunction"]), step=0.01)
                        age_up = c6.number_input("Usia",          1,   120,   int(r["Age"]))
                        if st.form_submit_button("Perbarui Data"):
                            # Hitung ulang skor AHP dari nilai baru
                            df_temp = pd.DataFrame([{
                                "Glucose": g_up, "BMI": bm_up, "Age": age_up,
                                "BloodPressure": bp_up, "DiabetesPedigreeFunction": dpf_up,
                                "Insulin": ins_up
                            }])
                            df_temp = hitung_ahp(df_temp)
                            skor_up   = float(df_temp["Skor AHP"].iloc[0])
                            risiko_up = str(df_temp["Risiko"].iloc[0])

                            conn = get_db_connection()
                            with conn.cursor() as cur:
                                cur.execute(
                                    "UPDATE pasien SET skor_ahp=%s, risiko=%s, glucose=%s, bmi=%s, age=%s, "
                                    "bloodpressure=%s, diabetespedigreefunction=%s, insulin=%s WHERE id=%s",
                                    (skor_up, risiko_up, g_up, bm_up, age_up, bp_up, dpf_up, ins_up, id_edit)
                                )
                            conn.commit()
                            conn.close()
                            st.success(f"Data ID {id_edit} diperbarui! Skor AHP: {skor_up:.4f} | Risiko: {risiko_up}")
                            st.rerun()
        except Exception as e:
            st.error(f"Gagal memproses edit: {e}")

    # ── 4. DELETE ─────────────────────────────────────────────────────────────
    elif crud_mode == "Hapus Data (Delete)":
        st.markdown("**Hapus Data Pasien**")
        try:
            df_db = fetch_db()
            if df_db.empty:
                st.info("Tidak ada data untuk dihapus.")
            else:
                st.dataframe(df_db, use_container_width=True)
                id_del = st.number_input("ID Pasien yang ingin dihapus:", min_value=int(df_db["id"].min()), max_value=int(df_db["id"].max()))
                st.warning(f"Yakin ingin menghapus data ID {id_del}?")
                if st.button("Hapus Permanen", type="primary"):
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM pasien WHERE id=%s", (id_del,))
                    conn.commit()
                    conn.close()
                    st.success(f"Data ID {id_del} berhasil dihapus!")
                    st.rerun()
        except Exception as e:
            st.error(f"Gagal menghapus data: {e}")