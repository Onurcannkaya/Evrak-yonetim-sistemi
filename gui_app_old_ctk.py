import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import threading
import os
import json
import webbrowser
from datetime import datetime
from pathlib import Path

from document_processor import DocumentProcessor
from database_manager import DatabaseManager
from city_guide_client import CityGuideClient

# Tema Ayarları
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sivas Belediyesi — Akıllı Evrak Sistemi v5.0")
        self.geometry("1500x900")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # footer row

        # Durum değişkenleri
        self.processor = None
        self.db_manager = None
        self.city_guide = None
        self.current_file = None
        self.current_data = None
        self.all_results = []
        self.current_page_idx = 0
        self.pdf_page_images = []

        # ══ Ana Tabview ══
        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_process = self.tabview.add("📄 Evrak İşle")
        self.tab_search = self.tabview.add("🔍 Evrak Arama")
        self.tab_dashboard = self.tabview.add("📊 Dashboard")

        self._build_process_tab(self.tab_process)
        self._build_search_tab(self.tab_search)
        self._build_dashboard_tab(self.tab_dashboard)

        # ══ Footer Bar ══
        footer = ctk.CTkFrame(self, height=32, corner_radius=0,
                              fg_color="#1a1a2e")
        footer.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        footer.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(footer,
                     text="🏛️ Sivas Belediyesi — Akıllı Şehir ve Kent Bilgi Sistemleri Müdürlüğü",
                     font=("Arial", 11), text_color="#8892b0",
                     anchor="w").grid(row=0, column=0, padx=15, pady=4)
        ctk.CTkLabel(footer,
                     text="v5.0 © 2025",
                     font=("Arial", 10), text_color="#5a6178",
                     anchor="e").grid(row=0, column=1, padx=15, pady=4, sticky="e")

        self.after(100, self._load_services)

    # ══════════════════════════════════════════════════════════════════════════
    #  SERVİSLER
    # ══════════════════════════════════════════════════════════════════════════
    def _load_services(self):
        def _load():
            try:
                self.processor = DocumentProcessor()
                self.db_manager = DatabaseManager()
                self.city_guide = CityGuideClient()
                self.after(0, lambda: self.status_label.configure(
                    text="✅ Sistem Hazır", text_color="green"))
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(
                    text="❌ Servis Hatası", text_color="red"))
                self.after(0, lambda: messagebox.showerror(
                    "Hata", f"Servisler başlatılamadı:\n{e}"))
        threading.Thread(target=_load, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  SEKME 1 — EVRAK İŞLE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_process_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # ── Sol Panel ──
        sidebar = ctk.CTkFrame(parent, width=220, corner_radius=8)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        sidebar.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(sidebar, text="📄 EVRAK MATİK",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=15, pady=(15, 3))
        ctk.CTkLabel(sidebar, text="v5.0 — Profesyonel",
                     font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=1, column=0, padx=15, pady=(0, 10))

        self.btn_load = ctk.CTkButton(sidebar, text="📂 Dosya Seç",
                                       command=self.load_file)
        self.btn_load.grid(row=2, column=0, padx=15, pady=6)

        self.btn_process = ctk.CTkButton(sidebar, text="🔍 Analiz Et",
                                          command=self.start_processing,
                                          state="disabled")
        self.btn_process.grid(row=3, column=0, padx=15, pady=6)

        self.btn_save = ctk.CTkButton(sidebar, text="💾 Kaydet",
                                       command=self.save_results,
                                       state="disabled", fg_color="#2d8a4e")
        self.btn_save.grid(row=4, column=0, padx=15, pady=6)

        self.btn_save_all = ctk.CTkButton(sidebar, text="📦 Tümünü Kaydet",
                                          command=self.save_all_results,
                                          state="disabled", fg_color="#c77a10")
        self.btn_save_all.grid(row=5, column=0, padx=15, pady=6)

        pf = ctk.CTkFrame(sidebar, fg_color="transparent")
        pf.grid(row=6, column=0, padx=15, pady=(10, 3), sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(pf)
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)
        self.progress_label = ctk.CTkLabel(pf, text="", font=("Arial", 10))
        self.progress_label.pack(pady=2)

        self.status_label = ctk.CTkLabel(sidebar, text="⏳ Yükleniyor…",
                                          font=("Arial", 11))
        self.status_label.grid(row=9, column=0, padx=15, pady=15)

        # ── Orta — Görüntü + Metin ──
        mid = ctk.CTkFrame(parent, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="nsew")
        mid.grid_rowconfigure(1, weight=1)
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=1)

        self.image_frame = ctk.CTkScrollableFrame(mid, label_text="Orijinal Belge")
        self.image_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))
        self.image_label = ctk.CTkLabel(self.image_frame, text="Resim yüklenmedi")
        self.image_label.pack(expand=True, fill="both")

        nav = ctk.CTkFrame(mid, height=35, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="ew", pady=(3, 0))
        self.btn_prev = ctk.CTkButton(nav, text="◀", width=60,
                                       command=self.prev_page, state="disabled")
        self.btn_prev.pack(side="left", padx=3)
        self.page_info_label = ctk.CTkLabel(nav, text="",
                                             font=("Arial", 12, "bold"))
        self.page_info_label.pack(side="left", expand=True)
        self.btn_next = ctk.CTkButton(nav, text="▶", width=60,
                                       command=self.next_page, state="disabled")
        self.btn_next.pack(side="right", padx=3)

        self.text_editor = ctk.CTkTextbox(mid, font=("Consolas", 12), wrap="word")
        self.text_editor.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(5, 0))
        self.text_editor.insert("0.0", "OCR sonucu burada görünecek…")

        # ── Sağ — Detay Paneli ──
        detail = ctk.CTkScrollableFrame(parent, width=240, corner_radius=8)
        detail.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(detail, text="📋 Belge Bilgileri",
                     font=("Arial", 14, "bold")).pack(pady=(10, 8))

        self.entries = {}
        for field in ["Belge Tipi", "Tarih", "Ada", "Parsel", "Mahalle",
                       "Sokak", "Kapı No", "Karar No", "Konu"]:
            f = ctk.CTkFrame(detail, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(f, text=field, anchor="w",
                         font=("Arial", 10, "bold")).pack(fill="x")
            e = ctk.CTkEntry(f)
            e.pack(fill="x")
            self.entries[field] = e

        ctk.CTkFrame(detail, height=2, fg_color="gray40").pack(fill="x", padx=8, pady=6)
        self.lbl_conf = ctk.CTkLabel(detail, text="OCR Güven: —", font=("Arial", 12))
        self.lbl_conf.pack(pady=2)
        self.lbl_engine = ctk.CTkLabel(detail, text="Motor: —",
                                        font=("Arial", 10, "italic"))
        self.lbl_engine.pack(pady=2)
        ctk.CTkFrame(detail, height=2, fg_color="gray40").pack(fill="x", padx=8, pady=6)
        self.lbl_validation = ctk.CTkLabel(detail, text="Kent Rehberi: —",
                                            font=("Arial", 11), wraplength=200)
        self.lbl_validation.pack(pady=2)
        ctk.CTkFrame(detail, height=2, fg_color="gray40").pack(fill="x", padx=8, pady=6)
        self.lbl_file_info = ctk.CTkLabel(detail, text="Dosya: —",
                                           font=("Arial", 9), text_color="gray",
                                           wraplength=200)
        self.lbl_file_info.pack(pady=3)

    # ══════════════════════════════════════════════════════════════════════════
    #  SEKME 2 — EVRAK ARAMA (Gelişmiş)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_search_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # ── Üst — Filtreler ──
        filter_frame = ctk.CTkFrame(parent, corner_radius=8)
        filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(filter_frame, text="🔍 Gelişmiş Evrak Arama",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, columnspan=8, padx=15, pady=(8, 5), sticky="w")

        # Satır 1: Ada, Parsel, Mahalle, Sokak
        row1 = ctk.CTkFrame(filter_frame, fg_color="transparent")
        row1.grid(row=1, column=0, columnspan=8, padx=10, pady=2, sticky="ew")

        self._search_fields = {}
        for label, key, w, ph in [
            ("Ada:", "ada", 80, "örn: 150"),
            ("Parsel:", "parsel", 80, "örn: 3"),
            ("Mahalle:", "mahalle", 120, "opsiyonel"),
            ("Sokak:", "sokak", 140, "cadde/sokak adı"),
        ]:
            ctk.CTkLabel(row1, text=label, font=("Arial", 11)).pack(side="left", padx=(8, 3))
            e = ctk.CTkEntry(row1, width=w, placeholder_text=ph)
            e.pack(side="left", padx=2)
            e.bind("<Return>", lambda ev: self._do_advanced_search())
            self._search_fields[key] = e

        # Satır 2: Konu, Belge Tipi, Durum, Tarih
        row2 = ctk.CTkFrame(filter_frame, fg_color="transparent")
        row2.grid(row=2, column=0, columnspan=8, padx=10, pady=2, sticky="ew")

        ctk.CTkLabel(row2, text="Konu:", font=("Arial", 11)).pack(side="left", padx=(8, 3))
        e = ctk.CTkEntry(row2, width=120, placeholder_text="imar, ruhsat…")
        e.pack(side="left", padx=2)
        e.bind("<Return>", lambda ev: self._do_advanced_search())
        self._search_fields["konu"] = e

        ctk.CTkLabel(row2, text="Tip:", font=("Arial", 11)).pack(side="left", padx=(8, 3))
        self._search_type = ctk.CTkComboBox(
            row2, width=120, values=["Tümü", "meclis_karari", "tapu", "general"])
        self._search_type.pack(side="left", padx=2)
        self._search_type.set("Tümü")

        ctk.CTkLabel(row2, text="Durum:", font=("Arial", 11)).pack(side="left", padx=(8, 3))
        self._search_status = ctk.CTkComboBox(
            row2, width=110, values=["Tümü", "approved", "needs_review", "failed"])
        self._search_status.pack(side="left", padx=2)
        self._search_status.set("Tümü")

        ctk.CTkLabel(row2, text="Tarih:", font=("Arial", 11)).pack(side="left", padx=(8, 3))
        self._search_date_from = ctk.CTkEntry(row2, width=90, placeholder_text="YYYY-MM-DD")
        self._search_date_from.pack(side="left", padx=2)
        ctk.CTkLabel(row2, text="—", font=("Arial", 11)).pack(side="left")
        self._search_date_to = ctk.CTkEntry(row2, width=90, placeholder_text="YYYY-MM-DD")
        self._search_date_to.pack(side="left", padx=2)

        # Satır 3: Serbest metin + butonlar
        row3 = ctk.CTkFrame(filter_frame, fg_color="transparent")
        row3.grid(row=3, column=0, columnspan=8, padx=10, pady=(2, 8), sticky="ew")

        ctk.CTkLabel(row3, text="Metin:", font=("Arial", 11)).pack(side="left", padx=(8, 3))
        self._search_freetext = ctk.CTkEntry(row3, width=200,
                                              placeholder_text="OCR metninde ara…")
        self._search_freetext.pack(side="left", padx=2)
        self._search_freetext.bind("<Return>", lambda ev: self._do_advanced_search())

        ctk.CTkButton(row3, text="🔍 Ara", command=self._do_advanced_search,
                       width=80, fg_color="#1a73e8").pack(side="left", padx=(15, 5))
        ctk.CTkButton(row3, text="🗑️ Temizle", command=self._clear_search,
                       width=80, fg_color="#4a4a4a").pack(side="left", padx=3)
        self.btn_map = ctk.CTkButton(row3, text="🗺️ Haritada Göster",
                                      command=self._open_map, width=130,
                                      fg_color="#0d7377", state="disabled")
        self.btn_map.pack(side="left", padx=5)

        # ── Sol — Sonuç Listesi ──
        list_frame = ctk.CTkFrame(parent, corner_radius=8)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.search_result_label = ctk.CTkLabel(
            list_frame, text="Filtreleri doldurup 'Ara' butonuna basın",
            font=("Arial", 11), text_color="gray")
        self.search_result_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        tree_container = ctk.CTkFrame(list_frame, fg_color="transparent")
        tree_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white",
                         fieldbackground="#2b2b2b", rowheight=28,
                         font=("Arial", 10))
        style.configure("Treeview.Heading", background="#3b3b3b",
                         foreground="white", font=("Arial", 10, "bold"))
        style.map("Treeview", background=[("selected", "#1a73e8")])

        cols = ("id", "dosya", "tip", "tarih", "mahalle", "ada", "parsel",
                "sokak", "konu", "durum")
        self.result_tree = ttk.Treeview(tree_container, columns=cols,
                                         show="headings", height=15)
        headers = {"id": ("ID", 35), "dosya": ("Dosya", 150), "tip": ("Tip", 90),
                   "tarih": ("Tarih", 80), "mahalle": ("Mahalle", 90),
                   "ada": ("Ada", 50), "parsel": ("Parsel", 50),
                   "sokak": ("Sokak", 120), "konu": ("Konu", 130),
                   "durum": ("Durum", 80)}
        for c, (h, w) in headers.items():
            self.result_tree.heading(c, text=h)
            self.result_tree.column(c, width=w, anchor="center" if w < 60 else "w")

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical",
                                   command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.result_tree.bind("<<TreeviewSelect>>", self._on_result_select)

        # ── Sağ — Evrak Detayı ──
        detail_frame = ctk.CTkScrollableFrame(parent, width=340, corner_radius=8)
        detail_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        ctk.CTkLabel(detail_frame, text="📋 Evrak Detayı",
                     font=("Arial", 14, "bold")).pack(pady=(10, 8))

        self.search_detail_entries = {}
        for field in ["ID", "Dosya", "Belge Tipi", "Tarih", "Mahalle",
                       "Ada", "Parsel", "Sokak", "Kapı No", "Karar No",
                       "Konu", "Durum", "OCR Güven"]:
            f = ctk.CTkFrame(detail_frame, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(f, text=field, anchor="w",
                         font=("Arial", 10, "bold")).pack(fill="x")
            e = ctk.CTkEntry(f, state="disabled")
            e.pack(fill="x")
            self.search_detail_entries[field] = e

        ctk.CTkFrame(detail_frame, height=2, fg_color="gray40").pack(
            fill="x", padx=8, pady=6)

        ctk.CTkLabel(detail_frame, text="OCR Metni",
                     font=("Arial", 11, "bold")).pack(anchor="w", padx=8)
        self.search_text_box = ctk.CTkTextbox(detail_frame,
                                               font=("Consolas", 11),
                                               height=200, wrap="word")
        self.search_text_box.pack(fill="both", expand=True, padx=8, pady=(3, 8))

        btn_frame = ctk.CTkFrame(detail_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(5, 10))
        self.btn_open_file = ctk.CTkButton(
            btn_frame, text="📂 Dosyayı Aç", command=self._open_selected_file,
            state="disabled", fg_color="#4a4a4a", width=120)
        self.btn_open_file.pack(side="left", padx=3)
        self.btn_detail_map = ctk.CTkButton(
            btn_frame, text="🗺️ Haritada Göster", command=self._open_map_for_selected,
            state="disabled", fg_color="#0d7377", width=130)
        self.btn_detail_map.pack(side="left", padx=3)

    # ══════════════════════════════════════════════════════════════════════════
    #  SEKME 3 — DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    def _build_dashboard_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Başlık
        header = ctk.CTkFrame(parent, corner_radius=8)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(header, text="📊 Sistem İstatistikleri",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left", padx=15, pady=10)
        ctk.CTkButton(header, text="🔄 Yenile",
                       command=self._refresh_dashboard, width=100).pack(
            side="right", padx=15, pady=10)

        # ── Sol — Sayısal Kartlar ──
        cards = ctk.CTkFrame(parent, corner_radius=8)
        cards.grid(row=1, column=0, sticky="nsew", padx=(0, 5))

        self.dash_cards = {}
        card_defs = [
            ("total", "📄 Toplam Belge", "#1a73e8"),
            ("approved", "✅ Onaylanan", "#2d8a4e"),
            ("review", "⚠️ İnceleme Bekleyen", "#c77a10"),
            ("failed", "❌ Başarısız", "#dc2626"),
            ("confidence", "🎯 Ortalama Güven", "#7c3aed"),
            ("parcels", "📍 Benzersiz Parsel", "#0d7377"),
            ("streets", "🛣️ Benzersiz Sokak", "#6b7280"),
        ]
        for i, (key, title, color) in enumerate(card_defs):
            cf = ctk.CTkFrame(cards, corner_radius=8, border_width=2,
                               border_color=color)
            cf.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(cf, text=title, font=("Arial", 11),
                         text_color="gray").pack(anchor="w", padx=12, pady=(6, 0))
            lbl = ctk.CTkLabel(cf, text="—", font=("Arial", 22, "bold"))
            lbl.pack(anchor="w", padx=12, pady=(0, 6))
            self.dash_cards[key] = lbl

        # ── Sağ — Detaylar ──
        right = ctk.CTkFrame(parent, corner_radius=8)
        right.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Belge tipi dağılımı
        ctk.CTkLabel(right, text="📊 Belge Tipi Dağılımı",
                     font=("Arial", 12, "bold")).grid(
            row=0, column=0, padx=12, pady=(10, 5), sticky="w")

        self.dash_type_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.dash_type_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=5)

        # Mahalle dağılımı
        ctk.CTkLabel(right, text="🏘️ En Çok Belge İçeren Mahalleler",
                     font=("Arial", 12, "bold")).grid(
            row=2, column=0, padx=12, pady=(10, 5), sticky="w")

        self.dash_mahalle_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.dash_mahalle_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=5)

        # Son İşlenen
        ctk.CTkLabel(right, text="🕐 Son İşlenen Belgeler",
                     font=("Arial", 12, "bold")).grid(
            row=4, column=0, padx=12, pady=(10, 5), sticky="w")

        self.dash_recent_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.dash_recent_frame.grid(row=5, column=0, sticky="nsew", padx=12, pady=(5, 10))

    def _refresh_dashboard(self):
        if not self.db_manager:
            try:
                self.db_manager = DatabaseManager()
            except Exception:
                return

        stats = self.db_manager.get_statistics()

        self.dash_cards["total"].configure(text=str(stats.get("total_documents", 0)))
        self.dash_cards["approved"].configure(
            text=str(stats.get("by_status", {}).get("approved", 0)))
        self.dash_cards["review"].configure(
            text=str(stats.get("by_status", {}).get("needs_review", 0)))
        self.dash_cards["failed"].configure(
            text=str(stats.get("by_status", {}).get("failed", 0)))
        self.dash_cards["confidence"].configure(
            text=f"%{stats.get('avg_confidence', 0)}")
        self.dash_cards["parcels"].configure(
            text=str(stats.get("total_parcels", 0)))
        self.dash_cards["streets"].configure(
            text=str(stats.get("total_streets", 0)))

        # Belge tipi dağılımı
        for w in self.dash_type_frame.winfo_children():
            w.destroy()
        type_colors = {"meclis_karari": "#1a73e8", "tapu": "#2d8a4e",
                       "general": "#6b7280"}
        total = stats.get("total_documents", 1) or 1
        for t, cnt in stats.get("by_type", {}).items():
            pct = cnt / total * 100
            row = ctk.CTkFrame(self.dash_type_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"{t}", font=("Arial", 10),
                         width=120, anchor="w").pack(side="left")
            bar = ctk.CTkProgressBar(row, width=150)
            bar.pack(side="left", padx=5)
            bar.set(pct / 100)
            ctk.CTkLabel(row, text=f"{cnt} (%{pct:.0f})",
                         font=("Arial", 10)).pack(side="left")

        # Mahalle dağılımı
        for w in self.dash_mahalle_frame.winfo_children():
            w.destroy()
        for item in stats.get("top_mahalle", [])[:7]:
            row = ctk.CTkFrame(self.dash_mahalle_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=item["mahalle"], font=("Arial", 10),
                         width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"{item['count']} belge",
                         font=("Arial", 10), text_color="#4ade80").pack(side="left")

        # Son belgeler
        for w in self.dash_recent_frame.winfo_children():
            w.destroy()
        for doc in stats.get("recent_documents", [])[:5]:
            row = ctk.CTkFrame(self.dash_recent_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            status_icon = {"approved": "✅", "needs_review": "⚠️",
                           "failed": "❌"}.get(doc["status"], "?")
            ctk.CTkLabel(row, text=f"{status_icon} {doc['file']}",
                         font=("Arial", 10), anchor="w").pack(
                side="left", fill="x", expand=True)
            ctk.CTkLabel(row, text=doc["type"] or "—",
                         font=("Arial", 9), text_color="gray").pack(side="right")

    # ══════════════════════════════════════════════════════════════════════════
    #  ARAMA FONKSİYONLARI
    # ══════════════════════════════════════════════════════════════════════════
    def _do_advanced_search(self):
        if not self.db_manager:
            try:
                self.db_manager = DatabaseManager()
            except Exception as e:
                messagebox.showerror("Hata", f"Veritabanı bağlantısı:\n{e}")
                return

        ada = self._search_fields["ada"].get().strip() or None
        parsel = self._search_fields["parsel"].get().strip() or None
        mahalle = self._search_fields["mahalle"].get().strip() or None
        sokak = self._search_fields["sokak"].get().strip() or None
        konu = self._search_fields["konu"].get().strip() or None
        doc_type = self._search_type.get()
        if doc_type == "Tümü":
            doc_type = None
        status = self._search_status.get()
        if status == "Tümü":
            status = None
        date_from = self._search_date_from.get().strip() or None
        date_to = self._search_date_to.get().strip() or None
        free_text = self._search_freetext.get().strip() or None

        if not any([ada, parsel, mahalle, sokak, konu, doc_type,
                    status, date_from, date_to, free_text]):
            messagebox.showwarning("Uyarı", "En az bir filtre girmelisiniz.")
            return

        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        results = self.db_manager.search_advanced(
            ada=ada, parsel=parsel, mahalle=mahalle, sokak=sokak,
            doc_type=doc_type, status=status, date_from=date_from,
            date_to=date_to, konu=konu, free_text=free_text)

        if not results:
            self.search_result_label.configure(
                text="❌ Sonuç bulunamadı", text_color="#f87171")
            self.btn_map.configure(state="disabled")
            return

        self.search_result_label.configure(
            text=f"✅ {len(results)} evrak bulundu", text_color="#4ade80")

        for doc in results:
            fp = doc.get("file_path", "")
            self.result_tree.insert("", "end", values=(
                doc.get("id", ""),
                Path(fp).name if fp else "—",
                doc.get("doc_type", "—"),
                doc.get("extracted_date", "—"),
                doc.get("p_mahalle") or "—",
                doc.get("ada") or "—",
                doc.get("parsel") or "—",
                doc.get("sokak") or doc.get("s_sokak") or "—",
                doc.get("subject") or "—",
                doc.get("status", "—"),
            ))

        self.btn_map.configure(state="normal" if ada else "disabled")

    def _clear_search(self):
        for e in self._search_fields.values():
            e.delete(0, "end")
        self._search_type.set("Tümü")
        self._search_status.set("Tümü")
        self._search_date_from.delete(0, "end")
        self._search_date_to.delete(0, "end")
        self._search_freetext.delete(0, "end")
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.search_result_label.configure(
            text="Filtreleri doldurup 'Ara' butonuna basın", text_color="gray")

    def _on_result_select(self, event):
        selection = self.result_tree.selection()
        if not selection:
            return
        item = self.result_tree.item(selection[0])
        values = item["values"]
        if not values:
            return

        doc_id = values[0]
        doc = self.db_manager.get_document_by_id(doc_id) if self.db_manager else None
        if not doc:
            return

        field_map = {
            "ID": "id", "Dosya": "file_path", "Belge Tipi": "doc_type",
            "Tarih": "extracted_date", "Karar No": "document_number",
            "Konu": "subject",
            "Sokak": lambda d: d.get("s_sokak") or d.get("sokak") or "—",
            "Kapı No": lambda d: d.get("s_kapi_no") or d.get("kapi_no") or "—",
            "Durum": "status", "OCR Güven": "ocr_confidence",
            "Mahalle": lambda d: d.get("p_mahalle") or "—",
            "Ada": lambda d: d.get("ada") or "—",
            "Parsel": lambda d: d.get("parsel") or "—",
        }
        for field, key in field_map.items():
            entry = self.search_detail_entries[field]
            entry.configure(state="normal")
            entry.delete(0, "end")
            if callable(key):
                val = key(doc)
            elif key:
                val = doc.get(key, "—")
            else:
                val = "—"
            if field == "Dosya" and val and val != "—":
                val = Path(str(val)).name
            if field == "OCR Güven" and val and val != "—":
                try:
                    val = f"%{float(val) * 100:.1f}"
                except (ValueError, TypeError):
                    val = "—"
            entry.insert(0, str(val or "—"))
            entry.configure(state="disabled")

        self.search_text_box.delete("0.0", "end")
        text = doc.get("corrected_text") or doc.get("raw_text") or ""
        self.search_text_box.insert("0.0", text)

        self.btn_open_file.configure(state="normal")
        self.btn_detail_map.configure(state="normal")
        self._selected_doc = doc
        self._selected_values = values

    def _open_selected_file(self):
        if hasattr(self, "_selected_doc") and self._selected_doc:
            path = self._selected_doc.get("file_path")
            if path and os.path.exists(path):
                os.startfile(path)
            else:
                messagebox.showwarning("Uyarı", f"Dosya bulunamadı:\n{path}")

    def _open_map(self):
        ada = self._search_fields["ada"].get().strip()
        parsel = self._search_fields["parsel"].get().strip() or None
        if ada:
            url = CityGuideClient.get_map_url(ada, parsel)
            webbrowser.open(url)
        else:
            from tkinter import messagebox
            messagebox.showinfo(
                "Harita",
                "Haritada göstermek için Ada numarası gereklidir.\n"
                "Arama alanına Ada numarası girin veya\n"
                "sonuç listesinden bir belge seçin.")

    def _open_map_for_selected(self):
        if hasattr(self, "_selected_values") and self._selected_values:
            ada = str(self._selected_values[5])
            parsel = str(self._selected_values[6])
            if ada and ada != "—":
                url = CityGuideClient.get_map_url(
                    ada, parsel if parsel != "—" else None)
                webbrowser.open(url)
            else:
                from tkinter import messagebox
                messagebox.showinfo(
                    "Harita",
                    "Bu belge için Ada/Parsel bilgisi bulunamadı.\n"
                    "Meclis kararları genellikle Ada/Parsel\n"
                    "yerine sokak/cadde referansı içerir.")
        else:
            from tkinter import messagebox
            messagebox.showinfo("Harita", "Önce listeden bir belge seçin.")

    # ══════════════════════════════════════════════════════════════════════════
    #  DOSYA YÜKLEME (SEKME 1)
    # ══════════════════════════════════════════════════════════════════════════
    def load_file(self):
        path = filedialog.askopenfilename(
            title="Belge Seç",
            filetypes=[
                ("Tüm Desteklenen", "*.jpg *.jpeg *.png *.pdf *.tif *.tiff *.bmp"),
                ("Görüntüler", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"),
                ("PDF Dosyaları", "*.pdf"),
                ("Tüm Dosyalar", "*.*"),
            ])
        if not path:
            return

        # Duplikasyon kontrolü
        if self.db_manager:
            dup = self.db_manager.check_duplicate(path)
            if dup:
                if not messagebox.askyesno(
                        "⚠️ Duplikasyon Uyarısı",
                        f"Bu dosya daha önce işlenmiş!\n\n"
                        f"ID: {dup['id']}\nDosya: {Path(dup['file_path']).name}\n"
                        f"İşlenme: {dup['processed_date']}\n\n"
                        f"Yine de devam etmek istiyor musunuz?"):
                    return

        self.current_file = path
        self.all_results = []
        self.current_page_idx = 0
        self.pdf_page_images = []

        self.text_editor.delete("0.0", "end")
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.lbl_conf.configure(text="OCR Güven: —", text_color="white")
        self.lbl_engine.configure(text="Motor: —")
        self.lbl_validation.configure(text="Kent Rehberi: —", text_color="white")

        if path.lower().endswith(".pdf"):
            self._load_pdf_preview(path)
        else:
            self._display_image_from_path(path)
            self.page_info_label.configure(text="")
            self.btn_prev.configure(state="disabled")
            self.btn_next.configure(state="disabled")

        self.btn_process.configure(state="normal")
        self.btn_save.configure(state="disabled")
        self.btn_save_all.configure(state="disabled")

        fname = Path(path).name
        fsize = os.path.getsize(path) / 1024
        self.lbl_file_info.configure(text=f"📁 {fname}\n📐 {fsize:.0f} KB")
        self.status_label.configure(text="📂 Dosya Yüklendi", text_color="white")

    def _load_pdf_preview(self, path):
        try:
            import fitz
            from PIL import Image as PILImage
            doc = fitz.open(path)
            total = len(doc)
            zoom = 150 / 72
            mat = fitz.Matrix(zoom, zoom)
            page = doc[0]
            pix = page.get_pixmap(matrix=mat)
            first_img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.pdf_page_images = [first_img]
            self._display_pil_image(first_img)
            self.page_info_label.configure(text=f"PDF — {total} sayfa")
            self.lbl_file_info.configure(text=f"📁 {Path(path).name}\n📄 {total} sayfa")
            doc.close()
        except ImportError:
            self.image_label.configure(
                text="⚠️ PDF desteği için PyMuPDF gerekli!\npip install PyMuPDF")
        except Exception as e:
            self.image_label.configure(text=f"PDF Hatası:\n{e}")

    def _display_image_from_path(self, path):
        try:
            img = Image.open(path)
            self._display_pil_image(img)
        except Exception as e:
            self.image_label.configure(text=f"Görüntüleme Hatası:\n{e}")

    def _display_pil_image(self, pil_img):
        try:
            w, h = pil_img.size
            ratio = min(600 / w, 800 / h)
            new_size = (int(w * ratio), int(h * ratio))
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                                    size=new_size)
            self.image_label.configure(image=ctk_img, text="")
            self.image_label.image = ctk_img
        except Exception as e:
            self.image_label.configure(text=f"Görüntüleme Hatası:\n{e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  İŞLEME (SEKME 1)
    # ══════════════════════════════════════════════════════════════════════════
    def start_processing(self):
        if not self.current_file:
            return
        self.btn_process.configure(state="disabled")
        self.btn_save.configure(state="disabled")
        self.btn_save_all.configure(state="disabled")
        self.status_label.configure(text="⏳ İşleniyor…", text_color="yellow")
        self.text_editor.delete("0.0", "end")
        self.progress_bar.set(0)

        if self.current_file.lower().endswith(".pdf"):
            self.text_editor.insert("0.0", "📄 PDF analiz ediliyor…")
            thread = threading.Thread(target=self._process_pdf_task, daemon=True)
        else:
            self.text_editor.insert("0.0", "🔍 Belge analiz ediliyor…")
            thread = threading.Thread(target=self._process_single_task, daemon=True)
        thread.start()

    def _process_single_task(self):
        try:
            if not self.processor:
                self.processor = DocumentProcessor()
            result = self.processor.process_document(self.current_file, doc_type="AUTO")
            self.all_results = [result]
            self.current_page_idx = 0
            self.after(0, lambda: self._show_result(0))
        except Exception as e:
            self.after(0, lambda: self._show_error(str(e)))

    def _process_pdf_task(self):
        try:
            if not self.processor:
                self.processor = DocumentProcessor()

            def on_progress(current, total):
                pct = current / total
                self.after(0, lambda c=current, t=total, p=pct:
                           self._update_progress(c, t, p))

            results = self.processor.process_pdf(
                self.current_file, dpi=300,
                progress_callback=on_progress, doc_type="AUTO")
            self.all_results = results
            self.current_page_idx = 0

            try:
                import fitz
                from PIL import Image as PILImage
                doc = fitz.open(self.current_file)
                zoom = 150 / 72
                mat = fitz.Matrix(zoom, zoom)
                self.pdf_page_images = []
                for p in doc:
                    pix = p.get_pixmap(matrix=mat)
                    self.pdf_page_images.append(
                        PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples))
                doc.close()
            except Exception:
                self.pdf_page_images = []

            self.after(0, self._on_pdf_complete)
        except Exception as e:
            self.after(0, lambda: self._show_error(str(e)))

    def _update_progress(self, current, total, pct):
        self.progress_bar.set(pct)
        self.progress_label.configure(text=f"Sayfa {current}/{total}")
        self.status_label.configure(
            text=f"⏳ Sayfa {current}/{total}", text_color="yellow")

    def _on_pdf_complete(self):
        total = len(self.all_results)
        success = sum(1 for r in self.all_results if r.get("success"))
        self.progress_bar.set(1.0)
        self.progress_label.configure(text=f"✅ {success}/{total}")
        if total > 1:
            self.btn_prev.configure(state="normal")
            self.btn_next.configure(state="normal")
            self.btn_save_all.configure(state="normal")
        self._show_result(0)

    # ══════════════════════════════════════════════════════════════════════════
    #  NAVİGASYON + SONUÇ GÖSTERME
    # ══════════════════════════════════════════════════════════════════════════
    def prev_page(self):
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self._show_result(self.current_page_idx)

    def next_page(self):
        if self.current_page_idx < len(self.all_results) - 1:
            self.current_page_idx += 1
            self._show_result(self.current_page_idx)

    def _show_result(self, idx):
        if idx < 0 or idx >= len(self.all_results):
            return
        self.current_page_idx = idx
        result = self.all_results[idx]
        self.btn_process.configure(state="normal")
        self.btn_save.configure(state="normal")

        total = len(self.all_results)
        self.btn_prev.configure(state="normal" if idx > 0 else "disabled")
        self.btn_next.configure(state="normal" if idx < total - 1 else "disabled")
        self.page_info_label.configure(
            text=f"Sayfa {idx + 1}/{total}" if total > 1 else "")

        if not result.get("success"):
            self.status_label.configure(text="❌ Hata", text_color="red")
            self.text_editor.delete("0.0", "end")
            self.text_editor.insert("0.0", f"Hata: {result.get('message', '?')}")
            return

        data = result["data"]
        self.current_data = data

        if self.pdf_page_images and idx < len(self.pdf_page_images):
            self._display_pil_image(self.pdf_page_images[idx])
        elif not self.current_file.lower().endswith(".pdf"):
            self._display_image_from_path(self.current_file)

        self.text_editor.delete("0.0", "end")
        self.text_editor.insert("0.0", data.get("corrected_text", ""))

        self._set_entry("Belge Tipi", data.get("doc_type"))
        self._set_entry("Tarih", data.get("tarih"))
        self._set_entry("Ada", data.get("ada"))
        self._set_entry("Parsel", data.get("parsel"))
        self._set_entry("Mahalle", data.get("mahalle"))
        self._set_entry("Sokak", data.get("sokak"))
        self._set_entry("Kapı No", data.get("kapi_no"))
        self._set_entry("Karar No", data.get("karar_no") or data.get("belge_no"))
        self._set_entry("Konu", data.get("konu"))

        details = data.get("ocr_details", {})
        conf = max(details.get("easyocr_conf", 0),
                   details.get("tesseract_conf", 0)) if details else 0
        color = "#4ade80" if conf > 0.8 else ("orange" if conf > 0.5 else "#f87171")
        self.lbl_conf.configure(text=f"OCR Güven: %{conf * 100:.1f}", text_color=color)
        self.lbl_engine.configure(text=f"Motor: {details.get('engine_used', '—')}")

        validation = data.get("city_guide_validation")
        if validation:
            if validation.get("is_valid"):
                self.lbl_validation.configure(
                    text=f"✅ Doğrulandı\n{validation.get('note', '')}",
                    text_color="#4ade80")
            else:
                self.lbl_validation.configure(
                    text=f"ℹ️ {validation.get('note', '—')}", text_color="gray")
        else:
            self.lbl_validation.configure(text="Kent Rehberi: —", text_color="white")

        self.status_label.configure(text="✅ Tamamlandı", text_color="green")

    def _set_entry(self, field, value):
        self.entries[field].delete(0, "end")
        if value:
            self.entries[field].insert(0, str(value))

    def _show_error(self, msg):
        self.btn_process.configure(state="normal")
        self.status_label.configure(text="❌ Hata", text_color="red")
        self.progress_bar.set(0)
        messagebox.showerror("Hata", msg)

    # ══════════════════════════════════════════════════════════════════════════
    #  KAYDETME
    # ══════════════════════════════════════════════════════════════════════════
    def save_results(self):
        if not self.current_data:
            messagebox.showwarning("Uyarı", "Kaydedilecek veri yok.")
            return
        data = self._collect_form_data()
        try:
            if not self.db_manager:
                self.db_manager = DatabaseManager()
            doc_id = self.db_manager.add_document(
                {**data, "image_path": self.current_file})
            messagebox.showinfo("Başarılı", f"Veritabanına kaydedildi (ID: {doc_id})")
        except Exception as e:
            messagebox.showerror("Veritabanı Hatası", str(e))
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("PDF Rapor", "*.pdf")])
        if save_path:
            if save_path.endswith(".json"):
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            elif save_path.endswith(".pdf"):
                self._export_pdf(save_path, data)

    def save_all_results(self):
        if not self.all_results:
            messagebox.showwarning("Uyarı", "Kaydedilecek sonuç yok.")
            return
        saved, errors = 0, 0
        try:
            if not self.db_manager:
                self.db_manager = DatabaseManager()
            for r in self.all_results:
                if not r.get("success"):
                    errors += 1
                    continue
                try:
                    data = r["data"]
                    data["image_path"] = self.current_file
                    self.db_manager.add_document(data)
                    saved += 1
                except Exception:
                    errors += 1
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        msg = f"✅ {saved} sayfa kaydedildi"
        if errors:
            msg += f"\n⚠️ {errors} sayfa hatalı"
        messagebox.showinfo("Toplu Kayıt", msg)

    def _collect_form_data(self):
        data = self.current_data.copy() if self.current_data else {}
        data["corrected_text"] = self.text_editor.get("0.0", "end").strip()
        data["doc_type"] = self.entries["Belge Tipi"].get()
        data["tarih"] = self.entries["Tarih"].get()
        data["ada"] = self.entries["Ada"].get()
        data["parsel"] = self.entries["Parsel"].get()
        data["mahalle"] = self.entries["Mahalle"].get()
        data["sokak"] = self.entries["Sokak"].get()
        data["kapi_no"] = self.entries["Kapı No"].get()
        data["karar_no"] = self.entries["Karar No"].get()
        data["konu"] = self.entries["Konu"].get()
        return data

    def _export_pdf(self, path, data):
        try:
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.pagesizes import A4
        except ImportError:
            messagebox.showerror("Hata", "reportlab gerekli.\npip install reportlab")
            return

        c = canvas.Canvas(path, pagesize=A4)
        w, h = A4
        try:
            pdfmetrics.registerFont(TTFont("Arial", "C:\\Windows\\Fonts\\arial.ttf"))
            fn = "Arial"
        except Exception:
            fn = "Helvetica"

        c.setFont(fn, 16)
        c.drawString(50, h - 50, "Sivas Belediyesi — Evrak Analiz Raporu")
        c.setFont(fn, 12)
        y = h - 100
        for label, key in [("Belge Tipi", "doc_type"), ("Karar No", "karar_no"),
                            ("Konu", "konu"), ("Tarih", "tarih"),
                            ("Mahalle", "mahalle"), ("Ada", "ada"),
                            ("Parsel", "parsel"), ("Sokak", "sokak"),
                            ("Kapı No", "kapi_no")]:
            c.drawString(50, y, f"{label}: {data.get(key) or '—'}")
            y -= 20

        c.drawString(50, y - 20, "OCR Metni:")
        to = c.beginText(50, y - 40)
        to.setFont(fn, 10)
        if data.get("corrected_text"):
            for line in data["corrected_text"].split("\n")[:60]:
                to.textLine(line[:90])
        c.drawText(to)
        try:
            c.save()
        except Exception as e:
            messagebox.showerror("Hata", f"PDF kaydedilemedi:\n{e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
