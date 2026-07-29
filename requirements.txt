# FacturasAI - BETA 3.1

Aplicación Streamlit para procesar facturas recibidas y emitidas de autónomos en España. Lee PDF y XML Facturae, separa proveedor y cliente, valida importes y exporta al modelo Excel de Gastos o Ingresos.

## Archivos del repositorio

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

Subí estos archivos directamente a la raíz del repositorio. No subas el ZIP, facturas reales, archivos `.pyc` ni carpetas `__pycache__`.

## Despliegue en Streamlit Community Cloud

- Repositorio: el repositorio de GitHub donde subiste estos archivos.
- Rama: `main`.
- Ruta del archivo principal: `app.py`.

`requirements.txt` instala las dependencias Python. `packages.txt` instala Tesseract y el idioma español para el OCR en Streamlit Community Cloud.

## Mejoras de la BETA 3.1

- Prioridad a bloques rotulados como `Seller`, `Buyer`, `Proveedor`, `Cliente`, `Emisor` y `Receptor`.
- Lectura de proveedores situados en la cabecera derecha de la factura.
- Compatibilidad con VAT ID extranjeros, además de NIF/CIF españoles.
- Corrección de importes cuando aparecen `Total I.V.A.` y `TOTAL FACTURA` en líneas cercanas.
- Reconocimiento de fechas ISO (`2026-06-30`) y fechas españolas.
- Reconocimiento de números como `FACTURA 2026/4`.
- Extracción del concepto desde tablas de productos o servicios.
- Regla recurrente para facturas de ENTIFY.
- Regla recurrente para recibos de cuotas de autónomos de la TGSS:
  - tipo `Débito`;
  - concepto `Cuota seguridad social`;
  - modelo 303 `no`;
  - base y total iguales al importe del recibo;
  - deducción IRPF del 100 %.
- Las facturas intracomunitarias con `Reverse charge` se marcan para el modelo 303 aunque el IVA de la factura sea 0.
- Trimestres exportados como `1T`, `2T`, `3T` o `4T`.
- Fechas exportadas como `dd-mm-aa`.

## Uso

1. Elegí `Recibidas (Gastos)` o `Emitidas (Ingresos)`.
2. Indicá el nombre y NIF/CIF del titular para excluir su bloque cuando sea necesario.
3. Subí uno o más PDF/XML.
4. Presioná `Procesar facturas`.
5. Revisá la tabla editable.
6. Descargá el Excel.

## Ejecutar localmente

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Para usar OCR localmente también necesitás Tesseract instalado en el sistema.
