"""
Hercules DJControl Mix Ultra TUI Application
Main application that handles MIDI input and TUI rendering.
"""

import asyncio
import curses
from dataclasses import dataclass, field
from typing import Optional

from midi import midi_input_generator, find_djcontrol_port, get_available_ports
from inputmap import MIDI_CC_MAP, MIDI_NOTE_MAP
from tui_renderer import TUIRenderer
from xbox_emulator import XboxEmulator


@dataclass
class DJControlApp:
    """Main application state"""
    needs_render: bool = True
    
    # Connection state
    connected: bool = False
    device_name: str = ""
    status_message: str = "Press 's' to scan for devices"
    battery_level: Optional[int] = None
    
    # Xbox emulator
    xbox_enabled: bool = False
    
    # Device selection
    show_device_list: bool = False
    devices: list = field(default_factory=list)
    selected_device_idx: int = 0
    
    # MIDI log
    midi_log: list = field(default_factory=list)
    
    # Deck A controls
    deck_a_volume: int = 64
    deck_a_eq_high: int = 64
    deck_a_eq_mid: int = 64
    deck_a_eq_low: int = 64
    deck_a_filter: int = 64
    deck_a_pitch: int = 64
    deck_a_jogwheel: int = 0
    jog_push_a: bool = False
    deck_a_play: bool = False
    deck_a_cue: bool = False
    deck_a_sync: bool = False
    deck_a_shift: bool = False
    deck_a_pads: list = field(default_factory=lambda: [False] * 8)
    
    # Deck B controls
    deck_b_volume: int = 64
    deck_b_eq_high: int = 64
    deck_b_eq_mid: int = 64
    deck_b_eq_low: int = 64
    deck_b_filter: int = 64
    deck_b_pitch: int = 64
    deck_b_jogwheel: int = 0
    jog_push_b: bool = False
    deck_b_play: bool = False
    deck_b_cue: bool = False
    deck_b_sync: bool = False
    deck_b_shift: bool = False
    deck_b_pads: list = field(default_factory=lambda: [False] * 8)
    
    # Mixer controls
    crossfader: int = 64
    master_volume: int = 100
    # headphone_volume: int = 100
    # headphone_mix: int = 64
    browse_encoder: int = 0
    browse_push: bool = False
    load_a: bool = False
    load_b: bool = False
    ph_a: bool = False
    ph_b: bool = False
    
    def get_deck_controls(self, deck: str) -> dict:
        """Get controls dict for a deck (A or B)"""
        prefix = f"deck_{deck.lower()}_"
        return {
            "play": getattr(self, f"{prefix}play"),
            "cue": getattr(self, f"{prefix}cue"),
            "sync": getattr(self, f"{prefix}sync"),
            "volume": getattr(self, f"{prefix}volume"),
            "pitch": getattr(self, f"{prefix}pitch"),
            "jogwheel": getattr(self, f"{prefix}jogwheel"),
            "eq_high": getattr(self, f"{prefix}eq_high"),
            "eq_mid": getattr(self, f"{prefix}eq_mid"),
            "eq_low": getattr(self, f"{prefix}eq_low"),
            "filter": getattr(self, f"{prefix}filter"),
            "pads": getattr(self, f"{prefix}pads"),
        }
    
    def get_mixer_controls(self) -> dict:
        """Get mixer controls dict"""
        return {
            "crossfader": self.crossfader,
            "master_volume": self.master_volume,
            # "headphone_volume": self.headphone_volume,
            # "headphone_mix": self.headphone_mix,
            "browse_encoder": self.browse_encoder,
            "browse_push": self.browse_push,
            "load_a": self.load_a,
            "load_b": self.load_b,
            "ph_a": self.ph_a,
            "ph_b": self.ph_b,
        }
    
    def reset_controls(self):
        """Reset all controls to default values"""
        self.needs_render = True
        # Deck A
        self.deck_a_volume = 64
        self.deck_a_eq_high = 64
        self.deck_a_eq_mid = 64
        self.deck_a_eq_low = 64
        self.deck_a_filter = 64
        self.deck_a_pitch = 64
        self.deck_a_jogwheel = 0
        self.deck_a_play = False
        self.deck_a_cue = False
        self.deck_a_sync = False
        self.deck_a_pads = [False] * 8
        
        # Deck B
        self.deck_b_volume = 64
        self.deck_b_eq_high = 64
        self.deck_b_eq_mid = 64
        self.deck_b_eq_low = 64
        self.deck_b_filter = 64
        self.deck_b_pitch = 64
        self.deck_b_jogwheel = 0
        self.deck_b_play = False
        self.deck_b_cue = False
        self.deck_b_sync = False
        self.deck_b_pads = [False] * 8
        
        # Mixer
        self.crossfader = 64
        self.master_volume = 100
        # self.headphone_volume = 100
        # self.headphone_mix = 64
        self.load_a = False
        self.load_b = False
    
    def add_log(self, message: str):
        """Add a message to the MIDI log"""
        self.needs_render = True
        self.midi_log.append(message)
        # Keep only last 100 messages
        if len(self.midi_log) > 100:
            self.midi_log = self.midi_log[-100:]
    
    def handle_midi_message(self, msg):
        """Process incoming MIDI message and update state"""
        self.needs_render = True
        log_entry = str(msg)
        
        if msg.type == 'control_change':
            key = (msg.channel, msg.control)
            if key in MIDI_CC_MAP:
                control_name, control_type = MIDI_CC_MAP[key]
                if hasattr(self, control_name):
                    if control_type == "encoder":
                        # Handle relative encoder values
                        current = getattr(self, control_name)
                        delta = msg.value - 128 if msg.value > 64 else msg.value  # Relative mode
                        new_value = current + delta
                        # new_value = new_value % 256  # Wrap around 0-127
                        setattr(self, control_name, new_value)
                    else:
                        setattr(self, control_name, msg.value)
                    log_entry = f"CC {control_name}: {msg.value}"
            else:
                log_entry = f"CC ch={msg.channel} ctrl={msg.control} val={msg.value}"
        
        elif msg.type == 'note_on' or msg.type == 'note_off':
            key = (msg.channel, msg.note)
            state = 'ON' if msg.velocity > 0 else 'OFF'
            if key in MIDI_NOTE_MAP:
                control_name = MIDI_NOTE_MAP[key]
                
                # Handle pad buttons specially
                if "_pads_" in control_name:
                    parts = control_name.rsplit("_", 1)
                    pad_attr = parts[0] # e.g., deck_a_pads
                    pad_idx = int(parts[1]) - 1 # Pads are 1-indexed
                    if hasattr(self, pad_attr):
                        pads = getattr(self, pad_attr)
                        pads[pad_idx] = msg.velocity > 0
                        setattr(self, pad_attr, pads)
                    log_entry = f"PAD {control_name}: {state}"
                elif hasattr(self, control_name):
                    setattr(self, control_name, msg.velocity > 0)
                    log_entry = f"BTN {control_name}: {state}"
            else:
                log_entry = f"{msg.type.upper()} ch={msg.channel} note={msg.note} vel={msg.velocity}"

        elif msg.type == 'pitchwheel':
            log_entry = f"PITCH ch={msg.channel} val={msg.pitch}"
        
        self.add_log(log_entry)


class DJControlTUI:
    """Main TUI controller"""
    
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.renderer = TUIRenderer(stdscr)
        self.app = DJControlApp()
        self.running = True
        self.midi_task: Optional[asyncio.Task] = None
        self.xbox_emulator = XboxEmulator()
    
    async def connect_midi(self):
        """Connect to MIDI device and start receiving messages"""
        port_name = find_djcontrol_port()
        
        if port_name:
            self.app.connected = True
            self.app.device_name = port_name
            self.app.status_message = f"Connected to {port_name}"
            self.app.add_log(f"Connected: {port_name}")
            
            try:
                async for msg in midi_input_generator():
                    if not self.running:
                        break
                    self.app.handle_midi_message(msg)
                    # Update Xbox emulator with current app state
                    if self.app.xbox_enabled:
                        self.xbox_emulator.update_from_app(self.app)
            except Exception as e:
                self.app.connected = False
                self.app.status_message = f"MIDI Error: {e}"
                self.app.add_log(f"Error: {e}")
        else:
            self.app.status_message = "No DJControl device found"
            self.app.add_log("No DJControl MIDI device found")
    
    def scan_devices(self):
        """Scan for available MIDI devices"""
        ports = get_available_ports()
        self.app.devices = [(p, p, "DJControl" in p or "Hercules" in p) for p in ports]
        self.app.show_device_list = True
        self.app.selected_device_idx = 0
        self.app.status_message = f"Found {len(ports)} MIDI device(s)"
    
    def handle_input(self, key: int) -> bool:
        self.needs_render = True
        """Handle keyboard input, returns False to quit"""
        if key == ord('q'):
            return False
        
        elif key == ord('s'):
            self.scan_devices()
        
        elif key == ord('c'):
            if self.app.connected:
                # Disconnect
                self.app.connected = False
                self.app.status_message = "Disconnected"
                if self.midi_task:
                    self.midi_task.cancel()
            else:
                # Try to connect
                self.app.show_device_list = False
                if self.midi_task is None or self.midi_task.done():
                    self.midi_task = asyncio.create_task(self.connect_midi())
        
        elif key == ord('r'):
            self.app.reset_controls()
            self.app.add_log("Controls reset")
        
        elif key == ord('x'):
            # Toggle Xbox emulator
            if self.app.xbox_enabled:
                self.xbox_emulator.stop()
                self.app.xbox_enabled = False
                self.app.add_log("Xbox emulator disabled")
            else:
                if self.xbox_emulator.available:
                    if self.xbox_emulator.start():
                        self.app.xbox_enabled = True
                        self.app.add_log("Xbox emulator enabled")
                    else:
                        self.app.add_log("Failed to start Xbox emulator")
                else:
                    self.app.add_log("vgamepad not installed (pip install vgamepad)")
        
        elif key == 27:  # ESC
            self.app.show_device_list = False
        
        elif key == curses.KEY_UP:
            if self.app.show_device_list and self.app.selected_device_idx > 0:
                self.app.selected_device_idx -= 1
        
        elif key == curses.KEY_DOWN:
            if self.app.show_device_list:
                if self.app.selected_device_idx < len(self.app.devices) - 1:
                    self.app.selected_device_idx += 1
        
        elif key == 10:  # Enter
            if self.app.show_device_list and self.app.devices:
                self.app.show_device_list = False
                if self.midi_task is None or self.midi_task.done():
                    self.midi_task = asyncio.create_task(self.connect_midi())
        
        return True
    
    async def run(self):
        """Main application loop"""
        # Auto-connect on startup
        port_name = find_djcontrol_port()
        if port_name:
            self.app.status_message = f"Found {port_name}, connecting..."
            self.midi_task = asyncio.create_task(self.connect_midi())
        else:
            self.app.status_message = "No DJControl found. Press 's' to scan."
        
        while self.running:
            # Handle keyboard input
            key = self.renderer.get_key()
            if key != -1:
                if not self.handle_input(key):
                    self.running = False
                    break
            
            # Render UI
            try:
                if self.app.needs_render:
                    self.renderer.render(self.app)
                    self.app.needs_render = False
            except curses.error:
                pass
            
            # Small delay to prevent CPU spinning
            await asyncio.sleep(0.032)  # ~30 FPS
        
        # Cleanup
        if self.app.xbox_enabled:
            self.xbox_emulator.stop()
        if self.midi_task and not self.midi_task.done():
            self.midi_task.cancel()
            try:
                await self.midi_task
            except asyncio.CancelledError:
                pass


def main(stdscr):
    """Entry point for curses wrapper"""
    tui = DJControlTUI(stdscr)
    asyncio.run(tui.run())


if __name__ == "__main__":
    curses.wrapper(main)
