"""
TUI Renderer for Hercules DJControl Mix Ultra
Handles all curses-based drawing routines.
"""

import curses
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hercules_dj_tui import DJControlApp


class TUIRenderer:
    """Handles all TUI drawing operations"""
    
    def __init__(self, stdscr):
        self.stdscr = stdscr
        
        # Setup colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # Active/On
        curses.init_pair(2, curses.COLOR_RED, -1)     # Inactive/Off
        curses.init_pair(3, curses.COLOR_CYAN, -1)    # Headers
        curses.init_pair(4, curses.COLOR_YELLOW, -1)  # Values
        curses.init_pair(5, curses.COLOR_MAGENTA, -1) # Status
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Selection
        
        # Make getch non-blocking
        self.stdscr.nodelay(True)
        curses.curs_set(0)  # Hide cursor
    
    def get_key(self) -> int:
        """Get keyboard input (non-blocking)"""
        try:
            return self.stdscr.getch()
        except Exception:
            return -1
    
    def get_size(self) -> tuple[int, int]:
        """Get terminal size (height, width)"""
        return self.stdscr.getmaxyx()
    
    def draw_box(self, y: int, x: int, height: int, width: int, title: str = ""):
        """Draw a box with optional title"""
        # Draw corners
        self.stdscr.addch(y, x, curses.ACS_ULCORNER)
        self.stdscr.addch(y, x + width - 1, curses.ACS_URCORNER)
        self.stdscr.addch(y + height - 1, x, curses.ACS_LLCORNER)
        try:
            self.stdscr.addch(y + height - 1, x + width - 1, curses.ACS_LRCORNER)
        except curses.error:
            pass  # Bottom-right corner might fail
        
        # Draw horizontal lines
        for i in range(1, width - 1):
            self.stdscr.addch(y, x + i, curses.ACS_HLINE)
            try:
                self.stdscr.addch(y + height - 1, x + i, curses.ACS_HLINE)
            except curses.error:
                pass
        
        # Draw vertical lines
        for i in range(1, height - 1):
            self.stdscr.addch(y + i, x, curses.ACS_VLINE)
            try:
                self.stdscr.addch(y + i, x + width - 1, curses.ACS_VLINE)
            except curses.error:
                pass
        
        # Draw title
        if title:
            title_str = f" {title} "
            title_x = x + (width - len(title_str)) // 2
            self.stdscr.addstr(y, title_x, title_str, curses.color_pair(3) | curses.A_BOLD)
    
    def draw_slider(self, y: int, x: int, value: int, width: int = 12, label: str = "", color: int = 1):
        """Draw a horizontal slider"""
        if label:
            self.stdscr.addstr(y, x, f"{label:8}", curses.color_pair(4))
            x += 9
        
        # Draw slider background
        self.stdscr.addstr(y, x, "[")
        
        filled = int((value / 127) * (width - 2))
        for i in range(width - 2):
            if i < filled:
                self.stdscr.addstr("█", curses.color_pair(color))
            else:
                self.stdscr.addstr("░", curses.color_pair(2))
        
        self.stdscr.addstr("]")
        self.stdscr.addstr(f" {value:3}", curses.color_pair(4))
    
    def draw_button(self, y: int, x: int, label: str, active: bool):
        """Draw a button"""
        color = curses.color_pair(1) if active else curses.color_pair(2)
        attr = curses.A_BOLD | curses.A_REVERSE if active else 0
        self.stdscr.addstr(y, x, f"[{label}]", color | attr)
    
    def draw_pads(self, y: int, x: int, pads: List[bool], label: str = "PADS"):
        """Draw performance pads"""
        self.stdscr.addstr(y, x, f"{label}:", curses.color_pair(3))
        for i, active in enumerate(pads[:4]):
            color = curses.color_pair(1) if active else curses.color_pair(2)
            attr = curses.A_REVERSE if active else 0
            self.stdscr.addstr(y, x + 6 + i * 3, f"[{i+1}]", color | attr)
        
        for i, active in enumerate(pads[4:8]):
            color = curses.color_pair(1) if active else curses.color_pair(2)
            attr = curses.A_REVERSE if active else 0
            self.stdscr.addstr(y + 1, x + 6 + i * 3, f"[{i+5}]", color | attr)
    
    def draw_jogwheel(self, y: int, x: int, value: int, label: str = "JOG"):
        """Draw jogwheel representation"""
        self.stdscr.addstr(y, x, label, curses.color_pair(3))
        
        # Simple ASCII jogwheel
        jog_chars = "◐◓◑◒"
        jog_idx = (value // 64) % 4
        self.stdscr.addstr(y, x + 2 + len(label), f"({jog_chars[jog_idx]})", curses.color_pair(4))
        self.stdscr.addstr(y + 1, x, f"Pos: {value:3}", curses.color_pair(4))
    
    def draw_deck(self, y: int, x: int, deck: str, controls: dict):
        """Draw a deck panel
        
        Args:
            y, x: Position
            deck: "A" or "B"
            controls: Dict with keys: play, cue, sync, volume, pitch, jogwheel,
                      eq_high, eq_mid, eq_low, filter, pads
        """
        width = 35
        height = 14
        
        self.draw_box(y, x, height, width, f"DECK {deck}")
        
        # Transport buttons
        self.draw_button(y + 1, x + 2, "SYNC", controls["sync"])
        self.draw_button(y + 1, x + 14, "CUE", controls["cue"])
        self.draw_button(y + 1, x + 22, "▶ PLAY", controls["play"])
        
        # Jogwheel
        self.draw_jogwheel(y + 3, x + 2, controls["jogwheel"])
        
        # Sliders
        self.draw_slider(y + 5, x + 2, controls["pitch"], 12, "PITCH", color=2)
        
        # EQ
        self.draw_slider(y + 7, x + 2, controls["eq_high"], 10, "HI", color=2)
        self.draw_slider(y + 8, x + 2, controls["eq_mid"], 10, "MID", color=2)
        self.draw_slider(y + 9, x + 2, controls["eq_low"], 10, "LOW", color=2)
        self.draw_slider(y + 10, x + 2, controls["filter"], 10, "FILTER", color=2)
        
        self.draw_slider(y + 12, x + 2, controls["volume"], 12, "VOL")

        # Pads
        self.draw_pads(y + 3, x + 16, controls["pads"])
    
    def draw_mixer(self, y: int, x: int, controls: dict):
        """Draw the mixer panel
        
        Args:
            y, x: Position
            controls: Dict with keys: crossfader, master_volume, headphone_volume,
                      headphone_mix, load_a, load_b, ph_a, ph_b
        """
        width = 26
        height = 12
        
        self.draw_box(y, x, height, width, "MIXER")
        self.draw_jogwheel(y + 1, x + 2, controls["browse_encoder"] * 64 % 256, "BROWSE")
        
        # Load buttons
        self.draw_button(y + 3, x + 2, "LOAD A", controls["load_a"])
        self.draw_button(y + 3, x + 13, "LOAD B", controls["load_b"])
        
        # PH buttons
        self.draw_button(y + 4, x + 2, "PH A", controls["ph_a"])
        self.draw_button(y + 4, x + 13, "PH B", controls["ph_b"])

        self.draw_slider(y + 7, x + 2, controls["master_volume"], 10, "MASTER")
        # Crossfader
        cf = controls["crossfader"]
        cf_pos = int((cf / 127) * 17)
        self.stdscr.addstr(y + 9, x + 2, "A")
        self.stdscr.addstr(y + 9, x + 22, "B")
        self.stdscr.addstr(y + 9, x + 4, "─" * 17)
        self.stdscr.addstr(y + 9, x + 4 + cf_pos, "│", curses.color_pair(1) | curses.A_BOLD)
        
        # self.draw_slider(y + 5, x + 2, controls["headphone_volume"], 10, "PHONES")
        # self.draw_slider(y + 6, x + 2, controls["headphone_mix"], 10, "PH MIX")

    
    def draw_header(self, connected: bool, device_name: str, status_message: str,
                    battery_level: Optional[int] = None, xbox_enabled: bool = False):
        """Draw the header with connection status"""
        height, width = self.stdscr.getmaxyx()
        
        title = "═══ HERCULES DJCONTROL MIX ULTRA ═══"
        self.stdscr.addstr(0, (width - len(title)) // 2, title, curses.color_pair(3) | curses.A_BOLD)
        
        # Connection status
        if connected:
            status = f"● Connected: {device_name}"
            self.stdscr.addstr(1, 2, status, curses.color_pair(1))
            if battery_level is not None:
                self.stdscr.addstr(1, 2 + len(status) + 2, f"🔋 {battery_level}%", curses.color_pair(4))
        else:
            self.stdscr.addstr(1, 2, "○ Not Connected", curses.color_pair(2))
        
        # Xbox emulator status (right side)
        if xbox_enabled:
            xbox_str = "🎮 XBOX ON"
            self.stdscr.addstr(1, width - len(xbox_str) - 2, xbox_str, curses.color_pair(1) | curses.A_BOLD)
        
        # Status message
        self.stdscr.addstr(2, 2, status_message[:width-4], curses.color_pair(5))
    
    def draw_log(self, y: int, x: int, width: int, height: int, messages: List[str]):
        """Draw MIDI activity log"""
        self.draw_box(y, x, height, width, "MIDI LOG")
        
        for i, msg in enumerate(messages[-(height-2):]):
            try:
                self.stdscr.addstr(y + 1 + i, x + 1, msg[:width-3])
            except curses.error:
                pass
    
    def draw_help(self, y: int, x: int):
        """Draw help panel"""
        help_text = [
            "CONTROLS:",
            " s - Scan devices",
            " c - Connect/Disconnect",
            " ↑/↓ - Select device",
            " Enter - Confirm",
            " r - Reset values",
            " x - Xbox emulator",
            " q - Quit",
        ]
        
        for i, line in enumerate(help_text):
            try:
                self.stdscr.addstr(y + i, x, line, curses.color_pair(4) if i == 0 else 0)
            except curses.error:
                pass
    
    def draw_device_list(self, y: int, x: int, width: int, height: int,
                         devices: List[tuple], selected_idx: int):
        """Draw device selection list
        
        Args:
            devices: List of (address, name, is_dj) tuples
            selected_idx: Currently selected device index
        """
        self.draw_box(y, x, height, width, "SELECT DEVICE")
        
        visible_devices = devices[:height-2]
        for i, (addr, name, is_dj) in enumerate(visible_devices):
            display = f"{name[:25]:25} {addr[:17]}"
            
            if i == selected_idx:
                attr = curses.color_pair(6)
            elif is_dj:
                attr = curses.color_pair(1) | curses.A_BOLD
            else:
                attr = 0
            
            try:
                marker = "★" if is_dj else " "
                self.stdscr.addstr(y + 1 + i, x + 1, f"{marker} {display}"[:width-3], attr)
            except curses.error:
                pass
    
    def draw_size_error(self, width: int, height: int):
        """Draw terminal size error message"""
        self.stdscr.addstr(0, 0, f"Terminal too small. Need 100x20, have {width}x{height}")
    
    def clear(self):
        """Clear the screen"""
        self.stdscr.clear()
    
    def refresh(self):
        """Refresh the screen"""
        self.stdscr.refresh()
    
    def render(self, app: "DJControlApp"):
        """Main render function - draws the complete UI based on app state"""
        self.clear()
        height, width = self.get_size()
        
        if height < 20 or width < 100:
            self.draw_size_error(width, height)
            self.refresh()
            return
        
        # Draw header
        self.draw_header(
            app.connected,
            app.device_name,
            app.status_message,
            app.battery_level,
            getattr(app, 'xbox_enabled', False)
        )
        
        if app.show_device_list:
            # Draw device selection overlay
            list_height = min(len(app.devices) + 2, height - 6)
            list_width = 50
            list_y = 4
            list_x = (width - list_width) // 2
            self.draw_device_list(list_y, list_x, list_width, list_height,
                                  app.devices, app.selected_device_idx)
        else:
            # Draw main interface
            deck_y = 4
            
            # Deck A
            self.draw_deck(deck_y, 2, "A", app.get_deck_controls("A"))
            
            # Mixer
            self.draw_mixer(deck_y, 38, app.get_mixer_controls())
            
            # Deck B
            self.draw_deck(deck_y, 64, "B", app.get_deck_controls("B"))
            
            # MIDI Log
            log_y = deck_y + 15
            log_height = min(12, height - log_y - 1)
            if log_height > 3:
                self.draw_log(log_y, 2, 62, log_height, app.midi_log)
            
            # Help
            self.draw_help(log_y, 65)
        
        self.refresh()
