# CiclonAI (Flask)

Herramientas de cálculo y balances de masa para procesamiento de minerales.
Migración de la app Streamlit original (`../app`), que se conserva sin cambios.

## Ejecutar

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py                 # http://127.0.0.1:5000
python -m pytest              # pruebas
```

Producción (Windows): `waitress-serve --port=8000 --call ciclonai:create_app`

## Estructura

```
ciclonai/
  core/            # cálculos en Python puro (sin Flask): fácil de probar y reutilizar
    pulp.py          Stream (mineral + agua → pulpa, densidad, % sólidos), validaciones
    circuits.py      hidrociclón, molienda directa / inversa / D-SAG
    metallurgical.py balance de N concentrados × N elementos (sistema lineal)
    tools.py         nivel de carga, % sólidos ↔ densidad, recuperación
    diagrams.py      escribe los resultados sobre los diagramas PNG
  forms.py         campos declarativos y lectura del formulario
  tables.py        tablas de resultados y exportación a Excel
  routes.py        páginas (una vista por tipo, configuradas con datos)
  templates/  static/
tests/             regresión contra la app original + pruebas web
```

## Agregar un circuito nuevo

1. Escribir la función de cálculo en `core/circuits.py` devolviendo un `CircuitResult`.
2. Agregar una entrada en `PULP_PAGES` (`routes.py`) con sus campos y valores por defecto.
3. (Opcional) Agregar el diagrama y sus coordenadas en `core/diagrams.py → LAYOUTS`.

## Desplegar en un VPS (Hostinger KVM, Ubuntu 22.04/24.04)

Desde Windows (carpeta `CiclonAI`):

```powershell
tar -czf ciclonai.tar.gz --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache -C ciclonai_flask .
scp ciclonai.tar.gz root@IP_DEL_VPS:/root/
ssh root@IP_DEL_VPS
```

En el servidor:

```bash
rm -rf /root/ciclonai && mkdir /root/ciclonai && tar -xzf /root/ciclonai.tar.gz -C /root/ciclonai
bash /root/ciclonai/deploy/setup.sh
```

Para **actualizar**, repetir los mismos pasos (el script es reejecutable).
Logs: `journalctl -u ciclonai -f` · Reiniciar: `systemctl restart ciclonai`.
