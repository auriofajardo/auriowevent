from fastapi import FastAPI, Request
from ventilador import calcular_ajuste

app = FastAPI()

@app.post("/webhook")
async def jotform_webhook(request: Request):
    data = await request.json()

    # Extraer datos del formulario
    nombre = data.get("nombre", "Paciente")
    Ppeak = float(data.get("Ppeak", 0))
    PEEP = float(data.get("PEEP", 0))
    PS = float(data.get("PS", 0))
    Sat = float(data.get("Sat", 0))
    FiO2 = float(data.get("FiO2", 0))
    esfuerzos = list(map(float, data.get("esfuerzos", "0,0,0").split(",")))

    # Flags booleanos
    epoc = data.get("tiene_epoc", "no").lower() == "si"
    asma = data.get("tiene_asma", "no").lower() == "si"
    hipercapnia = data.get("hipercapnia", "no").lower() == "si"
    hemodinamica = data.get("alteracion_hemodinamica", "no").lower() == "si"
    cambio_pH = data.get("cambio_pH", "no").lower() == "si"

    # Construir diccionario para el algoritmo
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

    # Ejecutar tu algoritmo
    resultado = calcular_ajuste(datos, esfuerzos)

    # Construir URL prellenada de Jotform
    url = (
        f"https://form.jotform.com/1234567890?"
        f"nombre={nombre}&PS={resultado['PS_final']:.1f}"
        f"&PEEP={resultado['PEEP_final']:.1f}"
        f"&FiO2={resultado['FiO2_sugerida']:.1f}"
    )

    return {"url": url}
