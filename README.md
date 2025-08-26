# Stringed Instrument Tab Generator

A comprehensive tool for generating UTF-8 tablature from structured JSON input for guitar, ukulele, bass, mandolin, banjo, and seven-string guitar. Features a complete song structure system with named parts, automatic numbering, and comprehensive musical notation support. Works as both an MCP server for AI integration and a standalone command-line tool.

## Features

### Core Features

- **JSON to UTF-8 Tab Conversion**: Convert structured tab specifications into properly aligned UTF-8 tablature
- **Song Parts System**: Define reusable song sections (Verse, Chorus, Bridge) with automatic numbering
- **Complete Song Structure**: Build full songs with part ordering and repetition
- **MCP Server Integration**: Works with Claude Desktop and other MCP-compatible AI tools
- **Standalone CLI Tool**: Use independently for development and testing
- **Multi-Instrument Support**: Guitar (6-string), Ukulele (4-string), Bass (4-string), Mandolin (4-string), Banjo (5-string), Seven-string guitar

### Musical Features

- **Playing Techniques**: Hammer-ons, pull-offs, slides, bends with Unicode fractions
- **Musical Expression**: Dynamics and emphasis markings (f, p, mf, ff, >, etc.)
- **Ornamental Notes**: Grace notes (acciaccatura and appoggiatura) with superscript notation
- **Rhythmic Elements**: Strum patterns with direction indicators and measure-level control
- **Performance Techniques**: Palm muting and chucks with intensity levels (light, medium, heavy)
- **Time Signature Support**: 4/4, 3/4, 6/8, 2/4 with proper beat validation
- **String Techniques**: Support for muted strings using "x" notation
- **Custom Tunings**: Support for alternate tunings with validation

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/stringed-instrument-tab-generator.git
cd stringed-instrument-tab-generator

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

```
fastmcp>=0.9.0
pydantic>=2.0.0
typing-extensions>=4.0.0
```

## Usage

### Command Line Tool

```bash
# Generate tab and display in console
python cli.py input.json

# Save tab to file
python cli.py input.json output.txt

# Validate input without generating tab
python cli.py --validate input.json

# Verbose output for debugging
python cli.py --verbose input.json
```

### MCP Server (AI Integration)

**Configure Claude Desktop:**

Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "stringed-instrument-tab-generator": {
      "command": "python",
      "args": ["/full/path/to/stringed-instrument-tab-generator/mcp_server.py"]
    }
  }
}
```

**Start the MCP server:**

```bash
python mcp_server.py
```

## Input Format - Parts System

The parts system allows you to define reusable song sections with automatic numbering:

### Basic Parts Example

```json
{
  "title": "Complete Song Example",
  "artist": "Demo Artist",
  "timeSignature": "4/4",
  "tempo": 120,
  "key": "G major",
  "instrument": "guitar",
  "parts": {
    "Intro": {
      "description": "Fingerpicked introduction",
      "measures": [
        {
          "strumPattern": ["", "", "", "", "", "", "", ""],
          "events": [
            {
              "type": "note",
              "string": 1,
              "beat": 1.0,
              "fret": 3,
              "emphasis": "p"
            },
            { "type": "note", "string": 2, "beat": 1.5, "fret": 0 },
            { "type": "note", "string": 3, "beat": 2.0, "fret": 0 }
          ]
        }
      ]
    },
    "Verse": {
      "description": "Main verse with chord progression",
      "measures": [
        {
          "strumPattern": ["D", "", "U", "", "D", "U", "D", "U"],
          "events": [
            {
              "type": "chord",
              "beat": 1.0,
              "chordName": "G",
              "emphasis": "mf",
              "frets": [
                { "string": 6, "fret": 3 },
                { "string": 5, "fret": 2 },
                { "string": 1, "fret": 3 }
              ]
            }
          ]
        },
        {
          "events": [
            {
              "type": "chord",
              "beat": 1.0,
              "chordName": "C",
              "frets": [
                { "string": 5, "fret": 3 },
                { "string": 4, "fret": 2 },
                { "string": 2, "fret": 1 }
              ]
            }
          ]
        }
      ]
    },
    "Chorus": {
      "description": "Energetic chorus with palm muting",
      "measures": [
        {
          "strumPattern": ["D", "", "", "D", "", "U", "D", "U"],
          "events": [
            {
              "type": "chord",
              "beat": 1.0,
              "chordName": "G",
              "emphasis": "f",
              "frets": [
                { "string": 6, "fret": 3 },
                { "string": 5, "fret": 2 },
                { "string": 1, "fret": 3 }
              ]
            },
            {
              "type": "palmMute",
              "beat": 2.5,
              "duration": 1.0,
              "intensity": "medium"
            }
          ]
        }
      ]
    }
  },
  "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus"]
}
```

### Automatic Part Numbering

The structure array automatically numbers repeated parts:

- **Input**: `["Intro", "Verse", "Chorus", "Verse", "Chorus"]`
- **Output**: Intro 1 → Verse 1 → Chorus 1 → Verse 2 → Chorus 2

### Part Variations

For different versions of sections, use distinct names:

```json
{
  "parts": {
    "Chorus": {"measures": [...]},
    "Chorus Alt": {"measures": [...]},
    "Chorus Outro": {"measures": [...]}
  },
  "structure": ["Verse", "Chorus", "Verse", "Chorus Alt", "Chorus Outro"]
}
```

### Part-Specific Changes

Override global settings per part:

```json
{
  "tempo": 120,
  "key": "G major",
  "parts": {
    "Bridge": {
      "tempo_change": 90,
      "key_change": "E minor",
      "measures": [...]
    }
  }
}
```

## Supported Event Types

### Basic Events

- **note**: `{"type": "note", "string": 1, "beat": 1.0, "fret": 3, "emphasis": "f"}`
- **chord**: `{"type": "chord", "beat": 1.0, "chordName": "G", "frets": [...]}`

### Playing Techniques

- **hammerOn**: `{"type": "hammerOn", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 5, "vibrato": true}`
- **pullOff**: `{"type": "pullOff", "string": 1, "startBeat": 1.0, "fromFret": 5, "toFret": 3, "emphasis": "p"}`
- **slide**: `{"type": "slide", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 7, "direction": "up"}`
- **bend**: `{"type": "bend", "string": 1, "beat": 1.0, "fret": 7, "semitones": 1.5, "vibrato": true}`

### Ornamental and Performance Elements

- **graceNote**: `{"type": "graceNote", "string": 1, "beat": 1.0, "fret": 5, "graceFret": 3, "graceType": "acciaccatura"}`
- **palmMute**: `{"type": "palmMute", "beat": 1.0, "duration": 2.0, "intensity": "heavy"}`
- **chuck**: `{"type": "chuck", "beat": 1.0, "intensity": "medium"}`

### Musical Expression

Available emphasis markings: `pp`, `p`, `mp`, `mf`, `f`, `ff`, `cresc.`, `dim.`, `<`, `>`, `-`, `.`

### Strum Patterns (Measure Level)

```json
{
  "strumPattern": ["D", "", "U", "", "D", "U", "D", "U"],
  "events": [...]
}
```

- **4/4 time**: 8 positions `["D","","U","","D","U","D","U"]`
- **3/4 time**: 6 positions `["D","","U","","D","U"]`
- **6/8 time**: 6 positions `["D","","","U","",""]`

## Instrument Support

### Guitar (6-string)

- **Standard tuning**: E-A-D-G-B-E
- **String numbering**: 1 (high E) to 6 (low E)
- **Custom tunings**: Drop D, Open G, etc.

### Ukulele (4-string)

```json
{
  "instrument": "ukulele",
  "parts": {
    "Main": {
      "measures": [
        {
          "events": [
            {
              "type": "chord",
              "beat": 1.0,
              "chordName": "C",
              "frets": [
                { "string": 4, "fret": 0 },
                { "string": 3, "fret": 0 },
                { "string": 2, "fret": 0 },
                { "string": 1, "fret": 3 }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

- **Standard tuning**: G-C-E-A
- **String numbering**: 1 (A, highest pitch) to 4 (G, lowest pitch)

### Bass Guitar (4-string)

- **Standard tuning**: E-A-D-G
- **String numbering**: 1 (G, highest pitch) to 4 (E, lowest pitch)
- **Optimized for bass techniques**: Slides, hammer-ons, pull-offs

### Mandolin (4-string)

- **Standard tuning**: G-D-A-E
- **String numbering**: 1 (E, highest pitch) to 4 (G, lowest pitch)

### Banjo (5-string)

- **Open G tuning**: D-G-B-D-g
- **String numbering**: 1 (high g) to 5 (drone string)

### Seven-String Guitar

- **Extended range**: B-E-A-D-G-B-E
- **String numbering**: 1 (high E) to 7 (low B)

## Time Signatures

Supported time signatures with proper beat validation:

- **4/4**: Common time (8 strum positions)
- **3/4**: Waltz time (6 strum positions)
- **2/4**: Cut time (4 strum positions)
- **6/8**: Compound time (6 strum positions)

## Custom Tunings

Support for alternate tunings with automatic validation:

```json
{
  "instrument": "guitar",
  "tuning": ["D", "A", "D", "G", "B", "E"],
  "tuning_name": "Drop D",
  "parts": {...}
}
```

## Output Example

```
# Complete Song Example
**Artist:** Demo Artist
**Time Signature:** 4/4 | **Tempo:** 120 BPM | **Key:** G major | **Custom Tuning:** Drop D

**Song Structure:**
Intro 1 → Verse 1 → Chorus 1 → Verse 2 → Chorus 2

**Parts Defined:**
- **Intro**: 1 measure - Fingerpicked introduction
- **Verse**: 2 measures - Main verse with chord progression
- **Chorus**: 1 measure - Energetic chorus with palm muting

## Intro 1
*Fingerpicked introduction*

    1 & 2 & 3 & 4 &
E |-3-0-0-----------|
B |-------0---------|
G |-------0---------|
D |-----------------|
A |-----------------|
D |-----------------|

## Verse 1
*Main verse with chord progression*

 G
 mf
  1 & 2 & 3 & 4 &   1 & 2 & 3 & 4 &
E |-3---------------|-----------------|
B |-0---------------|1----------------|
G |-0---------------|0----------------|
D |-0---------------|2----------------|
A |-2---------------|3----------------|
D |-3---------------|-----------------|
  D   U   D U D U   D   D   D U D U

## Chorus 1
*Energetic chorus with palm muting*

 G
 f          PM(M)--
  1 & 2 & 3 & 4 &
E |-3---------------|
B |-0---------------|
G |-0---------------|
D |-0---------------|
A |-2---------------|
D |-3---------------|
  D     D   U D U
```

## Testing

### Quick Tests

```bash
# Run critical functionality tests
python simple_test_runner.py

# Save outputs for inspection
python simple_test_runner.py --save
```

### Comprehensive Testing

```bash
# Run all tests
python run_tests.py

# Run smoke tests only
python run_tests.py --smoke

# Update golden outputs after changes
python run_tests.py --update
```

### Test Categories

- **Core Features**: Basic chords, multiple measures, strum patterns
- **Playing Techniques**: Hammer-ons, pull-offs, slides, bends
- **Ornamental Features**: Grace notes, emphasis, palm muting
- **Multi-Instrument**: Guitar, ukulele, bass, mandolin, banjo, seven-string
- **Error Handling**: Invalid inputs and edge cases

## Development

### Project Structure

```
stringed-instrument-tab-generator/
├── tab_generation.py       # Core tab generation logic
├── mcp_server.py           # MCP server implementation
├── cli.py                  # Command-line interface
├── tab_models.py           # Pydantic models for validation
├── notation_events.py      # Event type definitions
├── tab_constants.py        # Constants and instrument configs
├── time_signatures.py     # Time signature handling
├── validation.py           # Input validation pipeline
├── simple_test_runner.py   # Quick test validation
├── run_tests.py           # Comprehensive test framework
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Error Handling

The tool provides structured error messages optimized for both human developers and AI systems:

```json
{
  "isError": true,
  "errorType": "validation_error",
  "measure": 1,
  "beat": 4.7,
  "message": "Beat 4.7 invalid for 4/4 time signature",
  "suggestion": "Use valid beat values: 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5"
}
```

### Common Validation Errors

- **Invalid beats**: Beat values that don't match time signature
- **Technique direction**: Hammer-ons must go up, pull-offs must go down
- **String ranges**: Varies by instrument (Guitar: 1-6, Ukulele: 1-4, etc.)
- **Part references**: Structure must reference defined parts
- **Strum pattern length**: Must match time signature requirements
- **Tuning validation**: Must match instrument string count

## Troubleshooting

### Common Issues

**MCP server not connecting:**

- Verify the full path in Claude Desktop configuration
- Check that Python can find required dependencies

**Parts system validation errors:**

- Ensure all structure references exist in parts
- Use proper parts format: `"parts": {...}, "structure": [...]`

**Tab alignment issues:**

- Multi-digit frets (10+) may require template adjustments
- Grace notes need target notes at same beat and string
- Check warnings for formatting suggestions

**Time signature issues:**

- Strum pattern length must match time signature
- Valid beats depend on time signature (4/4: 1.0, 1.5, 2.0, etc.)

**Instrument-specific issues:**

- Verify string numbers match instrument (ukulele: 1-4, guitar: 1-6, etc.)
- Check custom tuning string count matches instrument

### Getting Help

- Check the [Issues](https://github.com/yourusername/stringed-instrument-tab-generator/issues) page
- Run tests to validate your environment: `python simple_test_runner.py`
- Use `--validate` flag to check input without generating output
- Review the comprehensive test suite for examples: `python run_tests.py --create-examples`

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp) for AI integration
- Uses [Pydantic](https://pydantic.dev/) for data validation
- Inspired by the Model Context Protocol specification

---

This tool supports both educational use and professional music arrangement workflows. The parts system makes it ideal for complete song structure planning and multi-instrument arrangements.
