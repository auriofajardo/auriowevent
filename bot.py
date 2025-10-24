# bot.py
import requests, time
import ventilador

TOKEN = "7170558002:AAGlxBhOXKU9FKIRF6XtE0pYbbZ4h14Y5DY"
URL = f"https://api.telegram.org/bot{TOKEN}/"
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
  "👉 ¿Alteración hemodinámica? (si/no):",
  "👉 ¿Cambios en pH? (si/no):",
  "✏️ Ingrese 3 esfuerzos inspiratorios obtenidos mediante pausa espiratoria de 3 segundos cada una separados por coma:"
]

def get_updates(offset=None):
    r = requests.get(URL + "getUpdates", params={"timeout": 30, "offset": offset})
    return r.json().get("result", [])

def send_message(chat_id, text):
    requests.post(URL + "sendMessage", json={"chat_id": chat_id, "text": text})

def handle(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if chat_id not in SESS:
        SESS[chat_id] = {"step": 0, "data": {}}
        send_message(chat_id, PROMPTS[0])
        return

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
            return
    except ValueError as e:
        send_message(chat_id, f"⚠️ Entrada inválida ({e}).\n{PROMPTS[step]}")
        return

    sess["step"] += 1

    if sess["step"] < len(PROMPTS):
        send_message(chat_id, PROMPTS[sess["step"]])
        return

    res = ventilador.calcular_ajuste(d, d["esfuerzos"])

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

def main():
    offset = None
    print("🤖 Bot corriendo en Pythonista...")
    while True:
        updates = get_updates(offset)
        for u in updates:
            offset = u["update_id"] + 1
            if "message" in u and "text" in u["message"]:
                handle(u["message"])
        time.sleep(1)

if __name__ == "__main__":
    main()




