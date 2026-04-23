# Visualizador de XMLS

Aplicación mínima para seleccionar un archivo XML, transformarlo con XSLT y ver el resultado en HTML.

## Archivos

- `app.py`: punto de entrada de la aplicación.
- `ui.py`: interfaz gráfica Tkinter.
- `transformer.py`: lógica de transformación XML -> HTML.
- `resolver.py`: resolución de referencias XSLT remotas.
- `requirements.txt`: dependencias necesarias.

## Uso

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Ejecuta la aplicación:
   ```bash
   python app.py
   ```
3. Selecciona un archivo XML, ajusta la URL de XSLT si lo deseas y pulsa "Transformar y abrir".

## Notas

- El resultado se guarda en la carpeta `converted` dentro del proyecto con el sufijo `_HTML.html`.
- Si existe `Titulo_7472.xml` en la carpeta, se selecciona automáticamente al iniciar.
