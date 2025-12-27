"""
BLE-MIDI Decoder

BLE-MIDI packet format:
- Header byte: 1ttttttt (bit 7 always 1, bits 0-6 are timestamp high)
- Timestamp byte: 1ttttttt (bit 7 always 1, bits 0-6 are timestamp low)
- MIDI message bytes follow

Multiple MIDI messages can be in one packet, each prefixed by a timestamp byte.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class MidiMessage:
    """Represents a decoded MIDI message."""
    timestamp: int  # 13-bit timestamp
    status: int     # MIDI status byte
    channel: int    # MIDI channel (0-15)
    data1: int      # First data byte
    data2: Optional[int]  # Second data byte (optional for some messages)
    message_type: str  # Human-readable message type
    
    def __repr__(self):
        if self.data2 is not None:
            return f"MidiMessage(ts={self.timestamp}, {self.message_type}, ch={self.channel+1}, data=[{self.data1}, {self.data2}])"
        return f"MidiMessage(ts={self.timestamp}, {self.message_type}, ch={self.channel+1}, data=[{self.data1}])"


def get_message_type(status: int) -> Tuple[str, int]:
    """
    Get the message type name and expected data byte count from status byte.
    
    Returns: (message_type_name, data_byte_count)
    """
    msg_type = status & 0xF0
    
    message_types = {
        0x80: ("Note Off", 2),
        0x90: ("Note On", 2),
        0xA0: ("Poly Aftertouch", 2),
        0xB0: ("Control Change", 2),
        0xC0: ("Program Change", 1),
        0xD0: ("Channel Aftertouch", 1),
        0xE0: ("Pitch Bend", 2),
    }
    
    return message_types.get(msg_type, ("Unknown", 2))


def decode_ble_midi_packet(hex_string: str) -> List[MidiMessage]:
    """
    Decode a BLE-MIDI packet from a hex string.
    
    Args:
        hex_string: Colon-separated hex bytes, e.g., "94:86:92:05:00"
                   Can also handle quoted strings like '"94:86:92:05:00"'
    
    Returns:
        List of decoded MidiMessage objects
    """
    # Strip quotes if present
    hex_string = hex_string.strip().strip('"\'')
    
    if not hex_string:
        return []
    
    # Parse hex bytes
    try:
        data = [int(b, 16) for b in hex_string.split(':')]
    except ValueError as e:
        raise ValueError(f"Invalid hex string: {hex_string}") from e
    
    if len(data) < 3:
        return []
    
    messages = []
    
    # First byte is the header (contains timestamp high bits)
    header = data[0]
    if not (header & 0x80):
        raise ValueError(f"Invalid BLE-MIDI header: 0x{header:02X} (bit 7 must be set)")
    
    timestamp_high = (header & 0x3F) << 7  # 6 bits for high part of timestamp
    
    i = 1
    running_status = None
    
    while i < len(data):
        # Check if this byte is a timestamp (bit 7 set)
        if data[i] & 0x80:
            # Could be timestamp or status byte
            if i + 1 < len(data) and (data[i + 1] & 0x80):
                # Next byte also has bit 7 set, so current is timestamp, next is status
                timestamp_low = data[i] & 0x7F
                timestamp = timestamp_high | timestamp_low
                i += 1
                
                # Status byte
                status = data[i]
                running_status = status
                i += 1
            elif data[i] >= 0x80 and data[i] <= 0xEF:
                # This is a status byte (channel message)
                timestamp_low = 0  # Use previous timestamp
                timestamp = timestamp_high
                status = data[i]
                running_status = status
                i += 1
            else:
                # Timestamp byte
                timestamp_low = data[i] & 0x7F
                timestamp = timestamp_high | timestamp_low
                i += 1
                
                if i < len(data) and (data[i] & 0x80):
                    # Status byte follows
                    status = data[i]
                    running_status = status
                    i += 1
                elif running_status is not None:
                    # Running status
                    status = running_status
                else:
                    continue
        else:
            # Data byte with running status
            if running_status is None:
                i += 1
                continue
            status = running_status
            timestamp = timestamp_high
        
        # Get message type and expected data bytes
        msg_type_name, data_byte_count = get_message_type(status)
        channel = status & 0x0F
        
        # Read data bytes
        data_bytes = []
        while len(data_bytes) < data_byte_count and i < len(data):
            if data[i] & 0x80:
                # This is a new timestamp or status, stop reading data
                break
            data_bytes.append(data[i])
            i += 1
        
        if len(data_bytes) >= 1:
            data1 = data_bytes[0]
            data2 = data_bytes[1] if len(data_bytes) > 1 else None
            
            # Special case: Note On with velocity 0 is actually Note Off
            if msg_type_name == "Note On" and data2 == 0:
                msg_type_name = "Note Off"
            
            msg = MidiMessage(
                timestamp=timestamp,
                status=status,
                channel=channel,
                data1=data1,
                data2=data2,
                message_type=msg_type_name
            )
            messages.append(msg)
    
    return messages


def decode_ble_midi_file(filepath: str) -> List[List[MidiMessage]]:
    """
    Decode all BLE-MIDI packets from a file.
    
    Args:
        filepath: Path to file with one hex packet per line
    
    Returns:
        List of decoded message lists (one per packet)
    """
    all_messages = []
    
    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                messages = decode_ble_midi_packet(line)
                if messages:
                    all_messages.append(messages)
            except ValueError as e:
                print(f"Warning: Line {line_num}: {e}")
    
    return all_messages


def format_note_name(note_num: int) -> str:
    return f"{note_num}"
    # """Convert MIDI note number to note name (e.g., 60 -> C4)."""
    # note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    # octave = (note_num // 12) - 1
    # note = note_names[note_num % 12]
    # return f"{note}{octave}"


def print_decoded_messages(messages: List[MidiMessage], verbose: bool = True):
    """Pretty print decoded MIDI messages."""
    for msg in messages:
        if verbose:
            extra = ""
            if "Note" in msg.message_type:
                extra = f" ({format_note_name(msg.data1)}, vel={msg.data2})"
            elif msg.message_type == "Control Change":
                extra = f" (CC#{msg.data1}={msg.data2})"
            elif msg.message_type == "Pitch Bend":
                bend_value = (msg.data2 << 7) | msg.data1 if msg.data2 else msg.data1
                extra = f" (value={bend_value})"
            
            print(f"  [{msg.timestamp:5d}] Ch{msg.channel+1:2d} {msg.message_type:18s}{extra}")
        else:
            print(f"  {msg}")


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    # # Test with sample data
    # test_packets = [
    #     "94:86:92:05:00",
    #     "94:87:95:05:00",
    #     "94:b0:91:05:7f",
    #     "95:d5:92:06:7f",
    #     "98:b1:91:05:7f:b2:92:05:7f:b2:95:05:7f",
    # ]
    
    # print("=== BLE-MIDI Decoder Test ===\n")
    
    # for packet in test_packets:
    #     print(f"Packet: {packet}")
    #     try:
    #         messages = decode_ble_midi_packet(packet)
    #         print_decoded_messages(messages)
    #     except Exception as e:
    #         print(f"  Error: {e}")
    #     print()
    
    # If a file is provided, decode it
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        print(f"\n=== Decoding file: {filepath} ===\n")
        all_packets = decode_ble_midi_file(filepath)
        for i, messages in enumerate(all_packets):
            print(f"Packet {i+1}:")
            print_decoded_messages(messages)
            print()
    else:
        # Default to mididata.txt if it exists
        try:
            print("\n=== Decoding mididata.txt ===\n")
            all_packets = decode_ble_midi_file("mididata.txt")
            for i, messages in enumerate(all_packets):
                print(f"Packet {i+1}:")
                print_decoded_messages(messages)
                print()
        except FileNotFoundError:
            print("Run with: python ble_midi_decoder.py <mididata.txt>")
