# Agent Notes for S2CombatLogSQL Project

## Project Overview
This project is a tool for analyzing and visualizing SMITE 2 combat log data. It consists of:

1. A parser that processes combat log files into a SQLite database
2. A Streamlit web application that provides interactive visualizations and analysis of the data

## Current Project State
As of the latest session:

- The SQLite database schema is fully implemented with tables for matches, players, events, etc.
- The Streamlit application has several functional pages:
  - Home page with upload functionality
  - Match Summary page with player performance tables and team comparisons
  - Items & Builds page with multiple visualizations for item purchases and build paths
- Testing framework is in place with passing tests

## Key Files and Directories

```
S2CombatLogSQL/
├── data/                      # Data storage directory
├── streamlit/                 # Streamlit application
│   ├── Home.py                # Home/Upload page
│   ├── pages/                 # Application pages
│   │   ├── 1_Match_Summary.py # Match summary page
│   │   ├── 2_Items_Builds.py  # Items & builds analysis
│   │   └── ... (other pages)
│   ├── modules/               # Reusable code modules
│   │   ├── queries.py         # SQL query functions
│   │   ├── item_queries.py    # Item-specific SQL queries
│   │   └── item_visualization.py # Item visualization functions
│   └── data/                  # App data and static files
│       └── items_data.json    # Item metadata
├── smite_parser/              # Combat log parser module
├── tests/                     # Test scripts
└── requirements.txt           # Python dependencies
```

## Important Technical Details

### Database Structure
The SQLite database has the following key tables:
- `matches` - General match information
- `players` - Player details and god selections
- `player_stats` - Performance statistics
- `combat_events` - Damage, healing events
- `item_events` - Item purchase events
- `timeline_events` - Key events throughout the match

### Item Build Visualizations
Multiple visualizations have been implemented for item analysis:
1. Item Purchase Timeline - Shows when items were purchased during the match
2. Simple Item Sequence - Chronological table of item purchases
3. Build Path by Category - Visual organization of items by type
4. Gold Distribution - Analysis of gold spending by item category

### SQL Query Pattern
Most data access is through SQL queries in the `modules/queries.py` and `modules/item_queries.py` files. These functions accept a database connection and parameters, returning pandas DataFrames.

### DataFrame Handling
Pandas DataFrames are used extensively. To avoid the SettingWithCopyWarning:
- Create explicit copies of dataframes before modification: `df_copy = df.copy()`
- Use proper assignment methods: `.loc[]` for assignment to views

## Outstanding Work
- Economy Analysis page (gold/XP over time)
- Combat Analysis page (damage distribution, combat heatmaps)
- Advanced filtering and comparison features

## Project Checklist
See `agent_notes/project_checklist.md` for detailed task tracking.

## User Preferences
- Prefer Streamlit for all visualizations
- Focus on clean, maintainable code with single responsibility principle
- Test coverage for all new functionality
- Keep documentation updated

## Technical Debt
- Some queries could be optimized for better performance
- Consider refactoring large files into smaller components
- Add more robust error handling for edge cases

## Working Environment
- Python 3.9+
- Streamlit for web application
- SQLite for database
- Pandas for data manipulation
- Plotly for interactive visualizations

## Recent Improvements
- Fixed DataFrame SettingWithCopyWarning issues in Match_Summary.py
- Implemented multiple item build visualizations
- Added comprehensive item build analysis capabilities
- Updated project documentation including README

## GitHub Repository
- Repository is maintained and regularly updated
- Documentation reflects current state of the project
- Testing framework ensures code quality