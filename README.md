# Guitar Tab Generator

A powerful tool for generating ASCII guitar tablature from structured JSON input. Works as both an MCP server for AI integration and a standalone command-line tool.

## Features

- **JSON to ASCII Tab Conversion**: Convert structured guitar tab specifications into properly aligned ASCII tablature
- **MCP Server Integration**: Works with Claude Desktop and other MCP-compatible AI tools
- **Standalone CLI Tool**: Use independently for development and testing
- **Comprehensive Validation**: Validates timing, technique rules, and musical constraints
- **Multiple Techniques**: Supports notes, chords, hammer-ons, pull-offs, slides, and bends
- **Cross-Platform**: Works on Windows, macOS, and Linux

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
      "args": ["/full/path/to/guitar-tab-generator/mcp_server.py"]
    }
  }
}
```

**Start the MCP server:**
```bash
python mcp_server.py
```

## Input Format

The tool accepts JSON input with the following structure:

```json
{
  "title": "Simple G Major Scale",
  "description": "Basic scale pattern for practice",
  "timeSignature": "4/4",
  "tempo": 120,
  "attempt": 1,
  "measures": [
    {
      "events": [
        {"type": "note", "string": 1, "beat": 1.0, "fret": 3},
        {"type": "hammerOn", "string": 1, "startBeat": 2.0, "fromFret": 3, "toFret": 5},
        {"type": "chord", "beat": 3.0, "chordName": "G", "frets": [
          {"string": 1, "fret": 3},
          {"string": 2, "fret": 0}, 
          {"string": 6, "fret": 3}
        ]}
      ]
    }
  ]
}
```

### Supported Event Types

- **note**: Single fretted note
- **chord**: Multiple simultaneous notes
- **hammerOn**: Hammer-on technique (3h5)
- **pullOff**: Pull-off technique (5p3)
- **slide**: Slide technique (3/5 or 5\3)
- **bend**: String bend (3b or 5r)

### Time Signatures
- 4/4 (fully supported)
- 3/4 (planned)
- 6/8 (planned)

## Output Example

```
# Simple G Major Scale
*Basic scale pattern for practice*
**Time Signature:** 4/4 | **Tempo:** 120 BPM

 1 & 2 & 3 & 4 & 
|---3---3h5---3---|
|---------------0-|
|-----------------|
|-----------------|
|-----------------|
|---------------3-|
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

## Development

### Project Structure
```
guitar-tab-generator/
├── core.py          # Core validation and generation logic
├── mcp_server.py    # FastMCP server implementation
├── cli.py           # Command-line interface
├── requirements.txt # Python dependencies
└── README.md        # This file
```

### Running Tests
```bash
# Validate a test file
python cli.py --validate examples/simple_scale.json

# Generate test output
python cli.py examples/chord_progression.json test_output.txt
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -m "Add feature description"`
5. Push to your fork: `git push origin feature-name`
6. Create a Pull Request

## Troubleshooting

### Common Issues

**"Permission denied" errors on Windows/WSL:**
- Ensure you're working in a directory with write permissions
- Use Windows filesystem paths for MCP server configuration

**MCP server not connecting:**
- Verify the full path in Claude Desktop configuration
- Check that Python can find the required dependencies
- Review stderr output for error messages

**Tab alignment issues:**
- Multi-digit frets (10+) may require template adjustments
- Check for warnings about formatting in the output

**JSON validation errors:**
- Use `--validate` flag to check input without generating output
- Ensure beat values match time signature constraints
- Check for conflicting events (multiple notes on same string/beat)

### Getting Help

- Check the [Issues](https://github.com/yourusername/guitar-tab-generator/issues) page for known problems
- Create a new issue with:
  - Your input JSON
  - Expected vs actual output
  - Error messages (if any)
  - Operating system and Python version

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp) for AI integration
- Uses [Pydantic](https://pydantic.dev/) for data validation
- Inspired by the Model Context Protocol specification

---

**Note:** This tool is designed for educational and practice purposes. For professional music notation, consider dedicated music notation software.
