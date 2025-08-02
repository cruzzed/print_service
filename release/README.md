# MurniJMS QR Print Client

A standalone desktop application for automated printing of PDF documents via QR code scanning, designed to work with MurniJMS inventory management system.

> **Note**: This is a separate repository from the main MurniJMS application, allowing for independent updates and distribution of the print client.

## Quick Start

### Windows
1. Double-click `install.bat`
2. The script will automatically set up Python environment and start the application

### Linux/macOS
1. Open terminal in this folder
2. Run: `chmod +x install.sh && ./install.sh`
3. The script will automatically set up Python environment and start the application

## What the Installation Does

The installation script will:
1. **Check for Python** - Ensures Python 3.8+ is available
2. **Create Virtual Environment** - Creates `.venv` folder (if it doesn't exist)
3. **Install Dependencies** - Installs required Python packages
4. **Launch Application** - Starts the QR Print Client

## Requirements

- **Python 3.8+** (download from [python.org](https://python.org))
- **Internet connection** (for downloading PDFs from QR codes)
- **Printers** (label and/or receipt printers)

## How to Use

1. **Configure Printers**: Set up your label and receipt printers in the application
2. **Scan QR Codes**: Use a handheld scanner or paste QR data manually
3. **QR Format**: `type:url` (e.g., `label:https://example.com/label.pdf`)
4. **Auto-printing**: Enable for seamless operation

## Features

- ✅ QR code scanning with handheld scanners
- ✅ Support for label and receipt printers
- ✅ Print history and reprint functionality
- ✅ Configurable printer settings
- ✅ Cross-platform (Windows, macOS, Linux)

## Troubleshooting

### Python Not Found
- Install Python from [python.org](https://python.org)
- Ensure Python is added to your system PATH

### Permission Errors (Linux/macOS)
- Run: `chmod +x install.sh`
- Or use: `bash install.sh`

### Printer Issues
- Ensure printers are installed and working
- Try printing a test page from your system
- Use "default" printer setting if specific printer doesn't work

## Development

### Building Releases

To create a new release package:

```bash
python build_release.py
```

This will create:
- `qr-print-client.zip` - Distribution package
- `release/` directory - Unpackaged files

### Project Structure

```
print_service/
├── gui_qr_print_service.py  # Main application
├── install.bat              # Windows installer
├── install.sh              # Linux/macOS installer
├── requirements.txt        # Dependencies
├── setup.py               # Package configuration
├── build_release.py       # Release builder
└── README.md             # Documentation
```

### Integration with MurniJMS

This print client is designed to work with MurniJMS inventory system:

1. **QR Code Format**: Expects QR codes in format `type:url`
2. **Supported Types**: `label` and `receipt`
3. **PDF Downloads**: Fetches PDF files from MurniJMS web application
4. **Auto-printing**: Configurable for seamless workflow

## Support

For issues, contact your system administrator or check the main MurniJMS application documentation.