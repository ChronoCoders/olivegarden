import sqlite3
import os
from datetime import datetime
from app.config import settings

def get_db_connection():
    """Veritabanı bağlantısı al"""
    conn = sqlite3.connect(settings.DATABASE_URL)
    conn.row_factory = sqlite3.Row  # Dict-like access
    return conn

def init_db():
    """Veritabanını başlat ve tablolar oluştur"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analizler (
            analiz_id TEXT PRIMARY KEY,
            tarih_saat TEXT NOT NULL,
            dosya_sayisi INTEGER,
            toplam_agac INTEGER DEFAULT 0,
            toplam_zeytin INTEGER DEFAULT 0,
            tahmini_zeytin_miktari REAL DEFAULT 0.0,
            ndvi_ortalama REAL DEFAULT 0.0,
            gndvi_ortalama REAL DEFAULT 0.0,
            ndre_ortalama REAL DEFAULT 0.0,
            saglik_durumu TEXT DEFAULT '',
            agac_cap_ortalama REAL DEFAULT 0.0,
            ndvi_path TEXT DEFAULT '',
            pdf_path TEXT DEFAULT '',
            excel_path TEXT DEFAULT '',
            geojson_path TEXT DEFAULT '',
            log_path TEXT DEFAULT '',
            durum TEXT DEFAULT 'yuklendi',
            analiz_modu TEXT DEFAULT 'cpu',
            kullanilan_cihaz TEXT DEFAULT 'cpu',
            analiz_suresi REAL DEFAULT 0.0,
            kullanici_id INTEGER DEFAULT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def create_analysis(analiz_id: str, dosya_sayisi: int):
    """Yeni analiz kaydı oluştur"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO analizler (analiz_id, tarih_saat, dosya_sayisi)
        VALUES (?, ?, ?)
    ''', (analiz_id, datetime.now().isoformat(), dosya_sayisi))
    
    conn.commit()
    conn.close()

def get_analysis(analiz_id: str):
    """Analiz kaydını getir"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM analizler WHERE analiz_id = ?', (analiz_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))
    return None

def update_analysis(analiz_id: str, analiz_sonuclari: dict, rapor_sonuclari: dict):
    """Analiz sonuçlarını güncelle"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE analizler SET
            toplam_agac = ?,
            toplam_zeytin = ?,
            tahmini_zeytin_miktari = ?,
            ndvi_ortalama = ?,
            gndvi_ortalama = ?,
            ndre_ortalama = ?,
            saglik_durumu = ?,
            agac_cap_ortalama = ?,
            ndvi_path = ?,
            pdf_path = ?,
            excel_path = ?,
            geojson_path = ?,
            durum = 'tamamlandi',
            analiz_modu = ?,
            kullanilan_cihaz = ?,
            analiz_suresi = ?
        WHERE analiz_id = ?
    ''', (
        analiz_sonuclari['toplam_agac'],
        analiz_sonuclari['toplam_zeytin'],
        analiz_sonuclari['tahmini_zeytin_miktari'],
        analiz_sonuclari['ndvi_ortalama'],
        analiz_sonuclari.get('gndvi_ortalama', 0.0),
        analiz_sonuclari.get('ndre_ortalama', 0.0),
        analiz_sonuclari['saglik_durumu'],
        analiz_sonuclari.get('agac_cap_ortalama', 0.0),
        analiz_sonuclari.get('ndvi_path', ''),
        rapor_sonuclari['pdf_path'],
        rapor_sonuclari['excel_path'],
        rapor_sonuclari['geojson_path'],
        analiz_sonuclari.get('analiz_modu', 'cpu'),
        analiz_sonuclari.get('kullanilan_cihaz', 'cpu'),
        analiz_sonuclari.get('analiz_suresi', 0.0),
        analiz_id
    ))
    
    conn.commit()
    conn.close()

def get_all_analyses():
    """Tüm analizleri getir"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM analizler ORDER BY tarih_saat DESC')
    rows = cursor.fetchall()
    
    conn.close()
    
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in rows]