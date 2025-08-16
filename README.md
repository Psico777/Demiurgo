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
python demiurgo.py <objetivo>
```
O modo asistido (pregunta objetivo):
```bash
python demiurgo.py
```

Flags CLI principales:
| Flag | Descripción |
|------|-------------|
| `--once` | Ejecuta solo un ciclo (útil para pruebas automatizadas) |
| `--report-format {text,markdown,html}` | Formato del informe táctico mostrado |
| `--log-file RUTA` | Forzar ruta de persistencia del `mission_log` |
| `--disable-cache` | Desactiva cache en memoria para comandos repetidos |

Variables de entorno útiles:
- `GOOGLE_API_KEY` / `GEMINI_API_KEY`: clave del modelo.
- `GEMINI_MODEL`: nombre del modelo (default gemini-2.5-pro).
- `SKIP_LLM_INIT=1`: modo dummy para tests.
- `DYNAMIC_ARSENAL_FILE`: nombre de archivo para arsenal dinámico (default `dynamic_arsenal.json`).

Funciones avanzadas:
- Registro de herramientas dinámicas: la IA puede proponer `EJECUCION_DE_CODIGO_NATIVA` con payload `NOMBRE::COMANDO` y quedará persistido.
- Cache de resultados para herramientas de reconocimiento pesado (nmap, whatweb, etc.).
- Persistencia automática del mission log y compresión gzip si supera 50KB.
- Informe final markdown `final_report_*.md` con huella de servicios y herramientas dinámicas.

## Estructura
- `demiurgo.py`: Núcleo de control y ciclo de misión.
- `arsenal.py`: Diccionario de comandos parametrizables.
- `prompt.txt`: Plantilla del prompt para el modelo.
- `requirements.txt`: Dependencias.

## Seguridad / Buenas Prácticas
- Nunca subas tu `.env` con claves reales.
- Revisa comandos antes de autorizarlos.
- Limita permisos del entorno de ejecución.
- No ejecutes contra objetivos sin autorización explícita.
- Revisa el comando exacto antes de autorizarlo (la política de lista blanca no es sustituto del juicio humano).

## Licencia
MIT. Ver `LICENSE`.
