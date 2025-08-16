# PsicoHackerIA - El Demiurgo

Asistente táctico de ciberseguridad interactivo que orquesta reconocimiento y ejecución controlada de comandos apoyado por un LLM (Gemini).

## Características
- Bucle de misión iterativo con supervisión humana.
- Prompt estructurado y JSON estricto.
- Arsenal de comandos para fases de reconocimiento, enumeración y explotación.
- Filtrado local de salida (por ahora Nmap + truncamiento genérico).

## Requisitos
Python 3.11+

Instala dependencias:
```bash
pip install -r requirements.txt
```
Configura tu clave en un archivo `.env`:
```
GOOGLE_API_KEY="TU_CLAVE"
```

## Uso
```bash
python demiurgo.py
```
Ingresa el objetivo (IP, dominio o URL base). Autoriza cada acción propuesta (s = ejecutar, a = dar directiva y recalcular, n/enter = salir).

## Estructura
- `demiurgo.py`: Núcleo de control y ciclo de misión.
- `arsenal.py`: Diccionario de comandos parametrizables.
- `prompt.txt`: Plantilla del prompt para el modelo.
- `requirements.txt`: Dependencias.

## Seguridad / Buenas Prácticas
- Nunca subas tu `.env` con claves reales.
- Revisa comandos antes de autorizarlos.
- Limita permisos del entorno de ejecución.

## Licencia
MIT. Ver `LICENSE`.
