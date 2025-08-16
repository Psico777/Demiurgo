import os
import subprocess
import json
import readline
import shutil
import time
import re
import logging
from typing import Any, Dict, Optional, List, Set, Tuple
import atexit
import datetime
import threading
import pathlib
import gzip
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv
from arsenal import ARSENAL

load_dotenv()

# ---------------------------------------------------------------------------
# Configuración / Constantes
# ---------------------------------------------------------------------------
API_KEY_ENV_NAMES = ["GOOGLE_API_KEY", "GEMINI_API_KEY"]
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
GENERATION_CONFIG = {
    "temperature": float(os.getenv("LLM_TEMPERATURE", "0.4")),
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)

def _collect_allowed_executables() -> Set[str]:
    allowed: Set[str] = set()
    for section, tools in ARSENAL.items():
        for name, cmd in tools.items():
            first = cmd.split()[0]
            if first:
                allowed.add(first)
    return allowed

ALLOWED_EXECUTABLES = _collect_allowed_executables()

# Cache simple en memoria para salidas de comandos (payload -> salida triageada)
_command_cache_lock = threading.Lock()
_command_cache: Dict[str, str] = {}
CACHEABLE_PREFIXES = {"nmap", "whatweb", "amass", "subfinder", "gobuster", "nikto", "searchsploit"}

class PsicoHackerIA:
    def __init__(self, target):
        self.target = target
        self.mission_log = [{"evento": "Inicio de campaña", "objetivo": self.target}]
        self.prompt_template = self._load_prompt()
        self.model = self._initialize_llm()
        # Limitar longitud del log para no crecer indefinidamente
        self._max_log_entries = 200
        self.report_format = "text"
        self.custom_tools: Dict[str, str] = {}
        self.log_output_path: Optional[str] = None
        self.dynamic_arsenal_path = os.getenv("DYNAMIC_ARSENAL_FILE", "dynamic_arsenal.json")
        self.service_fingerprints: Set[str] = set()
        self._load_dynamic_arsenal()
        if not self.model:
            raise SystemExit("\033[91m[!] No se pudo inicializar el LLM. Abortando.\033[0m")
        atexit.register(self._persist_mission_log)
        atexit.register(self._generate_final_report)

    def _load_prompt(self):
        try:
            with open('prompt.txt', 'r') as f: return f.read()
        except FileNotFoundError:
            raise SystemExit("\033[91m[!] Error Crítico: No se encontró 'prompt.txt'.\033[0m")

    def _initialize_llm(self):
        # Permitir saltar inicialización en pruebas
        if os.getenv('SKIP_LLM_INIT'):
            class _Dummy:
                def generate_content(self, prompt):
                    class R: text = '{"pensamiento_estrategico": "dummy", "accion_propuesta": {"tipo": "COMANDO_SHELL", "herramienta": "nmap_quick_scan", "payload": "echo dummy"}, "contramedida_blue_team": "dummy"}'
                    return R()
            return _Dummy()
        api_key = None
        for name in API_KEY_ENV_NAMES:
            api_key = os.getenv(name)
            if api_key:
                logging.info(f"Usando API key de variable {name}")
                break
        if not api_key:
            logging.error("No se encontró ninguna API key en las variables esperadas.")
            return None
        genai.configure(api_key=api_key)
        try:
            model = genai.GenerativeModel(DEFAULT_MODEL, generation_config=GENERATION_CONFIG)
            return model
        except Exception as e:
            logging.exception("Fallo inicializando el modelo")
            return None

    # ------------------------------------------------------------------
    # Utilidades de parsing / seguridad
    # ------------------------------------------------------------------
    def _extract_json_block(self, text: str) -> Optional[str]:
        """Extrae el primer bloque JSON equilibrado del texto.
        Estrategia: buscar primera llave '{' y balancear."""
        start = text.find('{')
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return None

    def _is_command_allowed(self, cmd: str) -> bool:
        # Obtiene el ejecutable principal (maneja tuberías y &&; solo el primero)
        # Evita encadenamientos múltiples: si detectamos ';' o '&&' lo rechazamos por simplicidad.
        if any(sep in cmd for sep in [';', '&&', '|', '||']):
            return False
        executable = cmd.strip().split()[0]
        return executable in ALLOWED_EXECUTABLES or executable in self.custom_tools

    def _cache_lookup(self, cmd: str) -> Optional[str]:
        first = cmd.split()[0]
        if first not in CACHEABLE_PREFIXES:
            return None
        with _command_cache_lock:
            return _command_cache.get(cmd)

    def _cache_store(self, cmd: str, value: str):
        first = cmd.split()[0]
        if first in CACHEABLE_PREFIXES:
            with _command_cache_lock:
                _command_cache[cmd] = value

    def _triage_output(self, tool_output, tool_name):
        print("\033[93m[*] Aplicando filtro cognitivo local...\033[0m")
        if not tool_output or not tool_output.strip(): return "La herramienta no produjo ninguna salida."
        
        if "nmap" in tool_name:
            open_ports = re.findall(r'^(\d+/tcp|\d+/udp)\s+open\s+(\S+)\s+(.*)', tool_output, re.MULTILINE)
            if not open_ports: return "Nmap no encontró puertos abiertos."
            for p, s, v in open_ports:
                fp = f"{p} {s} {v.strip()}"[:120]
                self.service_fingerprints.add(fp)
            return "Puertos Abiertos Encontrados:\n" + "\n".join([f"- {p} {s} {v}" for p, s, v in open_ports])
        
        return (tool_output[:2000] + '...') if len(tool_output) > 2000 else tool_output

    def _safe_register_tool(self, name: str, template: str) -> str:
        # Sólo permitir comandos de una palabra base + parámetros; sin ; | &&
        if any(sep in template for sep in [';', '&&', '|', '||']):
            return "Plantilla rechazada: contiene separadores peligrosos."
        base = template.strip().split()[0]
        if not re.match(r'^[a-zA-Z0-9_\-]+$', name):
            return "Nombre de herramienta inválido."
        self.custom_tools[name] = template
        # Persistir inmediatamente
        try:
            existing = {}
            if os.path.isfile(self.dynamic_arsenal_path):
                existing = json.load(open(self.dynamic_arsenal_path, 'r', encoding='utf-8'))
            existing[name] = template
            json.dump(existing, open(self.dynamic_arsenal_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning("No se pudo persistir herramienta dinámica: %s", e)
        return f"Herramienta '{name}' registrada localmente."

    def _web_search_stub(self, query: str) -> str:
        # Stub sin llamadas externas reales (evita fuga accidental). Simula ranking.
        pseudo = [
            {"titulo": f"Resultado simulado 1 para '{query}'", "url": "https://example.com/1", "resumen": "Resumen aproximado."},
            {"titulo": f"Resultado simulado 2 para '{query}'", "url": "https://example.com/2", "resumen": "Otro ángulo contextual."}
        ]
        return json.dumps(pseudo, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Persistencia y reportes
    # ------------------------------------------------------------------
    def _persist_mission_log(self):
        if not self.mission_log:
            return
        if not self.log_output_path:
            ts = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d_%H%M%S') if hasattr(datetime, 'UTC') else datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            self.log_output_path = f"mission_log_{ts}.json"
        try:
            with open(self.log_output_path, 'w', encoding='utf-8') as f:
                json.dump(self.mission_log, f, ensure_ascii=False, indent=2)
            # Comprimir si supera umbral (50KB)
            size = os.path.getsize(self.log_output_path)
            if size > 50 * 1024:
                gz_path = self.log_output_path + '.gz'
                with open(self.log_output_path, 'rb') as fin, gzip.open(gz_path, 'wb') as fout:
                    shutil.copyfileobj(fin, fout)
                os.remove(self.log_output_path)
                self.log_output_path = gz_path
        except Exception as e:
            logging.warning("No se pudo persistir mission_log: %s", e)

    def _render_report(self, decision: Dict[str, Any], action: Dict[str, Any], result: str) -> str:
        if self.report_format == 'markdown':
            return (f"## Informe Táctico\n\n**Objetivo:** {self.target}\n\n" \
                    f"**Acción:** `{action.get('tipo')}`\n\n" \
                    f"**Comando/Payload:** `{action.get('payload')}`\n\n" \
                    f"**Pensamiento Estratégico:**\n\n{decision.get('pensamiento_estrategico')}\n\n" \
                    f"**Resultado (resumido):**\n\n````\n{result[:1500]}\n````\n")
        if self.report_format == 'html':
            return (f"<h2>Informe Táctico</h2><p><b>Objetivo:</b> {self.target}</p>" \
                    f"<p><b>Acción:</b> {action.get('tipo')}</p>" \
                    f"<p><b>Comando/Payload:</b> <code>{action.get('payload')}</code></p>" \
                    f"<h3>Pensamiento Estratégico</h3><p>{decision.get('pensamiento_estrategico')}</p>" \
                    f"<h3>Resultado (resumido)</h3><pre>{result[:1500]}</pre>")
        # Texto plano default
        return (f"INFORME TÁCTICO\nObjetivo: {self.target}\nAcción: {action.get('tipo')}\n" \
                f"Comando/Payload: {action.get('payload')}\nPensamiento: {decision.get('pensamiento_estrategico')}\n" \
                f"Resultado:\n{result[:1500]}\n")

    def _load_dynamic_arsenal(self):
        try:
            if os.path.isfile(self.dynamic_arsenal_path):
                data = json.load(open(self.dynamic_arsenal_path, 'r', encoding='utf-8'))
                if isinstance(data, dict):
                    self.custom_tools.update({k: str(v) for k,v in data.items()})
        except Exception as e:
            logging.warning("No se pudo cargar arsenal dinámico: %s", e)

    def _generate_final_report(self):
        if not self.mission_log:
            return
        ts = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d_%H%M%S') if hasattr(datetime, 'UTC') else datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        path = f"final_report_{ts}.md"
        try:
            lines = [f"# Informe Final - Objetivo {self.target}", "", "## Línea Temporal", ""]
            for e in self.mission_log:
                lines.append(f"- {e.get('evento','accion')} | {e.get('decision',{}).get('accion_propuesta',{}).get('tipo','')} -> {str(e)[:160]}")
            if self.service_fingerprints:
                lines += ["", "## Huella de Servicios Detectados", ""]
                for fp in sorted(self.service_fingerprints):
                    lines.append(f"- {fp}")
            if self.custom_tools:
                lines += ["", "## Herramientas Dinámicas Registradas", ""]
                for name, tpl in self.custom_tools.items():
                    lines.append(f"- **{name}**: `{tpl}`")
            pathlib.Path(path).write_text("\n".join(lines), encoding='utf-8')
        except Exception as e:
            logging.warning("No se pudo generar informe final: %s", e)

    def get_ai_decision(self, context_summary):
        prompt = self.prompt_template.replace("{context}", context_summary)
        print(f"\n\033[95m[*] El Demiurgo está meditando...\033[0m")
        try:
            response = self.model.generate_content(prompt)
            raw_text = getattr(response, 'text', '') or ''
            json_block = self._extract_json_block(raw_text)
            if not json_block:
                raise ValueError("No se extrajo JSON válido")
            return json.loads(json_block)
        except Exception as e:
            logging.warning("Fallo parseando la decisión: %s", e)
            if 'raw_text' in locals():
                logging.debug("Respuesta bruta: %s", raw_text)
            return None

    def execute_action(self, action):
        # CORRECCIÓN: La función ahora es más robusta y busca en múltiples llaves posibles.
        action_type = action.get("tipo")
        payload = action.get("payload")
        
        print(f"\n\033[96m[+] AUTORIZANDO ACCIÓN: {action_type}\033[0m")
        if not payload: return "Error: No se proporcionó 'payload' en la acción."

        try:
            if action_type == "COMANDO_SHELL":
                if not self._is_command_allowed(payload):
                    return "Comando rechazado por política de seguridad local (no permitido)."
                cached = self._cache_lookup(payload)
                if cached:
                    return cached + "\n(CACHE)"
                print(f"    - Comando de sistema a ejecutar: {payload}")
                process = subprocess.run(payload, shell=True, capture_output=True, text=True, timeout=900)
                triaged = self._triage_output(process.stdout + process.stderr, action.get("herramienta", "shell"))
                self._cache_store(payload, triaged)
                return triaged
            elif action_type == "BUSQUEDA_WEB_NATIVA":
                return self._web_search_stub(payload)
            elif action_type == "EJECUCION_DE_CODIGO_NATIVA":
                # Interpretamos el payload como intento de crear herramienta segura: formato NAME::COMMAND_TEMPLATE
                if '::' in payload:
                    name, template = payload.split('::', 1)
                    return self._safe_register_tool(name.strip(), template.strip())
                return "Formato para creación de herramienta inválido. Usa NOMBRE::COMANDO"
            else:
                return f"Acción '{action_type}' no implementada para ejecución directa."
        except Exception as e:
            logging.exception("Fallo ejecutando acción")
            return f"Error Crítico durante la ejecución: {e}"

    def mission_loop(self):
        last_output = f"El objetivo inicial es {self.target}"
        commander_directive = None

        while True:
            context = {
                "resumen_mision": self.mission_log[-3:],
                "ultimo_resultado": last_output,
                "directiva_comandante": commander_directive, # Incluimos la directiva del comandante
                "huella_servicios": list(sorted(self.service_fingerprints))[:50],
                "herramientas_dinamicas": list(self.custom_tools.keys())
            }
            # Reseteamos la directiva después de usarla para el pensamiento
            commander_directive = None 

            decision = self.get_ai_decision(json.dumps(context, indent=2, ensure_ascii=False))
            if not decision: break
            
            # CORRECCIÓN: Hacemos el parseo de la decisión más robusto.
            action_to_execute = decision.get("accion_propuesta") or decision.get("accion_a_ejecutar")
            if not action_to_execute or not isinstance(action_to_execute, dict):
                print("\033[91m[!] La IA no propuso una acción válida y estructurada. Recalculando...\033[0m")
                last_output = "La última respuesta no contenía una 'accion_propuesta' válida. Reformula tu plan."
                self.mission_log.append({"evento": "Fallo de formato IA", "respuesta_bruta": decision})
                continue

            report_preview = self._render_report(decision, action_to_execute, "(pendiente de ejecución)")
            print("\n" + "="*40)
            print("  \033[1mINFORME DE INTELIGENCIA DEL DEMIURGO\033[0m")
            print("="*40)
            print(report_preview if self.report_format == 'text' else report_preview[:800] + ('...' if len(report_preview) > 800 else ''))

            auth = input("\n\033[92mComandante, autoriza? (s/n/salir/a:mejorar): \033[0m").lower()
            
            if auth == 'a':
                # MEJORA: Implementación correcta de la modificación estratégica.
                commander_directive = input("\033[92m    -> Directiva de mejora estratégica: \033[0m")
                last_output = f"El Comandante ha intervenido. Nueva directiva: '{commander_directive}'. Se debe refinar el plan anterior."
                self.mission_log.append({"evento": "Directiva del Comandante", "directiva": commander_directive, "plan_anterior": decision})
                continue # Volvemos al inicio del bucle para que la IA repiense con la nueva directiva
            
            elif auth == 's':
                last_output = self.execute_action(action_to_execute)
                self.mission_log.append({"decision": decision, "resultado": last_output})
                if len(self.mission_log) > self._max_log_entries:
                    self.mission_log = self.mission_log[-self._max_log_entries:]
                print("\n\033[92m[+] Acción ejecutada. Analizando nuevo estado...\033[0m")
            else:
                print("[*] Misión terminada por orden del Comandante.")
                break

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PsicoHackerIA - El Demiurgo")
    parser.add_argument("target", nargs="?", help="Objetivo (IP / dominio / URL)")
    parser.add_argument("--once", action="store_true", dest="once", help="Ejecuta solo un ciclo y sale")
    parser.add_argument("--report-format", choices=["text", "markdown", "html"], default="text", help="Formato de informe")
    parser.add_argument("--log-file", dest="log_file", help="Ruta personalizada para mission_log JSON")
    parser.add_argument("--disable-cache", action="store_true", dest="disable_cache", help="Desactiva cache de comandos")
    args = parser.parse_args()

    print("="*70)
    print("        PsicoHackerIA v13.2 - EL DEMIURGO (Núcleo Simbiótico)")
    print("="*70)

    target_input = args.target or input("\033[92mComandante, defina el objetivo primario de la campaña: \033[0m")
    if target_input:
        agent = PsicoHackerIA(target_input)
        agent.report_format = args.report_format
        if args.log_file:
            agent.log_output_path = args.log_file
        if args.disable_cache:
            CACHEABLE_PREFIXES.clear()
        if args.once:
            agent.mission_loop()
        else:
            agent.mission_loop()
