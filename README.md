![Dynamic Island for Windows Banner](src/Dynamic%20Island%200.jpg)

# Dynamic Island for Windows

A sleek, fluid, and highly customizable Dynamic Island for Windows built with Python and PyQt6.

## Features

**Island and panels**
- Fluid animated transitions between idle, hover, music and notification states.
- Scroll the mouse wheel over the island to cycle panels: system performance, media, weather, calendar, month view and basics (power, sleep, restart). Scroll sensitivity and the pause after each switch are adjustable.
- Two island styles (Default, Notch Nook) and four animation styles (Glow Sweep, Fluid Blobs, Neon Border, Equaliser driven by live system audio).
- Option to show the island on every display, and a compatibility mode that covers the full screen.
- Hold CTRL over the island to ghost it and click through.

**Media**
- Playback controls for any app that uses Windows media controls, with album art accent color.
- Synced lyrics (LRC) in the island while music plays. Can be turned off in Settings.
- Option to open the music tab automatically when playback starts.

**Popups and alerts**
- Windows notifications, with a per-app ignore list.
- Volume and brightness popups (external monitors via DDC/CI, optional).
- Charging popup with an animated bar and time to full.
- Wi-Fi, LAN, Bluetooth and VPN connect/disconnect alerts, plus Bluetooth device battery checks.
- Caps Lock and Num Lock switch popups.
- Local HTTP API (127.0.0.1) to send your own alerts with an icon, title, text and color.

**Outlook and tasks**
- Calendar events, Microsoft To Do tasks and unread mail count from classic Outlook, with an idle countdown to the next meeting and a pre-meeting alert.
- Local task list editable from the island.

**Customization**
- Settings dialog (right-click the island) for behavior, theme, status indicator, Outlook, notifications and the API.
- Status dot beside the clock shows battery, album color, weather or accent color; it can be hidden.
- `theme.json` overrides colors and QSS and hot-reloads while the app runs.
- Optional start with Windows.

## Previews

### Default View & Smart Theming
The island displays the current day and time by default. Its intelligent engine auto-detects your wallpaper's accent color to ensure the UI feels like a native part of your desktop.

![Default State](src/Dynamic%20Island%201.jpg)

### Smart Notifications & Keyboard Status
Stay informed with instant notification detection. The island also provides sleek visual cues when Caps Lock or Num Lock is toggled.

![Notifications](src/Dynamic%20Island%202.jpg)

### Interactive Information Panels
Access a variety of rich widgets including real-time Weather, a detailed Calendar with progress tracking, comprehensive System Monitoring (CPU, RAM, Storage, Network), and your Daily Tasks.

![Information Panels](src/Dynamic%20Island%203.jpg)

### Fluid Media Player
Control your music with ease. The media player's background and animations dynamically adapt their color palette to match the album art of the currently playing track.

![Music Player](src/Dynamic%20Island%205.jpg)

### Basics Control Hub
A dedicated panel for essential system tools. Quickly access Power, Sleep, and Restart controls through a fluid, scrollable interface.

![Basics Panel](src/Dynamic%20Island%207.jpg)

### Deep Customization
Tailor the experience to your liking. Right-click the island to access settings for animation styles, island designs, and location preferences.

![Context Menu](src/Dynamic%20Island%204.jpg)
![Settings](src/Dynamic%20Island%206.jpg)

### Notch Nook Style
For those who prefer a more integrated look, the "Notch Nook" style replaces the floating island with a sleek, top-centered notch that anchors directly to the screen edge.

![Notch Nook](src/Notch_Nook.jpg)

### Showcase Gallery

![Show1](src/Dynamic%20Island1.jpg)
![Show2](src/Dynamic%20Island3.jpg)
![Show3](src/Dynamic%20Island4.jpg)
![Show4](src/Dynamic%20Island5.jpg)

## Installation

### Prebuilt exe

Download `DynamicIsland.exe` from the [latest release](https://github.com/BoredManCodes/dynamic-island-for-windows/releases/latest) and run it. Settings are saved in `config.json` next to the exe.

### From source

1. Clone the repository:
   ```bash
   git clone https://github.com/BoredManCodes/dynamic-island-for-windows.git
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

To build the exe yourself, create a `venv`, install the requirements and run `.\build_exe.ps1`. The result is `dist\DynamicIsland.exe`.

## Dependencies

- PyQt6
- QtAwesome
- psutil
- winsdk (media and notification monitoring)
- pycaw, comtypes and soundcard (volume and audio levels)
- pywin32 (Outlook)
- Pillow and requests (album art and lyrics)

Windows only.

## License

[MIT License](LICENSE)
