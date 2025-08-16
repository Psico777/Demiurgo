# El Arsenal de Guerra de PsicoHackerIA - v10.0
ARSENAL = {
    "Reconocimiento Pasivo": {
        "amass": "amass enum -passive -d {target_domain}",
        "subfinder": "subfinder -d {target_domain} -silent"
    },
    "Reconocimiento Activo y Escaneo": {
        "nmap_quick_scan": "nmap -sV --top-ports 1000 -T4 --open -Pn {target}",
        "nmap_full_scan": "nmap -sV -p- -T4 --open -Pn {target}"
    },
    "Enumeración y Análisis Web": {
        "whatweb": "whatweb -v --no-errors {target_url}",
        "gobuster_common": "gobuster dir -u {target_url} -w /usr/share/seclists/Discovery/Web-Content/common.txt -t 50 -k",
        "nikto_scan": "nikto -h {target_url} -Tuning 4,5,x"
    },
    "Análisis de Vulnerabilidades Específicas": {
        "searchsploit": "searchsploit {keyword}"
    },
    "Explotación": {
        "metasploit_exploit": "msfconsole -q -x \"{msf_commands}\""
    }
}
