"""
BLE-MIDI to Mido Adapter

Decodes BLE-MIDI packets and converts them to mido Message objects.
Supports sending to virtual or hardware MIDI ports.
"""

import mido  # type: ignore[import-untyped]
from dataclasses import dataclass
from typing import List, Optional, Iterator, Callable, Any
import asyncio


@dataclass
class BLEMidiTimestamp:
    """BLE-MIDI timestamp (13-bit, wraps at 8191ms)."""
    value: int
    
    @property
    def milliseconds(self) -> float:
        """Convert to milliseconds."""
        return self.value  # BLE-MIDI timestamps are in milliseconds


class BLEMidiDecoder:
    """
    Decodes BLE-MIDI packets into mido Message objects.
    
    BLE-MIDI packet format:
    - Header byte: 1ttttttt (bit 7 always 1, bits 0-6 are timestamp high)
    - Timestamp byte: 1ttttttt (bit 7 always 1, bits 0-6 are timestamp low)  
    - MIDI message bytes follow
    
    Multiple MIDI messages can be in one packet, each prefixed by a timestamp byte.
    """
    
    # Status byte to mido message type mapping
    STATUS_TO_TYPE = {
        0x80: 'note_off',
        0x90: 'note_on',
        0xA0: 'polytouch',
        0xB0: 'control_change',
        0xC0: 'program_change',
        0xD0: 'aftertouch',
        0xE0: 'pitchwheel',
    }
    
    # Number of data bytes for each message type
    DATA_BYTES = {
        0x80: 2,  # note_off: note, velocity
        0x90: 2,  # note_on: note, velocity
        0xA0: 2,  # polytouch: note, value
        0xB0: 2,  # control_change: control, value
        0xC0: 1,  # program_change: program
        0xD0: 1,  # aftertouch: value
        0xE0: 2,  # pitchwheel: lsb, msb
    }
    
    def __init__(self):
        self._running_status: Optional[int] = None
        self._last_timestamp: int = 0
    
    def decode_packet(self, data: bytes | List[int] | str) -> List[mido.Message]:
        """
        Decode a BLE-MIDI packet into mido Messages.
        
        Args:
            data: BLE-MIDI packet as bytes, list of ints, or colon-separated hex string
            
        Returns:
            List of mido.Message objects
        """
        # Convert input to list of ints
        if isinstance(data, str):
            data = self._parse_hex_string(data)
        elif isinstance(data, bytes):
            data = list(data)
        
        if len(data) < 3:
            return []
        
        messages = []
        
        # First byte is header with timestamp high bits
        header = data[0]
        if not (header & 0x80):
            raise ValueError(f"Invalid BLE-MIDI header: 0x{header:02X}")
        
        timestamp_high = (header & 0x3F) << 7
        
        i = 1
        while i < len(data):
            # Check for timestamp byte (bit 7 set, but not a status byte pattern we're tracking)
            if data[i] & 0x80:
                if self._is_timestamp_byte(data, i):
                    timestamp_low = data[i] & 0x7F
                    timestamp = timestamp_high | timestamp_low
                    self._last_timestamp = timestamp
                    i += 1
                    
                    if i >= len(data):
                        break
                    
                    # Check for status byte
                    if data[i] & 0x80 and data[i] < 0xF0:
                        self._running_status = data[i]
                        i += 1
                elif data[i] < 0xF0:
                    # This is a status byte
                    self._running_status = data[i]
                    i += 1
                else:
                    # System message, skip for now
                    i += 1
                    continue
            
            if self._running_status is None:
                i += 1
                continue
            
            # Parse message based on running status
            msg = self._parse_message(data, i)
            if msg:
                messages.append(msg[0])
                i = msg[1]
            else:
                i += 1
        
        return messages
    
    def _is_timestamp_byte(self, data: List[int], pos: int) -> bool:
        """Determine if byte at position is a timestamp byte."""
        byte = data[pos]
        if not (byte & 0x80):
            return False
        
        # If next byte exists and is also high-bit set, this could be timestamp
        if pos + 1 < len(data):
            next_byte = data[pos + 1]
            # If next byte is a valid status byte, this is likely a timestamp
            if next_byte & 0x80 and next_byte < 0xF0:
                return True
            # If next byte is a data byte, check if we have running status
            if not (next_byte & 0x80) and self._running_status:
                return True
        
        return byte < 0x80 or (byte >= 0x80 and byte < 0x90)
    
    def _parse_message(self, data: List[int], start: int) -> Optional[tuple[mido.Message, int]]:
        """Parse a MIDI message starting at given position."""
        if self._running_status is None:
            return None
        
        status_type = self._running_status & 0xF0
        channel = self._running_status & 0x0F
        
        if status_type not in self.STATUS_TO_TYPE:
            return None
        
        msg_type = self.STATUS_TO_TYPE[status_type]
        num_data_bytes = self.DATA_BYTES[status_type]
        
        # Collect data bytes
        data_bytes = []
        pos = start
        while len(data_bytes) < num_data_bytes and pos < len(data):
            if data[pos] & 0x80:
                # Hit a timestamp or status byte
                break
            data_bytes.append(data[pos])
            pos += 1
        
        if len(data_bytes) < num_data_bytes:
            return None
        
        # Create mido message
        try:
            msg = self._create_mido_message(msg_type, channel, data_bytes)
            return (msg, pos)
        except Exception:
            return None
    
    def _create_mido_message(self, msg_type: str, channel: int, data: List[int]) -> mido.Message:
        """Create a mido Message from parsed data."""
        if msg_type == 'note_off':
            return mido.Message('note_off', channel=channel, note=data[0], velocity=data[1])
        elif msg_type == 'note_on':
            # Note On with velocity 0 is actually Note Off
            if data[1] == 0:
                return mido.Message('note_off', channel=channel, note=data[0], velocity=0)
            return mido.Message('note_on', channel=channel, note=data[0], velocity=data[1])
        elif msg_type == 'polytouch':
            return mido.Message('polytouch', channel=channel, note=data[0], value=data[1])
        elif msg_type == 'control_change':
            return mido.Message('control_change', channel=channel, control=data[0], value=data[1])
        elif msg_type == 'program_change':
            return mido.Message('program_change', channel=channel, program=data[0])
        elif msg_type == 'aftertouch':
            return mido.Message('aftertouch', channel=channel, value=data[0])
        elif msg_type == 'pitchwheel':
            # Pitch wheel is 14-bit value centered at 8192
            pitch = (data[1] << 7) | data[0]
            pitch = pitch - 8192  # Center at 0
            return mido.Message('pitchwheel', channel=channel, pitch=pitch)
        else:
            raise ValueError(f"Unknown message type: {msg_type}")
    
    def _parse_hex_string(self, hex_string: str) -> List[int]:
        """Parse colon-separated hex string to list of ints."""
        hex_string = hex_string.strip().strip('"\'')
        if not hex_string:
            return []
        return [int(b, 16) for b in hex_string.split(':')]
    
    def reset(self):
        """Reset decoder state (running status, etc.)."""
        self._running_status = None
        self._last_timestamp = 0


class BLEMidiAdapter:
    """
    Adapter for routing BLE-MIDI messages to mido ports.
    
    Can decode BLE-MIDI packets and send them to virtual or hardware MIDI ports.
    """
    
    def __init__(self, output_port: Optional[str] = None, virtual: bool = False):
        """
        Initialize the adapter.
        
        Args:
            output_port: Name of the output port to use. If None, no port is opened.
            virtual: If True, create a virtual MIDI port (Linux/macOS only)
        """
        self.decoder = BLEMidiDecoder()
        self._port: Optional[mido.ports.BaseOutput] = None
        self._port_name = output_port
        self._virtual = virtual
        self._callback: Optional[Callable[[mido.Message], None]] = None
        
        if output_port:
            self.open_port(output_port, virtual)
    
    def open_port(self, port_name: str, virtual: bool = False):
        """Open a MIDI output port."""
        self.close_port()
        
        if virtual:
            self._port = mido.open_output(port_name, virtual=True)
        else:
            self._port = mido.open_output(port_name)
        
        self._port_name = port_name
        self._virtual = virtual
    
    def close_port(self):
        """Close the current MIDI output port."""
        if self._port:
            self._port.close()
            self._port = None
    
    def set_callback(self, callback: Callable[[mido.Message], None]):
        """
        Set a callback for decoded messages.
        
        The callback will be called for each decoded message, regardless of
        whether a port is open.
        """
        self._callback = callback
    
    def process_packet(self, data: bytes | List[int] | str) -> List[mido.Message]:
        """
        Process a BLE-MIDI packet and send messages to the port.
        
        Args:
            data: BLE-MIDI packet data
            
        Returns:
            List of decoded mido.Message objects
        """
        messages = self.decoder.decode_packet(data)
        
        for msg in messages:
            if self._callback:
                self._callback(msg)
            
            if self._port:
                self._port.send(msg)
        
        return messages
    
    def process_packets(self, packets: Iterator[bytes | List[int] | str]) -> Iterator[mido.Message]:
        """
        Process multiple BLE-MIDI packets.
        
        Args:
            packets: Iterator of packet data
            
        Yields:
            Decoded mido.Message objects
        """
        for packet in packets:
            for msg in self.process_packet(packet):
                yield msg
    
    def decode_only(self, data: bytes | List[int] | str) -> List[mido.Message]:
        """
        Decode a packet without sending to port.
        
        Args:
            data: BLE-MIDI packet data
            
        Returns:
            List of decoded mido.Message objects
        """
        return self.decoder.decode_packet(data)
    
    def send(self, message: mido.Message):
        """
        Send a mido message directly to the port.
        
        Args:
            message: mido.Message to send
        """
        if self._port:
            self._port.send(message)
        else:
            raise RuntimeError("No output port is open")
    
    def reset(self):
        """Reset the decoder state."""
        self.decoder.reset()
    
    @staticmethod
    def list_output_ports() -> List[str]:
        """List available MIDI output ports."""
        return mido.get_output_names()
    
    @staticmethod
    def list_input_ports() -> List[str]:
        """List available MIDI input ports."""
        return mido.get_input_names()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_port()
        return False


class AsyncBLEMidiAdapter(BLEMidiAdapter):
    """
    Async version of BLEMidiAdapter for use with asyncio.
    """
    
    def __init__(self, output_port: Optional[str] = None, virtual: bool = False):
        super().__init__(output_port, virtual)
        self._queue: asyncio.Queue[mido.Message] = asyncio.Queue()
    
    async def process_packet_async(self, data: bytes | List[int] | str) -> List[mido.Message]:
        """
        Process a BLE-MIDI packet asynchronously.
        
        Messages are also added to an internal queue for async iteration.
        """
        messages = self.process_packet(data)
        for msg in messages:
            await self._queue.put(msg)
        return messages
    
    async def get_message(self) -> mido.Message:
        """Get the next decoded message from the queue."""
        return await self._queue.get()
    
    async def messages(self):
        """Async generator yielding decoded messages."""
        while True:
            msg = await self._queue.get()
            yield msg


def decode_file(filepath: str, send_to_port: Optional[str] = None) -> List[mido.Message]:
    """
    Decode all BLE-MIDI packets from a file.
    
    Args:
        filepath: Path to file with hex packets (one per line)
        send_to_port: Optional port name to send messages to
        
    Returns:
        List of all decoded mido messages
    """
    adapter = BLEMidiAdapter(send_to_port)
    all_messages = []
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages = adapter.decode_only(line)
                    all_messages.extend(messages)
                except ValueError:
                    pass
    
    return all_messages


def find_djcontrol_port() -> Optional[str]:
    """Find the first available DJControl MIDI output port."""
    for port in mido.get_output_names():
        if "DJControl" in port:
            return port
    return None


# Example usage
if __name__ == "__main__":
    import sys
    import time
    
    print("=== BLE-MIDI to Mido Adapter ===\n")
    
    # Show available ports
    print("Available output ports:")
    for port in BLEMidiAdapter.list_output_ports():
        print(f"  - {port}")
    print()
    
    # Find DJControl port
    djcontrol_port = find_djcontrol_port()
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "mididata.txt"
    if djcontrol_port:
        print(f"Found DJControl port: {djcontrol_port}")
        print(f"Sending messages from {filename}...\n")
        
        # Create adapter with DJControl port
        with BLEMidiAdapter(djcontrol_port) as adapter:
            try:
                with open(f"{filename}", 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            # Process packet and send to port
                            messages = adapter.process_packet(line)
                            for msg in messages:
                                print(f"[{line_num:3d}] Sent: {msg}")
                            
                            # Small delay between packets to avoid flooding
                            time.sleep(0.01)
                        except ValueError as e:
                            print(f"[{line_num:3d}] Error: {e}")
                
                print("\nDone sending all messages!")
                
            except FileNotFoundError:
                print(f"Error: {filename} not found")
    else:
        print("No DJControl port found!")
        print("Available ports:")
        for port in BLEMidiAdapter.list_output_ports():
            print(f"  - {port}")
