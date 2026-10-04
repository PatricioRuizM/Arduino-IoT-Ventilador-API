from datetime import datetime
import os
import sqlite3
import time
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ALLOWED_DEVICE: str
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Instancia reutilizable
settings = Settings()

DB_PATH = os.path.join(os.path.dirname(__file__), "iot_mediciones.db")
VENTANA_TIEMPO_SEGUNDOS = 3600

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lecturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_hora TEXT NOT NULL,
                timestamp REAL NOT NULL,
                temperatura REAL NOT NULL,
                humedad REAL NOT NULL,
                velocidad_ventilador TEXT NOT NULL DEFAULT 'media'
            )
        """)
        # Migración segura por si la tabla ya existía sin la columna
        cur = conn.execute("PRAGMA table_info(lecturas)")
        columnas = [col[1] for col in cur.fetchall()]
        if "velocidad_ventilador" not in columnas:
            conn.execute("ALTER TABLE lecturas ADD COLUMN velocidad_ventilador TEXT NOT NULL DEFAULT 'media'")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON lecturas(timestamp)")

# ==========================================
# LÓGICA DIFUSA (SISTEMA DE INFERENCIA MAMDANI)
# ==========================================

def triangular(x: float, a: float, b: float, c: float) -> float:
    """Función de pertenencia triangular."""
    if x <= a or x >= c:
        return 0.0
    elif a < x <= b:
        return (x - a) / (b - a)
    elif b < x < c:
        return (c - x) / (c - b)
    return 0.0


def trapezoidal(x: float, a: float, b: float, c: float, d: float) -> float:
    """Función de pertenencia trapezoidal."""
    if x <= a or x >= d:
        return 0.0
    elif a < x < b:
        return (x - a) / (b - a)
    elif b <= x <= c:
        return 1.0
    elif c < x < d:
        return (d - x) / (d - c)
    return 0.0


def fusificar_temperatura(temp: float) -> dict:
    """Devuelve el grado de pertenencia mu en [0, 1] para Temperatura."""
    return {
        "baja": trapezoidal(temp, -10, 0, 15, 25),
        "media": triangular(temp, 18, 25, 32),
        "alta": trapezoidal(temp, 28, 35, 100, 110),
    }


def fusificar_humedad(hum: float) -> dict:
    """Devuelve el grado de pertenencia mu en [0, 1] para Humedad."""
    return {
        "baja": trapezoidal(hum, -10, 0, 30, 45),
        "media": triangular(hum, 35, 55, 75),
        "alta": trapezoidal(hum, 65, 80, 100, 110),
    }


VELOCIDADES = {
    "baja": lambda v: trapezoidal(v, -10, 0, 20, 40),
    "media": lambda v: triangular(v, 30, 50, 70),
    "alta": lambda v: trapezoidal(v, 60, 80, 100, 110),
}

# Reglas del sistema Mamdani
REGLAS_MAMDANI = [
    ("baja", "baja", "baja"),
    ("baja", "media", "baja"),
    ("baja", "alta", "media"),
    ("media", "baja", "baja"),
    ("media", "media", "media"),
    ("media", "alta", "alta"),
    ("alta", "baja", "media"),
    ("alta", "media", "alta"),
    ("alta", "alta", "alta"),
]


def inferencia_mamdani(temp_val: float, hum_val: float):
    mu_temp = fusificar_temperatura(temp_val)
    mu_hum = fusificar_humedad(hum_val)
    activaciones = {"baja": 0.0, "media": 0.0, "alta": 0.0}
    trazabilidad = []
    for t_label, h_label, vel_label in REGLAS_MAMDANI:
        alfa = min(mu_temp[t_label], mu_hum[h_label])
        if alfa > 0:
            trazabilidad.append(
                f"SI Temp es {t_label} ({mu_temp[t_label]:.2f}) Y Hum es {h_label} ({mu_hum[h_label]:.2f}) "
                f"-> Vel es {vel_label} [Fuerza de disparo = {alfa:.2f}]"
            )
            activaciones[vel_label] = max(activaciones[vel_label], alfa)

    universo = range(0, 101)
    numerador = 0.0
    denominador = 0.0

    for v in universo:
        mu_baja = min(activaciones["baja"], VELOCIDADES["baja"](v))
        mu_media = min(activaciones["media"], VELOCIDADES["media"](v))
        mu_alta = min(activaciones["alta"], VELOCIDADES["alta"](v))
        mu_agregado = max(mu_baja, mu_media, mu_alta)

        numerador += v * mu_agregado
        denominador += mu_agregado

    vel_defusificada = (numerador / denominador) if denominador != 0 else 0.0

    categoria = "baja"
    if vel_defusificada > 65:
        categoria = "alta"
    elif vel_defusificada > 35:
        categoria = "media"

    return vel_defusificada, categoria, mu_temp, mu_hum, trazabilidad


def calcular_velocidad_ventilador(temperatura: float, humedad: float) -> str:
    """
    Calcula la velocidad requerida del ventilador ('baja', 'media', 'alta')
    según la temperatura y humedad utilizando lógica difusa (Mamdani).
    """
    _, categoria, _, _, _ = inferencia_mamdani(temperatura, humedad)
    return categoria


def guardar_lectura(temperatura: float, humedad: float, velocidad_ventilador: str) -> dict:
    now_ts = time.time()
    fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO lecturas (fecha_hora, timestamp, temperatura, humedad, velocidad_ventilador) 
            VALUES (?, ?, ?, ?, ?)
            """,
            (fecha_str, now_ts, temperatura, humedad, velocidad_ventilador)
        )
        limite_tiempo = now_ts - VENTANA_TIEMPO_SEGUNDOS
        conn.execute("DELETE FROM lecturas WHERE timestamp < ?", (limite_tiempo,))
        conn.commit()

        cur = conn.execute("SELECT COUNT(*) FROM lecturas")
        total = cur.fetchone()[0]

    return {
        "fecha_hora": fecha_str,
        "timestamp": now_ts,
        "temperatura": temperatura,
        "humedad": humedad,
        "velocidad_ventilador": velocidad_ventilador,
        "total_almacenados_1h": total
    }


def obtener_historial_1h():
    limite_tiempo = time.time() - VENTANA_TIEMPO_SEGUNDOS
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT fecha_hora, timestamp, temperatura, humedad, velocidad_ventilador 
            FROM lecturas 
            WHERE timestamp >= ? 
            ORDER BY timestamp DESC
            """,
            (limite_tiempo,)
        )
        return [dict(row) for row in cur.fetchall()]


def obtener_ultima_lectura():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT fecha_hora, timestamp, temperatura, humedad, velocidad_ventilador 
            FROM lecturas 
            ORDER BY timestamp DESC LIMIT 1
            """
        )
        row = cur.fetchone()
        return dict(row) if row else None


app = FastAPI(
    title="Servidor IoT - Sensor de Temperatura y Humedad",
    description="API para recibir datos desde Arduino WiFi y mantener historial móvil de 1 hora.",
    version="1.0.0"
)

init_db()

class LecturaSensor(BaseModel):
    temperatura: float = Field(..., description="Temperatura en °C", example=24.5)
    humedad: float = Field(..., description="Humedad relativa en %", example=55.0)
    key: str = Field(..., description="Clave de acceso", example="clave_secreta")

@app.post("/datos")
async def recibir_datos_post(lectura: LecturaSensor):
    """
    Endpoint principal para Arduino mediante POST con cuerpo JSON.
    Ejemplo de JSON:
    {"temperatura": 25.4, "humedad": 60.2, "key": "clave_secreta"}
    """
    if lectura.key != settings.ALLOWED_DEVICE:
        return {"status": "error", "mensaje": "Clave de acceso inválida"}

    velocidad = calcular_velocidad_ventilador(lectura.temperatura, lectura.humedad)
    resultado = guardar_lectura(lectura.temperatura, lectura.humedad, velocidad)
    print(f"[{resultado['fecha_hora']}] Nueva lectura -> Temp: {lectura.temperatura}°C, Hum: {lectura.humedad}%, Ventilador: {velocidad} | Total 1h: {resultado['total_almacenados_1h']}")
    return {
        "status": "ok",
        "velocidad_ventilador": velocidad,
    }

@app.get("/historial")
async def ver_historial():
    lecturas = obtener_historial_1h()
    if not lecturas:
        return {"total_lecturas": 0, "lecturas": []}

    temps = [r["temperatura"] for r in lecturas]
    hums = [r["humedad"] for r in lecturas]

    return {
        "total_lecturas": len(lecturas),
        "estadisticas": {
            "temperatura_promedio": round(sum(temps) / len(temps), 2),
            "humedad_promedio": round(sum(hums) / len(hums), 2),
            "temperatura_min": min(temps),
            "temperatura_max": max(temps),
            "humedad_min": min(hums),
            "humedad_max": max(hums)
        },
        "lecturas": lecturas
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
