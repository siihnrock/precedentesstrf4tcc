"""
database.py - Gerenciamento do banco de dados SQLite para precedentes do TRF4
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "trf4_precedentes.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS precedentes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        processo TEXT NOT NULL,
        orgao TEXT NOT NULL,
        uf TEXT NOT NULL,
        relator TEXT,
        data_julgamento TEXT,
        data_publicacao TEXT,
        assunto TEXT,
        texto_completo TEXT NOT NULL,
        link_eproc TEXT,
        link_inteiro_teor TEXT,
        data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (processo, orgao, data_julgamento)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proc ON precedentes (processo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_uf ON precedentes (uf)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orgao ON precedentes (orgao)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_julg ON precedentes (data_julgamento)")
    conn.commit()
    conn.close()

def salvar_precedente(prec: Dict) -> bool:
    """Salva um precedente se ele for novo; ignora se já existir."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT OR IGNORE INTO precedentes (
            processo, orgao, uf, relator, data_julgamento, data_publicacao,
            assunto, texto_completo, link_eproc, link_inteiro_teor
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prec.get('processo'),
            prec.get('orgao'),
            prec.get('uf'),
            prec.get('relator'),
            prec.get('data_julgamento'),
            prec.get('data_publicacao'),
            prec.get('assunto', 'Direito Previdenciário'),
            prec.get('texto_completo'),
            prec.get('link_eproc'),
            prec.get('link_inteiro_teor')
        ))
        inserted = cursor.rowcount > 0
        conn.commit()
        return inserted
    except Exception as e:
        print(f"Erro ao salvar precedente: {e}")
        return False
    finally:
        conn.close()

def buscar_precedentes(termo: str = "", uf: Optional[str] = None, orgao: Optional[str] = None, limite: int = 50) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM precedentes WHERE 1=1"
    params = []
    
    if termo:
        # Busca por palavras-chave no texto ou assunto
        termos = termo.strip().split()
        for t in termos:
            query += " AND (texto_completo LIKE ? OR assunto LIKE ?)"
            params.extend([f"%{t}%", f"%{t}%"])
            
    if uf and uf != "TODOS":
        query += " AND uf = ?"
        params.append(uf)
        
    if orgao:
        query += " AND orgao LIKE ?"
        params.append(f"%{orgao}%")
        
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limite)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def obter_estatisticas() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM precedentes")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT uf, COUNT(*) FROM precedentes GROUP BY uf")
    por_uf = dict(cursor.fetchall())
    
    cursor.execute("SELECT orgao, COUNT(*) FROM precedentes GROUP BY orgao ORDER BY COUNT(*) DESC LIMIT 10")
    por_orgao = dict(cursor.fetchall())
    
    cursor.execute("SELECT MAX(data_coleta) FROM precedentes")
    ultima_coleta = cursor.fetchone()[0]
    
    conn.close()
    return {
        'total': total,
        'por_uf': por_uf,
        'por_orgao': por_orgao,
        'ultima_coleta': ultima_coleta
    }

if __name__ == "__main__":
    init_db()
    print("Banco de dados inicializado com sucesso!")
