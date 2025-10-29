from fastapi import FastAPI, Request
import os, requests
from ventilador import calcular_ajuste
from fastapi.responses import RedirectResponse


app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok"}

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
            key = ["Ppeak", "PEEP", "PS", "SatO2", "FiO2"][step]
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

@app.get("/formulario", response_class=HTMLResponse)
def formulario_html():
    html = """
    <html>
        <head>
            <title>Formulario Ventilatorio</title>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: 'Segoe UI', sans-serif;
                    background-color: #eef4f7;
                    padding: 2em;
                    color: #333;
                }
                .form-card {
                    background-color: rgba(173,243,228,0.42);
                    padding: 2em;
                    border-radius: 10px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    max-width: 600px;
                    margin: auto;
                    animation: fadeIn 0.8s ease-in;
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                h2 {
                    color: #007BFF;
                    margin-bottom: 1em;
                }
                label {
                    display: block;
                    margin-top: 1em;
                    font-weight: bold;
                }
                input, select {
                    width: 100%;
                    padding: 0.5em;
                    margin-top: 0.3em;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    transition: box-shadow 0.3s ease;
                }
                input:focus, select:focus {
                    outline: none;
                    box-shadow: 0 0 5px rgba(0, 123, 255, 0.5);
                }
                button {
                    margin-top: 2em;
                    padding: 0.7em 1.5em;
                    background-color: #007BFF;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    transition: transform 0.2s ease;
                }
                button:hover {
                    background-color: #0056b3;
                    transform: scale(1.03);
                }
            </style>
            <script>
                function validarEsfuerzo(id) {
                    const input = document.getElementById(id);
                    const val = parseFloat(input.value);
                    if (val < -5 || val > 5) {
                        input.style.borderColor = "red";
                        input.setCustomValidity("Esfuerzo fuera de rango clínico (-5 a +5 cmH₂O)");
                    } else {
                        input.style.borderColor = "";
                        input.setCustomValidity("");
                    }
                }
            </script>
        </head>
        <body>
            <div class="form-card">
                <h2>🩺 Ingreso de Datos Clínicos</h2>
                <form action="/procesar" method="post">
                    <label>👉 Ingrese Ppeak (cmH₂O):</label>
                    <input type="number" name="Ppeak" step="0.1" required>

                    <label>👉 Ingrese PEEP actual (cmH₂O):</label>
                    <input type="number" name="PEEP" step="0.1" required>

                    <label>👉 Ingrese PS actual (cmH₂O):</label>
                    <input type="number" name="PS" step="0.1" required>

                    <label>👉 Ingrese SatO₂ (%):</label>
                    <input type="number" name="SatO2" step="0.1" required>

                    <label>👉 Ingrese FiO₂ actual (%):</label>
                    <input type="number" name="FiO2" step="0.1" required>

                    <label>👉 ¿EPOC?</label>
                    <select name="tiene_epoc" required>
                        <option value="" disabled selected>Seleccione una opción</option>
                        <option value="si">si</option>
                        <option value="no">no</option>
                    </select>

                    <label>👉 ¿Asma?</label>
                    <select name="tiene_asma" required>
                        <option value="" disabled selected>Seleccione una opción</option>
                        <option value="si">si</option>
                        <option value="no">no</option>
                    </select>

                    <label>👉 ¿Hipercapnia?</label>
                    <select name="hipercapnia" required>
                        <option value="" disabled selected>Seleccione una opción</option>
                        <option value="si">si</option>
                        <option value="no">no</option>
                    </select>

                    <label>👉 ¿Alteración hemodinámica?</label>
                    <select name="alteracion_hemodinamica" required>
                        <option value="" disabled selected>Seleccione una opción</option>
                        <option value="si">si</option>
                        <option value="no">no</option>
                    </select>

                    <label>👉 ¿Cambios en pH?</label>
                    <select name="cambio_pH" required>
                        <option value="" disabled selected>Seleccione una opción</option>
                        <option value="si">si</option>
                        <option value="no">no</option>
                    </select>

                    <label>✏️ Ingrese esfuerzo inspiratorio #1 (cmH₂O):</label>
                    <input type="number" name="esfuerzo1" id="esfuerzo1" step="0.1" required oninput="validarEsfuerzo('esfuerzo1')">

                    <label>✏️ Ingrese esfuerzo inspiratorio #2 (cmH₂O):</label>
                    <input type="number" name="esfuerzo2" id="esfuerzo2" step="0.1" required oninput="validarEsfuerzo('esfuerzo2')">

                    <label>✏️ Ingrese esfuerzo inspiratorio #3 (cmH₂O):</label>
                    <input type="number" name="esfuerzo3" id="esfuerzo3" step="0.1" required oninput="validarEsfuerzo('esfuerzo3')">

                    <button type="submit">Calcular</button>
                </form>
            </div>
        </body>
    </html>
    """
    return html






@app.post("/procesar", response_class=HTMLResponse)
async def procesar_formulario(request: Request):
    form = await request.form()
    print("📥 Formulario recibido:", form)
    data = dict(form)
    print("📥 Diccionario plano:", data)

    try:
        # Validación de selects vacíos
        campos_booleanos = [
            "tiene_epoc", "tiene_asma", "hipercapnia",
            "alteracion_hemodinamica", "cambio_pH"
        ]
        for campo in campos_booleanos:
            if data.get(campo, "") not in ["si", "no"]:
                raise ValueError(f"Campo clínico '{campo}' no fue respondido correctamente.")

        datos = {
            "Ppeak": float(data.get("Ppeak", "0") or "0"),
            "PEEP": float(data.get("PEEP", "0") or "0"),
            "PS": float(data.get("PS", "0") or "0"),
            "SatO2": float(data.get("SatO2", "0") or "0"),
            "FiO2": float(data.get("FiO2", "0") or "0"),
            "tiene_epoc": data.get("tiene_epoc") == "si",
            "tiene_asma": data.get("tiene_asma") == "si",
            "hipercapnia": data.get("hipercapnia") == "si",
            "alteracion_hemodinamica": data.get("alteracion_hemodinamica") == "si",
            "cambio_pH": data.get("cambio_pH") == "si"
        }

        esfuerzos = [
            float(data.get("esfuerzo1", "0") or "0"),
            float(data.get("esfuerzo2", "0") or "0"),
            float(data.get("esfuerzo3", "0") or "0")
        ]

        # Validación de rango clínico
        for i, e in enumerate(esfuerzos):
            if not -5 <= e <= 5:
                raise ValueError(f"Esfuerzo inspiratorio #{i+1} fuera de rango clínico (-5 a +5 cmH₂O).")

        # Cálculo clínico
        from ventilador import calcular_PDrop, calcular_ajuste

        PDrop = calcular_PDrop(esfuerzos)
        DPooc = datos["PEEP"] - PDrop
        Pmus = 0.75 * DPooc
        PTP = (datos["Ppeak"] - datos["PEEP"]) - (2.0 / 3.0) * DPooc

        resultado = calcular_ajuste(datos, esfuerzos)
        logs_html = "".join(f"<li>{log}</li>" for log in resultado["logs"])

        html = f"""
        <html>
            <head>
                <title>Resultados Clínicos</title>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: 'Segoe UI', sans-serif;
                        background-color: #f0f4f8;
                        padding: 2em;
                        color: #333;
                    }}
                    .card {{
                        background-color: rgba(173,243,228,0.42);
                        padding: 2em;
                        border-radius: 10px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                        max-width: 600px;
                        margin: auto;
                        animation: fadeIn 0.8s ease-in;
                    }}
                    @keyframes fadeIn {{
                        from {{ opacity: 0; transform: translateY(20px); }}
                        to {{ opacity: 1; transform: translateY(0); }}
                    }}
                    h2 {{
                        color: #007BFF;
                        margin-bottom: 1em;
                    }}
                    h3 {{
                        margin-top: 1.5em;
                        color: #007BFF;
                    }}
                    p {{
                        font-size: 1.1em;
                        margin: 0.5em 0;
                    }}
                    ul {{
                        margin-top: 0.5em;
                        padding-left: 1.2em;
                    }}
                    li {{
                        margin-bottom: 0.4em;
                    }}
                    .summary {{
                        margin-top: 1.5em;
                        background-color: #ffffffaa;
                        padding: 1em;
                        border-radius: 8px;
                        border-left: 4px solid #007BFF;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>✅ Resultados Clínicos</h2>

                    <h3>📊 Parámetros Dinámicos:</h3>
                    <p>• PDrop = {PDrop:.2f} cmH₂O</p>
                    <p>• DPooc = {DPooc:.2f} cmH₂O</p>
                    <p>• Pmus = {Pmus:.2f} cmH₂O</p>
                    <p>• PTP dinámica = {PTP:.2f} cmH₂O</p>

                    <h3>📋 Detalles del análisis:</h3>
                    <ul>{logs_html}</ul>

                    <div class="summary">
                        <p><strong>✅ PROGRAMACIÓN SUGERIDA:</strong></p>
                        <p>• PS&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= {resultado['PS_final']:.1f} cmH₂O</p>
                        <p>• PEEP&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= {resultado['PEEP_final']:.1f} cmH₂O</p>
                        <p>• FiO₂&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= {resultado['FiO2_sugerida']:.1f}%</p>
                    </div>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(content=html)

    except Exception as e:
        return HTMLResponse(content=f"<p>Error: {e}</p>", status_code=400)




@app.get("/")
async def root():
    return {"mensaje": "✅ Webot activo. Usa /webhook para enviar datos o /resultados para ver ajustes."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


@app.get("/", response_class=HTMLResponse)
def redirigir_a_formulario():
    return RedirectResponse(url="/formulario")



