# FacturasAI - BETA 3

Aplicación Streamlit para facturas de autónomos en España. Lee PDF y XML Facturae, distingue proveedor y cliente mediante la posición visual de los bloques, NIF/CIF e identidad del titular, valida los importes y exporta a Excel.

## Estructura del repositorio

```text
app.py
extractor_v2.py
excel_exporter.py
requirements.txt
packages.txt
README.md
.gitignore
.streamlit/
  config.toml
```

No subas el ZIP, archivos `.pyc`, carpetas `__pycache__` ni facturas reales al repositorio público.

## Despliegue en Streamlit Community Cloud

1. Subí todos los archivos y la carpeta `.streamlit` a la raíz del repositorio.
2. Elegí el repositorio `AFranciscoSaralegui/facturas-app-beta3`.
3. Seleccioná la rama real del repositorio, normalmente `main`.
4. Escribí `app.py` como ruta del archivo principal.
5. Desplegá la aplicación.

`requirements.txt` declara las dependencias Python. `packages.txt` instala Tesseract y el idioma español para el OCR.

## Uso

Antes de procesar facturas, completá en la barra lateral:

- nombre o razón social del titular;
- NIF/CIF del titular.

La app usa esos datos únicamente durante la sesión para excluir el bloque propio y elegir correctamente el proveedor en facturas recibidas o el cliente en facturas emitidas.

## Mejoras incluidas en BETA 3

- Separación visual de bloques de proveedor y cliente.
- Exclusión del NIF/CIF del titular.
- Asociación conjunta de nombre, NIF/CIF, dirección y código postal.
- Lectura de fechas españolas con meses abreviados.
- Diferenciación entre porcentaje de IVA y cuota de IVA.
- Validación matemática de base, IVA, retención y total.
- OCR automático como respaldo.
- Exportación con hojas de Gastos/Ingresos, Control y Detalle IVA.
- Campos vacíos cuando no existe evidencia suficiente, sin escribir “No detectado”.

## Ejecutar localmente

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Para OCR local también necesitás Tesseract instalado en el sistema.
