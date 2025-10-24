import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--onefile',  # Single executable
    '--windowed',  # No console window
    '--name=LinuxAppInstaller',
    '--hidden-import=PyQt5.QtCore',
    '--hidden-import=PyQt5.QtGui',
    '--hidden-import=PyQt5.QtWidgets',
    '--add-data=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:.'  # Fallback font
])