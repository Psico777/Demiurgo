import os
import json
import types
import importlib

# Forzamos modo dummy para no llamar al LLM real
eos_environ_backup = dict(os.environ)
os.environ['SKIP_LLM_INIT'] = '1'

mod = importlib.import_module('demiurgo')
PsicoHackerIA = mod.PsicoHackerIA


def test_json_parsing():
    agent = PsicoHackerIA('dummy')
    block = agent._extract_json_block('{"a":1,"b":2}')
    assert block == '{"a":1,"b":2}'
    block2 = agent._extract_json_block('xx {"x":5} zz')
    assert block2 == '{"x":5}'


def test_command_filter():
    agent = PsicoHackerIA('dummy')
    assert agent._is_command_allowed('nmap -sV 127.0.0.1') is True
    assert agent._is_command_allowed('nmap -sV 127.0.0.1; id') is False
    assert agent._is_command_allowed('echo hello && whoami') is False


def test_cache_store_and_hit():
    agent = PsicoHackerIA('dummy')
    cmd = 'nmap -sV 127.0.0.1'
    # Primero no en cache
    assert agent._cache_lookup(cmd) is None
    agent._cache_store(cmd, 'OK')
    assert agent._cache_lookup(cmd) == 'OK'


def test_dynamic_tool_registration(tmp_path):
    os.environ['DYNAMIC_ARSENAL_FILE'] = str(tmp_path / 'dyn.json')
    # Reimport to pick new path
    importlib.reload(mod)
    PsicoHackerIA2 = mod.PsicoHackerIA
    agent = PsicoHackerIA2('dummy')
    resp = agent._safe_register_tool('mi_tool','whatweb {target}')
    assert 'registrada' in resp
    assert 'mi_tool' in agent.custom_tools


def teardown_module(module):
    # Restaurar solo claves sobre-escritas evitando eliminar variables internas que usa pytest
    for k in list(os.environ.keys()):
        if k not in eos_environ_backup and k.startswith('DYNAMIC_ARSENAL_FILE'):
            os.environ.pop(k, None)
    for k, v in eos_environ_backup.items():
        os.environ[k] = v
