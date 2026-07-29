# eNTify Invoices · BETA 4.0 ADITIVA

Este paquete **no reemplaza ni elimina** los archivos que ya funcionan.
Agrega un sistema multipágina y multi-autónomo sobre la BETA 3.1.1.

## Qué se agrega

- `pages/0_eNTify_Invoices.py`
- `pages/2_Facturas_recibidas.py`
- `pages/3_Facturas_emitidas.py`
- `pages/4_Autonomos.py`
- `pages/5_Configuracion.py`
- carpeta `modules/`
- carpeta `data/`

## Qué se conserva

No borres ni reemplaces:

- `app.py`
- `extractor_v2.py`
- `excel_exporter.py`
- `requirements.txt`
- `packages.txt`
- `.streamlit/config.toml`

Las páginas nuevas importan y reutilizan `extractor_v2.py` y `excel_exporter.py`.

## Cómo subirlo a GitHub

1. Descomprimí el ZIP.
2. En GitHub elegí **Add file → Upload files**.
3. Arrastrá las carpetas `pages`, `modules`, `data` y este archivo.
4. Confirmá el commit.
5. No elimines los archivos anteriores.

Streamlit detectará automáticamente la carpeta `pages` y agregará las nuevas opciones en el menú lateral.
El archivo principal del despliegue sigue siendo:

```text
app.py
```

## Autónomos

El paquete incluye a Adam Aizenberg Tirza como perfil inicial. Desde la página **Autónomos** se pueden agregar y editar los demás.

En Streamlit Cloud, los cambios escritos en `data/autonomos.json` pueden perderse cuando el servidor se reinicia. Para hacerlos permanentes:

1. descargá `autonomos.json` desde la aplicación;
2. reemplazá `data/autonomos.json` en GitHub.

## Funcionamiento

- En **Facturas recibidas**, el autónomo activo se interpreta como cliente/receptor y se excluye al buscar al proveedor.
- En **Facturas emitidas**, el autónomo activo se interpreta como emisor y se busca al cliente.
- Los lotes quedan separados por autónomo y por tipo de factura dentro de la sesión.
- Los PDF no se guardan como archivo histórico.
