from seguridad import analizar

print(analizar("1.1.1.1", 22.0, 55.0, 21.5, True))   # debe dar normal
print(analizar("1.1.1.1", 90.0, 55.0, 22.0, True))   # debe dar datos_falsos

for i in range(150):
    r = analizar("3.3.3.3", 22.0, 55.0, 22.0, True)
print(r)                                             # debe dar flooding

for i in range(8):
    r = analizar("2.2.2.2", 22.0, 55.0, 22.0, False)
print(r)                                             # probablemente fuerza_bruta