#!/usr/bin/env python3
"""Script para instalar dependências e iniciar o servidor."""
import subprocess, sys, os

print("╔══════════════════════════════════════════════════╗")
print("║   SIMULADOR ELEITORAL ES — SaaS                  ║")
print("╠══════════════════════════════════════════════════╣")
print("║  Instalando dependências…                        ║")
print("╚══════════════════════════════════════════════════╝\n")

subprocess.check_call([sys.executable, "-m", "pip", "install",
                       "flask", "werkzeug", "-q"])

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("\n╔══════════════════════════════════════════════════╗")
print("║  ✅ Tudo pronto! Iniciando servidor…             ║")
print("║                                                  ║")
print("║  🌐 Acesse: http://localhost:5000                ║")
print("║                                                  ║")
print("║  👤 Admin padrão:                               ║")
print("║     E-mail: admin@simulador.es                   ║")
print("║     Senha:  admin123                             ║")
print("║                                                  ║")
print("║  Pressione Ctrl+C para parar                     ║")
print("╚══════════════════════════════════════════════════╝\n")

subprocess.run([sys.executable, "app.py"])
