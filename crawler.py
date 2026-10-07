"""
crawler.py - Coletor automatizado de jurisprudência do TRF4
Acessa o sistema eproc de jurisprudência e extrai acórdãos atualizados com metadados e fundamentações.
Suporta:
- 2ª Instância (5ª, 6ª, 9ª, 10ª e 11ª Turmas Especializadas em Previdenciário + 2ª Seção)
- Turma Regional de Uniformização (TRU4)
- Turmas Recursais dos JEFs (RS, SC, PR)
"""
import urllib.request
import urllib.parse
import ssl
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from database import salvar_precedente

BASE_URL = 'https://eproc-jur.trf4.jus.br/eproc2trf4/externo_controlador.php?acao=jurisprudencia@jurisprudencia/listar_resultados'

# Mapeamento completo dos órgãos previdenciários do TRF4
ORGAOS_PREVIDENCIARIOS_TRF4 = {
    'Tribunal (2ª Instância)': [
        '5ª Turma',
        '6ª Turma',
        '9ª Turma',
        '10ª Turma',
        '11ª Turma',
        '2ª Seção'
    ],
    'Turmas Recursais RS': [
        '1ª Turma Recursal do Rio Grande do Sul',
        '2ª Turma Recursal do Rio Grande do Sul',
        '3ª Turma Recursal do Rio Grande do Sul',
        '4ª Turma Recursal do Rio Grande do Sul',
        '5ª Turma Recursal do Rio Grande do Sul',
    ],
    'Turmas Recursais SC': [
        '1ª Turma Recursal de Santa Catarina',
        '2ª Turma Recursal de Santa Catarina',
        '3ª Turma Recursal de Santa Catarina',
        '4ª Turma Recursal de Santa Catarina',
    ],
    'Turmas Recursais PR': [
        '1ª Turma Recursal do Paraná',
        '2ª Turma Recursal do Paraná',
        '3ª Turma Recursal do Paraná',
        '4ª Turma Recursal do Paraná',
    ],
    'Uniformização (TRU4)': [
        'Turma Regional de Uniformização - Previdenciária',
        'Turma Regional de Uniformização'
    ]
}
ORGAOS_TRF4 = ORGAOS_PREVIDENCIARIOS_TRF4

def normalizar_uf(orgao: str) -> str:
    orgao_up = orgao.upper()
    if any(t in orgao_up for t in ['5ª TURMA', '6ª TURMA', '9ª TURMA', '10ª TURMA', '11ª TURMA', '2ª SEÇÃO']):
        return 'TRF4 (2ª Instância)'
    elif 'RIO GRANDE DO SUL' in orgao_up or ' RS' in orgao_up or '/RS' in orgao_up:
        return 'RS'
    elif 'SANTA CATARINA' in orgao_up or ' SC' in orgao_up or '/SC' in orgao_up:
        return 'SC'
    elif 'PARANÁ' in orgao_up or 'PARANA' in orgao_up or ' PR' in orgao_up or '/PR' in orgao_up:
        return 'PR'
    elif 'UNIFORMIZAÇÃO' in orgao_up or 'UNIFORMIZACAO' in orgao_up or 'TRU' in orgao_up:
        return 'TRU4'
    return 'TRF4'

def buscar_jurisprudencia_trf4(
    termo: str = "",
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    data_decisao_inicio: Optional[str] = None,
    data_decisao_fim: Optional[str] = None,
    orgao: Optional[str] = None,
    origem: str = "todas", # "1" (Tribunal), "2" (TRU), "3" (Turmas Recursais), "todas"
    agrupar: bool = False
) -> List[Dict]:
    """
    Executa busca no eproc do TRF4 e retorna lista de acórdãos estruturados.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    data = [
        ('txtPesquisa', termo),
        ('selTipoDocumento[]', '1'),  # 1 = Acórdão
        ('rdoCampo', 'E'),  # E = Ementa
    ]

    # Origem
    if origem == "1":
        data.append(('selOrigem[]', '1')) # Tribunal (2ª Instância)
    elif origem == "2":
        data.append(('selOrigem[]', '2')) # TRU4
    elif origem == "3":
        data.append(('selOrigem[]', '3')) # Turmas Recursais
    else: # todas
        data.append(('selOrigem[]', '1'))
        data.append(('selOrigem[]', '2'))
        data.append(('selOrigem[]', '3'))

    if orgao:
        data.append(('selOrgao[]', orgao))

    if agrupar:
        data.append(('chkAgruparResultados', 'S'))

    # Filtros de data de publicação
    if data_inicio:
        data.append(('dtPublicacaoInicio', data_inicio))
    if data_fim:
        data.append(('dtPublicacaoFim', data_fim))

    # Filtros de data de julgamento/sessão
    if data_decisao_inicio:
        data.append(('dtDecisaoInicio', data_decisao_inicio))
    if data_decisao_fim:
        data.append(('dtDecisaoFim', data_decisao_fim))

    encoded_data = urllib.parse.urlencode(data, doseq=True).encode('iso-8859-1')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://eproc-jur.trf4.jus.br/eproc2trf4/externo_controlador.php?acao=jurisprudencia@jurisprudencia/pesquisar'
    }

    try:
        req = urllib.request.Request(BASE_URL, data=encoded_data, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            html = resp.read().decode('iso-8859-1', errors='ignore')
    except Exception as e:
        print(f"Erro na requisição ao TRF4: {e}")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find_all('div', class_=lambda c: c and 'resultadoItem' in c)
    resultados = []

    for item in items:
        proc_elem = item.find('a', class_='numero-processo')
        numero_proc = proc_elem.get_text(strip=True) if proc_elem else "N/A"
        proc_link = proc_elem.get('href') if proc_elem else ""

        download_btn = item.find('a', attrs={'data-link': lambda l: l and 'download_inteiro_teor' in l})
        inteiro_teor_url = ""
        if download_btn:
            inteiro_teor_url = "https://eproc-jur.trf4.jus.br/eproc2trf4/" + download_btn['data-link']

        citacao_btn = item.find(attrs={'data-citacao': True})
        citacao = citacao_btn['data-citacao'] if citacao_btn else ""

        # Extrair labels do card
        labels_vals = {}
        for row in item.find_all('div', class_='row'):
            lbl = row.find('div', class_='resLabel')
            val = row.find('div', class_='resValue')
            if lbl and val:
                lbl_text = lbl.get_text(strip=True).upper()
                val_text = val.get_text(strip=True)
                labels_vals[lbl_text] = val_text

        # Órgão julgador
        orgao_val = labels_vals.get('ÓRGÃO JULGADOR', labels_vals.get('RGO JULGADOR', ''))
        if not orgao_val:
            m_orgao = re.search(r'((?:\d+[ªa]|QUINTA|SEXTA|NONA|DÉCIMA|1ª|2ª|3ª|4ª|5ª|6ª|9ª|10ª|11ª)\s+(?:Turma|TURMA)[^\,\)]*|SEÇÃO|TRU|Turma\s+Regional\s+de\s+Uniformiza[çc][ãa]o)', citacao, re.IGNORECASE)
            orgao_val = m_orgao.group(1).strip() if m_orgao else "Turma TRF4"

        # Relator
        relator = ""
        m_rel = re.search(r'Relator[a]?\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ\s]+)(?:,|$|\n)', citacao)
        if m_rel:
            relator = m_rel.group(1).strip()

        # Data de julgamento
        data_julg = labels_vals.get('DATA DO JULGAMENTO', '')
        if not data_julg:
            m_data = re.search(r'julgado\s+em\s+(\d{2}/\d{2}/\d{4})', citacao, re.IGNORECASE)
            data_julg = m_data.group(1) if m_data else ""

        # Data de publicação
        data_pub = labels_vals.get('DATA DA PUBLICAÇÃO', labels_vals.get('DATA DA PUBLICAO', ''))

        uf = normalizar_uf(orgao_val)

        resultados.append({
            'processo': numero_proc,
            'orgao': orgao_val,
            'uf': uf,
            'relator': relator,
            'data_julgamento': data_julg,
            'data_publicacao': data_pub,
            'assunto': 'Direito Previdenciário',
            'texto_completo': citacao,
            'link_eproc': proc_link,
            'link_inteiro_teor': inteiro_teor_url
        })

    return resultados

def coletar_e_salvar(termo: str, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, origem: str = "todas") -> Dict:
    """Busca precedentes no TRF4 e persiste no banco de dados SQLite."""
    precedentes = buscar_jurisprudencia_trf4(termo=termo, data_inicio=data_inicio, data_fim=data_fim, origem=origem)
    total_encontrados = len(precedentes)
    novos = 0
    for prec in precedentes:
        if salvar_precedente(prec):
            novos += 1
    return {
        'termo': termo,
        'encontrados': total_encontrados,
        'novos_inseridos': novos,
        'precedentes': precedentes
    }

def atualizar_semanalmente_previdenciario(dias_atras: int = 15) -> Dict:
    """
    Rotina periódica de atualização com os julgados previdenciários mais recentes,
    incluindo as Turmas Especializadas do Tribunal (5ª, 6ª, 9ª, 10ª) e Turmas Recursais.
    """
    hoje = datetime.now()
    inicio = (hoje - timedelta(days=dias_atras)).strftime('%d/%m/%Y')
    fim = hoje.strftime('%d/%m/%Y')

    termos_chave = [
        'previdenciário "prova emprestada"',
        'previdenciário "Súmula 106"',
        'previdenciário "laudo similar"',
        'previdenciário aposentadoria especial',
        'previdenciário auxílio incapacidade',
        'previdenciário reafirmação DER'
    ]

    total_novos = 0
    total_encontrados = 0
    detalhes = []

    for t in termos_chave:
        res = coletar_e_salvar(termo=t, data_inicio=inicio, data_fim=fim, origem="todas")
        total_novos += res['novos_inseridos']
        total_encontrados += res['encontrados']
        detalhes.append(f"{t}: {res['encontrados']} encontrados ({res['novos_inseridos']} novos)")

    return {
        'periodo': f"{inicio} até {fim}",
        'total_encontrados': total_encontrados,
        'total_novos': total_novos,
        'detalhes': detalhes
    }
