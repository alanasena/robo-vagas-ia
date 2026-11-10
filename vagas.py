"""Robô de vagas júnior da Alana — só vagas do Brasil.

Fontes:
- Gupy: página oficial de carreiras da empresa (diz se é CLT, PJ, estágio)
- Comunidades de vagas no GitHub: frontendbr, backend-br, react-brasil, qa-brasil
Remotas sempre. Híbridas/presenciais só no Nordeste, a partir de DATA_NORDESTE.
Só envia e-mail quando há vaga nova. Guarda as já vistas em vistas.json.
Cada vaga nova recebe uma nota de compatibilidade dada por IA (ver ia.py).
"""
import html
import json
import os
import re
import smtplib
import unicodedata
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from ia import avaliar, ordenar

ARQ_VISTAS = "vistas.json"
ARQ_RESUMO = "resumo.json"
HORA_RESUMO = 21  # depois desta hora (Brasília) manda o resumo do dia por e-mail
FUSO_BRASIL = timezone(timedelta(hours=-3))
MAX_DIAS = 14  # vagas publicadas há até 14 dias
# A partir desta data também entram vagas híbridas/presenciais no Nordeste
DATA_NORDESTE = datetime(2026, 11, 5, tzinfo=timezone.utc)
# Estados, capitais e siglas do Nordeste (para vagas híbridas/presenciais)
NORDESTE_NOMES = re.compile(r"\b(nordeste|alagoas|bahia|ceara|maranhao|paraiba|pernambuco|piaui|rio grande do norte|"
                            r"sergipe|maceio|salvador|fortaleza|sao luis|joao pessoa|recife|teresina|natal|aracaju)\b")
NORDESTE_UF = {"al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"}
UA = {"User-Agent": "Mozilla/5.0 (robo-vagas-junior)"}

REPOS_GITHUB = ["frontendbr/vagas", "backend-br/vagas", "react-brasil/vagas", "qa-brasil/vagas"]

JUNIOR = re.compile(r"\b(junior|jr\.?|trainee|recem[- ]formad\w*|entry[- ]level)\b")
# Nível acima de júnior: sai mesmo que o título também diga "júnior" (ex.: "Jr/Pl")
SENIOR = re.compile(r"\b(senior|sr\.?|pleno|pl|lead|principal|staff|especialista|tech lead|gerente|coordenador\w*|ii|iii)\b")
PJ_TITULO = re.compile(r"\bpj\b")
# "Analista I", "Desenvolvedor 1": primeiro nível, conta como júnior
NIVEL_I = re.compile(r"\b(analista|desenvolvedor\w*|programador\w*|engenheir\w*|tester|qa)\s+(de \w+\s+)?(i|1)\b")
# Sinais de júnior na descrição, para títulos que não dizem o nível
JUNIOR_DESC = re.compile(r"(\bjunior\b|\bjr\b|inicio de carreira|comeco de carreira|recem[- ]formad\w*|primeiro emprego|"
                         r"sem experiencia|nao (e necessari\w|exigimos|precisa ter) experiencia|"
                         r"(0|zero|1|um) a (1|2|dois) anos? de experiencia|ate (1|2|um|dois) anos? de experiencia|entry[- ]level)")
# Sinais de nível acima na descrição
SENIOR_DESC = re.compile(r"(\b(nivel|vaga|posicao|cargo) (pleno|senior)\b|experiencia (minima |comprovada )?de ([3-9]|tres|quatro|cinco) anos|"
                         r"([3-9]|tres|quatro|cinco)\+? anos de experiencia)")
# Áreas que a Alana não quer
AREAS_FORA = re.compile(r"(infraestrutura|\binfra\b|seguranca|governanca|cloud|suporte|help ?desk|service ?desk|\bios\b|swift|devops|\bsre\b|\bredes\b)")
# Vagas em espanhol
ESPANHOL_TITULO = re.compile(r"\b(soporte|datos|desarrollador\w*|ingenier[oa]|empleo)\b")
# Áreas que não são tecnologia
NAO_TECH = re.compile(r"(manutencao|mecanic|eletromecanic|eletrotecnic|usinagem|\bcnc\b|\bpcp\b|torneiro|programador de producao|redes sociais|social media|\brh\b|recursos humanos|recrutamento|selecao|departamento pessoal|\bdp\b|people|talent|gente e gest|treinamento|comercial|vendas|vendedor|marketing|financeir|contabil|fiscal|juridic|advogad|administrativ|logistic|compras|faturamento|cobranca|telemarketing|atendente|recepc|secretari|enfermag|medic|farmac|laborat|producao|industrial)")
# Precisa ter pelo menos uma destas no título
AREA_DELA = re.compile(r"(desenvolvedor\w*|programador\w*|analista de sistemas|\bsistemas\b|\bdev\b|developer|software|front[- ]?end|\bfront\b|back[- ]?end|\bback\b|full[- ]?stack|\bqa\b|quality assurance|\btestes?\b|tester|qualidade|\bux\b|ui ?/ ?ux|\bdados\b|\bdata\b)")
# "Qualidade" sozinha pode ser de fábrica/laboratório: vai para o Talvez
QUALIDADE_SOFT = re.compile(r"(software|\bqa\b|\btestes?\b|tester|sistemas|\bti\b|tecnologia)")
# Vagas exclusivas para pessoas com deficiência (as "também para PcD" continuam entrando)
SO_PCD = re.compile(r"(\bpcd\b|\bpcds\b|pessoas? com deficiencia)")
TAMBEM_PCD = re.compile(r"(tambem|inclusive)\s+(p/|para|a)?\s*(pcd|pessoas? com)")
# Inglês acima do básico (no texto já normalizado)
INGLES_NIVEL = re.compile(r"(ingles\s*((em|de|no|nivel|a|o|e|minimo|pelo menos)\s+){0,4}(intermediario|avancado|fluente|fluencia|conversacao|tecnico avancado|nivel b2|b2|c1|c2)|"
                          r"(intermediario|avancado|fluente|fluencia|conversacao)\s*(em|de|no)?\s*ingles|"
                          r"(fluent|fluency|advanced|intermediate|upper[- ]intermediate|proficient|professional)\s*(level\s*)?(of\s*|in\s*)?english|"
                          r"english\s*[(:-]?\s*(fluent|advanced|intermediate|b2|c1|c2))")
OPCIONAL = re.compile(r"(diferencial|desejavel|desejado|plus|nice to have|bonus|sera um|e um diferencial|nao obrigatorio|preferencial)")
# Vaga em inglês
TITULO_INGLES = re.compile(r"\b(engineer|engineering|developer|analyst|intern|internship|specialist)\b")
TITULO_PT = re.compile(r"(desenvolvedor|analista|engenheir|programador|estagi|testador)")
# Na descrição
RESIDIR = re.compile(r"(residir|residente|resida|morar)\s+(no estado d[eo]|na cidade d[eo]|na regiao d[eo]|em|no|na|proximo)\s+([a-z ,/.-]{2,60})")
NOTURNO = re.compile(r"(noturn\w*|turno da noite|madrugada|\b23h|\b23 00|\b23 horas)")
ESPANHOL_DESC = re.compile(r"(espanhol (obrigatorio|fluente|avancado|nativo)|fluente em espanhol|fluencia em espanhol|dominio do espanhol)")
INGLES_ALTO = re.compile(r"(ingles (fluente|avancado)|fluent|advanced english|\bc1\b|\bc2\b)")
ENCERRADA = re.compile(r"(vaga encerrada|inscrições encerradas|processo encerrado|vaga expirada|vaga não encontrada|"
                       r"no longer accepting|job not found|the job you requested was not found|"
                       r"position (has been )?filled|job (has )?expired|this job is closed|no longer available)", re.I)

GUPY_TIPOS = {
    "vacancy_type_effective": "CLT (efetivo)",
    "vacancy_type_internship": "Estágio",
    "vacancy_type_trainee": "Trainee",
    "vacancy_type_legal_entity": "PJ",
    "vacancy_legal_entity": "PJ",
    "vacancy_type_temporary": "Temporário",
    "vacancy_type_apprentice": "Jovem aprendiz",
    "vacancy_type_freelancer": "Freelancer",
    "vacancy_type_autonomous": "Autônomo",
}
GUPY_MODELO = {"remote": "Remoto", "hybrid": "Híbrido", "on-site": "Presencial"}


# ---------- utilidades ----------
def norm(txt):
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 +#.-]", " ", txt.lower()).strip()


def no_nordeste(texto, com_sigla=False):
    """True se o texto fala de um lugar do Nordeste. com_sigla=True também aceita "CE", "PE"...
    (só para campos de cidade/estado, onde a sigla não se confunde com outra palavra)."""
    t = norm(texto)
    if NORDESTE_NOMES.search(t):
        return True
    return com_sigla and any(p in NORDESTE_UF for p in re.findall(r"[a-z]+", t))


def limpar(txt, descricao=False):
    txt = re.sub(r"<[^>]+>", " ", txt or "")
    txt = html.unescape(txt)
    if descricao:  # separa títulos grudados no texto ("qualificaçõesGraduação"), só na descrição
        txt = re.sub(r"([a-zà-ú;:.])([A-ZÀ-Ú][a-zà-ú])", r"\1 \2", txt)
    return re.sub(r"\s+", " ", txt).strip()


def data(v):
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def trecho(desc, palavras, tamanho=350):
    m = re.search(palavras, desc or "", re.I)
    return desc[m.start():m.start() + tamanho].strip() + "…" if m else None


# ---------- fonte 1: Gupy ----------
GUPY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://portal.gupy.io",
    "Referer": "https://portal.gupy.io/",
}
# Endereços da busca pública da Gupy (se um mudar, tenta o outro)
GUPY_URLS = [
    "https://portal.gupy.io/api/job-search/jobs?jobName={termo}&limit={limite}&offset={offset}",
    "https://employability-portal.gupy.io/api/v1/jobs?jobName={termo}&limit={limite}&offset={offset}",
]
_gupy_campos_mostrados = False


def _lista(dados):
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for k in ("data", "jobs", "results", "result", "items", "content"):
            if isinstance(dados.get(k), list):
                return dados[k]
            if isinstance(dados.get(k), dict):
                achou = _lista(dados[k])
                if achou:
                    return achou
    return []


def gupy_pagina(termo, offset):
    erros = []
    for modelo in GUPY_URLS:
        for limite in (100, 12):
            url = modelo.format(termo=termo, limite=limite, offset=offset)
            try:
                r = requests.get(url, headers=GUPY_HEADERS, timeout=30)
            except Exception as e:
                erros.append(str(e)[:80])
                break
            if r.status_code == 200:
                return _lista(r.json()), limite
            erros.append(f"{r.status_code} em {url.split('?')[0]} (limit={limite})")
            if r.status_code not in (400, 422):
                break  # não é problema de tamanho da página
    print(f"Gupy falhou ({termo}):", " | ".join(erros))
    return None, 0


def _pega(j, *chaves):
    for c in chaves:
        v = j
        for parte in c.split("."):
            v = v.get(parte) if isinstance(v, dict) else None
        if v not in (None, ""):
            return v
    return None


# Na Gupy, busca pelo nível E pela área (muita vaga júnior não diz "júnior" no título)
GUPY_TERMOS = ["junior", "júnior", "jr", "trainee", "desenvolvedor", "desenvolvedora", "programador",
               "analista de sistemas", "front-end", "back-end", "full stack", "analista de testes", "qa",
               "analista de dados", "ux"]


def gupy():
    global _gupy_campos_mostrados
    vagas = []
    for termo in GUPY_TERMOS:
        offset = 0
        while offset < 300:
            itens, limite = gupy_pagina(termo, offset)
            if not itens:
                break
            if not _gupy_campos_mostrados:
                print("Gupy campos:", sorted(itens[0].keys()))
                _gupy_campos_mostrados = True
            for j in itens:
                tipo = _pega(j, "type", "contractType", "jobType") or ""
                if tipo == "vacancy_type_talent_pool":
                    continue  # banco de talentos, não é vaga aberta
                wt = _pega(j, "workplaceType", "workplace", "workModel")
                modelo = GUPY_MODELO.get(wt, "Remoto" if _pega(j, "isRemoteWork", "remote") else "Não informado")
                cidade = ", ".join(str(x) for x in [_pega(j, "city", "address.city", "location.city"),
                                                    _pega(j, "state", "address.state", "location.state")] if x)
                vagas.append({
                    "fonte": "gupy", "fonte_nome": "Gupy — página oficial da empresa",
                    "id": str(_pega(j, "id", "jobId")),
                    "empresa": _pega(j, "careerPageName", "companyName", "company.name", "careerPage.name") or "?",
                    "cargo": _pega(j, "name", "title", "jobName") or "?",
                    "url": _pega(j, "jobUrl", "applyUrl", "url", "link"),
                    "publicada": data(_pega(j, "publishedDate", "publishedAt", "createdAt")),
                    "prazo": data(_pega(j, "applicationDeadline", "deadline")),
                    "modalidade": modelo, "local": cidade,
                    "no_nordeste": no_nordeste(cidade, com_sigla=True),
                    "exterior": False,
                    "contrato": GUPY_TIPOS.get(tipo, "Não informado"),
                    "descricao": limpar(_pega(j, "description") or "", descricao=True),
                    "junior_etiqueta": False, "avisos": [],
                    "ja_confirmada": True,  # a Gupy só lista vagas publicadas
                })
            if len(itens) < limite:
                break
            offset += limite
    return vagas


# ---------- fonte 2: comunidades no GitHub ----------
def github_vagas(agora):
    headers = dict(UA)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    desde = (agora - timedelta(days=MAX_DIAS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    vagas = []
    for repo in REPOS_GITHUB:
        try:
            r = requests.get(f"https://api.github.com/repos/{repo}/issues",
                             params={"state": "open", "per_page": 100, "since": desde},
                             headers=headers, timeout=30)
            r.raise_for_status()
            itens = r.json()
        except Exception as e:
            print(f"GitHub {repo} falhou:", e)
            continue
        for i in itens:
            if "pull_request" in i:
                continue
            etiquetas = [norm(l["name"]) for l in i.get("labels", [])]
            tem = lambda *ks: any(k in e for e in etiquetas for k in ks)
            titulo = i.get("title", "")
            t = norm(titulo)
            corpo = i.get("body") or ""

            if tem("remoto") or "remoto" in t or "remote" in t:
                modelo = "Remoto"
            elif tem("hibrido") or "hibrido" in t:
                modelo = "Híbrido"
            elif tem("presencial", "alocado") or "presencial" in t:
                modelo = "Presencial"
            elif tem("flexivel"):
                modelo = "Flexível"
            else:
                modelo = "Não informado"

            if tem("clt") or "clt" in t:
                contrato = "CLT"
            elif tem("pj") or re.search(r"\bpj\b", t):
                contrato = "PJ"
            elif tem("estagi"):
                contrato = "Estágio"
            elif tem("freela"):
                contrato = "Freela"
            else:
                contrato = "Não informado"

            m = re.search(r"\s(?:na|no|@|at|-)\s+([^\[\]|/-]{2,40})$", titulo)
            avisos = []
            if tem("falta", "pendente"):
                avisos.append("A comunidade marcou esse anúncio como faltando informações")
            if tem("ingles"):
                avisos.append("Pede inglês")
            vagas.append({
                "fonte": repo, "fonte_nome": f"Comunidade {repo.split('/')[0]} no GitHub — confirme no site da empresa",
                "id": str(i["id"]),
                "empresa": m.group(1).strip() if m else "Ver no anúncio",
                "cargo": titulo, "url": i.get("html_url"),
                "publicada": data(i.get("created_at")), "prazo": None,
                "modalidade": modelo,
                "local": next((l["name"] for l in i.get("labels", []) if no_nordeste(l["name"])), ""),
                "no_nordeste": any(no_nordeste(e) for e in etiquetas) or no_nordeste(titulo),
                "exterior": tem("exterior", "fora-do-pais", "fora do pais"),
                "contrato": contrato, "descricao": limpar(corpo, descricao=True),
                "junior_etiqueta": tem("junior"), "avisos": avisos,
                "ja_confirmada": True,  # issue aberta = vaga ativa
            })
    return vagas


# ---------- fontes 3, 4 e 5: Sólides, Remotar e Programathor ----------
NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
TERMOS_BUSCA = ["desenvolvedor junior", "desenvolvedora junior", "desenvolvedor jr", "dev junior",
                "qa junior", "analista de testes", "qualidade de software", "software junior",
                "front-end junior", "back-end junior", "full stack junior", "ux junior",
                "analista de dados junior", "engenheiro de dados junior"]


def contrato_pelo_texto(texto):
    t = norm(texto)
    clt = bool(re.search(r"\bclt\b", t))
    pj = bool(re.search(r"\bpj\b|pessoa juridica", t))
    if clt and pj:
        return "CLT ou PJ"
    if clt:
        return "CLT"
    if pj:
        return "PJ"
    return "Não informado"


def solides():
    vagas = []
    for termo in TERMOS_BUSCA:
        for pagina in (1, 2):
            try:
                r = requests.get("https://vagas.solides.com.br/api/vacancies",
                                 params={"page": pagina, "take": 14, "title": termo, "locations": ""},
                                 headers={**NAVEGADOR, "Referer": "https://vagas.solides.com.br/"}, timeout=30)
                r.raise_for_status()
                dados = r.json()
                itens = dados.get("data") or []
            except Exception as e:
                print(f"Sólides falhou ({termo}):", str(e)[:120])
                break
            for j in itens:
                if j.get("isDisabled") or j.get("isHiddenJob"):
                    continue
                niveis = [norm(x.get("name", "")) for x in (j.get("seniority") or [])]
                contratos = [x.get("name", "") for x in (j.get("recruitmentContractType") or [])]
                if j.get("homeOffice") or j.get("jobType") == "remoto":
                    modelo = "Remoto"
                else:
                    modelo = {"hibrido": "Híbrido", "presencial": "Presencial"}.get(j.get("jobType"), "Não informado")
                cidade = ", ".join(x for x in [(j.get("city") or {}).get("name"), (j.get("state") or {}).get("code")] if x)
                slug, vid = j.get("slug"), j.get("id")
                url = f"https://{slug}.vagas.solides.com.br/vaga/{vid}" if slug and vid else None
                if contratos:
                    contrato = "PJ" if contratos == ["PJ"] else " / ".join(contratos)
                else:
                    contrato = contrato_pelo_texto(j.get("description", ""))
                vagas.append({
                    "fonte": "solides", "fonte_nome": "Sólides — página oficial da empresa",
                    "id": str(vid), "empresa": (j.get("companyName") or "?").strip(),
                    "cargo": (j.get("title") or "?").strip(), "url": url,
                    "publicada": data(j.get("createdAt")), "prazo": None,
                    "modalidade": modelo, "local": cidade,
                    "no_nordeste": norm((j.get("state") or {}).get("code", "")) in NORDESTE_UF,
                    "exterior": False, "contrato": contrato,
                    "descricao": limpar(j.get("description", ""), descricao=True),
                    "junior_etiqueta": "junior" in niveis,
                    "nivel_acima": bool(niveis) and "junior" not in niveis and "trainee" not in niveis,
                    "so_pcd": bool(j.get("pcdOnly")),
                    "avisos": [], "ja_confirmada": True,
                })
            if len(itens) < 14:
                break
    return vagas


def remotar():
    vagas = []
    for termo in ["junior", "jr"]:
        for pagina in (1, 2):
            try:
                r = requests.get("https://api.remotar.com.br/jobs",
                                 params={"search": termo, "page": pagina},
                                 headers={**NAVEGADOR, "Origin": "https://remotar.com.br",
                                          "Referer": "https://remotar.com.br/"}, timeout=30)
                r.raise_for_status()
                itens = r.json().get("data") or []
            except Exception as e:
                print(f"Remotar falhou ({termo}):", str(e)[:120])
                break
            for j in itens:
                if j.get("expired") or not j.get("active", True):
                    continue
                empresa = j.get("companyDisplayName") or (j.get("company") or {}).get("name") or "?"
                url = j.get("externalLink") if j.get("isExternalLink") and j.get("externalLink") \
                    else f"https://remotar.com.br/job/{j.get('id')}"
                desc = limpar((j.get("subtitle") or "") + " " + (j.get("description") or ""), descricao=True)
                vagas.append({
                    "fonte": "remotar", "fonte_nome": "Remotar — vagas 100% remotas",
                    "id": str(j.get("id")), "empresa": empresa.strip(),
                    "cargo": (j.get("title") or "?").strip(), "url": url,
                    "publicada": data(j.get("createdAt")), "prazo": data(j.get("expiresAt")),
                    "modalidade": "Remoto", "local": "Brasil",
                    "no_nordeste": False, "exterior": False,
                    "contrato": contrato_pelo_texto(desc), "descricao": desc,
                    "junior_etiqueta": False, "avisos": [],
                    "ja_confirmada": not j.get("isExternalLink"),  # link externo: confere se ainda existe
                })
            if len(itens) < 50:
                break
    return vagas


def programathor():
    vagas = []
    for pagina in (1, 2, 3):
        try:
            r = requests.get(f"https://programathor.com.br/jobs/page/{pagina}",
                             params={"expertise": "Júnior", "contract_type": "CLT"},
                             headers=NAVEGADOR, timeout=30)
            r.raise_for_status()
            pagina_html = r.text
        except Exception as e:
            print("Programathor falhou:", str(e)[:120])
            break
        blocos = re.findall(r'<a href="(/jobs/(\d+)[^"]*)">(.*?)</a>', pagina_html, re.S)
        if not blocos:
            break
        for link, vid, bloco in blocos:
            h3 = re.search(r"<h3[^>]*>(.*?)</h3>", bloco, re.S)
            if not h3:
                continue
            if re.search(r">\s*Vencida\s*<", h3.group(1)):
                continue  # inscrições encerradas
            titulo_html = re.sub(r"<span[^>]*>.*?</span>", " ", h3.group(1), flags=re.S)
            cargo = limpar(titulo_html)
            campo = lambda icone: (lambda m: limpar(m.group(1)) if m else "")(
                re.search(rf"<i class=['\"][^'\"]*{icone}[^'\"]*['\"]></i>(.*?)</span>", bloco, re.S))
            local = campo("fa-map-marker-alt")
            ln = norm(local)
            if "remoto" in ln:
                modelo = "Remoto"
            elif "hibrido" in ln:
                modelo = "Híbrido"
            elif "presencial" in ln:
                modelo = "Presencial"
            else:
                modelo = "Não informado"
            vagas.append({
                "fonte": "programathor", "fonte_nome": "Programathor — vagas de tecnologia",
                "id": vid, "empresa": campo("fa-briefcase") or "?", "cargo": cargo,
                "url": "https://programathor.com.br" + link,
                "publicada": None, "prazo": None,
                "modalidade": modelo, "local": local,
                "no_nordeste": no_nordeste(local, com_sigla=True),
                "exterior": False, "contrato": campo("fa-file-alt") or "Não informado",
                "descricao": "", "junior_etiqueta": "junior" in norm(campo("fa-chart-bar")),
                "avisos": [], "ja_confirmada": True,
            })
    return vagas


# ---------- filtros ----------
def chave_dup(v):
    """Empresa + título, sem maiúsculas, acento, traço ou espaço."""
    limpa = lambda x: re.sub(r"[^a-z0-9]", "", norm(x))
    empresa = v["empresa"] if v["empresa"] not in ("?", "Ver no anúncio") else ""
    return "dup:" + limpa(empresa) + "|" + limpa(v["cargo"])


def classificar(v):
    """Devolve ("fora", motivo), ("talvez", motivo) ou ("ok", None)."""
    t = norm(v["cargo"])
    d = norm(v["descricao"])

    # --- título: o que sai direto ---
    if SENIOR.search(t) or v.get("nivel_acima"):
        return "fora", "nível pleno/sênior"
    if "banco de talentos" in t:
        return "fora", "banco de talentos"
    sem_nivel_no_titulo = not (v["junior_etiqueta"] or JUNIOR.search(t) or NIVEL_I.search(t))
    if sem_nivel_no_titulo:
        # o título não diz o nível: decide pela descrição
        if SENIOR_DESC.search(d) and not JUNIOR_DESC.search(d):
            return "fora", "nível pleno/sênior (pela descrição)"
    if v["contrato"] == "PJ" or PJ_TITULO.search(t):
        return "fora", "PJ"
    if v.get("so_pcd") or (SO_PCD.search(t) and not TAMBEM_PCD.search(t)):
        return "fora", "exclusiva PcD"
    if ESPANHOL_TITULO.search(t):
        return "fora", "vaga em espanhol"
    if NAO_TECH.search(t):
        return "fora", "outra área"
    if AREAS_FORA.search(t):
        return "fora", "área fora do seu foco"
    if not AREA_DELA.search(t):
        return "fora", "título sem palavra da sua área"

    # --- inglês acima do básico ---
    motivos = []
    m = INGLES_NIVEL.search(d)
    if m:
        perto = d[max(0, m.start() - 80): m.end() + 80]
        if OPCIONAL.search(perto):
            motivos.append("Inglês intermediário/avançado aparece como diferencial")
        else:
            return "fora", "pede inglês intermediário/avançado"

    # --- dúvidas: vão para o "Talvez" ---
    if "qualidade" in t and not QUALIDADE_SOFT.search(t):
        motivos.append("“Qualidade” pode não ser de software")
    m = RESIDIR.search(d)
    if m and not no_nordeste(m.group(0)):
        motivos.append(f"Pede para morar em: “{m.group(3).strip()[:40]}”")
    if v["modalidade"] == "Não informado":
        motivos.append("Não diz se é remota, híbrida ou presencial")
    palavras = d.split()
    en = sum(palavras.count(w) for w in ("the", "and", "you", "with", "will", "our", "are"))
    pt = sum(palavras.count(w) for w in ("de", "e", "com", "para", "voce", "nossa", "sera"))
    if (TITULO_INGLES.search(t) and not TITULO_PT.search(t)) or (en > 10 and en > pt):
        motivos.append("Vaga em inglês — deve pedir inglês")
    if NOTURNO.search(d):
        motivos.append("Fala em horário noturno")
    if ESPANHOL_DESC.search(d):
        motivos.append("Pede espanhol")
    if sem_nivel_no_titulo and not JUNIOR_DESC.search(d):
        motivos.append("Não diz o nível (júnior ou pleno) — confira")
    if motivos:
        return "talvez", "; ".join(motivos)
    return "ok", None


def modalidade_ok(v, agora):
    if v["exterior"]:
        return False
    if v["modalidade"] in ("Remoto", "Flexível", "Não informado"):
        return True
    return v["no_nordeste"] and agora >= DATA_NORDESTE


def aberta_no_ats(url):
    """Ashby, Greenhouse e Lever montam a página com JavaScript; pergunta direto para a API deles.
    Devolve True/False, ou None se não for um desses sites."""
    m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})", url)
    if m:
        r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}", headers=UA, timeout=20)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return any(j.get("id") == m.group(2) for j in r.json().get("jobs", []))
    m = re.search(r"greenhouse\.io/([^/?#]+)/jobs/(\d+)", url)
    if m:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}", headers=UA, timeout=20)
        return r.status_code == 200
    m = re.search(r"jobs\.lever\.co/([^/?#]+)/([0-9a-f-]{36})", url)
    if m:
        r = requests.get(f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}", headers=UA, timeout=20)
        return r.status_code == 200
    return None


def inscricoes_abertas(v, agora):
    if v["prazo"] and v["prazo"] < agora:
        return False, None
    if v.get("ja_confirmada"):
        return True, None
    try:
        ats = aberta_no_ats(v["url"])
        if ats is not None:
            return ats, None
        r = requests.get(v["url"], headers=UA, timeout=20)
        if r.status_code in (404, 410) or ENCERRADA.search(r.text[:200000]):
            return False, None
        if r.status_code >= 400:
            return True, "Não consegui abrir a página para confirmar se está aberta"
        return True, None
    except Exception:
        return True, "Não consegui abrir a página para confirmar se está aberta"


def completar_avisos(v):
    if v["contrato"] == "Não informado":
        v["avisos"].append("Tipo de contratação não informado")


# ---------- e-mail ----------
def bloco(v, talvez=False):
    req = trecho(v["descricao"], r"(requisitos|requirements|qualifica|o que (voc[eê]|esperamos)|precisa ter)") or "Não encontrei — veja na página"
    ben = trecho(v["descricao"], r"(benef[ií]cios|oferecemos|o que oferecemos)") or "Não informado"
    modal = v["modalidade"] + (f" — {v['local']}" if v["local"] else "")
    avisos = "".join(f"<li>⚠️ {html.escape(a)}</li>" for a in v["avisos"])
    faixa = ""
    borda = "#ddd"
    if talvez:
        borda = "#f59e0b"
        faixa = (f'<div style="background:#fef3c7;color:#92400e;border-radius:6px;padding:6px 10px;'
                 f'margin-bottom:8px;font-weight:bold">🤔 TALVEZ — {html.escape(v.get("motivo_talvez", ""))}</div>')
    return f"""
    <div style="border:2px solid {borda};border-radius:8px;padding:12px;margin:12px 0">
      {faixa}
      {bloco_ia(v.get("ia"))}
      <h3 style="margin:0">{html.escape(v['cargo'])}</h3>
      <p style="margin:4px 0"><b>{html.escape(v['empresa'])}</b></p>
      <p style="margin:4px 0"><b>Modalidade:</b> {html.escape(modal)}</p>
      <p style="margin:4px 0"><b>Contratação:</b> {html.escape(v['contrato'])}</p>
      <p style="margin:4px 0"><b>Requisitos:</b> {html.escape(req)}</p>
      <p style="margin:4px 0"><b>Benefícios:</b> {html.escape(ben)}</p>
      <p style="margin:4px 0;color:#666;font-size:13px">Fonte: {html.escape(v['fonte_nome'])}</p>
      {f'<ul style="color:#b45309">{avisos}</ul>' if avisos else ''}
      <p><a href="{html.escape(v['url'] or '#')}">Ver vaga e se inscrever →</a></p>
    </div>"""


def bloco_ia(ia):
    if not ia:
        return ""
    cor = "#15803d" if ia["nota"] >= 7 else "#b45309" if ia["nota"] >= 4 else "#b91c1c"
    lista = lambda itens: "; ".join(html.escape(x.strip().rstrip(".")) for x in itens[:3])
    linha = lambda icone, rotulo, itens: (f'<p style="margin:2px 0">{icone} <b>{rotulo}:</b> {lista(itens)}</p>'
                                          if itens else "")
    titulo = f"🤖 Nota {ia['nota']}/10" + (" — ❌ eliminada" if ia.get("eliminada") else "")
    return f"""
      <div style="background:#f8fafc;border-left:4px solid {cor};padding:8px;margin-bottom:8px">
        <p style="margin:0;font-size:18px;color:{cor}"><b>{titulo}</b></p>
        <p style="margin:2px 0">{html.escape(ia['resumo'])}</p>
        {linha("❌", "Eliminada por", ia.get("motivos_eliminacao", []))}
        {linha("✅", "Combina", ia.get("pontos_fortes", []))}
        {linha("📚", "Falta", ia.get("pontos_fracos", []))}
        {linha("🚩", "Atenção", ia.get("alertas", []))}
        {f'<p style="margin:2px 0;color:#666;font-size:12px">Cálculo: {html.escape(ia["calculo"])}</p>' if ia.get("calculo") else ""}
      </div>"""


def bloco_eliminada(v):
    motivo = "; ".join(v["ia"].get("motivos_eliminacao") or []) or v["ia"].get("resumo", "")
    return (f"<li style='margin:4px 0'><a href=\"{html.escape(v['url'] or '#')}\">{html.escape(v['cargo'])}</a>"
            f" — {html.escape(v['empresa'])}<br><span style='color:#666;font-size:13px'>{html.escape(motivo)}</span></li>")


def enviar(certas, talvez, eliminadas=()):
    user = os.environ["GMAIL_USER"]
    senha = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    assunto = f"🔔 {len(certas)} vaga(s) júnior nova(s)"
    if talvez:
        assunto += f" + {len(talvez)} talvez"
    notas = [v["ia"]["nota"] for v in certas + talvez if v.get("ia")]
    if notas:
        assunto += f" — melhor nota {max(notas)}/10"
    msg["Subject"] = assunto
    msg["From"] = user
    destino = os.environ.get("EMAIL_DESTINO") or user  # por padrão, manda para o próprio Gmail
    msg["To"] = destino
    corpo = "<div style='font-family:sans-serif;max-width:640px'>"
    if certas:
        corpo += "<h2>✅ Vagas para você</h2>" + "".join(bloco(v) for v in certas)
    if talvez:
        corpo += ("<h2 style='margin-top:28px'>🤔 Talvez — confira antes de aplicar</h2>"
                  "<p style='color:#666'>Passaram nos filtros, mas tem algo que pode não servir.</p>"
                  + "".join(bloco(v, talvez=True) for v in talvez))
    if eliminadas:
        corpo += ("<details style='margin-top:28px'><summary style='color:#666;cursor:pointer'>"
                  f"🗑️ {len(eliminadas)} vaga(s) que a IA eliminou (só pra você conferir)</summary>"
                  "<ul>" + "".join(bloco_eliminada(v) for v in eliminadas) + "</ul></details>")
    corpo += "</div>"
    msg.attach(MIMEText(corpo, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, senha)
        s.sendmail(user, [destino], msg.as_string())


def enviar_whatsapp(vagas, n_talvez=0):
    """Opcional: só funciona se os segredos WHATSAPP_NUMERO e CALLMEBOT_APIKEY existirem."""
    numero = os.environ.get("WHATSAPP_NUMERO")
    chave = os.environ.get("CALLMEBOT_APIKEY")
    if not numero or not chave:
        return
    if not vagas:
        vagas = []
    # manda em grupos de 5 para a mensagem não ficar grande demais
    mensagens = []
    for i in range(0, len(vagas), 5):
        partes = [f"🔔 *{len(vagas)} vaga(s) júnior nova(s)*"] if i == 0 else []
        for v in vagas[i:i + 5]:
            nota = (f"🤖 Nota {v['ia']['nota']}/10" + (" ❌ eliminada" if v["ia"].get("eliminada") else "") + "\n"
                    if v.get("ia") else "")
            partes.append(
                f"\n{nota}*{v['cargo']}*\n{v['empresa']}\n"
                f"{v['modalidade']} · {v['contrato']}"
                + (f"\n⚠️ {'; '.join(v['avisos'])}" if v["avisos"] else "")
                + f"\n{v['url']}"
            )
        mensagens.append(partes)
    if n_talvez:
        mensagens.append([f"🤔 +{n_talvez} vaga(s) no *Talvez* — veja no e-mail"])
    for partes in mensagens:
        try:
            r = requests.get("https://api.callmebot.com/whatsapp.php",
                             params={"phone": numero, "text": "\n".join(partes), "apikey": chave},
                             timeout=30)
            print("WhatsApp:", r.status_code)
        except Exception as e:
            print("WhatsApp falhou:", e)


# ---------- resumo diário ----------
NOMES_FONTES = {"gupy": "Gupy", "solides": "Sólides", "remotar": "Remotar", "programathor": "Programathor",
                **{r: f"Comunidade {r.split('/')[0]}" for r in REPOS_GITHUB}}


def resumo_vazio(agora):
    return {"inicio": agora.isoformat(), "ultimo_envio": None, "rodadas": 0, "enviadas": 0, "talvez": 0,
            "descartadas": {}, "lidas_max": {}, "vazias": {}}


def carregar_resumo(agora):
    try:
        with open(ARQ_RESUMO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return resumo_vazio(agora)


def somar_rodada(r, todas, certas, talvez, descartes):
    r["rodadas"] += 1
    r["enviadas"] += len(certas)
    r["talvez"] += len(talvez)
    for motivo, n in descartes.items():
        r["descartadas"][motivo] = r["descartadas"].get(motivo, 0) + n
    por_fonte = {}
    for v in todas:
        por_fonte[v["fonte"]] = por_fonte.get(v["fonte"], 0) + 1
    for fonte in NOMES_FONTES:
        n = por_fonte.get(fonte, 0)
        r["lidas_max"][fonte] = max(r["lidas_max"].get(fonte, 0), n)
        if n == 0:  # a fonte não trouxe nada: pode ter saído do ar ou mudado
            r["vazias"][fonte] = r["vazias"].get(fonte, 0) + 1


def enviar_resumo(r, agora):
    inicio = datetime.fromisoformat(r["inicio"]).astimezone(FUSO_BRASIL)
    fim = agora.astimezone(FUSO_BRASIL)
    linha = lambda rotulo, valor: f"<tr><td style='padding:3px 12px 3px 0'>{rotulo}</td><td><b>{valor}</b></td></tr>"
    desc = "".join(linha(html.escape(m), n) for m, n in sorted(r["descartadas"].items(), key=lambda x: -x[1])) \
        or linha("Nenhuma", "")
    fontes = "".join(linha(html.escape(NOMES_FONTES[f]), r["lidas_max"].get(f, 0)) for f in NOMES_FONTES)
    problemas = [f"{NOMES_FONTES[f]} veio vazia em {n} de {r['rodadas']} rodadas"
                 for f, n in r["vazias"].items() if r["rodadas"] and n == r["rodadas"]]
    alerta = ("<p style='color:#b91c1c'>⚠️ <b>Atenção:</b> " + "; ".join(html.escape(p) for p in problemas)
              + ". Se for a Gupy, a Sólides ou a Remotar, o site pode ter mudado; numa comunidade pequena, pode só não ter tido vaga.</p>") if problemas else "<p>✅ Todas as fontes funcionaram.</p>"
    corpo = f"""<div style='font-family:sans-serif;max-width:640px'>
      <h2>📊 Resumo do robô de vagas</h2>
      <p style='color:#666'>De {inicio:%d/%m %H:%M} até {fim:%d/%m %H:%M}</p>
      <table>{linha("Rodadas", r["rodadas"])}{linha("Vagas novas enviadas", r["enviadas"])}{linha("No Talvez", r["talvez"])}</table>
      <h3>Descartadas pelos filtros</h3><table>{desc}</table>
      <h3>Vagas lidas por fonte (maior número numa rodada)</h3><table>{fontes}</table>
      {alerta}</div>"""
    user = os.environ["GMAIL_USER"]
    destino = os.environ.get("EMAIL_DESTINO") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Resumo do dia — robô de vagas ({fim:%d/%m}): {r['enviadas']} enviada(s)"
    msg["From"], msg["To"] = user, destino
    msg.attach(MIMEText(corpo, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, os.environ["GMAIL_APP_PASSWORD"])
        s.sendmail(user, [destino], msg.as_string())


def atualizar_resumo(agora, todas, certas, talvez, descartes):
    r = carregar_resumo(agora)
    somar_rodada(r, todas, certas, talvez, descartes)
    hoje = agora.astimezone(FUSO_BRASIL)
    if hoje.hour >= HORA_RESUMO and r.get("ultimo_envio") != hoje.date().isoformat():
        try:
            enviar_resumo(r, agora)
            print("Resumo do dia enviado")
            r = resumo_vazio(agora)
            r["ultimo_envio"] = hoje.date().isoformat()
        except Exception as e:
            print("Resumo do dia falhou:", e)  # tenta de novo na próxima rodada
    with open(ARQ_RESUMO, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False)


# ---------- principal ----------
def main():
    agora = datetime.now(timezone.utc)
    vistas = set(json.load(open(ARQ_VISTAS))) if os.path.exists(ARQ_VISTAS) else set()

    todas = gupy() + github_vagas(agora) + solides() + remotar() + programathor()
    certas, talvez, ja, adiadas = [], [], set(), 0
    descartes = {}
    for v in todas:
        chave = f"{v['fonte']}:{v['id']}"
        if chave in vistas or chave in ja or not v["url"]:
            continue
        ja.add(chave)
        if v["publicada"] and v["publicada"] < agora - timedelta(days=MAX_DIAS):
            vistas.add(chave)
            continue
        tipo, motivo = classificar(v)
        if tipo == "fora":
            descartes[motivo] = descartes.get(motivo, 0) + 1
            vistas.add(chave)
            continue
        if not modalidade_ok(v, agora):
            # vaga do Nordeste antes da data: não marca como vista, pode entrar depois
            if not (v["no_nordeste"] and not v["exterior"]):
                vistas.add(chave)
            else:
                adiadas += 1
            continue
        # mesma empresa + mesmo título = manda uma vez só
        dup = chave_dup(v)
        if dup in vistas or dup in ja:
            vistas.add(chave)
            continue
        aberta, aviso = inscricoes_abertas(v, agora)
        vistas.add(chave)
        if not aberta:
            continue
        ja.add(dup)
        vistas.add(dup)
        completar_avisos(v)
        if aviso:
            v["avisos"].append(aviso)
        if tipo == "talvez":
            v["motivo_talvez"] = motivo
            talvez.append(v)
        else:
            certas.append(v)

    print(f"{len(todas)} vagas lidas, {len(certas)} novas, {len(talvez)} no Talvez, "
          f"{adiadas} do Nordeste guardadas para depois")
    if descartes:
        print("Descartadas:", ", ".join(f"{k}: {n}" for k, n in sorted(descartes.items(), key=lambda x: -x[1])))
    if certas or talvez:
        avaliar(certas + talvez)  # IA dá a nota (as "certas" têm prioridade na cota)
        certas, talvez = ordenar(certas), ordenar(talvez)
        # vagas que a IA eliminou saem do topo do e-mail e do WhatsApp
        elim = lambda v: bool(v.get("ia") and v["ia"].get("eliminada"))
        eliminadas = [v for v in certas + talvez if elim(v)]
        certas = [v for v in certas if not elim(v)]
        talvez = [v for v in talvez if not elim(v)]
        if eliminadas:
            descartes["eliminada pela IA"] = len(eliminadas)
            print(f"{len(eliminadas)} eliminada(s) pela IA")
        if certas or talvez:  # só manda e-mail se sobrou alguma vaga boa
            enviar(certas, talvez, eliminadas)
            enviar_whatsapp(certas, len(talvez))
    json.dump(sorted(vistas), open(ARQ_VISTAS, "w"))
    atualizar_resumo(agora, todas, certas, talvez, descartes)


if __name__ == "__main__":
    main()
