# ventilador.py
import numpy as np

PTP_OBJ_LOW, PTP_OBJ_HIGH = 12.0, 15.0

def calcular_PDrop(esfuerzos):
    return float(np.mean(esfuerzos))

def calcular_delta_PS(PTP):
    if PTP_OBJ_LOW <= PTP <= PTP_OBJ_HIGH:
        return 0, "PTP dentro de 12-15 → delta_PS = 0"
    if PTP > PTP_OBJ_HIGH:
        return -2, "PTP > 15 → delta_PS = -2"
    return +2, "PTP < 12 → delta_PS = +2"

def calcular_ajuste(params, esfuerzos):
    logs = []
    
    Ppeak = params["Ppeak"]
    PEEP  = params["PEEP"]
    PS    = params["PS"]
    Sat   = params["SatO2"]
    FiO2  = params["FiO2"]
    
    epoc  = params["tiene_epoc"]
    asma  = params["tiene_asma"]
    hipercapnia = params["hipercapnia"]
    hemodin = params["alteracion_hemodinamica"]
    cambio_pH = params["cambio_pH"]

    if hipercapnia or hemodin or cambio_pH:
        logs.append("⚙️ PRIORIDAD: cambiar a MODO PC inmediatamente.")

    PDrop = calcular_PDrop(esfuerzos)
    DPooc = PEEP - PDrop
    Pmus  = 0.75 * DPooc
    PTP   = (Ppeak - PEEP) - (2.0 / 3.0) * DPooc

    delta_PS, motivo = calcular_delta_PS(PTP)
    PS_final = max(0, PS + delta_PS)

    logs.append(f"📈 PTP = {PTP:.2f} cmH2O → {motivo}")
    logs.append(f"📈 PS_final = {PS:.2f} {delta_PS:+.2f} = {PS_final:.2f} cmH2O")

    if asma:
        PEEP_final = PEEP - 2
        logs.append("✓ Asma → PEEP - 2 cmH2O")
    elif epoc or Sat < 88:
        PEEP_final = PEEP + 2
        logs.append("✓ EPOC o SatO2 < 88% → PEEP + 2 cmH2O")
    else:
        PEEP_final = PEEP

    FiO2_sugerida = min(FiO2 * 1.20, 100.0) if Sat < 88 else FiO2

    return {
        'PS_final': PS_final,
        'PEEP_final': PEEP_final,
        'FiO2_sugerida': FiO2_sugerida,
        'sugerir_modo_PC': hipercapnia or hemodin or cambio_pH,
        'logs': logs
    }
