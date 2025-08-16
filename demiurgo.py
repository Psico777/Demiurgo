import os
import subprocess
import json
import readline
import shutil
import time
import re
import logging
from typing import Any, Dict, Optional, List, Set
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

class PsicoHackerIA:
    def __init__(self, target):
        self.target = target
        self.mission_log = [{"evento": "Inicio de campaña", "objetivo": self.target}]
        self.prompt_template = self._load_prompt()
        self.model = self._initialize_llm()
        # Limitar longitud del log para no crecer indefinidamente
        self._max_log_entries = 200
        if not self.model:
            raise SystemExit("\033[91m[!] No se pudo inicializar el LLM. Abortando.\033[0m")

    def _load_prompt(self):
        try:
            with open('prompt.txt', 'r') as f: return f.read()
        except FileNotFoundError:
            raise SystemExit("\033[91m[!] Error Crítico: No se encontró 'prompt.txt'.\033[0m")

    def _initialize_llm(self):
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
        return executable in ALLOWED_EXECUTABLES

    def _triage_output(self, tool_output, tool_name):
        print("\033[93m[*] Aplicando filtro cognitivo local...\033[0m")
        if not tool_output or not tool_output.strip(): return "La herramienta no produjo ninguna salida."
        
        if "nmap" in tool_name:
            open_ports = re.findall(r'^(\d+/tcp|\d+/udp)\s+open\s+(\S+)\s+(.*)', tool_output, re.MULTILINE)
            if not open_ports: return "Nmap no encontró puertos abiertos."
            return "Puertos Abiertos Encontrados:\n" + "\n".join([f"- {p} {s} {v}" for p, s, v in open_ports])
        
        return (tool_output[:2000] + '...') if len(tool_output) > 2000 else tool_output

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
                print(f"    - Comando de sistema a ejecutar: {payload}")
                process = subprocess.run(payload, shell=True, capture_output=True, text=True, timeout=900)
                return self._triage_output(process.stdout + process.stderr, action.get("herramienta", "shell"))
            elif action_type == "BUSQUEDA_WEB_NATIVA":
                return "Capacidad BUSQUEDA_WEB_NATIVA aún no implementada localmente. Ajusta el plan."
            elif action_type == "EJECUCION_DE_CODIGO_NATIVA":
                return "Ejecución dinámica de código deshabilitada por seguridad. Ajusta el plan."
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
                "directiva_comandante": commander_directive # Incluimos la directiva del comandante
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

            print("\n" + "="*40)
            print("  \033[1mINFORME DE INTELIGENCIA DEL DEMIURGO\033[0m")
            print("="*40)
            print(f"\033[94m[*] Pensamiento Estratégico:\033[0m {decision.get('pensamiento_estrategico')}")
            print(f"    \033[94m- Acción Propuesta:\033[0m {action_to_execute.get('tipo')}")
            print(f"    \033[94m- Payload/Comando:\033[0m {action_to_execute.get('payload')}")

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
    args = parser.parse_args()

    print("="*70)
    print("        PsicoHackerIA v13.2 - EL DEMIURGO (Núcleo Simbiótico)")
    print("="*70)

    target_input = args.target or input("\033[92mComandante, defina el objetivo primario de la campaña: \033[0m")
    if target_input:
        agent = PsicoHackerIA(target_input)
        if args.once:
            # Ejecuta un solo ciclo (útil para automatizaciones / pruebas)
            agent.mission_loop()  # El bucle se controla manualmente; simplificación: usuario aborta tras primer ciclo
        else:
            agent.mission_loop()
