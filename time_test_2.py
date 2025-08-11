import sys
sys.path.append('.')
from time_signatures import get_time_signature_config

print('=== Time Signature Configurations ===')
for ts in ['4/4', '3/4', '2/4', '6/8']:
    config = get_time_signature_config(ts)
    print(f'{ts}:')
    print(f'  measure_width: {config["measure_width"]}')
    print(f'  char_positions: {config["char_positions"]}')
    print()
