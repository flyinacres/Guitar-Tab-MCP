# Guitar Tab Generator with Parts System

A powerful tool for generating UTF-8 guitar and ukulele tablature from structured JSON input. Features a complete song structure system with named parts, automatic numbering, and comprehensive musical notation support. Works as both an MCP server for AI integration and a standalone command-line tool.

## Features

### Core Features

- **JSON to UTF-8 Tab Conversion**: Convert structured guitar/ukulele tab specifications into properly aligned UTF-8 tablature
- **Song Parts System**: Define reusable song sections (Verse, Chorus, Bridge) with automatic numbering
- **Complete Song Structure**: Build full songs with part ordering and repetition
- **MCP Server Integration**: Works with Claude Desktop and other MCP-compatible AI tools
- **Standalone CLI Tool**: Use independently for development and testing
- **Multi-Instrument Support**: Guitar (6-string) and Ukulele (4-string)

### Musical Features

- **Advanced Techniques**: Hammer-ons, pull-offs, slides, bends with Unicode fractions
- **Emphasis & Dynamics**: Musical expression markings (f, p, mf, ff, >, etc.)
- **Grace Notes**: Acciaccatura (quick) and appoggiatura (longer) with superscript notation
- **Strum Patterns**: Direction indicators with measure-level control
- **Palm Muting & Chucks**: With intensity levels (light, medium, heavy)
- **Multiple Time Signatures**: 4/4, 3/4, 6/8, 2/4 with proper beat validation
- **Muted Strings**: Support for "x" fret notation

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/guitar-tab-generator.git
cd guitar-tab-generator

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
    "guitar-tab-generator": {
      "command": "python",
      "args": ["/full/path/to/guitar-tab-generator/mcp_server_parts.py"]
    }
  }
}
```

**Start the MCP server:**

```bash
python mcp_server_parts.py
```

## Input Format - Parts System (Recommended)

The parts system allows you to define reusable song sections with automatic numbering:

### Basic Parts Example

```json
{
  "title": "Complete Song Example",
  "artist": "Demo Artist",
  "timeSignature": "4/4",
  "tempo": 120,
  "key": "G major",
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

### Guitar Techniques

- **hammerOn**: `{"type": "hammerOn", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 5, "vibrato": true}`
- **pullOff**: `{"type": "pullOff", "string": 1, "startBeat": 1.0, "fromFret": 5, "toFret": 3, "emphasis": "p"}`
- **slide**: `{"type": "slide", "string": 1, "startBeat": 1.0, "fromFret": 3, "toFret": 7, "direction": "up"}`
- **bend**: `{"type": "bend", "string": 1, "beat": 1.0, "fret": 7, "semitones": 1.5, "vibrato": true}`

### Advanced Features

- **graceNote**: `{"type": "graceNote", "string": 1, "beat": 1.0, "fret": 5, "graceFret": 3, "graceType": "acciaccatura"}`
- **palmMute**: `{"type": "palmMute", "beat": 1.0, "duration": 2.0, "intensity": "heavy"}`
- **chuck**: `{"type": "chuck", "beat": 1.0, "intensity": "medium"}`

### Emphasis & Dynamics

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

## Ukulele Support

Set the instrument field for ukulele tabs:

```json
{
  "title": "Ukulele Song",
  "instrument": "ukulele",
  "timeSignature": "4/4",
  "parts": {
    "Main": {
      "measures": [
        {
          "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
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
  },
  "structure": ["Main"]
}
```

**Ukulele String Numbering:**

- String 1: A (highest pitch)
- String 2: E
- String 3: C
- String 4: G (lowest pitch)

## Time Signatures

Supported time signatures with proper beat validation:

- **4/4**: Common time (8 strum positions)
- **3/4**: Waltz time (6 strum positions)
- **2/4**: Cut time (4 strum positions)
- **6/8**: Compound time (6 strum positions)

## Output Example

```
# Complete Song Example
**Artist:** Demo Artist
**Time Signature:** 4/4 | **Tempo:** 120 BPM | **Key:** G major

**Song Structure:**
Intro 1 → Verse 1 → Chorus 1 → Verse 2 → Chorus 2

**Parts Defined:**
- **Intro**: 1 measure - Fingerpicked introduction
- **Verse**: 2 measures - Main verse with chord progression
- **Chorus**: 1 measure - Energetic chorus with palm muting

## Intro 1

  1 & 2 & 3 & 4 &
|-3-0-0-----------|
|-------0---------|
|-------0---------|
|-----------------|
|-----------------|
|-----------------|

## Verse 1

 G
 mf
  1 & 2 & 3 & 4 &   1 & 2 & 3 & 4 &
|-3---------------|-----------------|
|-0---------------|1----------------|
|-0---------------|0----------------|
|-0---------------|2----------------|
|-2---------------|3----------------|
|-3---------------|-----------------|
  D   U   D U D U   D   D   D U D U

## Chorus 1

 G
 f          PM(M)--
  1 & 2 & 3 & 4 &
|-3---------------|
|-0---------------|
|-0---------------|
|-0---------------|
|-2---------------|
|-3---------------|
  D     D   U D U

## Verse 2
[identical to Verse 1]

## Chorus 2
[identical to Chorus 1]
```

## Backwards Compatibility

Legacy format with direct `measures` array is still supported:

```json
{
  "title": "Legacy Format",
  "timeSignature": "4/4",
  "measures": [
    {
      "strumPattern": ["D", "", "D", "", "D", "U", "D", "U"],
      "events": [
        {"type": "chord", "beat": 1.0, "chordName": "G", "frets": [...]}
      ]
    }
  ]
}
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
# Run all tests (25+ tests covering all features)
python run_tests.py

# Run only enhanced feature tests
python run_tests.py --enhanced

# Run smoke tests only
python run_tests.py --smoke

# Update golden outputs after changes
python run_tests.py --update
```

### Test Categories

- **Core Features**: Basic chords, multiple measures, strum patterns
- **Guitar Techniques**: Hammer-ons, pull-offs, slides, bends
- **Advanced Features**: Grace notes, emphasis, palm muting
- **Instruments**: Guitar and ukulele support
- **Error Handling**: Invalid inputs and edge cases

## Development

### Project Structure

```
guitar-tab-generator/
├── core_parts.py           # Core logic with parts system support
├── mcp_server_parts.py     # Enhanced MCP server with parts
├── cli.py                  # Command-line interface
├── tab_models_parts.py     # Pydantic models for parts system
├── tab_constants.py        # Constants and instrument configs
├── time_signatures.py     # Time signature handling
├── simple_test_runner.py   # Quick test validation
├── run_tests.py           # Comprehensive test framework
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

### Running Tests

```bash
# Validate project structure
python run_tests.py --validate-structure

# Create example files for manual testing
python run_tests.py --create-examples

# Environment validation
python simple_test_runner.py --validate-env
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
- **String ranges**: Guitar (1-6), Ukulele (1-4)
- **Part references**: Structure must reference defined parts
- **Strum pattern length**: Must match time signature requirements

## Troubleshooting

### Common Issues

**MCP server not connecting:**

- Verify the full path in Claude Desktop configuration
- Use `mcp_server_parts.py` for full parts system support
- Check that Python can find required dependencies

**Parts system validation errors:**

- Ensure all structure references exist in parts
- Use proper parts format: `"parts": {...}, "structure": [...]`
- Don't mix legacy `measures` format with parts format

**Tab alignment issues:**

- Multi-digit frets (10+) may require template adjustments
- Grace notes need target notes at same beat and string
- Check warnings for formatting suggestions

**Time signature issues:**

- Strum pattern length must match time signature
- Valid beats depend on time signature (4/4: 1.0, 1.5, 2.0, etc.)

### Getting Help

- Check the [Issues](https://github.com/yourusername/guitar-tab-generator/issues) page
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

**Note:** This tool supports both educational use and professional songwriting workflows. The parts system makes it ideal for complete song arrangement and structure planning.
