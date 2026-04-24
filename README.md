# XMLens

Aplicación de escritorio para transformar archivos XML con XSLT y visualizar el resultado HTML directamente en la app.

## Características

- Selección de archivo XML con detección automática de la URL de XSLT declarada en el documento
- Transformación XML → HTML vía XSLT con soporte de referencias remotas
- Visor HTML embebido (motor WebEngine/Chromium) en panel lateral
- Toggle de tema claro / oscuro
- Carpeta de salida configurable
- Registro de actividad en tiempo real

## Estructura

| Archivo | Descripción |
|---|---|
| `app.py` | Punto de entrada |
| `ui.py` | Interfaz gráfica (PyQt6) |
| `transformer.py` | Lógica de transformación XML → HTML |
| `resolver.py` | Resolución de imports XSLT remotos vía HTTP |
| `requirements.txt` | Dependencias |

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python app.py
```

1. Seleccioná un archivo XML — la URL de XSLT se detecta automáticamente si está declarada en el documento
2. Ajustá la URL de XSLT si es necesario
3. Elegí la carpeta de salida (por defecto: `converted/`)
4. Presioná **Transformar** — el resultado se muestra en el panel derecho y se guarda como `<nombre>_HTML.html`

## Dependencias

- [PyQt6](https://pypi.org/project/PyQt6/) — interfaz gráfica
- [PyQt6-WebEngine](https://pypi.org/project/PyQt6-WebEngine/) — visor HTML embebido
- [lxml](https://pypi.org/project/lxml/) — parseo y transformación XML/XSLT
- [requests](https://pypi.org/project/requests/) — descarga de XSLT remotos

## Versiones

| Versión | Descripción |
|---|---|
| v0.1.0 | Versión inicial: transformación XML → HTML con UI tkinter |
| v0.2.0 | Migración a PyQt6, visor HTML embebido, toggle tema claro/oscuro |
