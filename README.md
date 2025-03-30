# SMITE 2 Combat Log Analysis Tool

A comprehensive tool for analyzing and visualizing SMITE 2 combat log data. This project parses combat log files from SMITE 2 matches into a SQLite database and provides an interactive Streamlit web application for detailed analysis and visualization.

## Features

### Combat Log Parser

- Processes raw combat log files into a structured SQLite database
- Extracts events, player information, combat data, and item purchases
- Supports multiple match data in a single database
- Handles various event types (damage, healing, deaths, item purchases, etc.)

### Streamlit Analysis Application

The Streamlit web application provides an interactive interface with:

1. **Home/Upload Page**
   - Upload and process combat log files
   - Select database for analysis
   - View match metadata

2. **Match Summary Page**
   - Overview of match statistics and outcomes
   - Player performance tables
   - Team comparison visualizations

3. **Items & Builds Analysis**
   - Item purchase timelines by player
   - Item purchase sequence in chronological order
   - Build path visualization categorized by item type
   - Gold distribution analysis by item category
   - Item impact analysis

4. **Coming Soon: Economy Analysis**
   - Gold and XP earning over time
   - Resource efficiency metrics

5. **Coming Soon: Combat Analysis**
   - Damage distribution by player and source
   - Healing and damage taken analysis
   - Combat heatmaps

## Getting Started

### Prerequisites

- Python 3.9+
- SQLite 3
- Required Python packages (see requirements.txt)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/S2CombatLogSQL.git
   cd S2CombatLogSQL
   ```

2. Create and activate a virtual environment:
   ```bash
   # macOS/Linux
   python -m venv venv
   source venv/bin/activate
   
   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

1. Start the Streamlit application:
   ```bash
   streamlit run streamlit/Home.py
   ```

2. Open your browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

3. Upload your SMITE 2 combat log files using the interface

## Data Structure

The SQLite database contains the following tables:

- **matches**: General match information including duration, map, and match ID
- **players**: Player details including god selection, roles, and team
- **player_stats**: Performance statistics for each player
- **item_events**: Item purchases throughout the match
- **combat_events**: Detailed combat interactions between players
- **timeline_events**: Key events throughout the match
- **reward_events**: Gold, XP, and objective rewards

## Visualization Features

### Match Summary
- View team performance metrics
- Compare player statistics
- See key match events timeline

### Items & Builds Analysis
- **Item Purchase Timeline**: Interactive visualization showing when items were purchased
- **Simple Item Sequence**: Straightforward table showing item purchase order
- **Build Path by Category**: Organized view of item builds by type category
- **Gold Distribution**: Analysis of gold spending by item category

## Development

### Project Structure
```
S2CombatLogSQL/
├── data/                      # Data storage directory
├── streamlit/                 # Streamlit application
│   ├── Home.py                # Home/Upload page
│   ├── pages/                 # Application pages
│   │   ├── 1_Match_Summary.py # Match summary page
│   │   ├── 2_Items_Builds.py  # Items & builds analysis
│   │   └── ... (other pages)
│   └── data/                  # App data
├── smite_parser/              # Combat log parser module
├── tests/                     # Test scripts
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

### Testing

Run the test suite to verify functionality:
```bash
python streamlit/tests/run_tests.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- SMITE 2 game and its data are property of Hi-Rez Studios
- Visualization design patterns are based on best practices in data visualization