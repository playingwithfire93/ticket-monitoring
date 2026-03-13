# Generador de CV — Instrucciones

Este script crea un CV en español (`CV_Tripulante_Espanol.docx`) y deja un hueco para la foto (placeholder). Opcionalmente intenta generar un PDF si `docx2pdf` y Microsoft Word están disponibles en Windows.

Requisitos (recomendado usar un entorno virtual):

```
pip install -r requirements.txt
```

Requerimientos concretos añadidos:
- python-docx
- Pillow
- docx2pdf (opcional, solo si quieres conversión automática a PDF desde Word en Windows)

Uso:

1. Para generar el `DOCX` con un placeholder para la foto (usa el placeholder creado automáticamente):

```
python generate_cv.py
```

2. Si quieres que el script inserte tu foto (JPG/PNG), pásala como argumento:

```
python generate_cv.py mi_foto.jpg
```

3. Si el PDF no se genera automáticamente, abre `CV_Tripulante_Espanol.docx` en Microsoft Word y exporta a PDF (`Guardar como` → `PDF`).

Fichero resultante:
- `CV_Tripulante_Espanol.docx` (editable)
- `CV_Tripulante_Espanol.pdf` (si la conversión automática funciona)

Si quieres que lo genere yo directamente (subiendo la foto como archivo descargable en la conversación), puedo insertarla yo y devolverte los archivos listos.
