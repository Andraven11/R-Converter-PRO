"""
Script per creare l'eseguibile di R-Converter
Esegui con: python build_exe.py
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def install_pyinstaller():
    """Installa PyInstaller se non presente"""
    try:
        import PyInstaller
        print("✓ PyInstaller già installato")
    except ImportError:
        print("Installazione PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller installato")

def build_executable():
    """Crea l'eseguibile"""
    
    # Configurazione
    app_name = "R-Converter"
    main_script = "main.py"
    icon_file = "icon.ico"  # Opzionale
    
    # Comandi PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--windowed",  # No console window
        "--onedir",    # Cartella portable (più veloce di --onefile)
        "--noconfirm", # Sovrascrivi senza chiedere
        "--clean",     # Pulisci cache
        
        # Ottimizzazioni
        "--optimize", "2",
        
        # Includi moduli necessari
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageTk",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "windnd",
        "--hidden-import", "windnd.windnd",
        "--hidden-import", "ctypes",
        "--hidden-import", "ctypes.wintypes",
        
        # Raccogli tutto il pacchetto windnd
        "--collect-all", "windnd",
        
        # Escludi moduli non necessari per ridurre dimensioni
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "pytest",
        "--exclude-module", "setuptools",
        "--exclude-module", "wheel",
        "--exclude-module", "pip",
        
        main_script
    ]
    
    # Aggiungi icona se esiste
    if os.path.exists(icon_file):
        cmd.insert(-1, "--icon")
        cmd.insert(-1, icon_file)
    
    print(f"\nCreazione {app_name}.exe...")
    print("Questo può richiedere alcuni minuti...\n")
    
    try:
        subprocess.check_call(cmd)
        print(f"\n✓ Build completata!")
        print(f"\nTrovi l'applicazione in: dist/{app_name}/")
        print(f"Eseguibile: dist/{app_name}/{app_name}.exe")
        
        # Crea README nella cartella dist
        create_portable_readme(f"dist/{app_name}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Errore durante la build: {e}")
        return False

def create_portable_readme(dist_folder):
    """Crea un README per la versione portable"""
    readme_content = """# R-Converter - Versione Portable

## Avvio
Esegui `R-Converter.exe` per avviare l'applicazione.

## Note
- Non richiede installazione
- Puoi copiare l'intera cartella su una chiavetta USB
- Tutte le funzionalità sono incluse

## Requisiti Sistema
- Windows 10/11 (64-bit)
- Nessuna dipendenza esterna richiesta

## Supporto
Per problemi o suggerimenti, visita il repository del progetto.
"""
    
    readme_path = Path(dist_folder) / "README.txt"
    try:
        readme_path.write_text(readme_content, encoding='utf-8')
        print(f"✓ Creato {readme_path}")
    except:
        pass

def build_single_file():
    """Crea un singolo eseguibile (più lento all'avvio ma più comodo)"""
    
    app_name = "R-Converter"
    main_script = "main.py"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", f"{app_name}_Portable",
        "--windowed",
        "--onefile",   # Singolo file .exe
        "--noconfirm",
        "--clean",
        "--optimize", "2",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageTk",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "windnd",
        "--hidden-import", "windnd.windnd",
        "--hidden-import", "ctypes",
        "--hidden-import", "ctypes.wintypes",
        "--collect-all", "windnd",
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "pytest",
        main_script
    ]
    
    print(f"\nCreazione {app_name}_Portable.exe (singolo file)...")
    print("Questo può richiedere diversi minuti...\n")
    
    try:
        subprocess.check_call(cmd)
        print(f"\n✓ Build completata!")
        print(f"\nTrovi l'eseguibile in: dist/{app_name}_Portable.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Errore durante la build: {e}")
        return False

def clean_build():
    """Pulisce i file di build"""
    folders = ['build', '__pycache__']
    files = ['*.spec']
    
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"✓ Rimosso {folder}/")
    
    for pattern in files:
        for f in Path('.').glob(pattern):
            f.unlink()
            print(f"✓ Rimosso {f}")

def main():
    print("=" * 50)
    print("  R-Converter - Build Tool")
    print("=" * 50)
    print("\nOpzioni:")
    print("1. Crea versione Portable (cartella)")
    print("2. Crea singolo file .exe")
    print("3. Crea entrambe le versioni")
    print("4. Pulisci file di build")
    print("0. Esci")
    
    choice = input("\nScelta [1]: ").strip() or "1"
    
    if choice == "0":
        return
    
    install_pyinstaller()
    
    if choice == "1":
        build_executable()
    elif choice == "2":
        build_single_file()
    elif choice == "3":
        build_executable()
        build_single_file()
    elif choice == "4":
        clean_build()
    else:
        print("Scelta non valida")

if __name__ == "__main__":
    main()
