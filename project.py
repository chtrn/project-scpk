import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="SPK Risiko Diabetes - AHP",
    layout="wide"
)

# ── Kriteria ──────────────────────────────────────────────────────────────────
KRITERIA = {
    "Glucose":                  "Glukosa",
    "BMI":                      "BMI",
    "Age":                      "Usia",
    "BloodPressure":            "Tekanan Darah",
    "DiabetesPedigreeFunction": "Riwayat Keluarga",
    "Insulin":                  "Insulin",
}
KEYS   = list(KRITERIA.keys())
LABELS = list(KRITERIA.values())

MAT_DEFAULT = np.array([
    [1,   3,   3,   5,   3,   7],
    [1/3, 1,   2,   3,   2,   5],
    [1/3, 1/2, 1,   2,   2,   5],
    [1/5, 1/3, 1/2, 1,   1/2, 3],
    [1/3, 1/2, 1/2, 2,   1,   4],
    [1/7, 1/5, 1/5, 1/3, 1/4, 1],
], dtype=float)

RI = {1:0, 2:0, 3:0.58, 4:0.90, 5:1.12,
      6:1.24, 7:1.32, 8:1.41, 9:1.45, 10:1.49}

# ── Fungsi AHP ────────────────────────────────────────────────────────────────
def hitung_bobot(mat):
    n     = mat.shape[0]
    norm  = mat / mat.sum(axis=0)
    bobot = norm.mean(axis=1)
    lam   = (mat @ bobot / bobot).mean()
    ci    = (lam - n) / (n - 1)
    cr    = ci / RI[n]
    return bobot, lam, ci, cr

def normalisasi(df):
    out = df[KEYS].copy().astype(float)
    for col in KEYS:
        mn, mx = out[col].min(), out[col].max()
        out[col] = (out[col] - mn) / (mx - mn) if mx > mn else 0.5
    return out

def level_risiko(skor, batas_r, batas_t):
    if skor < batas_r:
        return "Rendah"
    elif skor < batas_t:
        return "Sedang"
    else:
        return "Tinggi"

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load():
    return pd.read_csv("diabetes.csv")

df = load()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Pengaturan")

    st.subheader("Batas Klasifikasi")
    batas_rendah = st.slider("Batas Rendah–Sedang", 0.20, 0.55, 0.35, 0.01)
    batas_tinggi = st.slider("Batas Sedang–Tinggi", 0.40, 0.80, 0.60, 0.01)

    st.subheader("Edit bobot kriteria AHP")
    edit_mat = st.checkbox("Edit manual")

    if edit_mat:
        st.caption("Nilai 1–9: baris lebih penting dari kolom")
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

# ── Hitung AHP ────────────────────────────────────────────────────────────────
bobot, lam_max, ci, cr = hitung_bobot(mat)
bobot_dict = dict(zip(KEYS, bobot))

norm_df  = normalisasi(df)
skor     = norm_df[KEYS].values @ bobot
df_hasil = df.copy()
df_hasil["Skor AHP"] = skor
df_hasil["Risiko"]   = [level_risiko(s, batas_rendah, batas_tinggi) for s in skor]

# Ranking global
df_hasil = df_hasil.sort_values(
    "Skor AHP",
    ascending=False
).reset_index(drop=True)

df_hasil["Ranking"] = range(1, len(df_hasil) + 1)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("SPK Penentuan Tingkat Risiko Diabetes")
st.caption("Metode AHP (Analytical Hierarchy Process) | Dataset: Pima Indians Diabetes (768 pasien)")
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Ringkasan", "Bobot & Konsistensi", "Cek Pasien", "Data Lengkap"])


# ═══════════ TAB 1 – RINGKASAN ═══════════════════════════════════════════════
with tab1:
    jumlah = df_hasil["Risiko"].value_counts()
    total  = len(df_hasil)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Pasien",  total)
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
        ax.pie(sz, labels=lbl_pie,
               colors=[warna[l.split()[0]] for l in lbl_pie],
               autopct="%1.1f%%", startangle=90,
               wedgeprops={"edgecolor":"white","linewidth":1.5})
        ax.axis("equal")
        st.pyplot(fig)
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


# ═══════════ TAB 2 – BOBOT & KONSISTENSI ═════════════════════════════════════
with tab2:
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
        "Jenis": [
            "Benefit",
            "Benefit",
            "Benefit",
            "Benefit",
            "Benefit",
            "Benefit",
        ],
        "Keterangan": [
            "Semakin tinggi glukosa → semakin berisiko",
            "Semakin tinggi BMI → semakin berisiko",
            "Semakin tinggi usia → semakin berisiko",
            "Semakin tinggi tekanan darah → semakin berisiko",
            "Semakin tinggi riwayat keluarga → semakin berisiko",
            "Semakin tinggi insulin → semakin berisiko",
        ]
    })

    st.dataframe(
        jenis_df,
        use_container_width=True
    )

    st.subheader("Uji Konsistensi")
    d1, d2, d3 = st.columns(3)
    d1.metric("λ maks", f"{lam_max:.4f}")
    d2.metric("CI", f"{ci:.4f}")
    d3.metric("CR", f"{cr:.4f}")

    if cr <= 0.1:
        st.success(f"CR = {cr:.4f} ≤ 0.10 → Matriks konsisten.")
    else:
        st.error(f"CR = {cr:.4f} > 0.10 → Matriks tidak konsisten, perlu direvisi.")


# ═══════════ TAB 3 – CEK PASIEN ══════════════════════════════════════════════
with tab3:
    st.subheader("Penilaian Risiko Pasien")

    mode = st.radio("Sumber data:", ["Pilih dari dataset", "Input manual"], horizontal=True)

    if mode == "Pilih dari dataset":
        idx  = st.number_input("Nomor baris pasien", 0, len(df)-1, 0)
        baris = df.iloc[int(idx)]
    else:
        r1, r2, r3, r4 = st.columns(4)
        g   = r1.number_input("Glukosa",            0, 300, 120)
        bm  = r2.number_input("BMI",                0.0, 70.0, 28.0, step=0.1)
        age = r3.number_input("Usia",               10, 100, 35)
        bp  = r4.number_input("Tekanan Darah",      0, 200, 72)
        ins = r1.number_input("Insulin",            0, 900, 80)
        dpf = r2.number_input("Riwayat Keluarga",   0.0, 3.0, 0.5, step=0.01)
   
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
    level    = level_risiko(skor_ind, batas_rendah, batas_tinggi)

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
            "Kriteria":     LABELS,
            "Nilai Asli":   [float(baris[k]) for k in KEYS],
            "Nilai Normal": [norm_vals[k] for k in KEYS],
            "Bobot":        bobot,
            "Kontribusi":   [norm_vals[k] * bobot_dict[k] for k in KEYS],
        }).sort_values("Kontribusi", ascending=False).reset_index(drop=True)
        det_df.index += 1
        st.dataframe(
            det_df.style.format({
                "Nilai Asli":"{:.1f}", "Nilai Normal":"{:.3f}",
                "Bobot":"{:.4f}", "Kontribusi":"{:.4f}"
            }),
            use_container_width=True
        )


# ═══════════ TAB 4 – DATA LENGKAP ════════════════════════════════════════════
with tab4:

    st.subheader("Proses Ranking Risiko Diabetes")

    if st.button("Hitung Ranking Risiko Diabetes"):

        # ── TOP 10 PASIEN RISIKO TERTINGGI ──
        st.subheader("Top 10 Pasien Risiko Tertinggi")

        top10 = df_hasil.sort_values(
            "Skor AHP",
            ascending=False
        ).head(10).copy()

        top10["Ranking"] = range(1, len(top10) + 1)

        st.dataframe(
            top10[[
                "Ranking",
                "Glucose",
                "BMI",
                "Age",
                "Skor AHP",
                "Risiko"
            ]],
            use_container_width=True
        )

        st.bar_chart(top10.set_index("Ranking")["Skor AHP"])

        # ── DATA LENGKAP ──
        st.subheader("Hasil Penilaian Seluruh Pasien")

        f1, f2 = st.columns(2)

        filter_r = f1.multiselect(
            "Filter risiko:",
            ["Rendah", "Sedang", "Tinggi"],
            default=["Rendah", "Sedang", "Tinggi"]
        )

        filter_o = f2.selectbox(
            "Filter outcome:",
            ["Semua", "Positif (1)", "Negatif (0)"]
        )

        tampil = df_hasil[df_hasil["Risiko"].isin(filter_r)].copy()

        if filter_o == "Positif (1)":
            tampil = tampil[tampil["Outcome"] == 1]

        elif filter_o == "Negatif (0)":
            tampil = tampil[tampil["Outcome"] == 0]

        tampil = tampil.sort_values(
            "Skor AHP",
            ascending=False
        ).reset_index(drop=True)

        tampil.index += 1

        def warnai(val):
            if val == "Tinggi":
                return "background-color:#fde8e8"

            if val == "Sedang":
                return "background-color:#fff8e1"

            if val == "Rendah":
                return "background-color:#e8f5e9"

            return ""

        kolom = ["Risiko", "Skor AHP"] + KEYS + ["Outcome"]

        st.dataframe(
            tampil[kolom]
            .rename(columns=KRITERIA)
            .style
            .applymap(warnai, subset=["Risiko"])
            .format({
                "Skor AHP": "{:.4f}",
                "BMI": "{:.1f}",
                "DiabetesPedigreeFunction": "{:.3f}"
            }),
            use_container_width=True,
            height=420
        )

        st.caption(f"Menampilkan {len(tampil)} dari {total} pasien")

        # ── CROSSTAB ──
        st.subheader("Tabulasi Risiko vs Outcome Aktual")

        crosstab = pd.crosstab(
            df_hasil["Risiko"],
            df_hasil["Outcome"],
            rownames=["Risiko AHP"],
            colnames=["Outcome"]
        )

        st.dataframe(crosstab, use_container_width=True)

        # ── EVALUASI SISTEM ──
        st.subheader("Evaluasi Sistem")

        prediksi = df_hasil["Risiko"].apply(
            lambda x: 1 if x == "Tinggi" else 0
        )

        akurasi = (
            (prediksi == df_hasil["Outcome"]).mean()
        ) * 100

        st.metric(
            "Akurasi Prediksi Sederhana",
            f"{akurasi:.2f}%"
        )

        if akurasi >= 80:
            st.success("Sistem memiliki tingkat akurasi sangat baik.")

        elif akurasi >= 60:
            st.warning("Sistem memiliki akurasi cukup baik.")

        else:
            st.error("Sistem masih memiliki akurasi rendah.")


        # ── KESIMPULAN ──
        st.subheader("Kesimpulan")

        tertinggi = df_hasil.sort_values(
            "Skor AHP",
            ascending=False
        ).iloc[0]

        terendah = df_hasil.sort_values(
            "Skor AHP",
            ascending=True
        ).iloc[0]

        st.success(
            f"""
            Pasien dengan risiko diabetes tertinggi memiliki skor AHP
            sebesar {tertinggi['Skor AHP']:.4f}
            dengan kategori risiko {tertinggi['Risiko']}.
            """
        )

        st.info(
            f"""
            Pasien dengan risiko diabetes terendah memiliki skor AHP
            sebesar {terendah['Skor AHP']:.4f}
            dengan kategori risiko {terendah['Risiko']}.
            """
        )

        st.write(
            f"""
            Berdasarkan hasil perhitungan metode AHP,
            sebagian besar pasien berada pada kategori
            risiko {jumlah.idxmax()} sebanyak
            {jumlah.max()} pasien.
            """
        )