import os
import re
import glob
from flask import Flask, request, jsonify, render_template, send_file
from dotenv import load_dotenv
import PyPDF2

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ── Localiza o PDF (procura em várias localizações) ──────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def encontrar_pdf():
    # 1. static/manual.pdf (preferência em produção)
    static_pdf = os.path.join(BASE_DIR, "static", "manual.pdf")
    if os.path.exists(static_pdf):
        return static_pdf
    # 2. Qualquer PDF na raiz do projeto
    pdfs = glob.glob(os.path.join(BASE_DIR, "*.pdf"))
    return pdfs[0] if pdfs else None

MANUAL_PATH = encontrar_pdf()
MANUAL_NOME = os.path.splitext(os.path.basename(MANUAL_PATH))[0] if MANUAL_PATH else "Manual"
# Remove sufixos do nome para exibição
MANUAL_NOME = re.sub(r'\s*-\s*Finalizado.*$', '', MANUAL_NOME).strip()

# ── Carrega chunks com número de página ─────────────────────
def load_chunks():
    if not MANUAL_PATH:
        return []
    reader = PyPDF2.PdfReader(MANUAL_PATH)
    chunks = []
    for idx, page in enumerate(reader.pages):
        texto = page.extract_text() or ""
        tamanho, overlap = 700, 150
        i = 0
        while i < len(texto):
            trecho = texto[i:i + tamanho].strip()
            if trecho:
                chunks.append({"texto": trecho, "pagina": idx + 1})
            i += tamanho - overlap
    return chunks

CHUNKS = load_chunks()

try:
    TOTAL_PAGINAS = len(PyPDF2.PdfReader(MANUAL_PATH).pages) if MANUAL_PATH else 0
except:
    TOTAL_PAGINAS = 0

print(f"✅ Manual: {MANUAL_NOME} ({TOTAL_PAGINAS} pág, {len(CHUNKS)} chunks)")

# ── Busca ────────────────────────────────────────────────────
STOPWORDS = {'o','a','os','as','de','do','da','em','no','na','para','que',
             'e','é','um','uma','por','com','se','ao','ou','qual','quais',
             'como','quando','onde','me','meu','minha','isso','este','esta',
             'tem','ter','foi','ser','são','está','não','mas','mais'}

def extrair_palavras(texto):
    palavras = set(re.findall(r'\w+', texto.lower()))
    return {p for p in palavras if len(p) > 2 and p not in STOPWORDS}


def buscar(pergunta, n=6):
    palavras = extrair_palavras(pergunta)
    if not palavras:
        return [], []

    scored = []
    for chunk in CHUNKS:
        lower = chunk["texto"].lower()
        score = sum(lower.count(p) for p in palavras)
        score += sum(2 for p in palavras if p in lower[:100])
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: -x[0])
    top = scored[:n]

    # Páginas únicas por ordem de relevância
    seen = set()
    paginas = []
    for _, c in top:
        if c["pagina"] not in seen:
            paginas.append(c["pagina"])
            seen.add(c["pagina"])

    return paginas, top, list(palavras)


# ── Rotas ────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html",
                           manual_nome=MANUAL_NOME,
                           total_paginas=TOTAL_PAGINAS)


@app.route("/manual.pdf")
def serve_pdf():
    return send_file(MANUAL_PATH, mimetype="application/pdf")


@app.route("/perguntar", methods=["POST"])
def perguntar():
    data = request.get_json()
    if not data or "pergunta" not in data:
        return jsonify({"erro": "Pergunta não fornecida"}), 400

    if not MANUAL_PATH:
        return jsonify({"erro": "Nenhum PDF encontrado na pasta."}), 500

    pergunta = data["pergunta"].strip()
    result = buscar(pergunta)
    paginas, top, palavras = result

    if not top:
        return jsonify({
            "resposta": "⚠️ Nenhuma informação relacionada foi encontrada no manual.",
            "paginas": [],
            "palavras_busca": list(extrair_palavras(pergunta))
        })

    linhas = []
    for score, chunk in top:
        linhas.append(f"**[Página {chunk['pagina']}]**\n{chunk['texto']}")

    resposta = f"Encontrei {len(top)} trecho(s) em {len(paginas)} página(s) do manual:\n\n" + "\n\n".join(linhas)

    return jsonify({
        "resposta": resposta,
        "paginas": paginas,
        "palavras_busca": palavras
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
