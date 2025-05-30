#!/usr/bin/env python3
"""
Enhanced QSO Logger for Log4OM Integration
A modern PyQt5 application for logging amateur radio contacts
"""

import sys
import socket
import json
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QMessageBox,
    QGroupBox, QStatusBar, QMainWindow, QMenuBar, QAction,
    QCheckBox, QSpinBox, QTextEdit, QFrame, QSplitter, QDialog, QDialogButtonBox,
    QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QUrl
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette, QPainter
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class ConfigManager:
    """Handles application configuration and persistence"""
    
    def __init__(self):
        self.config_file = Path.home() / '.qso_logger_config.json'
        self.default_config = {
            'udp_ip': '192.168.1.100',
            'udp_port': 2234,
            'default_rst_sent': '59',
            'default_rst_recv': '59',
            'auto_clear_call': True,
            'window_geometry': None,
            'qrz_username': '',
            'qrz_password': '',
            'auto_lookup': True,
            'show_photo': True
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or return defaults"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return {**self.default_config, **config}
        except Exception as e:
            print(f"Error loading config: {e}")
        return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")


class QRZLookupThread(QThread):
    """Background thread for QRZ.com lookups"""
    
    lookup_complete = pyqtSignal(dict)  # Emitted when lookup is complete
    lookup_error = pyqtSignal(str)      # Emitted on error
    
    def __init__(self, callsign: str, username: str, password: str):
        super().__init__()
        self.callsign = callsign.upper().strip()
        self.username = username
        self.password = password
        self.session_key = None
    
    def run(self):
        """Run the QRZ lookup in background thread"""
        try:
            # Get session key first
            if not self.get_session_key():
                self.lookup_error.emit("Failed to authenticate with QRZ.com")
                return
            
            print(f"DEBUG: Authentication successful, session key: {self.session_key[:10]}...")
            
            # Now lookup callsign data
            lookup_data = self.lookup_callsign()
            if lookup_data:
                print(f"DEBUG: Lookup successful, emitting data")
                self.lookup_complete.emit(lookup_data)
            else:
                print(f"DEBUG: No data found for {self.callsign}")
                self.lookup_error.emit(f"No data found for {self.callsign}")
                
        except Exception as e:
            print(f"DEBUG: Exception in run(): {e}")
            self.lookup_error.emit(f"QRZ lookup error: {str(e)}")
    
    def get_session_key(self) -> bool:
        """Get QRZ.com session key"""
        try:
            url = f"https://xmldata.qrz.com/xml/current/?username={self.username}&password={self.password}&agent=QSOLogger2.0"
            print(f"DEBUG: Attempting QRZ login for user: {self.username}")
            response = requests.get(url, timeout=10)
            print(f"DEBUG: QRZ response status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"DEBUG: QRZ response: {response.text}")
                root = ET.fromstring(response.content)
                
                # Simple direct access to elements
                for session in root.iter():
                    if session.tag.endswith('Session'):
                        print("DEBUG: Found session element")
                        for child in session:
                            print(f"DEBUG: Session child: {child.tag} = {child.text}")
                            if child.tag.endswith('Key'):
                                self.session_key = child.text
                                print(f"DEBUG: Got session key: {self.session_key}")
                                return True
                            elif child.tag.endswith('Error'):
                                raise Exception(f"QRZ Auth Error: {child.text}")
                            elif child.tag.endswith('Message'):
                                print(f"DEBUG: QRZ Message: {child.text}")
                
                raise Exception("No session key found in response")
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except ET.ParseError as e:
            print(f"DEBUG: XML parsing error: {e}")
            raise Exception(f"XML parsing failed: {str(e)}")
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Network error: {e}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            print(f"DEBUG: Error: {e}")
            raise Exception(f"Authentication failed: {str(e)}")
        
        return False
    
    def lookup_callsign(self) -> Optional[Dict[str, str]]:
        """Lookup callsign data from QRZ.com"""
        if not self.session_key:
            print("DEBUG: No session key available for lookup")
            return None
        
        try:
            url = f"https://xmldata.qrz.com/xml/current/?s={self.session_key}&callsign={self.callsign}"
            print(f"DEBUG: Looking up callsign {self.callsign} with session key {self.session_key[:8]}...")
            response = requests.get(url, timeout=10)
            print(f"DEBUG: Lookup response status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"DEBUG: Lookup response: {response.text}")
                root = ET.fromstring(response.content)
                
                data = {}
                # Look for callsign data
                for element in root.iter():
                    if element.tag.endswith('Callsign'):
                        print("DEBUG: Found Callsign element")
                        for child in element:
                            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                            if child.text:
                                data[tag_name] = child.text.strip()
                                print(f"DEBUG: Found {tag_name}: {child.text.strip()}")
                
                if data:
                    print(f"DEBUG: Returning data with {len(data)} fields")
                    return data
                else:
                    print("DEBUG: No callsign data found")
                    # Check for errors
                    for element in root.iter():
                        if element.tag.endswith('Error'):
                            print(f"DEBUG: Error in response: {element.text}")
                        elif element.tag.endswith('Message'):
                            print(f"DEBUG: Message in response: {element.text}")
                    
            return None
        except Exception as e:
            print(f"DEBUG: Lookup exception: {e}")
            raise Exception(f"Lookup failed: {str(e)}")


class QSOValidator:
    """Validates QSO data entries"""
    
    @staticmethod
    def validate_callsign(call: str) -> bool:
        """Validate amateur radio callsign format"""
        pattern = r'^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]$'
        return bool(re.match(pattern, call.upper().strip()))
    
    @staticmethod
    def validate_frequency(freq: str) -> bool:
        """Validate frequency format"""
        try:
            freq_float = float(freq)
            return 0.1 <= freq_float <= 300000  # Reasonable amateur frequency range
        except ValueError:
            return False
    
    @staticmethod
    def validate_rst(rst: str) -> bool:
        """Validate RST report format"""
        return rst.isdigit() and 11 <= int(rst) <= 59


class QSOLogger(QMainWindow):
    """Main QSO Logger application window"""
    
    qso_logged = pyqtSignal(str)  # Signal emitted when QSO is successfully logged
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        self.validator = QSOValidator()
        self.network_manager = QNetworkAccessManager()
        self.current_lookup_thread = None
        
        self.init_ui()
        self.setup_connections()
        self.load_window_state()
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
        # Lookup delay timer (to avoid too many requests while typing)
        self.lookup_timer = QTimer()
        self.lookup_timer.setSingleShot(True)
        self.lookup_timer.timeout.connect(self.perform_qrz_lookup)
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('Enhanced QSO Logger v2.0 - with QRZ Integration')
        self.setMinimumSize(500, 600)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Ready to log QSOs')
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create a horizontal splitter for adaptive layout
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left widget for QSO data
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # QSO Information Group
        qso_group = QGroupBox("QSO Information")
        qso_layout = QGridLayout(qso_group)
        qso_layout.setVerticalSpacing(8)
        qso_layout.setHorizontalSpacing(10)
        qso_layout.setContentsMargins(10, 15, 10, 15)
        
        # Call sign with validation indicator
        call_label = QLabel('Call Sign:')
        call_label.setMinimumHeight(25)
        qso_layout.addWidget(call_label, 0, 0)
        self.call_input = QLineEdit()
        self.call_input.setMinimumHeight(30)
        self.call_input.setPlaceholderText("Enter callsign (e.g., W1AW)")
        self.call_input.textChanged.connect(self.validate_callsign_input)
        qso_layout.addWidget(self.call_input, 0, 1)
        
        self.call_valid_label = QLabel("✗")
        self.call_valid_label.setStyleSheet("color: red; font-weight: bold;")
        self.call_valid_label.setMinimumWidth(20)
        qso_layout.addWidget(self.call_valid_label, 0, 2)
        
        # Band
        band_label = QLabel('Band:')
        band_label.setMinimumHeight(25)
        qso_layout.addWidget(band_label, 1, 0)
        self.band_select = QComboBox()
        self.band_select.setMinimumHeight(30)
        self.band_select.addItems([
            '2200m', '630m', '160m', '80m', '60m', '40m', '30m', '20m', 
            '17m', '15m', '12m', '10m', '6m', '4m', '2m', '1.25m', '70cm'
        ])
        self.band_select.setCurrentText('20m')
        qso_layout.addWidget(self.band_select, 1, 1, 1, 2)
        
        # Frequency
        freq_label = QLabel('Frequency (MHz):')
        freq_label.setMinimumHeight(25)
        qso_layout.addWidget(freq_label, 2, 0)
        self.freq_input = QLineEdit()
        self.freq_input.setMinimumHeight(30)
        self.freq_input.setPlaceholderText("e.g., 14.074")
        self.freq_input.textChanged.connect(self.validate_frequency_input)
        qso_layout.addWidget(self.freq_input, 2, 1)
        
        self.freq_valid_label = QLabel("✗")
        self.freq_valid_label.setStyleSheet("color: red; font-weight: bold;")
        self.freq_valid_label.setMinimumWidth(20)
        qso_layout.addWidget(self.freq_valid_label, 2, 2)
        
        # Mode
        mode_label = QLabel('Mode:')
        mode_label.setMinimumHeight(25)
        qso_layout.addWidget(mode_label, 3, 0)
        self.mode_select = QComboBox()
        self.mode_select.setMinimumHeight(30)
        self.mode_select.addItems([
            'SSB', 'CW', 'FT8', 'FT4', 'RTTY', 'PSK31', 'JT65', 'JT9',
            'MFSK', 'OLIVIA', 'CONTESTIA', 'AM', 'FM', 'DIGITAL'
        ])
        self.mode_select.setCurrentText('FT8')
        qso_layout.addWidget(self.mode_select, 3, 1, 1, 2)
        
        # RST Reports
        rst_sent_label = QLabel('RST Sent:')
        rst_sent_label.setMinimumHeight(25)
        qso_layout.addWidget(rst_sent_label, 4, 0)
        self.rst_sent_input = QComboBox()
        self.rst_sent_input.setMinimumHeight(30)
        self.rst_sent_input.setEditable(True)
        self.populate_rst_combo(self.rst_sent_input)
        self.rst_sent_input.setCurrentText(self.config['default_rst_sent'])
        qso_layout.addWidget(self.rst_sent_input, 4, 1, 1, 2)
        
        rst_recv_label = QLabel('RST Received:')
        rst_recv_label.setMinimumHeight(25)
        qso_layout.addWidget(rst_recv_label, 5, 0)
        self.rst_recv_input = QComboBox()
        self.rst_recv_input.setMinimumHeight(30)
        self.rst_recv_input.setEditable(True)
        self.populate_rst_combo(self.rst_recv_input)
        self.rst_recv_input.setCurrentText(self.config['default_rst_recv'])
        qso_layout.addWidget(self.rst_recv_input, 5, 1, 1, 2)
        
        # Set proper column stretch
        qso_layout.setColumnStretch(0, 0)  # Labels don't stretch
        qso_layout.setColumnStretch(1, 1)  # Input fields stretch
        qso_layout.setColumnStretch(2, 0)  # Validation indicators don't stretch
        
        qso_group.setMinimumHeight(220)
        left_layout.addWidget(qso_group)
        
        # Options Group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.auto_clear_checkbox = QCheckBox("Auto-clear call sign after logging")
        self.auto_clear_checkbox.setChecked(self.config['auto_clear_call'])
        options_layout.addWidget(self.auto_clear_checkbox)
        
        self.auto_lookup_checkbox = QCheckBox("Auto-lookup callsigns on QRZ.com")
        self.auto_lookup_checkbox.setChecked(self.config.get('auto_lookup', True))
        options_layout.addWidget(self.auto_lookup_checkbox)
        
        left_layout.addWidget(options_group)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        
        self.log_button = QPushButton('Log QSO')
        self.log_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.log_button.setEnabled(False)
        button_layout.addWidget(self.log_button)
        
        self.clear_button = QPushButton('Clear All')
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        button_layout.addWidget(self.clear_button)
        
        left_layout.addLayout(button_layout)
        
        # Log display
        log_group = QGroupBox("Recent QSOs")
        log_layout = QVBoxLayout(log_group)
        
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(80)
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        left_layout.addWidget(log_group)
        
        # Add left widget to splitter
        splitter.addWidget(left_widget)
        
        # Right widget for QRZ data
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # QRZ Information Group
        self.qrz_info_group = QGroupBox("QRZ Information")
        qrz_info_layout = QVBoxLayout(self.qrz_info_group)
        
        # Photo display
        self.photo_frame = QFrame()
        self.photo_frame.setFrameStyle(QFrame.StyledPanel)
        self.photo_frame.setFixedSize(150, 150)
        self.photo_frame.setStyleSheet("background-color: #f0f0f0; border: 2px solid #ccc;")
        
        photo_layout = QVBoxLayout(self.photo_frame)
        self.photo_label = QLabel("No Photo")
        self.photo_label.setAlignment(Qt.AlignCenter)
        self.photo_label.setStyleSheet("color: #888; font-size: 12px;")
        photo_layout.addWidget(self.photo_label)
        
        qrz_info_layout.addWidget(self.photo_frame, 0, Qt.AlignCenter)
        
        # Station information - using QTextEdit for visibility
        self.station_info_text = QTextEdit()
        self.station_info_text.setReadOnly(True)
        self.station_info_text.setPlainText("Enter a callsign to see QRZ information")
        
        # Set colors directly with palette
        palette = QPalette()
        palette.setColor(QPalette.Base, Qt.white)
        palette.setColor(QPalette.Text, Qt.black)
        self.station_info_text.setPalette(palette)
        
        # Set font
        font = QFont("Arial", 12, QFont.Bold)
        self.station_info_text.setFont(font)
        
        # Stylesheet
        self.station_info_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                border: 2px solid black;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        
        self.station_info_text.setMinimumHeight(100)
        self.station_info_text.setMaximumHeight(200)
        qrz_info_layout.addWidget(self.station_info_text)
        
        # Lookup status
        self.lookup_status_label = QLabel("")
        self.lookup_status_label.setStyleSheet("""
            QLabel {
                color: black;
                font-style: italic;
                font-size: 11px;
                font-weight: bold;
                padding: 5px;
                background-color: #e0e0e0;
                border: 1px solid #666666;
                border-radius: 3px;
            }
        """)
        qrz_info_layout.addWidget(self.lookup_status_label)
        
        right_layout.addWidget(self.qrz_info_group)
        right_layout.addStretch()
        
        # Add right widget to splitter
        splitter.addWidget(right_widget)
        
        # Set splitter proportions
        splitter.setSizes([400, 200])
        splitter.setCollapsible(1, True)
        
        # Toggle button for QRZ panel
        toggle_qrz_button = QPushButton("Toggle QRZ Panel")
        toggle_qrz_button.clicked.connect(self.toggle_qrz_panel)
        main_layout.addWidget(toggle_qrz_button)
    
    def create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        save_config_action = QAction('Save Configuration', self)
        save_config_action.triggered.connect(self.save_configuration)
        file_menu.addAction(save_config_action)
        
        qrz_settings_action = QAction('QRZ.com Settings...', self)
        qrz_settings_action.triggered.connect(self.show_qrz_settings)
        file_menu.addAction(qrz_settings_action)
        
        # Add test QRZ lookup for debugging
        test_qrz_action = QAction('Test QRZ Lookup...', self)
        test_qrz_action.triggered.connect(self.test_qrz_lookup)
        file_menu.addAction(test_qrz_action)
        
        log4om_settings_action = QAction('Log4OM Connection...', self)
        log4om_settings_action.triggered.connect(self.show_log4om_settings)
        file_menu.addAction(log4om_settings_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction('Quit', self)
        quit_action.setShortcut('Ctrl+Q')
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def populate_rst_combo(self, combo: QComboBox):
        """Populate RST combo box with common values"""
        common_rst = ['59', '58', '57', '56', '55', '44', '33', '22', '11']
        combo.addItems(common_rst)
        for i in range(11, 60):
            if str(i) not in common_rst:
                combo.addItem(str(i))
    
    def setup_connections(self):
        """Setup signal-slot connections"""
        self.log_button.clicked.connect(self.log_qso)
        self.clear_button.clicked.connect(self.clear_all_fields)
        self.call_input.returnPressed.connect(self.log_qso)
        self.freq_input.returnPressed.connect(self.log_qso)
        
        # Connect validation signals
        self.call_input.textChanged.connect(self.update_log_button_state)
        self.freq_input.textChanged.connect(self.update_log_button_state)
        self.call_input.textChanged.connect(self.on_callsign_changed)
    
    def toggle_qrz_panel(self):
        """Toggle the QRZ information panel visibility"""
        splitter = self.findChild(QSplitter)
        if splitter:
            sizes = splitter.sizes()
            if sizes[1] == 0:
                splitter.setSizes([400, 200])
            else:
                splitter.setSizes([600, 0])
    
    def show_qrz_settings(self):
        """Show QRZ.com settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("QRZ.com Settings")
        dialog.setModal(True)
        dialog.resize(350, 200)
        
        layout = QVBoxLayout(dialog)
        
        # QRZ Settings Group
        qrz_group = QGroupBox("QRZ.com Credentials")
        qrz_layout = QGridLayout(qrz_group)
        
        qrz_layout.addWidget(QLabel('Username:'), 0, 0)
        qrz_username_input = QLineEdit(self.config.get('qrz_username', ''))
        qrz_username_input.setPlaceholderText("QRZ.com username")
        qrz_layout.addWidget(qrz_username_input, 0, 1)
        
        qrz_layout.addWidget(QLabel('Password:'), 1, 0)
        qrz_password_input = QLineEdit(self.config.get('qrz_password', ''))
        qrz_password_input.setEchoMode(QLineEdit.Password)
        qrz_password_input.setPlaceholderText("QRZ.com password")
        qrz_layout.addWidget(qrz_password_input, 1, 1)
        
        layout.addWidget(qrz_group)
        
        # Info label
        info_label = QLabel("Note: QRZ.com XML subscription required for full features.\nCredentials are stored locally and used only for QRZ lookups.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 10px; background-color: #f9f9f9; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog and handle result
        if dialog.exec_() == QDialog.Accepted:
            self.config['qrz_username'] = qrz_username_input.text().strip()
            self.config['qrz_password'] = qrz_password_input.text().strip()
            self.save_configuration()
            self.status_bar.showMessage("QRZ.com settings saved", 3000)
    
    def show_log4om_settings(self):
        """Show Log4OM connection settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Log4OM Connection Settings")
        dialog.setModal(True)
        dialog.resize(350, 180)
        
        layout = QVBoxLayout(dialog)
        
        # Connection Settings Group
        conn_group = QGroupBox("Log4OM Connection")
        conn_layout = QGridLayout(conn_group)
        
        conn_layout.addWidget(QLabel('Log4OM IP Address:'), 0, 0)
        ip_input = QLineEdit(self.config['udp_ip'])
        ip_input.setPlaceholderText("e.g., 192.168.1.100")
        conn_layout.addWidget(ip_input, 0, 1)
        
        conn_layout.addWidget(QLabel('ADIF Port:'), 1, 0)
        port_input = QSpinBox()
        port_input.setRange(1, 65535)
        port_input.setValue(self.config['udp_port'])
        conn_layout.addWidget(port_input, 1, 1)
        
        layout.addWidget(conn_group)
        
        # Info label
        info_label = QLabel("Configure the IP address and port for Log4OM ADIF integration.\nDefault port is usually 2234.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 10px; background-color: #f9f9f9; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog and handle result
        if dialog.exec_() == QDialog.Accepted:
            self.config['udp_ip'] = ip_input.text().strip()
            self.config['udp_port'] = port_input.value()
            self.save_configuration()
            self.status_bar.showMessage("Log4OM connection settings saved", 3000)
    
    def test_qrz_lookup(self):
        """Test QRZ lookup with a dialog"""
        from PyQt5.QtWidgets import QInputDialog
        
        callsign, ok = QInputDialog.getText(self, 'Test QRZ Lookup', 'Enter callsign to test:')
        if ok and callsign.strip():
            callsign = callsign.strip().upper()
            print(f"\n=== MANUAL QRZ TEST FOR {callsign} ===")
            
            username = self.config.get('qrz_username', '').strip()
            password = self.config.get('qrz_password', '').strip()
            
            if not username or not password:
                QMessageBox.warning(self, "Test Failed", "QRZ credentials not configured.\nGo to File → QRZ.com Settings first.")
                return
            
            # Force a fresh lookup
            self.current_lookup_thread = QRZLookupThread(callsign, username, password)
            self.current_lookup_thread.lookup_complete.connect(self.on_test_lookup_complete)
            self.current_lookup_thread.lookup_error.connect(self.on_test_lookup_error)
            self.current_lookup_thread.start()
            
            self.status_bar.showMessage(f"Testing QRZ lookup for {callsign}...")
    
    def on_test_lookup_complete(self, data):
        """Handle test lookup completion"""
        print(f"=== TEST LOOKUP SUCCESS ===")
        print(f"Data received: {data}")
        QMessageBox.information(self, "Test Success", f"Found {len(data)} fields:\n" + "\n".join([f"{k}: {v[:50]}..." if len(str(v)) > 50 else f"{k}: {v}" for k, v in data.items()]))
    
    def on_test_lookup_error(self, error):
        """Handle test lookup error"""
        print(f"=== TEST LOOKUP ERROR ===")
        print(f"Error: {error}")
        QMessageBox.warning(self, "Test Failed", f"QRZ lookup failed:\n{error}")
    
    def validate_callsign_input(self, text: str):
        """Validate callsign input and update indicator"""
        if text.strip():
            is_valid = self.validator.validate_callsign(text)
            self.call_valid_label.setText("✓" if is_valid else "✗")
            self.call_valid_label.setStyleSheet(
                "color: green; font-weight: bold;" if is_valid 
                else "color: red; font-weight: bold;"
            )
        else:
            self.call_valid_label.setText("✗")
            self.call_valid_label.setStyleSheet("color: red; font-weight: bold;")
    
    def validate_frequency_input(self, text: str):
        """Validate frequency input and update indicator"""
        if text.strip():
            is_valid = self.validator.validate_frequency(text)
            self.freq_valid_label.setText("✓" if is_valid else "✗")
            self.freq_valid_label.setStyleSheet(
                "color: green; font-weight: bold;" if is_valid 
                else "color: red; font-weight: bold;"
            )
        else:
            self.freq_valid_label.setText("✗")
            self.freq_valid_label.setStyleSheet("color: red; font-weight: bold;")
    
    def update_log_button_state(self):
        """Enable/disable log button based on input validation"""
        call_text = self.call_input.text().strip()
        freq_text = self.freq_input.text().strip()
        
        call_valid = bool(call_text and self.validator.validate_callsign(call_text))
        freq_valid = bool(freq_text and self.validator.validate_frequency(freq_text))
        
        self.log_button.setEnabled(call_valid and freq_valid)
    
    def on_callsign_changed(self, text: str):
        """Handle callsign input changes for QRZ lookup"""
        print(f"DEBUG: Callsign changed to: '{text}'")
        
        # Clear previous lookup results
        self.clear_qrz_info()
        
        # Stop any existing lookup
        if self.current_lookup_thread and self.current_lookup_thread.isRunning():
            self.current_lookup_thread.terminate()
            self.current_lookup_thread.wait()
        
        # Start lookup timer if conditions are met
        should_lookup = (
            self.auto_lookup_checkbox.isChecked() and 
            text.strip() and 
            len(text.strip()) >= 3 and
            self.config.get('qrz_username', '').strip() and
            self.config.get('qrz_password', '').strip()
        )
        
        print(f"DEBUG: Should lookup? {should_lookup}")
        print(f"DEBUG: Auto-lookup enabled: {self.auto_lookup_checkbox.isChecked()}")
        print(f"DEBUG: Text length: {len(text.strip())}")
        print(f"DEBUG: Has credentials: {bool(self.config.get('qrz_username', '').strip() and self.config.get('qrz_password', '').strip())}")
        
        if should_lookup:
            print(f"DEBUG: Starting lookup timer for {text.strip()}")
            self.lookup_timer.stop()
            self.lookup_timer.start(1500)
    
    def perform_qrz_lookup(self):
        """Perform QRZ.com lookup"""
        callsign = self.call_input.text().strip()
        if not callsign or not self.validator.validate_callsign(callsign):
            return
        
        username = self.config.get('qrz_username', '').strip()
        password = self.config.get('qrz_password', '').strip()
        
        if not username or not password:
            self.lookup_status_label.setText("QRZ credentials required")
            return
        
        self.lookup_status_label.setText(f"Looking up {callsign}...")
        
        self.current_lookup_thread = QRZLookupThread(callsign, username, password)
        self.current_lookup_thread.lookup_complete.connect(self.on_qrz_lookup_complete)
        self.current_lookup_thread.lookup_error.connect(self.on_qrz_lookup_error)
        self.current_lookup_thread.start()
    
    @pyqtSlot(dict)
    def on_qrz_lookup_complete(self, data: Dict[str, str]):
        """Handle successful QRZ lookup"""
        self.display_qrz_info(data)
        self.lookup_status_label.setText(f"Last lookup: {datetime.now().strftime('%H:%M:%S')}")
        
        if 'image' in data and data['image']:
            self.load_qrz_photo(data['image'])
    
    @pyqtSlot(str)
    def on_qrz_lookup_error(self, error_message: str):
        """Handle QRZ lookup error"""
        self.lookup_status_label.setText(f"Lookup error: {error_message}")
        self.station_info_text.setPlainText("QRZ lookup failed")
    
    def display_qrz_info(self, data: Dict[str, str]):
        """Display QRZ information"""
        info_lines = []
        
        # Name
        name_parts = []
        if 'fname' in data:
            name_parts.append(data['fname'])
        if 'name' in data:
            name_parts.append(data['name'])
        if name_parts:
            info_lines.append(f"Name: {' '.join(name_parts)}")
        
        # Address
        addr_parts = []
        if 'addr1' in data:
            addr_parts.append(data['addr1'])
        if 'addr2' in data:
            addr_parts.append(data['addr2'])
        if 'state' in data:
            addr_parts.append(data['state'])
        if 'zip' in data:
            addr_parts.append(data['zip'])
        if addr_parts:
            info_lines.append(f"Address: {', '.join(addr_parts)}")
        
        # Country
        if 'country' in data:
            info_lines.append(f"Country: {data['country']}")
        
        # Grid square
        if 'grid' in data:
            info_lines.append(f"Grid: {data['grid']}")
        
        # Email
        if 'email' in data:
            info_lines.append(f"Email: {data['email']}")
        
        # Bio (truncated)
        if 'bio' in data and data['bio']:
            bio = data['bio'][:200] + "..." if len(data['bio']) > 200 else data['bio']
            info_lines.append(f"Bio: {bio}")
        
        if info_lines:
            display_text = "\n".join(info_lines)
            self.station_info_text.setPlainText(display_text)
            print(f"DEBUG: Set station info text to: {display_text}")
        else:
            self.station_info_text.setPlainText("No additional information available")
    
    def load_qrz_photo(self, image_url: str):
        """Load photo from QRZ.com"""
        try:
            print(f"DEBUG: Loading photo from: {image_url}")
            request = QNetworkRequest(QUrl(image_url))
            reply = self.network_manager.get(request)
            reply.finished.connect(lambda: self.on_photo_loaded(reply))
        except Exception as e:
            print(f"Error loading photo: {e}")
            self.photo_label.setText("Photo Load Error")
    
    def on_photo_loaded(self, reply: QNetworkReply):
        """Handle photo loading completion"""
        if reply.error() == QNetworkReply.NoError:
            image_data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                scaled_pixmap = pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.photo_label.setPixmap(scaled_pixmap)
                self.photo_label.setText("")
            else:
                self.photo_label.setText("Invalid Image")
        else:
            self.photo_label.setText("Photo Load Failed")
        
        reply.deleteLater()
    
    def clear_qrz_info(self):
        """Clear QRZ information display"""
        self.station_info_text.setPlainText("Enter a callsign to see QRZ information")
        self.photo_label.clear()
        self.photo_label.setText("No Photo")
        self.lookup_status_label.setText("")
    
    def log_qso(self):
        """Log the QSO to Log4OM"""
        if not self.log_button.isEnabled():
            return
        
        try:
            qso_data = self.gather_qso_data()
            adif_entry = self.create_adif_entry(qso_data)
            self.send_to_log4om(adif_entry)
            self.handle_successful_log(qso_data['call'])
            
        except Exception as e:
            QMessageBox.critical(self, "Logging Error", 
                               f"Failed to log QSO: {str(e)}")
    
    def gather_qso_data(self) -> Dict[str, Any]:
        """Gather all QSO data from form fields"""
        return {
            'call': self.call_input.text().strip().upper(),
            'band': self.band_select.currentText(),
            'freq': self.freq_input.text().strip(),
            'mode': self.mode_select.currentText(),
            'rst_sent': self.rst_sent_input.currentText(),
            'rst_recv': self.rst_recv_input.currentText(),
            'datetime': datetime.utcnow()
        }
    
    def create_adif_entry(self, qso_data: Dict[str, Any]) -> str:
        """Create ADIF format entry"""
        dt = qso_data['datetime']
        
        return (
            f"<CALL:{len(qso_data['call'])}>{qso_data['call']}"
            f"<QSO_DATE:8>{dt.strftime('%Y%m%d')}"
            f"<TIME_ON:6>{dt.strftime('%H%M%S')}"
            f"<BAND:{len(qso_data['band'])}>{qso_data['band']}"
            f"<FREQ:{len(qso_data['freq'])}>{qso_data['freq']}"
            f"<MODE:{len(qso_data['mode'])}>{qso_data['mode']}"
            f"<RST_SENT:{len(qso_data['rst_sent'])}>{qso_data['rst_sent']}"
            f"<RST_RCVD:{len(qso_data['rst_recv'])}>{qso_data['rst_recv']}"
            "<EOR>"
        )
    
    def send_to_log4om(self, adif_entry: str):
        """Send ADIF entry to Log4OM via UDP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            
            ip = self.config['udp_ip']
            port = self.config['udp_port']
            
            sock.sendto(adif_entry.encode('utf-8'), (ip, port))
            sock.close()
            
        except socket.timeout:
            raise Exception("Connection timeout - check IP and port settings")
        except socket.error as e:
            raise Exception(f"Network error: {str(e)}")
    
    def handle_successful_log(self, callsign: str):
        """Handle successful QSO logging"""
        QMessageBox.information(self, "Success", 
                               f"QSO logged successfully for {callsign}")
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {callsign} logged successfully\n"
        self.log_display.append(log_entry.strip())
        
        if self.auto_clear_checkbox.isChecked():
            self.call_input.clear()
            self.clear_qrz_info()
        
        self.status_bar.showMessage(f"Last QSO: {callsign} at {timestamp}")
        self.qso_logged.emit(callsign)
        self.call_input.setFocus()
    
    def clear_all_fields(self):
        """Clear all input fields"""
        self.call_input.clear()
        self.freq_input.clear()
        self.rst_sent_input.setCurrentText(self.config['default_rst_sent'])
        self.rst_recv_input.setCurrentText(self.config['default_rst_recv'])
        self.band_select.setCurrentText('20m')
        self.mode_select.setCurrentText('FT8')
        self.call_input.setFocus()
        self.clear_qrz_info()
    
    def save_configuration(self):
        """Save current configuration"""
        self.config.update({
            'default_rst_sent': self.rst_sent_input.currentText(),
            'default_rst_recv': self.rst_recv_input.currentText(),
            'auto_clear_call': self.auto_clear_checkbox.isChecked(),
            'auto_lookup': self.auto_lookup_checkbox.isChecked(),
            'window_geometry': {
                'x': self.x(),
                'y': self.y(),
                'width': self.width(),
                'height': self.height()
            }
        })
        
        self.config_manager.save_config(self.config)
        self.status_bar.showMessage("Configuration saved", 2000)
    
    def load_window_state(self):
        """Load and restore window state"""
        if self.config.get('window_geometry'):
            geom = self.config['window_geometry']
            self.setGeometry(geom['x'], geom['y'], geom['width'], geom['height'])
    
    def update_status(self):
        """Update status bar with current time"""
        current_time = datetime.utcnow().strftime('UTC: %H:%M:%S')
        if 'Last QSO:' not in self.status_bar.currentMessage():
            self.status_bar.showMessage(f"Ready - {current_time}")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About QSO Logger",
                         "Enhanced QSO Logger v2.0 - QRZ Edition\n\n"
                         "A modern PyQt5 application for logging\n"
                         "amateur radio contacts to Log4OM with\n"
                         "integrated QRZ.com lookups.\n\n"
                         "Features:\n"
                         "• Real-time input validation\n"
                         "• QRZ.com photo and info display\n"
                         "• Auto-lookup callsigns\n"
                         "• Configuration persistence\n"
                         "• Enhanced error handling\n"
                         "• Modern UI design\n\n"
                         "Note: QRZ.com XML subscription required\n"
                         "for photo and detailed lookups.")
    
    def closeEvent(self, event):
        """Handle application close event"""
        if self.current_lookup_thread and self.current_lookup_thread.isRunning():
            self.current_lookup_thread.terminate()
            self.current_lookup_thread.wait()
        
        self.save_configuration()
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("QSO Logger")
    app.setApplicationVersion("2.0")
    
    # Set application style
    app.setStyle('Fusion')
    
    logger = QSOLogger()
    logger.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()