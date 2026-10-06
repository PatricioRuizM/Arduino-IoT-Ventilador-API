import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, accuracy_score


# De aqui para abajo es la logica de la ciberseguridad con random forest, utilize varios casos en los que el sistema
# podria llegar a ser atacado.
rng = np.random.default_rng(42)   # semilla: resultados repetibles
n = 100
normal = np.column_stack([
    rng.integers(8, 13, n),       # peticiones/min
    rng.integers(0, 2, n),        # fallos de clave
    rng.uniform(0, 2, n),         # salto de temperatura
    np.zeros(n),                  # fuera de rango
])
y_normal = np.zeros(n)            # etiqueta 0

flooding = np.column_stack([
    rng.integers(40, 500, n),       # peticiones/min
    rng.integers(0, 2, n),        # fallos de clave
    rng.uniform(0, 2, n),         # salto de temperatura
    np.zeros(n),                  # fuera de rango
])
y_flooding = np.ones(n)            # etiqueta 0

fuerza_bruta = np.column_stack([
    rng.integers(10, 60, n),       # peticiones/min
    rng.integers(2, 30, n),        # fallos de clave
    rng.uniform(0, 2, n),         # salto de temperatura
    np.zeros(n),                  # fuera de rango
])
y_fuerza_bruta = np.full(n, 2)            # etiqueta 0

datos_falsos = np.column_stack([
    rng.integers(8, 13, n),       # peticiones/min
    rng.integers(0, 2, n),        # fallos de clave
    rng.uniform(3, 40, n),       # salto de temperatura
    rng.integers(0, 2, n),        # fuera de rango
])
y_datos_falsos = np.full(n, 3)            # etiqueta 0


X = np.vstack([normal, flooding, fuerza_bruta, datos_falsos])
y = np.concatenate([y_normal, y_flooding, y_fuerza_bruta, y_datos_falsos])

print(X.shape, y.shape)
print(np.bincount(y.astype(int)))

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

print(X_train.shape, X_test.shape)
print(np.bincount(y_train.astype(int)), np.bincount(y_test.astype(int)))

modelo = RandomForestClassifier(random_state = 42)
modelo.fit(X_train, y_train)
print(accuracy_score(y_test, modelo.predict(X_test)))

pred = modelo.predict(X_test)
print(confusion_matrix(y_test, pred))

errores = X_test[y_test != pred]
print(errores)


scaler = StandardScaler()
X_train_esc = scaler.fit_transform(X_train)
X_test_esc = scaler.transform(X_test)

knn = KNeighborsClassifier(n_neighbors=5)
knn.fit(X_train_esc, y_train)

knn_pred = knn.predict(X_test_esc)

print(accuracy_score(y_test, knn_pred))
print(confusion_matrix(y_test, knn_pred))