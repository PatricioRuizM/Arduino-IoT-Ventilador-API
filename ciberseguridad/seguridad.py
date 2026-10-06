import numpy as np
from sklearn.ensemble import RandomForestClassifier
import time

def entrenar_modelo():
    rng = np.random.default_rng(42)
    n = 100
    normal = np.column_stack([
        rng.integers(8, 13, n),  # peticiones/min
        rng.integers(0, 2, n),  # fallos de clave
        rng.uniform(0, 2, n),  # salto de temperatura
        np.zeros(n),  # fuera de rango
    ])
    y_normal = np.zeros(n)  # etiqueta 0

    flooding = np.column_stack([
        rng.integers(40, 500, n),  # peticiones/min
        rng.integers(0, 2, n),  # fallos de clave
        rng.uniform(0, 2, n),  # salto de temperatura
        np.zeros(n),  # fuera de rango
    ])
    y_flooding = np.ones(n)  # etiqueta 0

    fuerza_bruta = np.column_stack([
        rng.integers(10, 60, n),  # peticiones/min
        rng.integers(2, 30, n),  # fallos de clave
        rng.uniform(0, 2, n),  # salto de temperatura
        np.zeros(n),  # fuera de rango
    ])
    y_fuerza_bruta = np.full(n, 2)  # etiqueta 0

    datos_falsos = np.column_stack([
        rng.integers(8, 13, n),  # peticiones/min
        rng.integers(0, 2, n),  # fallos de clave
        rng.uniform(3, 40, n),  # salto de temperatura
        rng.integers(0, 2, n),  # fuera de rango
    ])
    y_datos_falsos = np.full(n, 3)  # etiqueta 0

    X = np.vstack([normal, flooding, fuerza_bruta, datos_falsos])
    y = np.concatenate([y_normal, y_flooding, y_fuerza_bruta, y_datos_falsos])

    modelo = RandomForestClassifier(random_state=42)
    modelo.fit(X, y)
    return modelo

##

peticiones = {}   # la libreta: {"192.168.1.5": [hora1, hora2, hora3]}

def contar_peticiones(ip):
    ahora = time.time()
    if ip not in peticiones:
        peticiones[ip] = []
    peticiones[ip].append(ahora)
    peticiones[ip] = [t for t in peticiones[ip] if ahora - t <= 60]
    return len(peticiones[ip])

fallos = {}
def registrar_fallo(ip):
    ahora = time.time()
    if ip not in fallos:
        fallos[ip] = []
    fallos[ip].append(ahora)
    fallos[ip] = [t for t in fallos[ip] if ahora - t <= 60]
    return len(fallos[ip])

def calcular_salto(temperatura, temp_anterior):
    if temp_anterior is None:
        return 0.0
    return abs(temperatura - temp_anterior)

def fuera_de_rango(temperatura, humedad):
    if temperatura < -20 or temperatura > 60 or humedad < 0 or humedad > 100:
        return 1
    return 0

def fallos_recientes(ip):
    ahora = time.time()
    return len([t for t in fallos.get(ip, []) if ahora - t <= 60])


modelo = entrenar_modelo()

CLASES = {0: "normal", 1: "flooding", 2: "fuerza_bruta", 3: "datos_falsos"}

def analizar(ip, temperatura, humedad, temp_anterior, clave_correcta):
    n_peticiones = contar_peticiones(ip)
    if clave_correcta:
        n_fallos = fallos_recientes(ip)
    else:
        n_fallos = registrar_fallo(ip)
    salto = calcular_salto(temperatura, temp_anterior)
    fuera = fuera_de_rango(temperatura, humedad)
    prediccion = modelo.predict([[n_peticiones, n_fallos, salto, fuera]])
    return CLASES[int(prediccion[0])]