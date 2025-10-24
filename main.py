from fastapi import FastAPI, Request
import os, requests
from ventilador import calcular_ajuste

app = FastAPI()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SESS = {}

PROMPTS = [
    "🚀 Bienvenido al asistente ventilatorio.\nIngrese Ppeak (cmH2O):",
    "👉 Ingrese PEEP inicial (cmH2O):",
    "👉 Ingrese PS actual (cmH2O):",
    "👉 Ingrese SatO2 (%):",
    "👉 Ingrese FiO2 actual (%):",
    "👉 ¿EPOC? (si/no):",
    "👉 ¿Asma? (si/no):",
    "👉 ¿Hipercapnia? (si/no):",
    "👉 ¿Alteración hemodinámica? (si/no):",
    "👉 ¿Cambios en pH? (si/no):",
    "✏️ Ingrese 3 esfuerzos inspiratorios separados por coma:"
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

    if chat_id not in SESS:
        SESS[chat_id] = {"step": 0, "data": {}}
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
        elif step == 10:
            esfuerzos = list(map(float, text.split(",")))
            if len(esfuerzos) != 3:
                raise ValueError("Se requieren exactamente 3 valores.")
            d["esfuerzos"] = esfuerzos
        else:
            return {"ok": True}
    except ValueError as e:
        send_message(chat_id, f"⚠️ Entrada inválida ({e}).\n{PROMPTS[step]}")
        return {"ok": True}

    sess["step"] += 1

    if sess["step"] < len(PROMPTS):
        send_message(chat_id, PROMPTS[sess["step"]])
        return {"ok": True}

    res = calcular_ajuste(d, d["esfuerzos"])

    for log in res["logs"]:
        send_message(chat_id, log)

    summary = (
        f"\n✅ RESULTADOS FINALES:\n"
        f"• PS final       = {res['PS_final']:.1f} cmH2O\n"
        f"• PEEP final     = {res['PEEP_final']:.1f} cmH2O\n"
        f"• FiO2 sugerida  = {res['FiO2_sugerida']:.1f}%"
    )
    send_message(chat_id, summary)

    del SESS[chat_id]
    return {"ok": True}


from fastapi.responses import RedirectResponse

@app.post("/webhook")
async def jotform_webhook(request: Request):
    data = await request.json()

    # Extraer datos del formulario
    Ppeak = float(data.get("Ppeak", 0))
    PEEP = float(data.get("PEEP", 0))
    PS = float(data.get("PS", 0))
    Sat = float(data.get("Sat", 0))
    FiO2 = float(data.get("FiO2", 0))
    esfuerzos = list(map(float, data.get("esfuerzos", "0,0,0").split(",")))

    epoc = data.get("tiene_epoc", "no").lower() == "si"
    asma = data.get("tiene_asma", "no").lower() == "si"
    hipercapnia = data.get("hipercapnia", "no").lower() == "si"
    hemodinamica = data.get("alteracion_hemodinamica", "no").lower() == "si"
    cambio_pH = data.get("cambio_pH", "no").lower() == "si"

    datos = {
        "Ppeak": Ppeak,
        "PEEP": PEEP,
        "PS": PS,
        "Sat": Sat,
        "FiO2": FiO2,
        "tiene_epoc": epoc,
        "tiene_asma": asma,
        "hipercapnia": hipercapnia,
        "alteracion_hemodinamica": hemodinamica,
        "cambio_pH": cambio_pH
    }

    resultado = calcular_ajuste(datos, esfuerzos)

    # Construir URL prellenada
    url = (
        f"https://form.jotform.com/252945029926062?"
        f"PS={resultado['PS_sugerida']:.1f}"
        f"&PEEP={resultado['PEEP_sugerida']:.1f}"
        f"&FiO2={resultado['FiO2_sugerida']:.1f}"
    )

    return RedirectResponse(url)
