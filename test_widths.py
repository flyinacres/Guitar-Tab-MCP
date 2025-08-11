import sys
sys.path.append('.')
from time_signatures import get_content_width, get_measure_width, calculate_char_position

print('=== Width Testing ===')
time_sigs = ['4/4', '3/4', '2/4', '6/8']

for ts in time_sigs:
    content_w = get_content_width(ts)
    measure_w = get_measure_width(ts)
    print(f'{ts}: content_width={content_w}, measure_width={measure_w}')

print('\n=== Expected vs Actual Positioning ===')
# Test beat 1.0 in different measures
for ts in ['4/4', '3/4', '2/4']:
    print(f'{ts} time signature:')
    for measure_offset in range(3):
        pos = calculate_char_position(1.0, measure_offset, ts)
        print(f'  Measure {measure_offset}, beat 1.0 -> position {pos}')
    print()
