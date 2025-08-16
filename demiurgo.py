import os
import subprocess
import json
import readline
import shutil
import time
import re
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv
from arsenal import ARSENAL

load_dotenv()

class PsicoHackerIA:
    def __init__(self, target):
        self.target = target
        self.mission_log = [{"evento": "Inicio de campaña", "objetivo": self.target}]
        self.prompt_template = self._load_prompt()
        self.model = self._initialize_llm()
        if not self.model:
            raise SystemExit("\033[91m[!] No se pudo inicializar el LLM. Abortando.\033[0m")

    def _load_prompt(self):
        try:
            with open('prompt.txt', 'r') as f: return f.read()
        except FileNotFoundError:
            raise SystemExit("\033[91m[!] Error Crítico: No se encontró 'prompt.txt'.\033[0m")

    def _initialize_llm(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key: return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-pro')

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
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if not match: raise ValueError(f"No se encontró un objeto JSON válido en la respuesta: {response.text}")
            return json.loads(match.group(0))
        except Exception as e:
            print(f"\033[91m[!] Error de computación cognitiva: {e}\033[0m")
            if 'response' in locals(): print(f"Respuesta en bruto: {response.text}")
            return None

    def execute_action(self, action):
        # CORRECCIÓN: La función ahora es más robusta y busca en múltiples llaves posibles.
        action_type = action.get("tipo")
        payload = action.get("payload")
        
        print(f"\n\033[96m[+] AUTORIZANDO ACCIÓN: {action_type}\033[0m")
        if not payload: return "Error: No se proporcionó 'payload' en la acción."

        try:
            if action_type == "COMANDO_SHELL":
                print(f"    - Comando de sistema a ejecutar: {payload}")
                process = subprocess.run(payload, shell=True, capture_output=True, text=True, timeout=900)
                return self._triage_output(process.stdout + process.stderr, action.get("herramienta", "shell"))
            else:
                return f"Acción '{action_type}' no implementada para ejecución directa."
        except Exception as e:
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
                print("\n\033[92m[+] Acción ejecutada. Analizando nuevo estado...\033[0m")
            else:
                print("[*] Misión terminada por orden del Comandante.")
                break

if __name__ == "__main__":
    # La parte principal del script no cambia
    print("="*70)
    print("             PsicoHackerIA v13.1 - EL DEMIURGO (Núcleo Simbiótico)")
    print("="*70)
    target_input = input("\033[92mComandante, defina el objetivo primario de la campaña: \033[0m")
    if target_input:
        agent = PsicoHackerIA(target_input)
        agent.mission_loop()
