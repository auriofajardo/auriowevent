from fastapi import FastAPI, Request
import os, requests
from ventilador import calcular_ajuste

app = FastAPI()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SESS = {}

PROMPTS = [
    "👉 Ingrese Ppeak (cmH2O):",
    "👉 Ingrese PEEP actual (cmH2O):",
    "👉 Ingrese PS actual (cmH2O):",
    "👉 Ingrese SatO2 (%):",
    "👉 Ingrese FiO2 actual (%):",
    "👉 ¿EPOC? (si/no):",
    "👉 ¿Asma? (si/no):",
    "👉 ¿Hipercapnia? (si/no):",
    "👉 ¿Alteración hemodinámica? (si/no):",
    "👉 ¿Cambios en pH? (si/no):",
    "✏️ Ingrese esfuerzo inspiratorio #1 (cmH2O):",
    "✏️ Ingrese esfuerzo inspiratorio #2 (cmH2O):",
    "✏️ Ingrese esfuerzo inspiratorio #3 (cmH2O):"
]

def send_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"].strip()

    # 🔁 Opción de reinicio manual
    if text.lower() in ["reiniciar", "/start", "reset"]:
        SESS[chat_id] = {"step": 0, "data": {}}
        send_message(chat_id, "🔄 Sesión reiniciada.")
        send_message(chat_id, "🚀 Bienvenido al asistente ventilatorio.")
        send_message(chat_id, PROMPTS[0])
        return {"ok": True}

    # 🧭 Iniciar sesión si es nuevo usuario
    if chat_id not in SESS:
        SESS[chat_id] = {"step": 0, "data": {}}
        send_message(chat_id, "🚀 Bienvenido al asistente ventilatorio.")
        send_message(chat_id, PROMPTS[0])
        return {"ok": True}

    sess = SESS[chat_id]
    step = sess["step"]
    d = sess["data"]

    try:
        if step < 5:
            key = ["Ppeak", "PEEP", "PS", "Sat", "FiO2"][step]
            d[key] = float(text)

        elif step < 10:
            key = ["tiene_epoc", "tiene_asma", "hipercapnia",
                   "alteracion_hemodinamica", "cambio_pH"][step - 5]
            d[key] = text.lower() == "si"

        elif 10 <= step <= 12:
            try:
                esfuerzo = float(text)
            except ValueError:
                raise ValueError("Por favor ingrese un número válido.")

            if esfuerzo < -5 or esfuerzo > 5:
                raise ValueError(f"Esfuerzo fuera de rango clínico (-5 a +5 cmH₂O).")

            if "esfuerzos" not in d:
                d["esfuerzos"] = []
            d["esfuerzos"].append(esfuerzo)

            send_message(chat_id, f"✅ Esfuerzo #{step - 9} registrado: {esfuerzo:.1f} cmH₂O")

        else:
            return {"ok": True}

    except ValueError as e:
        send_message(chat_id, f"⚠️ Entrada inválida ({e}).\n{PROMPTS[step]}")
        return {"ok": True}

    sess["step"] += 1

    # 🧮 Ejecutar cálculo tras esfuerzo #3
    if sess["step"] == len(PROMPTS):
        res = calcular_ajuste(d, d["esfuerzos"])

        for log in res["logs"]:
            send_message(chat_id, log)

        summary = (
            f"\n✅ PROGRAMACIÓN SUGERIDA:\n"
            f"• PS        = {res['PS_final']:.1f} cmH2O\n"
            f"• PEEP      = {res['PEEP_final']:.1f} cmH2O\n"
            f"• FiO2      = {res['FiO2_sugerida']:.1f}%"
        )
        send_message(chat_id, summary)
        del SESS[chat_id]
        return {"ok": True}

    # ➡️ Enviar siguiente prompt
    send_message(chat_id, PROMPTS[sess["step"]])
    return {"ok": True}





from fastapi.responses import HTMLResponse
from fastapi import Request, Query

@app.post("/webhook")
async def jotform_webhook(request: Request):
    form = await request.form()
    data = dict(form)


    # Extraer datos del formulario
    Ppeak = float(data.get("Ppeak", 0))
    PEEP = float(data.get("PEEP", 0))
    PS = float(data.get("PS", 0))
    SatO2 = float(data.get("SatO2", 0))
    FiO2 = float(data.get("FiO2", 0))

    # Capturar esfuerzos inspiratorios desde tres campos separados
    try:
        esfuerzos = [
            float(data.get("esfuerzo1", 0)),
            float(data.get("esfuerzo2", 0)),
            float(data.get("esfuerzo3", 0))
        ]
        if len(esfuerzos) != 3:
            raise ValueError("Se requieren 3 esfuerzos.")
    except Exception as e:
        return {"error": f"Error al procesar esfuerzos: {e}"}

    # Capturar comorbilidades y condiciones clínicas
    epoc = data.get("tiene_epoc", "no").lower() == "si"
    asma = data.get("tiene_asma", "no").lower() == "si"
    hipercapnia = data.get("hipercapnia", "no").lower() == "si"
    hemodinamica = data.get("alteracion_hemodinamica", "no").lower() == "si"
    cambio_pH = data.get("cambio_pH", "no").lower() == "si"

    # Construir diccionario clínico
    datos = {
        "Ppeak": Ppeak,
        "PEEP": PEEP,
        "PS": PS,
        "SatO2": SatO2,
        "FiO2": FiO2,
        "tiene_epoc": epoc,
        "tiene_asma": asma,
        "hipercapnia": hipercapnia,
        "alteracion_hemodinamica": hemodinamica,
        "cambio_pH": cambio_pH
    }

    # Ejecutar cálculo clínico
    resultado = calcular_ajuste(datos, esfuerzos)

    # Construir URL de resultados
    url = (
        f"https://webot-wh7l.onrender.com/resultados?"
        f"PS={resultado['PS_sugerida']:.1f}"
        f"&PEEP={resultado['PEEP_sugerida']:.1f}"
        f"&FiO2={resultado['FiO2_sugerida']:.1f}"
    )

    # Devolver el link como campo para Jotform
    return {"link_resultados": url}







@app.get("/resultados")
async def mostrar_resultados(
    PS: float = Query(...),
    PEEP: float = Query(...),
    FiO2: float = Query(...)
):
    html_content = f"""
    <html>
        <head>
            <title>Resultados Clínicos</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f0f4f8;
                    padding: 2em;
                    color: #333;
                }}
                .card {{
                    background-color: white;
                    padding: 2em;
                    border-radius: 10px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    max-width: 500px;
                    margin: auto;
                }}
                h2 {{
                    color: #007BFF;
                    margin-bottom: 1em;
                }}
                p {{
                    font-size: 1.1em;
                    margin: 0.5em 0;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>✅ Resultados Clínicos</h2>
                <p><strong>PS sugerida:</strong> {PS:.1f} cmH₂O</p>
                <p><strong>PEEP sugerida:</strong> {PEEP:.1f} cmH₂O</p>
                <p><strong>FiO₂ sugerida:</strong> {FiO2:.1f}%</p>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/")
async def root():
    return {"mensaje": "✅ Webot activo. Usa /webhook para enviar datos o /resultados para ver ajustes."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


@app.get("/health")
def health_check():
    return {"status": "ok"}

