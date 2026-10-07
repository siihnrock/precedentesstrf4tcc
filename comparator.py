"""
comparator.py - Motor de Análise e Comparação de Precedentes das Turmas do TRF4.
Mapeia entendimentos das Turmas Especializadas em Previdenciário (5ª, 6ª, 9ª, 10ª Turmas e 2ª Seção)
e Turmas Recursais (RS, SC, PR e TRU4), com módulo especializado em PROVA EMPRESTADA.
"""
import re
import os
import json
from typing import List, Dict, Optional

def extrair_fundamentos_e_tese(texto: str) -> Dict:
    """
    Extrai informações estruturadas da ementa/voto:
    - Resultado (provido, desprovido, parcial)
    - Temas de uniformização citados (Tema XXX STF/STJ/TNU/TRU)
    - Dispositivos legais e súmulas citadas
    - Nuances específicas de PROVA EMPRESTADA
    """
    texto_clean = re.sub(r'\s+', ' ', texto)

    # Identificar resultado
    resultado = "Não identificado"
    if re.search(r'\b(negado provimento|desprovido|desprovimento do recurso|improcedente)\b', texto_clean, re.I):
        resultado = "Recurso Desprovido (Tese do INSS ou Sentença Mantida)"
    elif re.search(r'\b(dar provimento|deu-se provimento|provimento do recurso|recurso provido|julgado procedente)\b', texto_clean, re.I):
        resultado = "Recurso Provido (Tese do Segurado ou Reforma da Decisão)"
    elif re.search(r'\b(parcial provimento|parcialmente provido)\b', texto_clean, re.I):
        resultado = "Parcialmente Provido"
    elif re.search(r'\b(sobrestamento|sobrestado)\b', texto_clean, re.I):
        resultado = "Processo Sobrestado"
    elif re.search(r'\bextin[çc][ãa]o\s+sem\s+resolu[çc][ãa]o\s+do\s+m[ée]rito\b', texto_clean, re.I):
        resultado = "Extinto sem Resolução do Mérito (Tema 629/STJ - Falta de Prova)"

    # Identificar temas citados
    temas = re.findall(r'(?:Tema|TEMA)\s+(?:n[º°]\s*)?(\d+)(?:\s+(?:do\s+)?(STF|STJ|TNU|TRU))?', texto_clean, re.I)
    temas_formatados = []
    for t in temas:
        num = t[0]
        tribunal = t[1] if t[1] else ""
        temas_formatados.append(f"Tema {num} {tribunal}".strip())
    temas_formatados = list(dict.fromkeys(temas_formatados))

    # Identificar Súmulas
    sumulas = []
    if re.search(r'S[úu]mula\s+106\s+(?:do\s+)?TRF4', texto_clean, re.I) or '106' in texto_clean and 'trf4' in texto_clean.lower():
        sumulas.append("Súmula 106/TRF4 (Laudo em Empresa Similar)")
    if re.search(r'S[úu]mula\s+68\s+(?:da\s+)?TNU', texto_clean, re.I):
        sumulas.append("Súmula 68/TNU (Laudo Similar / Ruído)")

    # Nuances específicas de Prova Emprestada
    prova_emprestada_info = {
        'menciona_prova_emprestada': bool(re.search(r'\b(prova emprestada|laudo similar|laudo paradigma|similaridade)\b', texto_clean, re.I)),
        'empresa_ativa': bool(re.search(r'\bempresa\s+ativa\b', texto_clean, re.I)),
        'empresa_inativa_ou_extinta': bool(re.search(r'\b(empresa\s+(?:inativa|extinta|fechada|falida)|encerramento\s+das\s+atividades)\b', texto_clean, re.I)),
        'ruido_mencionado': bool(re.search(r'\bru[íi]do\b', texto_clean, re.I)),
        'agentes_quimicos': bool(re.search(r'\b(hidrocarbonetos|qu[íi]micos|solventes|poeira|graxa|tintas)\b', texto_clean, re.I)),
        'reclamatoria_trabalhista': bool(re.search(r'\b(trabalhista|reclamat[óo]ria|justi[çc]a do trabalho)\b', texto_clean, re.I)),
    }

    return {
        'resultado': resultado,
        'temas_vinculantes': temas_formatados,
        'sumulas': sumulas,
        'prova_emprestada': prova_emprestada_info
    }

def classificar_orgao_trf4(orgao: str) -> str:
    """Classifica o órgão no grupo analítico do TRF4."""
    org_up = orgao.upper()
    if '5ª TURMA' in org_up or 'QUINTA TURMA' in org_up:
        return '5ª Turma (Tribunal)'
    elif '6ª TURMA' in org_up or 'SEXTA TURMA' in org_up:
        return '6ª Turma (Tribunal)'
    elif '9ª TURMA' in org_up or 'NONA TURMA' in org_up:
        return '9ª Turma (Tribunal)'
    elif '10ª TURMA' in org_up or 'DÉCIMA TURMA' in org_up:
        return '10ª Turma (Tribunal)'
    elif '11ª TURMA' in org_up:
        return '11ª Turma (Tribunal)'
    elif '2ª SEÇÃO' in org_up or 'SEÇÃO' in org_up:
        return '2ª Seção (Tribunal)'
    elif 'TRU' in org_up or 'UNIFORMIZAÇÃO' in org_up:
        return 'TRU4 (Uniformização Regional)'
    elif 'RIO GRANDE DO SUL' in org_up or '/RS' in org_up:
        return 'Turmas Recursais RS'
    elif 'SANTA CATARINA' in org_up or '/SC' in org_up:
        return 'Turmas Recursais SC'
    elif 'PARANÁ' in org_up or 'PARANA' in org_up or '/PR' in org_up:
        return 'Turmas Recursais PR'
    return 'Outros Órgãos TRF4'

def gerar_analise_comparativa(termo_busca: str, precedentes: List[Dict], api_key_gemini: Optional[str] = None) -> Dict:
    """
    Gera o comparativo estruturado entre as turmas do TRF4.
    """
    if not precedentes:
        return {'status': 'sem_dados', 'mensagem': 'Nenhum precedente localizado.'}

    # Enriquecer cada acórdão
    grupos_orgaos = {}
    todos_temas = []
    todas_sumulas = []

    for p in precedentes:
        p['analise'] = extrair_fundamentos_e_tese(p.get('texto_completo', ''))
        todos_temas.extend(p['analise']['temas_vinculantes'])
        todas_sumulas.extend(p['analise']['sumulas'])

        grupo_nome = classificar_orgao_trf4(p.get('orgao', ''))
        if grupo_nome not in grupos_orgaos:
            grupos_orgaos[grupo_nome] = []
        grupos_orgaos[grupo_nome].append(p)

    todos_temas = list(dict.fromkeys(todos_temas))
    todas_sumulas = list(dict.fromkeys(todas_sumulas))

    # Construir síntese por grupo de turmas
    resumo_turmas = {}
    for grp, lista in grupos_orgaos.items():
        resultados = [p['analise']['resultado'] for p in lista]
        contagem = {}
        for r in resultados: contagem[r] = contagem.get(r, 0) + 1
        pos_pred = max(contagem, key=contagem.get) if contagem else "Sem padrão dominante"

        # Estatísticas de prova emprestada no grupo
        mencoes_pe = sum(1 for p in lista if p['analise']['prova_emprestada']['menciona_prova_emprestada'])
        mencoes_ativa = sum(1 for p in lista if p['analise']['prova_emprestada']['empresa_ativa'])

        resumo_turmas[grp] = {
            'total': len(lista),
            'posicao_predominante': pos_pred,
            'distribuicao': contagem,
            'mencoes_prova_emprestada': mencoes_pe,
            'mencoes_empresa_ativa': mencoes_ativa,
            'exemplos': lista[:3]
        }

    # Diagnóstico de divergência
    posicoes_ativas = {k: v['posicao_predominante'] for k, v in resumo_turmas.items()}
    divergencia_detectada = len(set(posicoes_ativas.values())) > 1

    diagnostico_txt = (
        "Divergência detectada entre os colegiados analisados: " +
        " | ".join([f"{k}: {v}" for k, v in posicoes_ativas.items()])
    ) if divergencia_detectada else "Alinhamento dominante observado entre os julgados analisados."

    relatorio = {
        'termo': termo_busca,
        'total_analisado': len(precedentes),
        'divergencia_detectada': divergencia_detectada,
        'diagnostico': diagnostico_txt,
        'temas_vinculantes': todos_temas,
        'sumulas_invocadas': todas_sumulas,
        'resumo_orgaos': resumo_turmas,
        'precedentes': precedentes
    }

    if api_key_gemini:
        try:
            relatorio['analise_ia_avancada'] = gerar_analise_com_llm(termo_busca, precedentes, api_key_gemini)
        except Exception as e:
            relatorio['analise_ia_avancada'] = f"Erro na IA: {e}"

    return relatorio

def gerar_analise_com_llm(termo: str, precedentes: List[Dict], api_key: str) -> str:
    """Síntese com LLM Gemini focada nas particularidades do TRF4."""
    import urllib.request
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    contexto = []
    for p in precedentes[:8]:
        contexto.append(
            f"PROCESSO: {p.get('processo')} | ÓRGÃO: {p.get('orgao')} | DATA: {p.get('data_julgamento')}\n"
            f"RELATOR: {p.get('relator')}\nEMENTA/VOTO: {p.get('texto_completo')[:1400]}\n---"
        )
    corpo = "\n".join(contexto)
    prompt = f"""
Você é um especialista em direito previdenciário e precedentes do Tribunal Regional Federal da 4ª Região (TRF4).
Analise os acórdãos anexos sobre: "{termo}".

Enfatize obrigatoriamente:
1. VALORAÇÃO DA PROVA EMPRESTADA E LAUDO POR SIMILARIDADE (SÚMULA 106/TRF4):
   - Como a 5ª, 6ª, 9ª e 10ª Turmas e as Turmas Recursais valoram a prova emprestada.
   - Rigor na exigência de empresa ativa vs inativa/extinta.
   - Distinção entre agente ruído (rejeitado por similaridade) e agentes químicos/físicos.
2. CONFRONTO DIRETO DE TESES ENTRE AS TURMAS.
3. ORIENTAÇÃO PRÁTICA PARA PETICIONAMENTO NO TRF4.

DADOS:
{corpo}
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res['candidates'][0]['content']['parts'][0]['text']
