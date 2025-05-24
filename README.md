# Mutual Fund Returns Tracker

A simple web app to track mutual fund returns across multiple timeframes in a single, sortable table. Built to fill the gap left by most platforms, which only show daily changes or long-term charts, but not a consolidated view.

## Features
- Fetches NAV data directly from the public [MFAPI](https://api.mfapi.in)
- Clean, minimal UI with sortable columns for different return periods
- Batch file (`start-mf-tracker.bat`) for one-click local setup and debugging
- Notes section for personal tracking
- Built using Python, Flask, and Bootstrap
- Developed rapidly using [Cursor](https://www.cursor.so/) (LLM-powered IDE)

## Motivation
Most mutual fund platforms (like Coin) only show yesterday's change or long-term charts. I wanted a simple table to compare returns across timeframes for my own workflow—so I built it. Sometimes, building your own tool is the most liberating way to solve a problem.

## Screenshots

### Frontend Table UI
![Frontend Table UI](screenshots/frontend_table.jpg)

### Terminal Logs
![Terminal Logs](screenshots/terminal_logs.jpg)

## Setup
1. Clone the repo:
   ```sh
   git clone https://github.com/ishankgp/MF_return_tracker.git
   cd MF_return_tracker
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Run the tracker:
   ```sh
   start-mf-tracker.bat
   ```

## Usage
- The app will open in your browser at `http://127.0.0.1:5000`.
- View and sort returns for each fund across multiple periods.
- Add personal notes below the table.

## Data Source
- [MFAPI](https://api.mfapi.in) (unofficial, public mutual fund NAV API)

## License
MIT