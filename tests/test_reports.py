#!/usr/bin/env python3
"""
Test suite for reporting and persistence functionality in Demiurgo.
"""

import json
import os
import tempfile
import gzip
from unittest.mock import patch, MagicMock
import pytest

# Add the parent directory to the path so we can import demiurgo
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demiurgo import PsicoHackerIA


class TestReporting:
    """Test report generation and formatting."""
    
    def setup_method(self):
        """Set up test environment with dummy LLM."""
        os.environ['SKIP_LLM_INIT'] = 'true'
        self.demiurgo = PsicoHackerIA("test-target")
        # Add some test data
        self.demiurgo.mission_log = [
            {
                "timestamp": "2025-08-15T10:00:00Z",
                "action": "nmap",
                "command": "nmap -sV sgd.midis.gob.pe",
                "output": "80/tcp open http Apache/2.4.41",
                "decision": "Found web server on port 80"
            }
        ]
        self.demiurgo.service_fingerprints = {
            "sgd.midis.gob.pe": ["Apache/2.4.41", "HTTP/1.1"]
        }
        self.demiurgo.custom_tools = ["custom_tool::custom_command {target}"]
    
    def teardown_method(self):
        """Clean up environment."""
        os.environ.pop('SKIP_LLM_INIT', None)
    
    def test_render_report_text_format(self):
        """Test text format report generation."""
        decision = {"accion": "nmap", "comando": "nmap -sV sgd.midis.gob.pe"}
        action = {"comando": "nmap -sV sgd.midis.gob.pe"}
        result = "80/tcp open http Apache/2.4.41"
        
        report = self.demiurgo._render_report(decision, action, result)
        
        assert "=== INFORME DE RECONOCIMIENTO ===" in report
        assert "nmap -sV sgd.midis.gob.pe" in report
        assert "Apache/2.4.41" in report
    
    def test_render_report_markdown_format(self):
        """Test markdown format report generation."""
        self.demiurgo.report_format = "markdown"
        decision = {"accion": "nmap", "comando": "nmap -sV sgd.midis.gob.pe"}
        action = {"comando": "nmap -sV sgd.midis.gob.pe"}
        result = "80/tcp open http Apache/2.4.41"
        
        report = self.demiurgo._render_report(decision, action, result)
        
        assert "# Informe de Reconocimiento" in report
        assert "## Acciones Ejecutadas" in report
        assert "```bash" in report
        assert "nmap -sV sgd.midis.gob.pe" in report
    
    def test_render_report_html_format(self):
        """Test HTML format report generation."""
        self.demiurgo.report_format = "html"
        decision = {"accion": "nmap", "comando": "nmap -sV sgd.midis.gob.pe"}
        action = {"comando": "nmap -sV sgd.midis.gob.pe"}
        result = "80/tcp open http Apache/2.4.41"
        
        report = self.demiurgo._render_report(decision, action, result)
        
        assert "<html>" in report
        assert "<h1>Informe de Reconocimiento</h1>" in report
        assert "<pre><code>" in report
        assert "nmap -sV sgd.midis.gob.pe" in report
    
    def test_generate_final_report(self):
        """Test final report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set the log output path for the final report
            self.demiurgo.log_output_path = os.path.join(temp_dir, "mission_log.json")
            
            result_path = self.demiurgo._generate_final_report()
            
            # Should create a final report in the same directory
            assert result_path is not None
            if result_path and os.path.exists(result_path):
                with open(result_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert "# Informe Final de Reconocimiento" in content


class TestPersistence:
    """Test mission log persistence and compression."""
    
    def setup_method(self):
        """Set up test environment."""
        os.environ['SKIP_LLM_INIT'] = 'true'
        self.demiurgo = PsicoHackerIA("test-target")
        self.demiurgo.mission_log = [
            {"timestamp": "2025-08-15T10:00:00Z", "action": "test", "output": "test"}
        ]
    
    def teardown_method(self):
        """Clean up environment."""
        os.environ.pop('SKIP_LLM_INIT', None)
    
    def test_persist_mission_log_small(self):
        """Test persistence of small mission log (no compression)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "mission_log.json")
            self.demiurgo.log_output_path = log_path
            
            result_path = self.demiurgo._persist_mission_log()
            
            assert result_path == log_path
            assert os.path.exists(log_path)
            
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                assert len(loaded) == 1
                assert loaded[0]["action"] == "test"
    
    def test_persist_mission_log_large_compression(self):
        """Test persistence with compression for large logs."""
        # Create a large mission log (>50KB)
        large_output = "X" * 60000  # 60KB of data
        self.demiurgo.mission_log = [
            {"timestamp": "2025-08-15T10:00:00Z", "action": "large_test", "output": large_output}
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "mission_log.json")
            self.demiurgo.log_output_path = log_path
            
            result_path = self.demiurgo._persist_mission_log()
            
            # Should return compressed path
            expected_gz_path = log_path + ".gz"
            assert result_path == expected_gz_path
            assert os.path.exists(expected_gz_path)
            assert not os.path.exists(log_path)  # Original should be removed
            
            # Verify compressed content
            with gzip.open(expected_gz_path, 'rt', encoding='utf-8') as f:
                loaded = json.load(f)
                assert len(loaded) == 1
                assert loaded[0]["action"] == "large_test"
                assert len(loaded[0]["output"]) == 60000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
