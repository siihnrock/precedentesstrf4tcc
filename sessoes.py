"""
sessoes.py - Rastreador do Calendário de Sessões de Julgamento e Pautas do TRF4.
Consulta a aba de Sessões de Julgamento (https://www.trf4.jus.br/trf4/controlador.php?acao=sessao_julgamento_listar)
para RS (JFRS), SC (JFSC), PR (JFPR) e TRU/Tribunal (TRF4), permitindo consulta de sessões passadas e futuras,
e extração das ementas dos processos julgados naquelas datas.
"""
import urllib.request
import urllib.parse
import ssl
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import List, Dict, Optional
from crawler import buscar_jurisprudencia_trf4

# Mapeamento amigável das siglas das Turmas Recursais e Turmas Especializadas do TRF4
NOMES_ORGAOS = {
    # 2ª Instância (Tribunal - Previdenciário)
    'ST5': '5ª Turma (Previdenciário)',
    'ST6': '6ª Turma (Previdenciário)',
    'ST9': '9ª Turma (Previdenciário)',
    'ST10': '10ª Turma (Previdenciário)',
    'ST11': '11ª Turma (Previdenciário)',
    'SE2': '2ª Seção do TRF4 (Previdenciário)',
    'TRU': 'Turma Regional de Uniformização (TRU4)',
    'TRUPREV': 'TRU4 - Matéria Previdenciária',

    # Turmas Recursais RS
    'RSPOATR01': '1ª Turma Recursal do RS',
    'RSPOATR02': '2ª Turma Recursal do RS',
    'RSPOATR03': '3ª Turma Recursal do RS',
    'RSPOATR04': '4ª Turma Recursal do RS',
    'RSPOATR05': '5ª Turma Recursal do RS',
    'RSPOATRSEP': 'Turma Recursal Suplementar de Equalização (RS)',
    
    # Turmas Recursais SC
    'SCFLPTR01': '1ª Turma Recursal de SC',
    'SCFLPTR02': '2ª Turma Recursal de SC',
    'SCFLPTR03': '3ª Turma Recursal de SC',
    'SCFLPTR04': '4ª Turma Recursal de SC',
    'SCFLPTRSUP': 'Turma Recursal Suplementar (SC)',

    # Turmas Recursais PR
    'PRCTBTR01': '1ª Turma Recursal do PR',
    'PRCTBTR02': '2ª Turma Recursal do PR',
    'PRCTBTR03': '3ª Turma Recursal do PR',
    'PRCTBTR04': '4ª Turma Recursal do PR',
    'PRCTBTRSUP': 'Turma Recursal Suplementar (PR)'
}

SIGLAS_FONTES = {
    'RS': 'jfrs',
    'SC': 'jfsc',
    'PR': 'jfpr',
    'Tribunal / TRU': 'trf4'
}

def normalizar_nome_orgao(sigla: str, uf: str) -> str:
    sigla_clean = sigla.upper().strip()
    if sigla_clean in NOMES_ORGAOS:
        return NOMES_ORGAOS[sigla_clean]
    
    # Mapeamento para siglas ST do tribunal
    if sigla_clean == 'ST5': return '5ª Turma do TRF4'
    if sigla_clean == 'ST6': return '6ª Turma do TRF4'
    if sigla_clean == 'ST9': return '9ª Turma do TRF4'
    if sigla_clean == 'ST10': return '10ª Turma do TRF4'
    if sigla_clean == 'ST11': return '11ª Turma do TRF4'
    if sigla_clean == 'SE2': return '2ª Seção do TRF4'
    
    if 'TR01' in sigla_clean: return f"1ª Turma Recursal ({uf})"
    if 'TR02' in sigla_clean: return f"2ª Turma Recursal ({uf})"
    if 'TR03' in sigla_clean: return f"3ª Turma Recursal ({uf})"
    if 'TR04' in sigla_clean: return f"4ª Turma Recursal ({uf})"
    if 'TR05' in sigla_clean: return f"5ª Turma Recursal ({uf})"
    if 'TRU' in sigla_clean: return "Turma Regional de Uniformização (TRU4)"
    return f"Órgão {sigla_clean} ({uf})"

def coletar_sessoes_trf4(uf_filtro: Optional[str] = None, mes: Optional[int] = None, ano: Optional[int] = None) -> List[Dict]:
    """
    Coleta o calendário oficial de sessões e audiências da 4ª Região.
    Permite filtrar por mês e ano para consultar sessões passadas.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    todas_sessoes = []

    fontes = SIGLAS_FONTES.items()
    if uf_filtro and uf_filtro in SIGLAS_FONTES:
        fontes = [(uf_filtro, SIGLAS_FONTES[uf_filtro])]

    hoje = datetime.now()
    mes_str = str(mes) if mes else str(hoje.month)
    ano_str = str(ano) if ano else str(hoje.year)

    for uf, sigla_orgao in fontes:
        url = f'https://www.trf4.jus.br/trf4/controlador.php?acao=sessao_julgamento_listar&sigla_orgao={sigla_orgao}'
        post_data = urllib.parse.urlencode({
            'selMes': mes_str,
            'selAno': ano_str,
            'selOrgaoJulgador': 'null'
        }).encode('iso-8859-1')

        req = urllib.request.Request(url, data=post_data, headers={
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded'
        })
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                html = resp.read().decode('iso-8859-1', errors='ignore')
        except Exception as e:
            print(f"Erro ao buscar sessões para {uf} no mês {mes_str}/{ano_str}: {e}")
            continue

        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=re.compile(r'sessao_julgamento', re.I))

        for a in links:
            href = a.get('href')

            # Extrair sig_orgao da URL
            sig_orgao_m = re.search(r'sig_orgao=([^&]+)', href)
            sig_orgao = sig_orgao_m.group(1) if sig_orgao_m else ""

            # Extrair data da URL
            data_m = re.search(r'data=([^&]+)', href)
            data_sessao_str = data_m.group(1) if data_m else ""
            data_sessao_str = urllib.parse.unquote(data_sessao_str).strip()

            # Converter data para ordenação
            dt_obj = None
            try:
                dt_obj = datetime.strptime(data_sessao_str[:10], '%d/%m/%Y')
            except Exception:
                dt_obj = datetime.min

            modalidade = "Virtual" if ("sin_virtual=S" in href or "modalidade=V" in href) else "Presencial"
            nome_amigavel = normalizar_nome_orgao(sig_orgao, uf)

            status_tempo = "Agendada / Futura"
            if dt_obj and dt_obj.date() < hoje.date():
                status_tempo = "Realizada (Sessão Passada)"
            elif dt_obj and dt_obj.date() == hoje.date():
                status_tempo = "HOJE"

            todas_sessoes.append({
                'uf': uf,
                'codigo_orgao': sig_orgao,
                'orgao_nome': nome_amigavel,
                'data_hora': data_sessao_str,
                'data_apenas': data_sessao_str[:10] if len(data_sessao_str) >= 10 else "",
                'data_obj': dt_obj,
                'modalidade': modalidade,
                'status': status_tempo,
                'link_pauta': href
            })

    # Ordenar por data da sessão decrescente (mais recentes primeiro)
    todas_sessoes.sort(key=lambda s: s['data_obj'], reverse=True)
    return todas_sessoes

def extrair_acordaos_da_sessao(nome_orgao: str, data_sessao_ddmmyyyy: str, termo_filtro: str = "") -> List[Dict]:
    """
    Busca no eproc-jur todos os acórdãos publicados decorrentes da sessão de julgamento daquela data e órgão.
    """
    # Mapear nome_orgao para a nomenclatura do eproc-jur
    orgao_busca = nome_orgao
    origem = "1" # 1 = Tribunal (2ª Instância) por padrão

    if "5ª Turma" in nome_orgao:
        orgao_busca = "5ª Turma"
        origem = "1"
    elif "6ª Turma" in nome_orgao:
        orgao_busca = "6ª Turma"
        origem = "1"
    elif "9ª Turma" in nome_orgao:
        orgao_busca = "9ª Turma"
        origem = "1"
    elif "10ª Turma" in nome_orgao:
        orgao_busca = "10ª Turma"
        origem = "1"
    elif "11ª Turma" in nome_orgao:
        orgao_busca = "11ª Turma"
        origem = "1"
    elif "2ª Seção" in nome_orgao:
        orgao_busca = "2ª Seção"
        origem = "1"
    elif "Turma Recursal do RS" in nome_orgao:
        m = re.search(r'(\d+[ªa]\s+Turma\s+Recursal\s+do\s+Rio\s+Grande\s+do\s+Sul)', nome_orgao)
        orgao_busca = m.group(1) if m else "1ª Turma Recursal do Rio Grande do Sul"
        origem = "3"
    elif "Turma Recursal de SC" in nome_orgao:
        m = re.search(r'(\d+[ªa]\s+Turma\s+Recursal\s+de\s+Santa\s+Catarina)', nome_orgao)
        orgao_busca = m.group(1) if m else "1ª Turma Recursal de Santa Catarina"
        origem = "3"
    elif "Turma Recursal do PR" in nome_orgao:
        m = re.search(r'(\d+[ªa]\s+Turma\s+Recursal\s+do\s+Paran[áa])', nome_orgao)
        orgao_busca = m.group(1) if m else "1ª Turma Recursal do Paraná"
        origem = "3"
    elif "TRU" in nome_orgao:
        orgao_busca = "Turma Regional de Uniformização"
        origem = "2"

    return buscar_jurisprudencia_trf4(
        termo=termo_filtro,
        data_decisao_inicio=data_sessao_ddmmyyyy,
        data_decisao_fim=data_sessao_ddmmyyyy,
        orgao=orgao_busca,
        origem=origem
    )

if __name__ == "__main__":
    print("Testando busca de sessões de Setembro/2026...")
    sessoes_set = coletar_sessoes_trf4(mes=9, ano=2026)
    print(f"Total encontradas em Setembro/2026: {len(sessoes_set)}")
    for s in sessoes_set[:5]:
        print(f"[{s['uf']}] {s['orgao_nome']} | Data: {s['data_hora']} | {s['status']}")

    print("\nTestando extração de acórdãos da sessão de 06/10/2026 da 10ª Turma...")
    acordaos = extrair_acordaos_da_sessao("10ª Turma (Previdenciário)", "06/10/2026")
    print(f"Total de acórdãos extraídos: {len(acordaos)}")
    for a in acordaos[:3]:
        print(f"Processo: {a['processo']} | Relator: {a['relator']}")
        print(f"Ementa: {a['texto_completo'][:180]}...\n")
