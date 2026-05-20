import requests
import pdfplumber
import io
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

# ─── CONFIGURAÇÕES ───────────────────────────────────────────
PALAVRAS_CHAVE = [
    "Auditor fiscal tributário estadual",
    "Auditor fiscal tributário estadual de mercadoria em trânsito",
    "Servidor fiscal tributário",
    "Secretaria da Fazenda",
    "SEFAZ",
    "ICMS",
]

emails_raw = os.environ.get("EMAILS_DESTINATARIOS", "")
EMAILS_DESTINATARIOS = [e.strip() for e in emails_raw.split(",") if e.strip()]

GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL", "")
GMAIL_SENHA_APP = os.environ.get("GMAIL_SENHA_APP", "")


# ─── FUNÇÕES ─────────────────────────────────────────────────
MESES = {
    1: "janeiro", 2: "fevereiro", 3: "março",    4: "abril",
    5: "maio",    6: "junho",     7: "julho",     8: "agosto",
    9: "setembro",10: "outubro",  11: "novembro", 12: "dezembro"
}

def montar_url_pdf(data: date) -> str:
    dia  = str(data.day).zfill(2)
    mes  = str(data.month).zfill(2)
    ano  = str(data.year)
    mes_extenso = MESES[data.month]
    return (
        f"https://auniao.pb.gov.br/servicos/doe/{ano}/{mes_extenso}/"
        f"diario-oficial-{dia}-{mes}-{ano}-portal.pdf"
    )

def baixar_pdf(url: str) -> bytes | None:
    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
        return resp.content
    return None  # PDF não encontrado (ex: fim de semana, feriado)

def extrair_trechos_relevantes(pdf_bytes: bytes) -> list[dict]:
    resultados = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, pagina in enumerate(pdf.pages, start=1):
            largura = pagina.width
            coluna_esq = pagina.crop((0, 0, largura / 2, pagina.height))
            coluna_dir = pagina.crop((largura / 2, 0, largura, pagina.height))

            for coluna in [coluna_esq, coluna_dir]:
                texto = coluna.extract_text() or ""
                linhas = texto.split("\n")
                linhas_ja_incluidas = set()  # controla o que já foi adicionado

                for j, linha in enumerate(linhas):
                    if any(kw.lower() in linha.lower() for kw in PALAVRAS_CHAVE):
                        inicio = max(0, j - 2)
                        fim = min(len(linhas), j + 3)

                        if inicio in linhas_ja_incluidas:
                            continue  # esse trecho já foi incluído, pula

                        for k in range(inicio, fim):
                            linhas_ja_incluidas.add(k)

                        trecho = "\n".join(linhas[inicio:fim])
                        resultados.append({"pagina": i, "trecho": trecho})
    return resultados

def montar_email_html(data: date, trechos: list[dict], url_pdf: str) -> str:
    data_str = data.strftime("%d/%m/%Y")
    if not trechos:
        return f"<p>Nenhuma publicação relevante encontrada em {data_str}.</p>"
    
    blocos = ""
    for item in trechos:
        link_pagina = f"{url_pdf}#page={item['pagina']}"
        blocos += f"""
        <div style="background:#f5f5f5;padding:12px;margin:10px 0;
                    border-left:4px solid #0066cc;border-radius:4px;">
            <small style="color:#666">Página {item['pagina']}
                <a href="{link_pagina}" style="color:#0066cc">📄 Página {item['pagina']}</a>
            </small>
            <pre style="white-space:pre-wrap;font-size:13px">{item['trecho']}</pre>
        </div>"""

    return f"""
    <h2>📋 Diário Oficial da Paraíba — {data_str}</h2>
    <p>Encontramos <strong>{len(trechos)} publicação(ões)</strong> relevante(s) para sua categoria.</p>
    {blocos}
    <hr>
    <p><a href="{url_pdf}">📄 Ver o Diário Oficial completo</a></p>
    <p style="color:#999;font-size:11px">Este e-mail é enviado automaticamente.</p>
    """

def enviar_emails(html: str, data):
    data_str = data.strftime("%d/%m/%Y")
    assunto = f"📋 Diário Oficial PB — {data_str}"

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(GMAIL_EMAIL, GMAIL_SENHA_APP)
        for destinatario in EMAILS_DESTINATARIOS:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = assunto
            msg["From"]    = GMAIL_EMAIL
            msg["To"]      = destinatario
            msg.attach(MIMEText(html, "html"))
            servidor.sendmail(GMAIL_EMAIL, destinatario, msg.as_string())
            print(f"E-mail enviado para {destinatario}")

# ─── EXECUÇÃO PRINCIPAL ──────────────────────────────────────
def main():
    hoje = date.today()
    url  = montar_url_pdf(hoje)
    print(f"Buscando: {url}")

    pdf_bytes = baixar_pdf(url)
    if not pdf_bytes:
        print("PDF não disponível hoje (fim de semana ou feriado). Encerrando.")
        return

    trechos = extrair_trechos_relevantes(pdf_bytes)
    print(f"{len(trechos)} trecho(s) encontrado(s)")

    html = montar_email_html(hoje, trechos, url)
    enviar_emails(html, hoje)

if __name__ == "__main__":
    main()