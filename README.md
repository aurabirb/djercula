# Djercula - Hercules DJControl Mix Ultra TUI Controller

A Linux terminal user interface (TUI) application for viewing, monitoring, and emulating the controls of the Hercules DJControl Mix Ultra DJ controller via MIDI. Includes **CURSED** Xbox 360 controller emulation for gaming!

## Interface Layout

```
═══ HERCULES DJCONTROL MIX ULTRA ═══
● Connected: DJControl Mix Ultra    [🎮 Xbox: ON]

┌─────── DECK A ───────┐  ┌──── MIXER ────┐  ┌─────── DECK B ───────┐
│ [▶ PLAY] [CUE] [SYNC]│  │  CROSSFADER   │  │ [▶ PLAY] [CUE] [SYNC]│
│ [SHIFT]              │  │ A ────│──── B │  │ [SHIFT]              │
│ JOG (◐) [TOUCH]      │  │               │  │ JOG (◐) [TOUCH]      │
│                      │  │ MASTER  [████]│  │                      │
│ VOL   [████████░░] 85│  │ BROWSE  (◐)   │  │ VOL   [████████░░] 85│
│ PITCH [██████░░░░] 64│  │               │  │ PITCH [██████░░░░] 64│
│                      │  │ [LD A] [LD B] │  │                      │
│ HI    [██████░░] 64  │  │ [PH A] [PH B] │  │ HI    [██████░░] 64  │
│ MID   [██████░░] 64  │  └───────────────┘  │ MID   [██████░░] 64  │
│ LOW   [██████░░] 64  │                     │ LOW   [██████░░] 64  │
│ FILTER[██████░░] 64  │                     │ FILTER[██████░░] 64  │
│                      │                     │                      │
│ PADS: [1][2][3][4]   │                     │ PADS: [1][2][3][4]   │
│       [5][6][7][8]   │                     │       [5][6][7][8]   │
└──────────────────────┘                     └──────────────────────┘

┌─────────────────── MIDI LOG ───────────────────┐
│ [12:34:56] CC deck_a_volume: 85                │
│ [12:34:57] BTN deck_a_play: ON                 │
└────────────────────────────────────────────────┘
```

## Features

- Real-time display of most DJ controller elements
- Xbox 360 Controller Emulation:
  - Use your DJ controller as a gamepad 🎮
  - Jog wheels → Left/Right analog sticks (circular motion)
  - Pitch sliders → Left/Right triggers
  - Deck A pads → D-pad (Pad 2=Up, 5=Left, 6=Down, 7=Right)
  - Deck B pads → Xbox buttons (Pad 1=A, 2=B, 5=X, 6=Y)
  - Browse push → Guide button
  - Load A/B → Back/Start buttons

- MIDI connectivity:
  - Auto-detection of Hercules DJ controllers
  - Standard MIDI protocol via ALSA
  - Real-time MIDI message logging

## Requirements

- Linux with ALSA MIDI support
- Python 3.8+
- Terminal with at least 100x20 character size
- For Xbox emulation: uinput kernel module (usually available by default)

## Installation

```bash
# Clone or download this folder
cd djercula

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `mido` - MIDI message handling
- `python-rtmidi` - MIDI I/O backend
- `vgamepad` - Xbox controller emulation (optional)

## Usage

```bash
python hercules_dj_tui.py
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `s` | Scan for MIDI devices |
| `x` | Toggle Xbox controller emulation |
| `c` | Connect/Disconnect |
| `↑/↓` | Navigate device list |
| `Enter` | Select device |
| `Esc` | Cancel selection |
| `r` | Reset all control values |
| `q` | Quit application |

## Xbox Controller Emulation

The Xbox emulator creates a virtual Xbox 360 controller that games can use. This allows you to play games with your DJ controller!

### Controller Mapping

| DJ Control | Xbox Control |
|-----------|--------------|
| Deck A Jog Wheel (touch + rotate) | Left Analog Stick |
| Deck B Jog Wheel (touch + rotate) | Right Analog Stick |
| Deck A Pitch Slider | Left Trigger (LT) |
| Deck B Pitch Slider | Right Trigger (RT) |
| Deck A Pad 2 | D-pad Up |
| Deck A Pad 5 | D-pad Left |
| Deck A Pad 6 | D-pad Down |
| Deck A Pad 7 | D-pad Right |
| Deck B Pad 1 | A Button |
| Deck B Pad 2 | B Button |
| Deck B Pad 5 | X Button |
| Deck B Pad 6 | Y Button |
| Browse Push | Guide Button |
| Load A | Back Button |
| Load B | Start Button |

### Jog Wheel Behavior

- Touch the jog wheel to activate the stick
- Rotate to move the stick in a circle
- Intensity ramps up as you rotate faster
- Release touch to return stick to center

## Technical Details

### MIDI Mapping

The application uses standard MIDI channels with mappings defined in `inputmap.py`.
MIDI CC messages are used for continuous controls (faders, knobs), while Note On/Off messages are used for buttons and pads.

## Troubleshooting

### "Terminal too small"
Resize your terminal to at least 100 columns × 20 rows.

### "No devices found"
1. Make sure your DJ controller is connected via USB and powered on
2. Check that ALSA can see the device:
   ```bash
   aconnect -l
   ```
3. Ensure your user has permissions to access MIDI devices

### "Connection failed"
1. Ensure the device is not in use by another application (like a DJ software)
2. Try disconnecting and reconnecting the USB cable
3. Check `dmesg` for any USB errors

### "vgamepad not installed"
To use Xbox controller emulation:
```bash
pip install vgamepad
```

You may also need to load the uinput kernel module:
```bash
sudo modprobe uinput
```

### Xbox emulator not working
0. Press `x` after connecting to the controller.
1. Make sure vgamepad is installed: `pip install vgamepad`
2. Check uinput permissions:
   ```bash
   sudo chmod 666 /dev/uinput
   # Or add a udev rule for permanent access
   ```
3. Verify the virtual controller is created:
   ```bash
   ls /dev/input/js*
   ```

## Project Structure

```
djercula/
├── hercules_dj_tui.py   # Main application and TUI controller
├── midi.py              # MIDI input handling
├── inputmap.py          # MIDI CC/Note to control mappings
├── tui_renderer.py      # Terminal UI rendering
├── xbox_emulator.py     # Xbox 360 controller emulation
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## License

MIT License - Feel free to modify and distribute.

## Contributing

Contributions welcome! If you have a Hercules DJControl Mix Ultra and can help verify/improve the MIDI mapping or add new features, please open an issue or PR.
