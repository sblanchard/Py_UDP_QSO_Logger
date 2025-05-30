# Enhanced QSO Logger v2.0

I required a solution to log QSO's from my Linux (Pi5) pc at my radio to Log4OM on my Windows workstation over the network, thus is born this solution...

A modern PyQt5 application for logging amateur radio contacts with integrated QRZ.com lookups and Log4OM integration.

## Features

### 🎯 Core Logging
- **Real-time input validation** - Callsign and frequency validation with visual indicators
- **Log4OM integration** - Direct UDP/ADIF logging to Log4OM
- **Multiple bands and modes** - Support for all amateur radio bands and digital modes
- **RST report management** - Editable RST sent/received with common values

### 📡 QRZ.com Integration
- **Automatic callsign lookups** - Real-time QRZ.com database queries
- **Photo display** - Shows operator photos from QRZ profiles
- **Station information** - Name, address, grid square, email, and bio
- **Background processing** - Non-blocking lookups with status indicators

### 🎨 Modern Interface
- **Responsive design** - Adapts to different screen sizes
- **Split-panel layout** - QSO form on left, QRZ info on right
- **Collapsible panels** - Hide/show QRZ panel as needed
- **Clean configuration** - Settings dialogs for QRZ and Log4OM setup

### ⚙️ Smart Features
- **Auto-clear options** - Automatically clear callsign after logging
- **Configuration persistence** - Saves all settings between sessions
- **Keyboard shortcuts** - Enter to log, intuitive navigation
- **Status indicators** - Real-time UTC time and logging status

## Installation

### Prerequisites
```bash
# On Raspberry Pi/Debian/Ubuntu
sudo apt update
sudo apt install python3-pyqt5 python3-requests

# Or using pip (in virtual environment)
python3 -m venv ~/qso_logger_env
source ~/qso_logger_env/bin/activate
pip install PyQt5 requests
```

### Download and Run
```bash
# Clone the repository
git clone https://github.com/yourusername/qso-logger.git
cd qso-logger

# Run the application
python3 qso_logger.py
```

## Configuration

### First Time Setup

1. **QRZ.com Settings** (File → QRZ.com Settings...)
   - Enter your QRZ.com username and password
   - Requires QRZ.com XML subscription for full features
   - Free accounts have limited data access

2. **Log4OM Connection** (File → Log4OM Connection...)
   - Set IP address of computer running Log4OM
   - Default port is usually 2234
   - Enable ADIF UDP import in Log4OM

### QRZ.com Subscription

This application requires a QRZ.com XML subscription for full functionality:
- **Free accounts**: Basic callsign validation only
- **XML subscription**: Full station data, photos, and biographical information
- **Sign up**: Visit [QRZ.com](https://www.qrz.com) for subscription options

## Usage

### Basic Logging
1. Enter callsign (validation indicator shows ✓/✗)
2. Select band and enter frequency
3. Choose mode and RST reports
4. Click "Log QSO" or press Enter
5. QSO is automatically sent to Log4OM

### QRZ Lookups
- **Automatic**: Enable "Auto-lookup callsigns on QRZ.com" in Options
- **Manual**: Use File → Test QRZ Lookup... for testing
- **Photo display**: Shows operator photos when available
- **Station info**: Displays name, location, grid square, etc.

### Interface Tips
- **Toggle QRZ Panel**: Hide/show QRZ information panel
- **Collapsible sections**: Click group headers to expand/collapse
- **Clear All**: Resets all fields to defaults
- **Auto-clear**: Automatically clears callsign after successful logging

## Troubleshooting

### QRZ Lookups Not Working
- Verify QRZ.com credentials in File → QRZ.com Settings
- Ensure you have an active XML subscription
- Check internet connection
- Use File → Test QRZ Lookup to diagnose issues

### Log4OM Connection Issues
- Verify Log4OM IP address and port settings
- Ensure Log4OM has ADIF UDP import enabled
- Check firewall settings on both computers
- Try localhost (127.0.0.1) if running on same computer

### Display Issues
- QRZ information not visible: Try toggling QRZ panel
- Text too small: Adjust system font scaling
- Layout problems: Resize window or restart application


### Key Components
- **ConfigManager**: Handles configuration persistence
- **QRZLookupThread**: Background QRZ.com API calls
- **QSOValidator**: Input validation logic
- **QSOLogger**: Main application window and logic

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Requirements

### System Requirements
- **Operating System**: Linux (Raspberry Pi OS, Ubuntu, Debian), Windows, macOS
- **Python**: 3.6 or higher
- **RAM**: 100MB minimum
- **Network**: Internet connection for QRZ lookups

### Python Dependencies
- **PyQt5**: GUI framework
- **requests**: HTTP library for QRZ API calls
- **Standard library**: json, socket, xml, datetime, pathlib, re, typing

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **QRZ.com** for providing the XML API service
- **Log4OM** team for the excellent logging software
- **PyQt5** developers for the GUI framework
- **Amateur radio community** for feedback and testing

## Support

### Getting Help
- **Issues**: Report bugs via GitHub Issues
- **Documentation**: Check this README and inline help
- **Testing**: Use File → Test QRZ Lookup for diagnostics

### Version History
- **v2.0**: QRZ.com integration, modern UI, enhanced validation
- **v1.0**: Basic Log4OM logging functionality

## Author
F4JZW

**Contact**: 
- GitHub Issues for bug reports
- Pull requests for contributions
- QRZ.com for API-related questions

---

*73! Enjoy logging your QSOs!* 📡✨
