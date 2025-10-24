# Linux Universal App Installer v2.0

A professional, enterprise-grade drag-and-drop application installer for Linux that supports multiple package formats with macOS-level elegance, comprehensive error handling, and advanced features suitable for selection as Linux's default installer.

## Supported Formats
- .deb (Debian packages) - Requires dpkg and apt
- .appimage (AppImage files) - Moved to ~/Applications
- .tar.gz, .tar.xz, .tgz (Tar archives) - Extracted to ~/Applications with optional install scripts
- .snap (Snap packages) - Requires snapd
- .flatpak (Flatpak bundles) - Requires flatpak
- .run, .bin (Executable installers) - Made executable and run

## Enterprise Features
- **Tabbed Interface**: Professional multi-tab UI with Install, Queue, History, Settings, and Help tabs
- **Batch Installation Queue**: Add multiple files and install them all at once with progress tracking
- **Installation History**: Complete audit trail of all installations with timestamps and status
- **Advanced Settings**: Configurable options for auto-start queue, notifications, logging, and directories
- **System Tray Integration**: Minimize to tray with context menu for quick access
- **Comprehensive Logging**: Verbose logging with file persistence for enterprise troubleshooting
- **Settings Persistence**: All user preferences saved across sessions
- **Professional UI**: macOS-level design with modern styling, shadows, and animations

## Core Features
- **Drag-and-Drop Interface**: Intuitive file dropping with visual feedback and animations
- **Browse Files**: Select files via file dialog for traditional file selection
- **Threaded Installations**: Non-blocking UI during installations with progress indicators
- **Comprehensive Error Handling**: Graceful handling of all edge cases with detailed error messages
- **Error Logging**: Persistent logging of all errors and failures for troubleshooting
- **Dependency Checks**: Automatic verification of required system tools at startup
- **Privilege Management**: GUI-based privilege escalation using pkexec
- **Robust File Handling**: Checks for file existence, readability, validity, and hash verification
- **Timeout Protection**: Prevents hanging on long-running operations (5-minute timeout)
- **Conflict Resolution**: Automatic renaming for duplicate AppImages and archives

## System Requirements
- Linux distribution with GUI (X11/Wayland)
- Python 3.6+ (3.13 recommended)
- pkexec (for privilege escalation)
- tar (for archive extraction)
- Optional: dpkg/apt, snapd, flatpak depending on package types used

## Usage

### Basic Installation
1. Launch the application
2. **Drag and Drop**: Drag application files onto the drop zone in the Install tab
3. **Browse Files**: Click the "Browse Files" button to select files via file dialog
4. The app will automatically detect the file type and install it

### Batch Installation
1. Use the "Queue" tab to add multiple files
2. Click "Install All in Queue" to process them sequentially
3. Monitor progress in the status bar and queue list

### History & Auditing
1. View the "History" tab for complete installation records
2. Filter and search through past installations
3. Clear history when needed

### Settings Configuration
1. Access the "Settings" tab to configure:
   - Auto-start installation queue
   - Desktop notifications
   - Verbose logging level
   - Default installation directory

### System Tray
- Minimize to system tray for background operation
- Right-click tray icon for quick access menu
- Restore window or quit from tray menu

## Building Standalone Executable
1. Install build dependencies: `pip install pyinstaller`
2. Run build script: `python build.py`
3. The executable `LinuxAppInstaller` will be created in the `dist/` directory

## Enterprise-Grade Stability
- **Single Installation Lock**: Prevents multiple simultaneous installations that could cause crashes
- **UI State Management**: Interface elements are properly disabled/enabled during operations
- **Global Exception Handler**: Catches and logs any unhandled exceptions to prevent silent crashes
- **Thread-Safe Operations**: All GUI updates are properly synchronized with the main thread
- **Timeout Protection**: All system commands have configurable timeouts
- **Comprehensive Error Recovery**: Graceful handling of all error conditions with detailed logging
- **Memory Management**: Efficient resource usage suitable for long-running enterprise deployments

## Error Recovery & Troubleshooting
The application provides clear error messages and suggestions for resolving issues. All operations are logged to `installer.log` for debugging. Use the "View Logs" menu option to access error logs.

## Security & Reliability
- Uses pkexec for secure privilege escalation (no sudo)
- Validates file integrity with SHA256 hashing
- No arbitrary code execution without user confirmation
- Safe handling of executable files with permission management
- Comprehensive input validation and sanitization
- Audit trail of all installation operations

## Distribution & Deployment
The standalone executable can be distributed as a single file, requiring no additional Python dependencies on target systems (except system tools). Suitable for enterprise deployment across multiple Linux distributions.

## Architecture
- **QMainWindow-based**: Professional desktop application architecture
- **Tabbed Interface**: Organized workflow with dedicated tabs for each function
- **Worker Threads**: Non-blocking installation operations with progress reporting
- **Settings Persistence**: QSettings-based configuration management
- **System Tray**: Qt system tray integration for background operation
- **Signal/Slot Pattern**: Proper Qt event handling throughout

## Future Enhancements
- Uninstall functionality for installed applications
- Package manager integration (apt, snap, flatpak)
- Network-based installation from URLs
- Plugin architecture for custom installers
- Multi-language support
- Dark mode theme
- Integration with system package managers