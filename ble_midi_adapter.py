"""
BLE-MIDI to Mido Adapter

Decodes BLE-MIDI packets and converts them to mido Message objects.
Supports sending to virtual or hardware MIDI ports.
"""

import mido  # type: ignore[import-untyped]
from typing import List, Optional, cast

def create_mido_message(msg_type: str, channel: int, data: List[int]) -> mido.Message:
    """Create a mido Message from note data."""
    if msg_type == 'note_off':
        return mido.Message('note_off', channel=channel, note=data[0], velocity=data[1])
    elif msg_type == 'note_on':
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


def find_djcontrol_port() -> Optional[str]:
    """Find the first available DJControl MIDI output port."""
    for port in mido.get_output_names():
        if "DJControl" in port:
            return port
    return None


if __name__ == "__main__":
    import sys
    import time
    
    print("=== Midi tester ===\n")
    
    # Show available ports
    print("Available output ports:")
    for portname in mido.get_output_names():
        print(f"  - {portname}")
    print()
    
    # Find DJControl port
    djcontrol_port = find_djcontrol_port()
    port = cast(mido.ports.BaseOutput, mido.open_output(djcontrol_port))
    if port is None:
        print("No DJControl port found!")
        sys.exit(1)

    print(f"Found DJControl port: {djcontrol_port}")

    led_coords = [
        ((0,1),),
        ((1,12), (2,12),),
        ((1,5),(1,6),(1,7),                         (2,5),(2,6),(2,7),),
        (     (1,15), (1,16), (1,17), (1,18),       (2,15), (2,16), (2,17), (2,18),),

        ((1,15),(2,15)),
        # ((6,50), (7,50),),

        (     (6,0), (6,1), (6,2), (6,3),           (7,0), (7,1), (7,2), (7,3),),
        (     (6,4), (6,5), (6,6), (6,7),           (7,4), (7,5), (7,6), (7,7),),
    ]


    delay = 0.05
    # prompt = "Enter channel,note:"
    try:
        # while (line := input(prompt))!= '':
        while True:
            for btns in led_coords:
                print(btns)
                for chan,note in btns:
                # try:
                    # [chan, note] = map(int, line.strip().split(','))
                    message = create_mido_message('note_on', chan, [note, 127])
                    port.send(message)
                    print(f"Sent: {message.dict()}")
                    
                    # Small delay between packets to avoid flooding
                    time.sleep(delay)

                if btns[0] == (1,15):
                    # skip turning off the hotcue row, reset to hotcue instead
                    continue
                for chan,note in btns:
                    message = create_mido_message('note_off', chan, [note, 0])
                    port.send(message)
                    print(f"Sent: {message.dict()}")
                    time.sleep(delay)

                # except Exception as e:
                #     print(f"Error: {e}")
        print("\nDone sending all messages!")
    except KeyboardInterrupt:
        print("\nInterrupted by user")
